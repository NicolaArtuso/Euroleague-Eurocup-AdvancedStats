import pandas as pd
from Team import TeamStat


class PlayerStat:
    """
    Compute advanced basketball statistics for a single player in a game.

    The class reconstructs the portion of the play-by-play DataFrame that
    covers only the minutes the player was actually on the court, then
    delegates team-level metric computation to a TeamStat instance built
    from that on-court slice.

    Attributes:
        code (str): Player's full name as it appears in the API data.
        home (str): Team code of the home side.
        guest (str): Team code of the away side.
        df (pd.DataFrame): Play-by-play slice covering the player's on-court time.
        minutes (str): Total minutes played in 'MM:SS' format.
        team_stat (TeamStat): Team stats computed over the player's on-court slice.
        team (int): 0 if the player belongs to the home team, 1 if away.
        sc (int): Total offensive plays (shooting chances) for this player.
        points (int): Total points scored by the player.
        ortg (float): Offensive Rating while on court.
        drtg (float): Defensive Rating while on court.
        netrtg (float): Net Rating (ORTG – DRTG) while on court.
        astrate (float): Assist ratio (assists / plays).
        astto (float | None): Assist-to-turnover ratio (None if 0 turnovers).
        orebpct (float): Offensive rebound percentage.
        drebpct (float): Defensive rebound percentage.
        tovpct (float): Turnover percentage (turnovers / plays).
        eFG (float): Effective field goal percentage.
        TS (float): True shooting percentage.
        usg (float): Usage percentage (player plays / team plays while on court).
    """

    def __init__(self, code, df, home, guest):
        self.code = code
        self.home = home
        self.guest = guest
        # Build the on-court slice first; all other attributes depend on it
        self.df = self.c_df(df)
        self.minutes = self.minutes(df)
        # Team stats computed over the player's on-court window
        self.team_stat = TeamStat(self.df, self.home, self.guest)
        self.team = self.find_team()
        self.sc = self.c_sc()
        self.points = self.c_points()
        # On-court ratings (guard against division by zero)
        self.ortg = (
            self.team_points() * 100 / self.team_stat.poss[self.team]
            if self.team_points() > 0 else 0
        )
        self.drtg = (
            self.opp_points() * 100 / self.team_stat.poss[abs(1 - self.team)]
            if self.opp_points() > 0 else 0
        )
        self.netrtg = self.ortg - self.drtg
        self.astrate = self.ar()
        self.astto = self.at()
        self.orebpct = self.oreb()
        self.drebpct = self.dreb()
        self.tovpct = self.c_tov()
        self.eFG = self.efg()
        self.TS = self.ts()
        # Usage % = player's plays as a share of team plays while he was on court
        self.usg = self.sc * 100 / self.team_stat.sc[self.team] if self.sc > 0 else 0

    # ------------------------------------------------------------------
    # Core counting utility
    # ------------------------------------------------------------------

    def count_stat(self, stat):
        """
        Count events of specified play-types attributed to this player.

        Args:
            stat (list[str]): List of PLAYTYPE codes to count.

        Returns:
            int: Number of matching rows where PLAYER equals self.code.
        """
        dfp = self.df.loc[self.df['PLAYER'] == self.code]
        return len(dfp.loc[self.df['PLAYTYPE'].isin(stat)])

    # ------------------------------------------------------------------
    # Rebounding percentages
    # ------------------------------------------------------------------

    def oreb(self):
        """
        Compute the player's Offensive Rebound Percentage.

        OREB% = player's offensive rebounds / total available offensive rebounds
                (i.e. team off. reb. + opponent def. reb.) * 100

        Returns:
            float: OREB% while the player was on court, or 0 if unavailable.
        """
        available = self.team_stat.reb()[self.team][0]
        if available == 0:
            return 0
        return self.count_stat(['O']) / available

    def dreb(self):
        """
        Compute the player's Defensive Rebound Percentage.

        DREB% = player's defensive rebounds / total available defensive rebounds
                (i.e. team def. reb. + opponent off. reb.) * 100

        Returns:
            float: DREB% while the player was on court, or 0 if unavailable.
        """
        available = self.team_stat.reb()[self.team][1]
        if available == 0:
            return 0
        return self.count_stat(['D']) / available

    # ------------------------------------------------------------------
    # On-court window construction
    # ------------------------------------------------------------------

    def IN_OUT(self, df):
        """
        Identify the row indices at which the player entered and left the court.

        The Euroleague API records substitutions as IN (enters) and OUT (leaves)
        events. Edge cases handled:
            - Player starts the game → no IN event before the first OUT; we
              insert row index 0 as the implicit entry point.
            - Player is on the court at the final buzzer → no trailing OUT event;
              we append the last row index as the implicit exit point.

        Args:
            df (pd.DataFrame): Full play-by-play DataFrame.

        Returns:
            tuple[list[int], list[int]]:
                - Sorted list of entry row indices.
                - Sorted list of exit row indices.
        """
        playerI = list(df.loc[(df['PLAYTYPE'] == 'IN') & (df['PLAYER'] == self.code)].index)
        playerO = list(df.loc[(df['PLAYTYPE'] == 'OUT') & (df['PLAYER'] == self.code)].index)

        # Player was in the starting five (no IN before the first OUT)
        if playerI == [] or (playerO != [] and playerI[0] > playerO[0]):
            playerI.insert(0, 0)

        # Player was on the court when the game ended (no trailing OUT)
        if playerO == [] or (playerI != [] and playerI[-1] > playerO[-1]):
            playerO.append(len(df) - 1)

        return sorted(playerI), sorted(playerO)

    def c_df(self, df):
        """
        Build a DataFrame containing only the rows where the player was on court.

        We iterate over matched (entry, exit) index pairs returned by IN_OUT
        and concatenate the corresponding slices of the full play-by-play.

        Args:
            df (pd.DataFrame): Full play-by-play DataFrame.

        Returns:
            pd.DataFrame: Subset of rows during the player's on-court stints.
        """
        playerI, playerO = self.IN_OUT(df)
        dfplayer = pd.DataFrame(columns=df.columns)
        for i in range(len(playerI)):
            df_subset = pd.DataFrame(df.loc[playerI[i]:playerO[i]])
            dfplayer = pd.concat([dfplayer, df_subset], axis=0)
        return dfplayer

    # ------------------------------------------------------------------
    # Minutes played
    # ------------------------------------------------------------------

    def minutes(self, df):
        """
        Calculate the total playing time for the player in 'MM:SS' format.

        For each (entry, exit) stint the elapsed seconds are computed from
        the MARKERTIME column (which counts *down* from 600 s at the start
        of each quarter):

            - Same quarter: seconds = entry_time - exit_time
            - Different quarters: partial seconds in entry quarter
                                 + partial seconds in exit quarter
                                 + 600 s * (number of full quarters in between)

        Args:
            df (pd.DataFrame): Full play-by-play DataFrame (used to look up
                               MARKERTIME values by absolute row index).

        Returns:
            str: Total playing time formatted as 'MM:SS'.
        """
        playerI, playerO = self.IN_OUT(df)
        total = 0
        quarters = list(self.df['QUARTER'].unique())

        for i in range(len(playerO)):
            qI = self.df.loc[playerI[i]]['QUARTER']
            qO = self.df.loc[playerO[i]]['QUARTER']

            if qI == qO:
                # Simple case: same quarter
                total += (
                    self.df.loc[playerI[i]]['MARKERTIME']
                    - self.df.loc[playerO[i]]['MARKERTIME']
                )
            else:
                # Remaining seconds in entry quarter
                total += (
                    self.df.loc[playerI[i]]['MARKERTIME']
                    - min(self.df.loc[self.df['QUARTER'] == qI]['MARKERTIME'])
                )
                # Seconds elapsed in exit quarter
                total += (
                    max(self.df.loc[self.df['QUARTER'] == qO]['MARKERTIME'])
                    - self.df.loc[playerO[i]]['MARKERTIME']
                )
                # Full quarters in between (600 s each)
                total += 600 * (quarters.index(qO) - quarters.index(qI) - 1)

        minuti = int(total // 60)
        secondi = int(total % 60)
        return f"{minuti:02d}:{secondi:02d}"

    # ------------------------------------------------------------------
    # Team identification
    # ------------------------------------------------------------------

    def find_team(self):
        """
        Determine whether the player belongs to the home or away team.

        Returns:
            int: 0 if the player is on the home team, 1 if on the away team.
        """
        row = self.df.loc[self.df['PLAYER'] == self.code].iloc[0]
        if row['CODETEAM'] == self.team_stat.home:
            return 0
        return 1

    def to_team(self):
        """Return the team code for this player's side."""
        return self.home if self.team == 0 else self.guest

    def opp(self):
        """Return the team code of the opposing side."""
        return self.guest if self.team == 0 else self.home

    # ------------------------------------------------------------------
    # Offensive plays and scoring
    # ------------------------------------------------------------------

    def c_sc(self):
        """
        Count the player's total offensive plays (shooting chances).

        A play is any event that consumes an offensive opportunity:
            2FGA / 3FGA  – field goal attempts (misses counted separately)
            2FGM / 3FGM  – made field goals (not fouled)
            RV           – non-shooting foul received
            SRV          – shooting foul received (leads to free throws)
            TO           – turnover
            AS           – assist (represents a ball-movement opportunity)

        Returns:
            int: Total plays for this player.
        """
        return self.count_stat(['2FGA', '3FGA', 'RV', '2FGM', '3FGM', 'SRV', 'TO', 'AS'])

    def c_points(self):
        """
        Calculate total points scored by the player.

            points = FTM + FTMF (1 pt each)
                   + 2FGM + 2FGF (2 pts each)
                   + 3FGM + 3FGF (3 pts each)

        Returns:
            int: Total points scored.
        """
        op = self.count_stat(['FTM', 'FTMF'])        # 1-point free throws
        twp = self.count_stat(['2FGM', '2FGF'])       # 2-point baskets
        thp = self.count_stat(['3FGM', '3FGF'])       # 3-point baskets
        return op + 2 * twp + 3 * thp

    def opp_points(self):
        """
        Calculate points scored by the opposing team while this player was on court.

        Delegates to TeamStat.count_stat using the opponent's team code.

        Returns:
            int: Opponent's points during the player's on-court time.
        """
        op = self.team_stat.count_stat(['FTM', 'FTMF'], self.opp())
        twp = self.team_stat.count_stat(['2FGM', '2FGF'], self.opp())
        thp = self.team_stat.count_stat(['3FGM', '3FGF'], self.opp())
        return op + 2 * twp + 3 * thp

    def team_points(self):
        """
        Calculate points scored by the player's team while he was on court.

        Returns:
            int: Team's points during the player's on-court time.
        """
        op = self.team_stat.count_stat(['FTM', 'FTMF'], self.to_team())
        twp = self.team_stat.count_stat(['2FGM', '2FGF'], self.to_team())
        thp = self.team_stat.count_stat(['3FGM', '3FGF'], self.to_team())
        return op + 2 * twp + 3 * thp

    # ------------------------------------------------------------------
    # Assist metrics
    # ------------------------------------------------------------------

    def ar(self):
        """
        Calculate Assist Ratio: assists / total plays.

        Returns:
            float: Proportion of plays that resulted in an assist, or 0.
        """
        if self.sc == 0:
            return 0
        return self.count_stat(['AS']) / self.sc

    def at(self):
        """
        Calculate Assist-to-Turnover ratio.

        Returns:
            float | None: AST/TO ratio, or None if the player has 0 turnovers.
        """
        to = self.count_stat(['TO'])
        if to == 0:
            return None
        return round(self.count_stat(['AS']) / to, 2)

    # ------------------------------------------------------------------
    # Turnover percentage
    # ------------------------------------------------------------------

    def c_tov(self):
        """
        Calculate Turnover Percentage: turnovers / plays.

        Returns:
            float: Fraction of plays that ended in a turnover, or 0.
        """
        if self.sc == 0:
            return 0
        return self.count_stat(['TO']) / self.sc

    # ------------------------------------------------------------------
    # Shooting efficiency
    # ------------------------------------------------------------------

    def efg(self):
        """
        Calculate Effective Field Goal Percentage (eFG%).

            eFG% = (FGM + 0.5 * 3FGM) / FGA * 100

        Includes and-one makes (2FGF / 3FGF) in both the numerator (as
        made shots) and denominator (as attempts).

        Returns:
            float: eFG% for this player, or 0 if no attempts recorded.
        """
        tfg = self.count_stat(['2FGM', '2FGF', '3FGF', '3FGM'])
        tp = 0.5 * self.count_stat(['3FGF', '3FGM'])   # Bonus for 3-pointers
        fga = self.count_stat(['2FGA', '3FGA', '2FGM', '2FGF', '3FGF', '3FGM'])
        return (tfg + tp) / fga * 100 if fga > 0 else 0

    def ts(self):
        """
        Calculate True Shooting Percentage (TS%).

            TS% = points / (2 * TSA) * 100

        TSA (True Shooting Attempts) approximated here as all field goal
        attempts plus final free throws (FTMF).

        Returns:
            float: TS% for this player, or 0 if no attempts recorded.
        """
        a = ['2FGM', '2FGF', '3FGF', '3FGM', '2FGA', '3FGA', 'FTMF']
        tsa = self.count_stat(a)
        if tsa == 0:
            return 0
        return self.points / (2 * tsa) * 100

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def to_dataframe(self):
        """
        Serialize all computed player statistics into a single-row DataFrame.

        The DataFrame is indexed by the player's name (self.code) so that
        rows from multiple players can be concatenated cleanly in main.py.

        Returns:
            pd.DataFrame: One row of stats with shape (1, 15).
        """
        data = {
            'Team': [self.to_team()],
            'Minutes': [self.minutes],
            'Plays': [self.sc],
            'Points': [self.points],
            'ORTG': [self.ortg],
            'DRTG': [self.drtg],
            'NETRTG': [self.netrtg],
            'AST rate': [self.astrate],
            'AST/TO': [self.astto],
            'ORB%': [self.orebpct],
            'DRB%': [self.drebpct],
            'TOV%': [self.tovpct],
            'eFG%': [self.eFG],
            'TS%': [self.TS],
            'USG%': [self.usg],
        }
        return pd.DataFrame(data, index=[self.code])

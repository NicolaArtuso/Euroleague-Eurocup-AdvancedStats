import pandas as pd


class TeamStat:
    """
    Compute advanced basketball statistics for both teams in a single game.

    The class operates on a cleaned play-by-play DataFrame produced by
    main.py. All metrics are derived from the custom play-type labels
    assigned during the data-preparation phase (see main.py for details
    on labels such as FTMF, 2FGF, SRV, ORV, etc.).

    Attributes:
        df (pd.DataFrame): Full play-by-play DataFrame for the game.
        home (str): Team code of the home side.
        guest (str): Team code of the away side.
        poss (list[int]): Estimated possessions [home, guest].
        sc (list[int]): Total plays / shooting chances [home, guest].
        points (list[int]): Final points scored [home, guest].
        ortg (list[float]): Offensive rating [home, guest].
        drtg (list[float]): Defensive rating [home, guest].
        netrtg (list[float]): Net rating (ORTG – DRTG) [home, guest].
        astrate (list[float]): Assist ratio (%) [home, guest].
        astto (list[float]): Assist-to-turnover ratio [home, guest].
        orebpct (list[float]): Offensive rebound percentage [home, guest].
        drebpct (list[float]): Defensive rebound percentage [home, guest].
        tovpct (list[float]): Turnover percentage [home, guest].
        eFG (list[float]): Effective field-goal percentage [home, guest].
        TS (list[float]): True shooting percentage [home, guest].

    Index convention used throughout:
        index 0  →  home team
        index 1  →  guest (away) team
    """

    def __init__(self, df, home, guest):
        self.df = df
        self.home = home
        self.guest = guest
        self.poss = self.c_poss()
        self.sc = self.c_sc()
        self.points = self.c_points()
        self.ortg = self.ortg()
        # Defensive rating of a team equals the opponent's offensive rating
        self.drtg = [self.ortg[1], self.ortg[0]]
        self.netrtg = [self.ortg[0] - self.ortg[1], self.ortg[1] - self.ortg[0]]
        self.astrate = self.ar()
        self.astto = self.at()
        self.orebpct = self.c_reb()[0]
        self.drebpct = self.c_reb()[1]
        self.tovpct = self.c_tov()
        self.eFG = self.efg()
        self.TS = self.ts()

    # ------------------------------------------------------------------
    # Core counting utility
    # ------------------------------------------------------------------

    def count_stat(self, stat, code):
        """
        Count the number of events of specified play-types for a given team.

        Args:
            stat (list[str]): List of PLAYTYPE codes to count
                              (e.g. ['2FGM', '3FGM']).
            code (str): Team code to filter on (e.g. 'MAD').

        Returns:
            int: Number of matching rows in the DataFrame.
        """
        dft = self.df.loc[self.df['CODETEAM'] == code]
        return len(dft.loc[self.df['PLAYTYPE'].isin(stat)])

    # ------------------------------------------------------------------
    # Possession estimation
    # ------------------------------------------------------------------

    def c_poss(self):
        """
        Estimate total possessions for each team.

        A possession ends when one of the following events occurs:
            - Made field goal that results in a throw-in (2FGM / 3FGM)
            - Final made free throw (FTMF)
            - Turnover (TO)
            - Opponent's defensive rebound (D) — i.e. missed shot rebounded
              by the other team

        Formula (home team example):
            home_poss = home_scored_or_TO + guest_defensive_rebounds

        Returns:
            list[int]: [home_possessions, guest_possessions]
        """
        home_poss = (
            self.count_stat(['2FGM', '3FGM', 'FTMF', 'TO'], self.home)
            + self.count_stat(['D'], self.guest)
        )
        guest_poss = (
            self.count_stat(['2FGM', '3FGM', 'FTMF', 'TO'], self.guest)
            + self.count_stat(['D'], self.home)
        )
        return [home_poss, guest_poss]

    # ------------------------------------------------------------------
    # Plays / shooting chances
    # ------------------------------------------------------------------

    def c_sc(self):
        """
        Compute the total number of offensive plays (shooting chances) per team.

        Plays extend possessions by including events that keep the ball alive
        without changing possession:
            - Offensive rebounds (O)  → extend the same possession
            - Non-shooting fouls received (RV) → no free throws awarded

        Formula:
            plays = possessions + offensive_rebounds + non_shooting_fouls_received

        Returns:
            list[int]: [home_plays, guest_plays]
        """
        home_sc = self.poss[0] + self.count_stat(['O', 'RV'], self.home)
        guest_sc = self.poss[1] + self.count_stat(['O', 'RV'], self.guest)
        return [home_sc, guest_sc]

    # ------------------------------------------------------------------
    # Points
    # ------------------------------------------------------------------

    def c_points(self):
        """
        Retrieve the final score for each team directly from the running
        score columns (POINTS_A for home, POINTS_B for guest).

        Returns:
            list[int]: [home_points, guest_points]
        """
        home_points = max(self.df['POINTS_A'])
        guest_points = max(self.df['POINTS_B'])
        return [home_points, guest_points]

    # ------------------------------------------------------------------
    # Ratings
    # ------------------------------------------------------------------

    def ortg(self):
        """
        Calculate Offensive Rating (ORTG) for each team.

        ORTG = points scored * 100 / possessions

        A value of 100 means the team scored exactly 1 point per possession.
        Guard against division by zero when a team has 0 possessions.

        Returns:
            list[float]: [home_ORTG, guest_ORTG]
        """
        hortg = self.points[0] * 100 / self.poss[0] if self.poss[0] > 0 else 0
        gortg = self.points[1] * 100 / self.poss[1] if self.poss[1] > 0 else 0
        return [hortg, gortg]

    # ------------------------------------------------------------------
    # Rebounding
    # ------------------------------------------------------------------

    def c_reb(self):
        """
        Calculate offensive and defensive rebound percentages for both teams.

        Rebound percentage measures what fraction of available rebounds a
        team secured:

            OREB% (home) = home_offensive_reb / (home_offensive_reb + guest_defensive_reb) * 100
            DREB% (home) = home_defensive_reb / (home_defensive_reb + guest_offensive_reb) * 100

        Returns:
            list[list[float]]: Two nested lists:
                [0] → [home_OREB%, guest_OREB%]
                [1] → [home_DREB%, guest_DREB%]
        """
        rh = [self.count_stat(['O'], self.home), self.count_stat(['D'], self.home)]
        rg = [self.count_stat(['O'], self.guest), self.count_stat(['D'], self.guest)]

        oreb = rh[0] / (rh[0] + rg[1]) * 100 if (rh[0] + rg[1]) != 0 else 0
        dreb = rh[1] / (rh[1] + rg[0]) * 100 if (rh[1] + rg[0]) != 0 else 0

        # Guest percentages are the complement of the home percentages
        return [[oreb, 100 - dreb], [dreb, 100 - oreb]]

    def reb(self):
        """
        Return the total number of available offensive and defensive rebounds
        for each team (i.e. all contested rebounds in each category).

        Used by PlayerStat to compute individual rebound percentages relative
        to team totals.

        Returns:
            list[list[int]]: Two nested lists:
                [0] → [home_oreb_available, home_dreb_available]
                [1] → [guest_oreb_available, guest_dreb_available]
        """
        horebdisp = self.count_stat(['O'], self.home) + self.count_stat(['D'], self.guest)
        hdrebdisp = self.count_stat(['O'], self.guest) + self.count_stat(['D'], self.home)
        return [[horebdisp, hdrebdisp], [hdrebdisp, horebdisp]]

    # ------------------------------------------------------------------
    # Turnover percentage
    # ------------------------------------------------------------------

    def c_tov(self):
        """
        Calculate Turnover Percentage (TOV%) for each team.

        TOV% = turnovers * 100 / possessions

        Represents the fraction of possessions that ended in a turnover.

        Returns:
            list[float]: [home_TOV%, guest_TOV%]
        """
        toh = self.count_stat(['TO'], self.home) * 100
        tog = self.count_stat(['TO'], self.guest) * 100
        return [
            toh / self.poss[0] if self.poss[0] > 0 else 0,
            tog / self.poss[1] if self.poss[1] > 0 else 0,
        ]

    # ------------------------------------------------------------------
    # Assist metrics
    # ------------------------------------------------------------------

    def ar(self):
        """
        Calculate Assist Ratio (AST RATIO) for each team.

        AST RATIO = assists / plays * 100

        Represents the percentage of plays that resulted in an assist.

        Returns:
            list[float]: [home_AST_RATIO, guest_AST_RATIO]
        """
        return [
            self.count_stat(['AS'], self.home) / self.sc[0] * 100 if self.sc[0] > 0 else 0,
            self.count_stat(['AS'], self.guest) / self.sc[1] * 100 if self.sc[1] > 0 else 0,
        ]

    def at(self):
        """
        Calculate Assist-to-Turnover ratio (AST/TO) for each team.

        When a team has zero turnovers the raw assist count is returned
        to avoid division by zero while still conveying ball-security quality.

        Returns:
            list[float]: [home_AST/TO, guest_AST/TO]
        """
        to_home = self.count_stat(['TO'], self.home)
        to_guest = self.count_stat(['TO'], self.guest)

        athome = (
            self.count_stat(['AS'], self.home) / to_home if to_home != 0
            else self.count_stat(['AS'], self.home)
        )
        atguest = (
            self.count_stat(['AS'], self.guest) / to_guest if to_guest != 0
            else self.count_stat(['AS'], self.guest)
        )
        return [athome, atguest]

    # ------------------------------------------------------------------
    # Shooting efficiency
    # ------------------------------------------------------------------

    def efg(self):
        """
        Calculate Effective Field Goal Percentage (eFG%) for each team.

        eFG% adjusts the standard FG% by giving extra weight to 3-pointers,
        since they are worth 50% more points than 2-pointers:

            eFG% = (FGM + 0.5 * 3FGM) / FGA * 100

        where FGM includes both 2- and 3-point makes (including and-one makes).

        Returns:
            list[float]: [home_eFG%, guest_eFG%]
        """
        tfg = [
            self.count_stat(['2FGM', '2FGF', '3FGF', '3FGM'], self.home),
            self.count_stat(['2FGM', '2FGF', '3FGF', '3FGM'], self.guest),
        ]
        # Extra 0.5 credit for each 3-pointer made
        tp = [
            0.5 * self.count_stat(['3FGF', '3FGM'], self.home),
            0.5 * self.count_stat(['3FGF', '3FGM'], self.guest),
        ]
        fga = [
            self.count_stat(['2FGA', '3FGA'], self.home),
            self.count_stat(['2FGA', '3FGA'], self.guest),
        ]
        efg_home = (tfg[0] + tp[0]) / (tfg[0] + fga[0]) * 100 if fga[0] > 0 else 0
        efg_guest = (tfg[1] + tp[1]) / (tfg[1] + fga[1]) * 100 if fga[1] > 0 else 0
        return [efg_home, efg_guest]

    def ts(self):
        """
        Calculate True Shooting Percentage (TS%) for each team.

        TS% accounts for 2-point field goals, 3-point field goals, and free
        throws in a single efficiency metric:

            TS% = points / (2 * TSA) * 100

        where TSA (True Shooting Attempts) = FGA + 0.44 * FTA.
        Here FTA is approximated by counting FTMF events (final free throws
        that end a possession) along with all field goal attempts.

        Returns:
            list[float]: [home_TS%, guest_TS%]
        """
        a = ['2FGM', '2FGF', '3FGF', '3FGM', '2FGA', '3FGA', 'FTMF']

        home = (
            self.points[0] / (2 * self.count_stat(a, self.home)) * 100
            if self.count_stat(a, self.home) > 0 else 0
        )
        guest = (
            self.points[1] / (2 * self.count_stat(a, self.guest)) * 100
            if self.count_stat(a, self.guest) > 0 else 0
        )
        return [home, guest]

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def to_dataframe(self):
        """
        Serialize all computed team statistics into a pandas DataFrame.

        Each row corresponds to one team (indexed by team code).
        Numeric rounding is applied in main.py before printing.

        Returns:
            pd.DataFrame: Team stats with shape (2, 13), indexed by team code.
        """
        data = {
            'Possessions': self.poss,
            'Plays': self.sc,
            'Points': self.points,
            'ORTG': self.ortg,
            'DRTG': self.drtg,
            'NETRTG': self.netrtg,
            'AST RATIO': self.astrate,
            'AST/TO': self.astto,
            'OREB%': self.orebpct,
            'DREB%': self.drebpct,
            'TOV%': self.tovpct,
            'eFG%': self.eFG,
            'TS%': self.TS,
        }
        return pd.DataFrame(data, index=[self.home, self.guest])

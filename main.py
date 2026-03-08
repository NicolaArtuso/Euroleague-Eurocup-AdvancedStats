import pandas as pd
import requests
import json
import time
from Team import TeamStat
from Player import PlayerStat


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def find_home(df):
    """
    Identify the home team code from the play-by-play DataFrame.

    The home team is the one associated with POINTS_A (the left-side score
    column in the Euroleague API response). We look for the first row where
    POINTS_A is non-zero and return its team code.

    Args:
        df (pd.DataFrame): Cleaned play-by-play DataFrame.

    Returns:
        str: Team code of the home side (e.g. 'MAD', 'BAR').
    """
    row = df[df['POINTS_A'] != 0.0].iloc[0]
    return row['CODETEAM']


def find_guest(df):
    """
    Identify the away (guest) team code from the play-by-play DataFrame.

    The away team is linked to POINTS_B. We look for the first row where
    POINTS_B is non-zero and return its team code.

    Args:
        df (pd.DataFrame): Cleaned play-by-play DataFrame.

    Returns:
        str: Team code of the away side (e.g. 'OLY', 'MIL').
    """
    row = df.loc[df['POINTS_B'] != 0.0].iloc[0]
    return row['CODETEAM']


def convert_to_seconds(time_str):
    """
    Convert a basketball game clock string ('MM:SS') to total seconds.

    The Euroleague API returns the remaining time on the shot clock in
    'MM:SS' format. Converting to seconds makes arithmetic comparisons
    (e.g. checking whether two events happened within the same second)
    straightforward.

    Args:
        time_str (str): Time string in 'MM:SS' format (e.g. '08:34').

    Returns:
        int: Total seconds corresponding to the input string.
    """
    minutes, seconds = time_str.split(':')
    return int(minutes) * 60 + int(seconds)


def create_url():
    """
    Prompt the user for competition, season, and game identifiers, then
    fetch the corresponding play-by-play data from the Euroleague Live API.

    The API endpoint used is:
        https://live.euroleague.net/api/PlaybyPlay?gamecode=<CODE>&seasoncode=<LEAGUE><SEASON>

    Where:
        - <LEAGUE>  is 'E' for EuroLeague or 'U' for EuroCup
        - <SEASON>  is the four-digit year the season started (e.g. '2023')
        - <CODE>    is the numeric game code visible in the official website URL

    Returns:
        dict: Raw JSON response from the API containing quarter-by-quarter
              play-by-play event lists.
    """
    league = input("Choose competition – EuroCup (U) or EuroLeague (E): ")
    season_code = input("Enter the season code (e.g. 2023): ")
    game_code = input("Enter the game code: ")

    link = (
        f"https://live.euroleague.net/api/PlaybyPlay"
        f"?gamecode={game_code}&seasoncode={league}{season_code}"
    )

    response = requests.get(url=link).json()
    return response


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    """
    Orchestrate the full stats pipeline:

    1. Fetch play-by-play data from the Euroleague API.
    2. Build and clean a unified DataFrame that spans all quarters.
    3. Derive custom play-type labels needed by the advanced-stats formulas
       (final free throws, field-goal-with-foul, shooting fouls, offensive fouls).
    4. Compute team-level and player-level advanced statistics.
    5. Print results and optionally export them as tab-separated .dat files.
    """

    # ------------------------------------------------------------------
    # Step 1 – Data acquisition
    # ------------------------------------------------------------------
    r = create_url()

    # Retrieve column names from the first event of the first quarter
    table_headers = list(r['FirstQuarter'][0].keys())

    # Prepend a QUARTER column to tag each event with its period
    df_cols = ['QUARTER'] + table_headers
    df = pd.DataFrame(columns=df_cols)

    quarters = ['FirstQuarter', 'SecondQuarter', 'ThirdQuarter', 'ForthQuarter', 'ExtraTime']

    # ------------------------------------------------------------------
    # Step 2 – Build the master DataFrame from all quarters
    # ------------------------------------------------------------------
    for q in quarters:
        # Convert each event dict to a list of values
        action = [None] * len(r[q])
        for i in range(len(r[q])):
            action[i] = list(r[q][i].values())

        temp_df1 = pd.DataFrame(action, columns=table_headers)
        temp_df2 = pd.DataFrame({'QUARTER': [q for i in range(len(r[q]))]})
        temp_df3 = pd.concat([temp_df2, temp_df1], axis=1)
        df = pd.concat([df, temp_df3], axis=0)

    df = df.drop_duplicates().reset_index(drop=True)
    del (temp_df1, temp_df2, temp_df3)

    # ------------------------------------------------------------------
    # Step 3 – Cleaning
    # ------------------------------------------------------------------

    # Drop columns that are redundant or irrelevant to the analysis
    df = df.drop(['TYPE', 'NUMBEROFPLAY', 'COMMENT', 'MINUTE', 'DORSAL'], axis=1)

    # Fill missing score values with 0 (only scoring events carry a value)
    df['POINTS_A'] = df['POINTS_A'].fillna(0.0)
    df['POINTS_B'] = df['POINTS_B'].fillna(0.0)

    # Cast scores to integer for consistent arithmetic
    df['POINTS_A'] = df['POINTS_A'].astype(int)
    df['POINTS_B'] = df['POINTS_B'].astype(int)

    # Fix game-clock markers for period boundaries:
    #   BP = Begin Period  → clock starts at 10:00
    #   EP = End Period    → clock stops at 00:00
    #   EG = End Game      → clock stops at 00:00
    df.loc[df['PLAYTYPE'] == 'BP', 'MARKERTIME'] = '10:00'
    df.loc[df['PLAYTYPE'] == 'EP', 'MARKERTIME'] = '00:00'
    df.loc[df['PLAYTYPE'] == 'EG', 'MARKERTIME'] = '00:00'

    # Convert clock strings to seconds for numeric comparisons
    df['MARKERTIME'] = df['MARKERTIME'].apply(convert_to_seconds)

    # Strip whitespace from string identifiers
    df['CODETEAM'] = df['CODETEAM'].str.strip()
    df['PLAYER_ID'] = df['PLAYER_ID'].str.strip()
    df['PLAYER'] = df['PLAYER'].str.strip()

    # ------------------------------------------------------------------
    # Step 4 – Custom play-type labelling
    # ------------------------------------------------------------------

    # --- 4a. Final free throws (FTMF) ---
    # A made free throw (FTM) ends a possession only when the next event
    # occurs at a different clock time (i.e. it is the last in the sequence).
    # We re-label those as FTMF to distinguish possession-ending FTs.
    dfFT = pd.DataFrame(df.loc[df['PLAYTYPE'].isin(['FTM', 'FTA'])])
    condition = (dfFT['PLAYTYPE'] == 'FTM') & (
        dfFT['MARKERTIME'].shift(-1) != dfFT['MARKERTIME']
    )
    dfFT.loc[condition, 'PLAYTYPE'] = 'FTMF'
    df.update(dfFT[dfFT['PLAYTYPE'] == 'FTMF'])
    del dfFT

    # --- 4b. Field goals with foul (2FGF / 3FGF) ---
    # A made 2- or 3-point basket followed immediately (within 1 second)
    # by a free-throw event means the shooter was fouled on the attempt.
    # These shots do NOT end the possession by themselves, so they receive
    # their own labels (2FGF / 3FGF).
    dfFG = pd.DataFrame(df.loc[df['PLAYTYPE'].isin(['FTM', 'FTA', '3FGM', '2FGM', 'FTMF'])])
    cond1 = (dfFG['PLAYTYPE'] == '2FGM') & (dfFG['PLAYTYPE'].shift(-1).isin(['FTM', 'FTMF', 'FTA']))
    cond2 = (dfFG['PLAYTYPE'] == '3FGM') & (dfFG['PLAYTYPE'].shift(-1).isin(['FTM', 'FTMF', 'FTA']))
    cond3 = cond1 & (abs(dfFG['MARKERTIME'] - dfFG['MARKERTIME'].shift(-1)) < 2)
    cond4 = cond2 & (abs(dfFG['MARKERTIME'] - dfFG['MARKERTIME'].shift(-1)) < 2)
    dfFG.loc[cond3, 'PLAYTYPE'] = '2FGF'
    dfFG.loc[cond4, 'PLAYTYPE'] = '3FGF'
    df.update(dfFG[dfFG['PLAYTYPE'] == '2FGF'])
    df.update(dfFG[dfFG['PLAYTYPE'] == '3FGF'])
    del dfFG

    # --- 4c. Shooting fouls received (SRV) ---
    # An RV (foul received) that is immediately followed by free-throw events
    # is a shooting foul. It does not represent an independent offensive play,
    # so it is re-labelled as SRV to avoid double-counting.
    dfF = pd.DataFrame(df.loc[df['PLAYTYPE'].isin(['FTM', 'FTA', 'RV', 'FTMF'])])
    condition = (dfF['PLAYTYPE'] == 'RV') & (dfF['PLAYTYPE'].shift(-1).isin(['FTM', 'FTMF', 'FTA']))
    dfF.loc[condition, 'PLAYTYPE'] = 'SRV'
    df.update(dfF[dfF['PLAYTYPE'] == 'SRV'])
    del dfF

    # --- 4d. Offensive foul received (ORV) ---
    # An RV event that occurs within 1 second of an OF (offensive foul)
    # signals an offensive foul on the ball-handler, which ends the possession.
    # We label the paired RV as ORV.
    dfOF = pd.DataFrame(df.loc[df['PLAYTYPE'].isin(['OF', 'RV'])])
    cond1 = (dfOF['PLAYTYPE'] == 'RV') & (dfOF['PLAYTYPE'].shift(1).isin(['OF']))
    cond2 = (dfOF['PLAYTYPE'] == 'RV') & (dfOF['PLAYTYPE'].shift(-1).isin(['OF']))
    cond3 = cond1 & (abs(dfOF['MARKERTIME'] - dfOF['MARKERTIME'].shift(1)) < 2)
    cond4 = cond2 & (abs(dfOF['MARKERTIME'] - dfOF['MARKERTIME'].shift(-1)) < 2)
    dfOF.loc[cond3, 'PLAYTYPE'] = 'ORV'
    dfOF.loc[cond4, 'PLAYTYPE'] = 'ORV'
    df.update(dfOF[dfOF['PLAYTYPE'] == 'ORV'])
    del dfOF

    # ------------------------------------------------------------------
    # Step 5 – Identify teams
    # ------------------------------------------------------------------
    home = find_home(df)
    guest = find_guest(df)

    # ------------------------------------------------------------------
    # Step 6 – Team stats
    # ------------------------------------------------------------------
    team_stats = TeamStat(df, home, guest)
    df_team_stats = team_stats.to_dataframe()
    # Round all values to 2 decimal places for readability
    df_team_stats = df_team_stats.applymap(lambda x: round(x, 2))
    print(df_team_stats)

    # ------------------------------------------------------------------
    # Step 7 – Player stats
    # ------------------------------------------------------------------
    # Collect all unique player names, excluding None / empty strings
    players_names = list(filter(lambda x: x is not None and x != '', df['PLAYER'].unique()))
    player_stats_list = []

    for code in players_names:
        player_stat = PlayerStat(code, df, home, guest)
        player_stats_list.append(player_stat.to_dataframe())

    # Concatenate individual DataFrames and sort by team
    all_player_stats = pd.concat(player_stats_list)
    all_player_stats = all_player_stats.sort_values(by='Team')
    all_player_stats = all_player_stats.round(2)
    print(all_player_stats)

    # ------------------------------------------------------------------
    # Step 8 – Optional export
    # ------------------------------------------------------------------
    richiesta = input('Press s to save results, or any other key to quit: ')
    if richiesta == 's':
        # Tab-separated .dat files, one for team stats and one for players
        df_team_stats.to_csv(home + '-' + guest + '.dat', sep='\t', index=True)
        all_player_stats.to_csv('players_' + home + '-' + guest + '.dat', sep='\t', index=True)


main()

# 🏀 Euroleague / EuroCup Advanced Stats

A Python tool that fetches play-by-play data from the **Euroleague Live API** and computes advanced basketball statistics for both teams and individual players in a single game.

---

## Table of Contents

- [Overview](#overview)
- [Stats Reference](#stats-reference)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Output](#output)
- [How It Works](#how-it-works)
- [Known Limitations](#known-limitations)

---

## Overview

Standard box scores tell only part of the story. This tool goes deeper by parsing every single play-by-play event of a EuroLeague or EuroCup game and computing metrics like **Offensive Rating**, **True Shooting %**, **Usage %**, and more — both at team level and at individual player level (on-court only).

No database or pre-downloaded files required: stats are calculated on-the-fly from the official Euroleague Live API.

---

## Stats Reference

### Team stats

| Metric | Description |
|---|---|
| **Possessions** | Estimated number of possessions per team |
| **Plays** | Total offensive plays (possessions + off. rebounds + non-shooting fouls received) |
| **Points** | Final points scored |
| **ORTG** | Offensive Rating – points per 100 possessions |
| **DRTG** | Defensive Rating – opponent points per 100 possessions |
| **NETRTG** | Net Rating – ORTG minus DRTG |
| **AST RATIO** | Percentage of plays that resulted in an assist |
| **AST/TO** | Assist-to-turnover ratio |
| **OREB%** | Percentage of available offensive rebounds secured |
| **DREB%** | Percentage of available defensive rebounds secured |
| **TOV%** | Percentage of possessions that ended in a turnover |
| **eFG%** | Effective FG% – weights 3-pointers proportionally to their extra value |
| **TS%** | True Shooting % – efficiency across 2FG, 3FG, and free throws |

### Player stats (on-court only)

All team metrics above, plus:

| Metric | Description |
|---|---|
| **Minutes** | Playing time in MM:SS format |
| **Plays** | Individual offensive plays |
| **Points** | Points scored |
| **USG%** | Usage % – share of team plays initiated while on court |

---

## Project Structure

```
Euroleague-Eurocup-AdvancedStats/
│
├── main.py        # Entry point – fetches data, cleans it, orchestrates the pipeline
├── Team.py        # TeamStat class – all team-level advanced metrics
├── Player.py      # PlayerStat class – per-player on-court advanced metrics
└── README.md
```

---

## Requirements

- Python 3.8+
- [pandas](https://pandas.pydata.org/)
- [requests](https://docs.python-requests.org/)

---

## Installation

```bash
# Clone the repository
git clone https://github.com/NicolaArtuso/Euroleague-Eurocup-AdvancedStats.git
cd Euroleague-Eurocup-AdvancedStats

# Install dependencies
pip install pandas requests
```

---

## Usage

Run the script from the project root:

```bash
python main.py
```

You will be prompted for three inputs:

```
Choose competition – EuroCup (U) or EuroLeague (E): E
Enter the season code (e.g. 2023): 2023
Enter the game code: 1
```

**How to find the game code:**
Navigate to any game on [euroleaguebasketball.net](https://www.euroleaguebasketball.net), open the play-by-play page, and look at the URL — the `gamecode` parameter is the number you need.

**Season code** is the four-digit year the season started (e.g. `2023` for the 2023-24 season).

---

## Output

After the stats are printed to the console, you will be asked:

```
Press s to save results, or any other key to quit:
```

Pressing `s` saves two tab-separated files in the current directory:

| File | Contents |
|---|---|
| `HOME-GUEST.dat` | Team-level advanced stats |
| `players_HOME-GUEST.dat` | Player-level advanced stats |

---

## How It Works

### 1 — Data acquisition
The script calls the Euroleague Live API endpoint:
```
https://live.euroleague.net/api/PlaybyPlay?gamecode=<CODE>&seasoncode=<LEAGUE><SEASON>
```
The response contains a list of play-by-play events for each quarter (including overtime).

### 2 — DataFrame construction
All quarters are merged into a single `pandas` DataFrame. Redundant columns (`TYPE`, `NUMBEROFPLAY`, `COMMENT`, `MINUTE`, `DORSAL`) are dropped and game-clock strings are converted to seconds for numeric comparisons.

### 3 — Custom play-type labelling
The raw API uses generic labels that need to be refined to correctly count possessions:

| Custom label | Meaning |
|---|---|
| `FTMF` | **Final free throw** – the last FT in a sequence, which ends the possession |
| `2FGF` / `3FGF` | **And-one make** – field goal made while being fouled; does not end possession by itself |
| `SRV` | **Shooting foul received** – foul that leads to free throws, not an independent play |
| `ORV` | **Offensive foul received** – possession-ending charge drawn by the defence |

### 4 — Statistics computation
- `TeamStat` computes all team metrics on the full game DataFrame.
- `PlayerStat` reconstructs the subset of rows where each player was on the court (using substitution IN/OUT events) and instantiates a `TeamStat` on that slice to calculate on-court ratings.

---

> This tool uses the unofficial Euroleague Live API. It is not affiliated with or endorsed by Euroleague Basketball.

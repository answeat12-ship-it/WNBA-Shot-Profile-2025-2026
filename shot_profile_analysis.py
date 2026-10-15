import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Rectangle, Arc

# Load the 2025 datasets
shots_2025 = pd.read_csv("data/shots_2025.csv")
schedule_2025 = pd.read_csv("data/wnba_schedule_2025.csv")

# Load the 2026 datasets
shots_2026 = pd.read_csv("data/shots_2026.csv")
schedule_2026 = pd.read_csv("data/wnba_schedule_2026.csv")

# Add a season label to each dataset
shots_2025["analysis_season"] = 2025
shots_2026["analysis_season"] = 2026

# Combine both seasons into one dataset
shots = pd.concat(
    [shots_2025, shots_2026],
    ignore_index=True
)

schedule = pd.concat(
    [schedule_2025, schedule_2026],
    ignore_index=True
)

# Verify that both seasons combined successfully
print("\nCombined Shot Dataset:")
print(shots.shape)

print("\nCombined Schedule Dataset:")
print(schedule.shape)

# Count shot records by season
print("\nShot Records by Season:")
print(shots["analysis_season"].value_counts().sort_index())

# Confirm each season has the expected records
print("\n2025 Shot Records:", len(shots_2025))
print("2026 Shot Records:", len(shots_2026))

# ==========================================
# FILTER REGULAR-SEASON SHOT EVENTS
# ==========================================

# Identify regular-season games from both schedules
regular_2025 = schedule_2025[
    schedule_2025["season_type"] == 2
].copy()

regular_2026 = schedule_2026[
    schedule_2026["season_type"] == 2
].copy()

# Build a combined table of valid regular-season game IDs
regular_games = pd.concat(
    [
        regular_2025[["id"]].assign(analysis_season=2025),
        regular_2026[["id"]].assign(analysis_season=2026)
    ],
    ignore_index=True
)

# Match shots to games using both game ID and season
regular_shots = shots.merge(
    regular_games,
    left_on=["game_id", "analysis_season"],
    right_on=["id", "analysis_season"],
    how="inner",
    validate="many_to_one"
)

# ==========================================
# EXCLUDE SPECIAL EVENTS: 2025 AND 2026
# ==========================================

CUP_ID_2025 = 401736430

CUP_ID_2026 = 401857321
ALL_STAR_ID_2026 = 401857320

# Exclude special games by season and game ID
special_game_mask = (
    (
        (regular_shots["analysis_season"] == 2025) &
        (regular_shots["game_id"] == CUP_ID_2025)
    )
    |
    (
        (regular_shots["analysis_season"] == 2026) &
        (
            regular_shots["game_id"].isin(
                [CUP_ID_2026, ALL_STAR_ID_2026]
            )
        )
    )
)

regular_shots = regular_shots[
    ~special_game_mask
].copy()

# Preserve the original 2025 All-Star exclusion
regular_shots = regular_shots[
    ~(
        (regular_shots["analysis_season"] == 2025) &
        (
            regular_shots["team_name"].isin(
                ["Team Clark", "Team Collier"]
            )
        )
    )
].copy()


# Select Kelsey Mitchell and Jackie Young
KELSEY_ID = 3142191
JACKIE_ID = 4065870

player_shots = regular_shots[
    regular_shots["athlete_id_1"].isin([KELSEY_ID, JACKIE_ID])
].copy()

print("\nRegular-Season Player Shot Events:")
print(
    player_shots.groupby(
        ["analysis_season", "athlete_name_1"]
    ).size()
)


# ==========================================
# FILTER FIELD-GOAL ATTEMPTS
# ==========================================

# Remove free-throw events
field_goals = player_shots[
    ~player_shots["type_text"].str.contains(
        "Free Throw",
        case=False,
        na=False
    )
].copy()

# Count field-goal attempts for each player and season
print("\nField-Goal Attempts by Season:")
print(
    field_goals.groupby(
        ["analysis_season", "athlete_name_1"]
    ).size()
)

# Count unique games represented for each player
print("\nGames Represented by Season:")
print(
    field_goals.groupby(
        ["analysis_season", "athlete_name_1"]
    )["game_id"].nunique()
)

# Find Team Coop shot events
team_coop = shots_2026[
    shots_2026["team_name"].str.contains(
        "Coop", case=False, na=False
    )
]

print("\n2026 Team Coop Games:")
print(
    team_coop.groupby(["game_id", "team_name"])
    .size()
)

# Find Liberty vs. Aces games in the schedule
liberty_aces = schedule_2026[
    (
        schedule_2026["home_name"].isin(
            ["Liberty", "Aces"]
        )
    ) &
    (
        schedule_2026["away_name"].isin(
            ["Liberty", "Aces"]
        )
    ) &
    (
        schedule_2026["home_name"] !=
        schedule_2026["away_name"]
    )
]

print("\n2026 Liberty vs. Aces Games:")
print(
    liberty_aces[
        ["id", "game_date", "home_name",
         "away_name", "season_type"]
    ].to_string(index=False)
)

# ==========================================
# FINAL PLAYER SEASON VALIDATION
# ==========================================

season_summary = (
    field_goals.groupby(
        ["analysis_season", "athlete_name_1"]
    )
    .agg(
        Games=("game_id", "nunique"),
        FGA=("game_id", "size")
    )
    .reset_index()
)

season_summary["FGA_per_Game"] = (
    season_summary["FGA"] /
    season_summary["Games"]
).round(2)

print("\nFINAL CLEANED SEASON SUMMARY:")
print(season_summary.to_string(index=False))

# ==========================================
# CALCULATE SHOT LOCATIONS
# ==========================================

# Normalize shot coordinates to one basket
field_goals["court_x"] = (
    field_goals["coordinate_x"].abs()
)

field_goals["court_y"] = (
    field_goals["coordinate_y"].where(
        field_goals["coordinate_x"] >= 0,
        -field_goals["coordinate_y"]
    )
)

# Basket location in our coordinate system
RIM_X = 41.25
RIM_Y = 0

# Calculate distance from the basket
field_goals["shot_distance"] = (
    (
        (field_goals["court_x"] - RIM_X) ** 2
        + (field_goals["court_y"] - RIM_Y) ** 2
    ) ** 0.5
)

# Validate the calculated distances
print("\nShot Distance Summary by Season:")
print(
    field_goals.groupby("analysis_season")[
        "shot_distance"
    ].describe().round(2)
)

print("\nMissing Shot Distances:")
print(
    field_goals.groupby("analysis_season")[
        "shot_distance"
    ].apply(lambda values: values.isna().sum())
)

# ==========================================
# CLASSIFY SHOT ZONES
# ==========================================

# Determine whether an attempt is worth 2 or 3 points
def classify_shot_value(row):
    if row["court_x"] >= 38.75 and abs(row["court_y"]) >= 22:
        return 3
    elif row["shot_distance"] >= 22.25:
        return 3
    else:
        return 2


field_goals["predicted_shot_value"] = field_goals.apply(
    classify_shot_value,
    axis=1
)


# Assign each attempt to a shot zone
def classify_shot_zone(row):
    if row["predicted_shot_value"] == 3:
        if row["court_x"] >= 38.75 and abs(row["court_y"]) >= 22:
            return "Corner 3"
        return "Above the Break 3"

    elif row["shot_distance"] <= 4:
        return "Rim"

    elif row["court_x"] >= 25 and abs(row["court_y"]) <= 8:
        return "Paint"

    else:
        return "Midrange"


field_goals["shot_zone"] = field_goals.apply(
    classify_shot_zone,
    axis=1
)

# Check shot-zone distribution by season
print("\nShot Zone Counts by Season:")
print(
    pd.crosstab(
        field_goals["analysis_season"],
        field_goals["shot_zone"]
    )
)

# Check for unclassified attempts
print("\nMissing Shot Zones:")
print(field_goals["shot_zone"].isna().sum())


# ==========================================
# PLAYER SHOT DISTRIBUTION BY SEASON
# ==========================================

# Count attempts by season, player, and shot zone
shot_distribution = (
    field_goals.groupby(
        ["analysis_season", "athlete_name_1", "shot_zone"]
    )
    .size()
    .reset_index(name="FGA")
)

# Calculate each player's total attempts per season
shot_distribution["Total_FGA"] = (
    shot_distribution.groupby(
        ["analysis_season", "athlete_name_1"]
    )["FGA"].transform("sum")
)

# Calculate the percentage of attempts from each zone
shot_distribution["Shot_Pct"] = (
    shot_distribution["FGA"] /
    shot_distribution["Total_FGA"] * 100
).round(1)

print("\nPLAYER SHOT DISTRIBUTION:")
print(
    shot_distribution.sort_values(
        ["athlete_name_1", "analysis_season", "shot_zone"]
    ).to_string(index=False)
)

# ==========================================
# FIELD-GOAL PERCENTAGE BY SHOT ZONE
# ==========================================

# Convert made-shot indicator into a numeric value
field_goals["made"] = (
    field_goals["scoring_play"]
    .astype(int)
)

# Group attempts and makes by player, season, and zone
shot_efficiency = (
    field_goals.groupby(
        ["analysis_season", "athlete_name_1", "shot_zone"]
    )
    .agg(
        FGA=("made", "size"),
        FGM=("made", "sum")
    )
    .reset_index()
)

# Calculate field-goal percentage
shot_efficiency["FG_Pct"] = (
    shot_efficiency["FGM"] /
    shot_efficiency["FGA"] * 100
).round(1)

print("\nFIELD-GOAL PERCENTAGE BY ZONE:")
print(
    shot_efficiency.sort_values(
        ["athlete_name_1", "shot_zone", "analysis_season"]
    ).to_string(index=False)
)

# ==========================================
# POINTS PER SHOT BY ZONE AND SEASON
# ==========================================

# Ensure recorded points are numeric
field_goals["score_value"] = pd.to_numeric(
    field_goals["score_value"],
    errors="coerce"
)

# Check for missing recorded point values
print("\nMissing Score Values:")
print(
    field_goals.groupby("analysis_season")[
        "score_value"
    ].apply(lambda values: values.isna().sum())
)

# Aggregate recorded points and attempts
points_per_shot = (
    field_goals.groupby(
        ["analysis_season", "athlete_name_1", "shot_zone"]
    )
    .agg(
        FGA=("score_value", "size"),
        Points=("score_value", "sum")
    )
    .reset_index()
)

# Calculate points per field-goal attempt
points_per_shot["PPS"] = (
    points_per_shot["Points"] /
    points_per_shot["FGA"]
).round(2)

print("\nPOINTS PER SHOT BY ZONE:")
print(
    points_per_shot.sort_values(
        ["athlete_name_1", "shot_zone", "analysis_season"]
    ).to_string(index=False)
)

# Validate scoring values for made and missed shots
print("\nSCORING VALUE VALIDATION:")

print(
    field_goals.groupby(
        ["analysis_season", "scoring_play"]
    )["score_value"].agg(
        ["count", "min", "max", "sum"]
    )
)

print("\nMissing Score Values:")
print(
    field_goals.groupby("analysis_season")[
        "score_value"
    ].apply(lambda values: values.isna().sum())
)

# ==========================================
# STEP 23: OVERALL SHOOTING COMPARISON
# ==========================================

overall_stats = (
    field_goals.groupby(
        ["analysis_season", "athlete_name_1"]
    )
    .agg(
        FGA=("scoring_play", "size"),
        FGM=("scoring_play", "sum"),
        Points=("score_value", "sum")
    )
    .reset_index()
)

# Calculate overall field-goal percentage
overall_stats["FG_Pct"] = (
    overall_stats["FGM"] / overall_stats["FGA"] * 100
).round(1)

# Calculate points per field-goal attempt
overall_stats["PPS"] = (
    overall_stats["Points"] / overall_stats["FGA"]
).round(2)

print("\nOVERALL SHOOTING COMPARISON:")
print(overall_stats.to_string(index=False))


# ==========================================
# STEP 24: YEAR-OVER-YEAR CHANGES
# ==========================================

# Separate the 2025 and 2026 statistics
stats_2025 = overall_stats[
    overall_stats["analysis_season"] == 2025
].copy()

stats_2026 = overall_stats[
    overall_stats["analysis_season"] == 2026
].copy()

# Match each player across both seasons
year_comparison = stats_2025.merge(
    stats_2026,
    on="athlete_name_1",
    suffixes=("_2025", "_2026"),
    validate="one_to_one"
)

# Calculate changes between seasons
year_comparison["FGA_Change"] = (
    year_comparison["FGA_2026"]
    - year_comparison["FGA_2025"]
)

year_comparison["FG_Pct_Change"] = (
    year_comparison["FG_Pct_2026"]
    - year_comparison["FG_Pct_2025"]
).round(1)

year_comparison["PPS_Change"] = (
    year_comparison["PPS_2026"]
    - year_comparison["PPS_2025"]
).round(2)

print("\nYEAR-OVER-YEAR SHOOTING CHANGES:")

print(
    year_comparison[
        [
            "athlete_name_1",
            "FGA_Change",
            "FG_Pct_Change",
            "PPS_Change"
        ]
    ].to_string(index=False)
)

# ==========================================
# STEP 25: OVERALL FG% VISUALIZATION
# ==========================================

players = ["Jackie Young", "Kelsey Mitchell"]

fg_2025 = (
    overall_stats[
        overall_stats["analysis_season"] == 2025
    ]
    .set_index("athlete_name_1")
    .loc[players, "FG_Pct"]
)

fg_2026 = (
    overall_stats[
        overall_stats["analysis_season"] == 2026
    ]
    .set_index("athlete_name_1")
    .loc[players, "FG_Pct"]
)

x = np.arange(len(players))
width = 0.35

fig, ax = plt.subplots(figsize=(9, 6))

bars_2025 = ax.bar(
    x - width / 2,
    fg_2025,
    width,
    label="2025",
    color="#777777"
)

bars_2026 = ax.bar(
    x + width / 2,
    fg_2026,
    width,
    label="2026",
    color="#F5B335"
)

ax.bar_label(bars_2025, fmt="%.1f%%", padding=3)
ax.bar_label(bars_2026, fmt="%.1f%%", padding=3)

ax.set_title(
    "WNBA Shooting Efficiency: 2025 vs. 2026",
    fontsize=15,
    fontweight="bold"
)

ax.set_ylabel("Field-Goal Percentage (%)")
ax.set_xticks(x)
ax.set_xticklabels(players)
ax.set_ylim(0, 60)
ax.legend()

plt.tight_layout()

plt.savefig(
    "visualizations/overall_fg_percentage_comparison.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

# ==========================================
# STEP 27: POINTS PER SHOT COMPARISON
# ==========================================

# Get PPS values for each player by season
pps_2025 = (
    overall_stats[
        overall_stats["analysis_season"] == 2025
    ]
    .set_index("athlete_name_1")
    .loc[players, "PPS"]
)

pps_2026 = (
    overall_stats[
        overall_stats["analysis_season"] == 2026
    ]
    .set_index("athlete_name_1")
    .loc[players, "PPS"]
)

# Create the chart
fig, ax = plt.subplots(figsize=(9, 6))

bars_2025 = ax.bar(
    x - width / 2,
    pps_2025,
    width,
    label="2025",
    color="#777777"
)

bars_2026 = ax.bar(
    x + width / 2,
    pps_2026,
    width,
    label="2026",
    color="#F5B335"
)

# Display values above each bar
ax.bar_label(bars_2025, fmt="%.2f", padding=3)
ax.bar_label(bars_2026, fmt="%.2f", padding=3)

ax.set_title(
    "WNBA Points Per Shot: 2025 vs. 2026",
    fontsize=15,
    fontweight="bold"
)

ax.set_ylabel("Points Per Field-Goal Attempt")
ax.set_xticks(x)
ax.set_xticklabels(players)
ax.set_ylim(0, 1.5)
ax.legend()

plt.tight_layout()

# Save the visualization
plt.savefig(
    "visualizations/overall_pps_comparison.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

# ==========================================
# STEP 28: SHOT DISTRIBUTION COMPARISON
# ==========================================

zones = [
    "Above the Break 3",
    "Corner 3",
    "Midrange",
    "Paint",
    "Rim"
]

# Create one chart for each player
for player in players:

    player_data = shot_distribution[
        shot_distribution["athlete_name_1"] == player
    ]

    comparison = player_data.pivot(
        index="shot_zone",
        columns="analysis_season",
        values="Shot_Pct"
    ).reindex(zones)

    x_zones = np.arange(len(zones))
    bar_width = 0.35

    fig, ax = plt.subplots(figsize=(11, 6))

    bars_2025 = ax.bar(
        x_zones - bar_width / 2,
        comparison[2025],
        bar_width,
        label="2025",
        color="#777777"
    )

    bars_2026 = ax.bar(
        x_zones + bar_width / 2,
        comparison[2026],
        bar_width,
        label="2026",
        color="#F5B335"
    )

    ax.bar_label(bars_2025, fmt="%.1f%%", padding=3)
    ax.bar_label(bars_2026, fmt="%.1f%%", padding=3)

    ax.set_title(
        f"{player}: Shot Distribution (2025 vs. 2026)",
        fontsize=15,
        fontweight="bold"
    )

    ax.set_ylabel("Percentage of Field-Goal Attempts")
    ax.set_xticks(x_zones)
    ax.set_xticklabels(zones, rotation=15)
    ax.set_ylim(0, 50)
    ax.legend()

    plt.tight_layout()

    filename = player.lower().replace(" ", "_")

    plt.savefig(
        f"visualizations/{filename}_shot_distribution_comparison.png",
        dpi=300,
        bbox_inches="tight"
    )

    plt.show()


# ==========================================
# 29. JACKIE YOUNG FG% BY SHOT ZONE
# ==========================================

# Select Jackie Young's shooting efficiency data
jackie_fg = shot_efficiency[
    shot_efficiency["athlete_name_1"] == "Jackie Young"
].copy()

# Organize the shot zones
zones = [
    "Above the Break 3",
    "Corner 3",
    "Midrange",
    "Paint",
    "Rim"
]

# Retrieve FG% for each season in zone order
jackie_2025 = (
    jackie_fg[jackie_fg["analysis_season"] == 2025]
    .set_index("shot_zone")
    .reindex(zones)["FG_Pct"]
)

jackie_2026 = (
    jackie_fg[jackie_fg["analysis_season"] == 2026]
    .set_index("shot_zone")
    .reindex(zones)["FG_Pct"]
)

# Set up the chart
x = np.arange(len(zones))
bar_width = 0.35

fig, ax = plt.subplots(figsize=(11, 6))

bars_2025 = ax.bar(
    x - bar_width / 2,
    jackie_2025,
    bar_width,
    label="2025",
    color="#777777"
)

bars_2026 = ax.bar(
    x + bar_width / 2,
    jackie_2026,
    bar_width,
    label="2026",
    color="#FFB335"
)

# Add percentage labels above the bars
ax.bar_label(bars_2025, fmt="%.1f%%", padding=3)
ax.bar_label(bars_2026, fmt="%.1f%%", padding=3)

# Titles and labels
ax.set_title(
    "Jackie Young: Field-Goal Percentage by Zone (2025 vs. 2026)",
    fontsize=15,
    fontweight="bold"
)

ax.set_ylabel("Field-Goal Percentage (%)")
ax.set_xticks(x)
ax.set_xticklabels(zones, rotation=15, ha="right")
ax.set_ylim(0, 85)
ax.legend()

plt.tight_layout()

# Save the visualization
plt.savefig(
    "visualizations/jackie_young_fg_percentage_comparison.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

# ==========================================
# 29A. Kelsey Mitchell FG% BY SHOT ZONE
# ==========================================

# Select Kelsey Mitchell's shooting efficiency data
kelsey_fg = shot_efficiency[
    shot_efficiency["athlete_name_1"] == "Kelsey Mitchell"
].copy()

# Organize the shot zones
zones = [
    "Above the Break 3",
    "Corner 3",
    "Midrange",
    "Paint",
    "Rim"
]

# Retrieve FG% for each season in zone order
kelsey_2025 = (
    kelsey_fg[kelsey_fg["analysis_season"] == 2025]
    .set_index("shot_zone")
    .reindex(zones)["FG_Pct"]
)

kelsey_2026 = (
    kelsey_fg[kelsey_fg["analysis_season"] == 2026]
    .set_index("shot_zone")
    .reindex(zones)["FG_Pct"]
)

# Set up the chart
x = np.arange(len(zones))
bar_width = 0.35

fig, ax = plt.subplots(figsize=(11, 6))

bars_2025 = ax.bar(
    x - bar_width / 2,
    kelsey_2025,
    bar_width,
    label="2025",
    color="#777777"
)

bars_2026 = ax.bar(
    x + bar_width / 2,
    kelsey_2026,
    bar_width,
    label="2026",
    color="#FFB335"
)

# Add percentage labels above the bars
ax.bar_label(bars_2025, fmt="%.1f%%", padding=3)
ax.bar_label(bars_2026, fmt="%.1f%%", padding=3)

# Titles and labels
ax.set_title(
    "Kelsey Mitchell: Field-Goal Percentage by Zone (2025 vs. 2026)",
    fontsize=15,
    fontweight="bold"
)

ax.set_ylabel("Field-Goal Percentage (%)")
ax.set_xticks(x)
ax.set_xticklabels(zones, rotation=15, ha="right")
ax.set_ylim(0, 85)
ax.legend()

plt.tight_layout()

# Save the visualization
plt.savefig(
    "visualizations/kelsey_mitchell_fg_percentage_comparison.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()


# ==========================================
# 30. POINTS PER SHOT BY ZONE
# ==========================================

# Group shots by season, player, and shot zone
pps_by_zone = (
    field_goals.groupby(
        ["analysis_season", "athlete_name_1", "shot_zone"]
    )
    .agg(
        FGA=("score_value", "size"),
        Points=("score_value", "sum")
    )
    .reset_index()
)

# Calculate points per field-goal attempt
pps_by_zone["PPS"] = (
    pps_by_zone["Points"] / pps_by_zone["FGA"]
)

# Display the results
print("\nPOINTS PER SHOT BY ZONE:")
print(pps_by_zone.to_string(index=False))

# ==========================================
# 30B. JACKIE YOUNG POINTS PER SHOT
# ==========================================

# Filter the PPS data for Jackie Young
jackie_pps = pps_by_zone[
    pps_by_zone["athlete_name_1"] == "Jackie Young"
].copy()

# Keep our shot zones in the same order
zones = [
    "Above the Break 3",
    "Corner 3",
    "Midrange",
    "Paint",
    "Rim"
]

# Separate the 2025 and 2026 values
jackie_pps_2025 = (
    jackie_pps[jackie_pps["analysis_season"] == 2025]
    .set_index("shot_zone")
    .reindex(zones)["PPS"]
)

jackie_pps_2026 = (
    jackie_pps[jackie_pps["analysis_season"] == 2026]
    .set_index("shot_zone")
    .reindex(zones)["PPS"]
)

# Set up the chart
x = np.arange(len(zones))
bar_width = 0.35

fig, ax = plt.subplots(figsize=(11, 6))

# Plot the 2025 bars
bars_2025 = ax.bar(
    x - bar_width / 2,
    jackie_pps_2025,
    bar_width,
    label="2025",
    color="#777777"
)

# Plot the 2026 bars
bars_2026 = ax.bar(
    x + bar_width / 2,
    jackie_pps_2026,
    bar_width,
    label="2026",
    color="#FFB335"
)

# Add PPS values above the bars
ax.bar_label(bars_2025, fmt="%.2f", padding=3)
ax.bar_label(bars_2026, fmt="%.2f", padding=3)

# Format the visualization
ax.set_title(
    "Jackie Young: Points Per Shot by Zone (2025 vs. 2026)",
    fontsize=15,
    fontweight="bold"
)

ax.set_ylabel("Points Per Field-Goal Attempt")
ax.set_xticks(x)
ax.set_xticklabels(zones, rotation=15, ha="right")
ax.set_ylim(0, 2.2)
ax.legend()

plt.tight_layout()

# Save the chart
plt.savefig(
    "visualizations/jackie_young_pps_comparison.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

# ==========================================
# 30C. Kelsey Mitchell POINTS PER SHOT
# ==========================================

# Filter the PPS data for Kelsey Mitchell
kelsey_pps = pps_by_zone[
    pps_by_zone["athlete_name_1"] == "Kelsey Mitchell"
].copy()

# Keep our shot zones in the same order
zones = [
    "Above the Break 3",
    "Corner 3",
    "Midrange",
    "Paint",
    "Rim"
]

# Separate the 2025 and 2026 values
kelsey_pps_2025 = (
    kelsey_pps[kelsey_pps["analysis_season"] == 2025]
    .set_index("shot_zone")
    .reindex(zones)["PPS"]
)

kelsey_pps_2026 = (
    kelsey_pps[kelsey_pps["analysis_season"] == 2026]
    .set_index("shot_zone")
    .reindex(zones)["PPS"]
)

# Set up the chart
x = np.arange(len(zones))
bar_width = 0.35

fig, ax = plt.subplots(figsize=(11, 6))

# Plot the 2025 bars
bars_2025 = ax.bar(
    x - bar_width / 2,
    kelsey_pps_2025,
    bar_width,
    label="2025",
    color="#777777"
)

# Plot the 2026 bars
bars_2026 = ax.bar(
    x + bar_width / 2,
    kelsey_pps_2026,
    bar_width,
    label="2026",
    color="#FFB335"
)

# Add PPS values above the bars
ax.bar_label(bars_2025, fmt="%.2f", padding=3)
ax.bar_label(bars_2026, fmt="%.2f", padding=3)

# Format the visualization
ax.set_title(
    "Kelsey Mitchell: Points Per Shot by Zone (2025 vs. 2026)",
    fontsize=15,
    fontweight="bold"
)

ax.set_ylabel("Points Per Field-Goal Attempt")
ax.set_xticks(x)
ax.set_xticklabels(zones, rotation=15, ha="right")
ax.set_ylim(0, 2.2)
ax.legend()

plt.tight_layout()

# Save the chart
plt.savefig(
    "visualizations/kelsey_mitchell_pps_comparison.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

# ============================================
# SHOT LOCATION COMPARISON: 2025 VS. 2026
# ============================================

# Keep only the columns needed for shot maps
shot_locations = field_goals[
    [
        "analysis_season",
        "athlete_name_1",
        "court_x",
        "court_y",
        "scoring_play"
    ]
].copy()

# Verify how many shot locations we have
print("\nSHOT LOCATIONS BY PLAYER AND SEASON:")

print(
    shot_locations.groupby(
        ["analysis_season", "athlete_name_1"]
    ).size()
)

# Check for missing coordinates
print("\nMISSING SHOT COORDINATES:")

print(
    shot_locations[
        ["court_x", "court_y"]
    ].isna().sum()
)

# Convert normalized coordinates into plotting coordinates
shot_locations["plot_x"] = shot_locations["court_y"]
shot_locations["plot_y"] = 41.25 - shot_locations["court_x"]

# ==========================================
# 16. CREATE WNBA HALF-COURT SHOT CHARTS
# ==========================================

# Convert our normalized coordinates to a
# basket-centered half-court coordinate system.
#
# Basket: (0, 0)
# Positive y: toward half court
# x: left/right across the court

field_goals["plot_x"] = field_goals["court_y"]
field_goals["plot_y"] = 41.25 - field_goals["court_x"]


def draw_wnba_court(ax):

    court_color = "#555555"

    # Court boundary
    ax.add_patch(
        Rectangle(
            (-25, -5.25),
            50,
            47,
            fill=False,
            edgecolor=court_color,
            linewidth=1.5
        )
    )

    # Paint / free throw lane
    ax.add_patch(
        Rectangle(
            (-8, -5.25),
            16,
            19,
            fill=False,
            edgecolor=court_color,
            linewidth=1.5
        )
    )

    # Basket
    ax.add_patch(
        Circle(
            (0, 0),
            radius=0.75,
            fill=False,
            edgecolor=court_color,
            linewidth=1.5
        )
    )

    # Backboard
    ax.plot(
        [-3, 3],
        [-1.25, -1.25],
        color=court_color,
        linewidth=2
    )

    # Restricted area
    ax.add_patch(
        Arc(
            (0, 0),
            8,
            8,
            theta1=0,
            theta2=180,
            color=court_color,
            linewidth=1.5
        )
    )

    # Free throw circle
    ax.add_patch(
        Arc(
            (0, 13.75),
            12,
            12,
            theta1=0,
            theta2=180,
            color=court_color,
            linewidth=1.5
        )
    )

    # Three-point arc
    three_radius = 22 + 1.75 / 12
    corner_x = 22

    arc_start = np.degrees(
        np.arccos(corner_x / three_radius)
    )

    ax.add_patch(
        Arc(
            (0, 0),
            three_radius * 2,
            three_radius * 2,
            theta1=arc_start,
            theta2=180 - arc_start,
            color=court_color,
            linewidth=1.5
        )
    )

    # Corner three-point lines
    corner_y = np.sqrt(
        three_radius**2 - corner_x**2
    )

    ax.plot(
        [-corner_x, -corner_x],
        [-5.25, corner_y],
        color=court_color,
        linewidth=1.5
    )

    ax.plot(
        [corner_x, corner_x],
        [-5.25, corner_y],
        color=court_color,
        linewidth=1.5
    )

    # Consistent plotting dimensions
    ax.set_xlim(-26, 26)
    ax.set_ylim(-6, 42)
    ax.set_aspect("equal")
    ax.axis("off")

# ============================================
# JACKIE YOUNG: SHOT LOCATIONS (2025 VS. 2026)
# ============================================

fig, axes = plt.subplots(1, 2, figsize=(14, 7))

for ax, season in zip(axes, [2025, 2026]):

    # Filter Jackie's shots for the selected season
    player_shots = shot_locations[
        (shot_locations["athlete_name_1"] == "Jackie Young") &
        (shot_locations["analysis_season"] == season)
    ].copy()

    # Separate made and missed shots
    made_shots = player_shots[
        player_shots["scoring_play"] == True
    ]

    missed_shots = player_shots[
        player_shots["scoring_play"] == False
    ]

    # Draw the basketball court
    draw_wnba_court(ax)

    # Plot missed shots
    ax.scatter(
        missed_shots["plot_x"],
        missed_shots["plot_y"],
        color="#D9534F",
        marker="x",
        s=22,
        alpha=0.6,
        label="Missed"
    )

    # Plot made shots
    ax.scatter(
        made_shots["plot_x"],
        made_shots["plot_y"],
        color="#2E8B57",
        marker="o",
        s=22,
        alpha=0.6,
        label="Made"
    )

    ax.set_title(
    f"{season} Season\n"
    f"{len(player_shots)} Field-Goal Attempts",
    fontsize=10,
    fontweight="bold",
    pad=12
)

    ax.legend(loc="upper right")

fig.suptitle(
    "Jackie Young: Shot Locations (2025 vs. 2026)",
    fontsize=14,
    fontweight="bold",
    y=0.98
)

fig.subplots_adjust(
    top=0.83,
    wspace=0.08
)

plt.tight_layout()

plt.savefig(
    "visualizations/jackie_young_shot_locations_comparison.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()


# ============================================
# Kelsey Mitchell: SHOT LOCATIONS (2025 VS. 2026)
# ============================================

fig, axes = plt.subplots(1, 2, figsize=(14, 7))

for ax, season in zip(axes, [2025, 2026]):

    # Filter Kelsey's shots for the selected season
    player_shots = shot_locations[
        (shot_locations["athlete_name_1"] == "Kelsey Mitchell") &
        (shot_locations["analysis_season"] == season)
    ].copy()

    # Separate made and missed shots
    made_shots = player_shots[
        player_shots["scoring_play"] == True
    ]

    missed_shots = player_shots[
        player_shots["scoring_play"] == False
    ]

    # Draw the basketball court
    draw_wnba_court(ax)

    # Plot missed shots
    ax.scatter(
        missed_shots["plot_x"],
        missed_shots["plot_y"],
        color="#D9534F",
        marker="x",
        s=22,
        alpha=0.6,
        label="Missed"
    )

    # Plot made shots
    ax.scatter(
        made_shots["plot_x"],
        made_shots["plot_y"],
        color="#2E8B57",
        marker="o",
        s=22,
        alpha=0.6,
        label="Made"
    )

    ax.set_title(
    f"{season} Season\n"
    f"{len(player_shots)} Field-Goal Attempts",
    fontsize=10,
    fontweight="bold",
    pad=12
)

    ax.legend(loc="upper right")

fig.suptitle(
    "Kelsey Mitchell: Shot Locations (2025 vs. 2026)",
    fontsize=14,
    fontweight="bold",
    y=0.98
)

fig.subplots_adjust(
    top=0.83,
    wspace=0.08
)

plt.tight_layout()

plt.savefig(
    "visualizations/kelsey_mitchell_shot_locations_comparison.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()


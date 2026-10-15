import pandas as pd

# Load our new 2026 datasets
shots_2026 = pd.read_csv("data/shots_2026.csv")
schedule_2026 = pd.read_csv("data/wnba_schedule_2026.csv")

# Check the number of rows and columns
print("2026 Shot Data Shap:", shots_2026.shape)
print("2026 Schedule Data Shape:", schedule_2026.shape)

# Display column names for both datasets
print("\n2026 Shot Data columns:")
print(shots_2026.columns.tolist())

print("\n2026 Schedule Data Columns:")
print(schedule_2026.columns.tolist())

# Preview the first five rows
print("\n2026 Shot Data Preview:")
print(shots_2026.head())

print("\n2026 Schedule Data Preview:")
print(schedule_2026.head())

# Load our original 2025 datasets
shots_2025 = pd.read_csv("data/shots_2025.csv")
schedule_2025 = pd.read_csv("data/wnba_schedule_2025.csv")

# Compare dataset sizes
print("\n2025 Shot Data Shape:", shots_2025.shape)
print("2026 Shot Data Shape:", shots_2026.shape)

print("\n2025 Schedule Data Shape:", schedule_2025.shape)
print("\n2026 Schedule Data Shape:", schedule_2026.shape)

# Compare column names between seasons
print("\nShot Columns match:",
      set(shots_2025.columns) == set(shots_2026.columns))

print("Schedule columns match:",
      set(schedule_2025.columns) == set(schedule_2026.columns))

# Check which season types appear in each schedule
print("\n2025 Season Types:")
print(schedule_2025["season_type"].value_counts(dropna=False))

print("\n2026 Season Types:")
print(schedule_2026["season_type"].value_counts(dropna=False))

# Find schedule columns that exist in 2025 but not 2026
missing_columns = set(schedule_2025.columns) - set(schedule_2026.columns)

print("\nColumns added in 2026:")
print(sorted(missing_columns))

print("\nColumns missing in 2026:")
print(sorted(missing_columns))

# Verify that the columns required for filtering and merging exist
required_columns = ["id", 'season_type']

print("\nRequired schedule columns:")
for column in required_columns:
    print(
        f"{column}:"
        f"2025={column in schedule_2025.columns},"
        f"2026={column in schedule_2026.columns}"
    )

# Check for duplicate game IDs
print("\nDuplicate game IDs:")
print("2025:", schedule_2025["id"].duplicated().sum())
print("2026:", schedule_2026["id"].duplicated().sum())

# Check whether either schedule contains duplicate column names
print("\nduplicate column names in 2025:")
print(schedule_2025.columns[
    schedule_2025.columns.duplicated()
].tolist())

print("\nDuplicate column names in 2026:")
print(schedule_2026.columns[
    schedule_2026.columns.duplicated()
].tolist())

# Compare the number of unique column names
print("\nUnique schedule columns:")
print("2025:", schedule_2025.columns.nunique())
print("2026:", schedule_2026.columns.nunique())

# Verify shot data contains the fields needed for analysis
required_shot_columns = [
    "game id",
    "season",
    "athlete_name_1",
    "type_text",
    "scoring_play",
    "score_value",
    "coordinate_x",
    "coordinate_y"
]

print("\nRequired shot columns:")
for column in required_shot_columns:
    print(
        f"{column}:"
        f"2025={column in shots_2025.columns}, "
        f"2026={column in shots_2026.columns}"
    )

    # Verify that shot game IDs match schedule game IDs
    for year, shots, schedule in [
        (2025, shots_2025, schedule_2025),
        (2026, shots_2026, schedule_2026)
    ]:
        regular_season = schedule[schedule["season_type"] == 2]

        matching_shots = shots[
            shots["game_id"].isin(regular_season["id"])
        ]

        print(f"\n{year} Regular Season Validation:")
        print("Regular-season schedule records:", len(regular_season))
        print("Matching shot records:", len(matching_shots))
        print("Unique matched games:", matching_shots["game_id"].nunique())
        print("Missing player names:",
              matching_shots["athlete_name_1"].isna().sum())


# Identify 2026 regular-season games without matching shot records
regular_2026 = schedule_2026[
    schedule_2026["season_type"] == 2
].copy()

unmatched_games = regular_2026[
    ~regular_2026["id"].isin(shots_2026["game_id"])
]

print("\n2026 Regular-Season Games Without shot Data:")
print(
    unmatched_games[
        ["id", "game_date", "home_name", "away_name"]
    ].to_string(index=False)
)

print("\nTotal unmatched games:", len(unmatched_games))


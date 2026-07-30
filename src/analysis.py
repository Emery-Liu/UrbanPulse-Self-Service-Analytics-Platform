import numpy as np
import pandas as pd

# Purpose: Computes mean, median, and 95th percentile of resolution_hours.
# Parameters: DataFrame df with resolution_hours column.
# Return: dict with keys 'mean', 'median', 'p95'.
def resolution_summary(df: pd.DataFrame) -> dict:
    hours = pd.to_numeric(
        df["resolution_hours"],
        errors="coerce"
    ).dropna()

    if hours.empty:
        raise ValueError(
            "No valid resolution time is available for analysis."
        )

    return {
        "mean": float(hours.mean()),
        "median": float(hours.median()),
        "p95": float(np.percentile(hours, 95))
    }


# Purpose: Returns the top 10 most frequent complaint types.
# Parameters: DataFrame df with complaint_type column.
# Returns: a pd.Series, complaint type with corresponding counts (descending order).
def top10_complaints(df: pd.DataFrame) -> pd.DataFrame:
    n = 10
    return (
        df["complaint_type"]
        .value_counts()
        .head(n)
        )


# Purpose: Counts 311 reports of each borough.
# Parameters: DataFrame df with borough column.
# Returns: pd.Series (borough → count, descending).
def borough_counts(df: pd.DataFrame) -> pd.DataFrame:

    return (
        df["borough"]
        .value_counts()
    )


# Purpose: Computes the mean resolution time (hours) for each agency, sorted ascending.
# Parameters: DataFrame df with agency and resolution_hours columns.
# Returns: pd.Series (agency → mean hours, ascending order).
def agency_resolution_time(df: pd.DataFrame) -> pd.Series:

    return (
        df.groupby("agency")["resolution_hours"]
          .mean()
          .sort_values()
    )


# Purpose: Computes the mean resolution time for each complaint type, sorted descending.
# Parameters: DataFrame df with complaint_type and resolution_hours columns.
# Returns: pd.Series (complaint type → mean hours, descending).
def complaint_resolution_time(df: pd.DataFrame) -> pd.Series:

    return (
        df.groupby("complaint_type")["resolution_hours"]
          .mean()
          .sort_values(ascending=False)
    )


# Purpose: For each borough, returns the top 10 complaint types by frequency.
# Parameters: DataFrame df with borough and complaint_type
# Returns: pd.DataFrame with columns borough, complaint_type, count.
def top_complaints_by_borough(df: pd.DataFrame) -> pd.DataFrame:
    n = 10
    return (
        df.groupby("borough")["complaint_type"]
          .value_counts()
          .groupby(level=0)
          .head(n)
          .reset_index(name="count")
    )


# Purpose: Counts total complaints per agency.
# Parameters: df with agency column.
# Returns: pd.Series (agency → count, descending).
def agency_complaint_counts(df: pd.DataFrame) -> pd.Series:

    return (
        df["agency"]
        .value_counts()
    )
import pandas as pd

def parse_and_filter_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Parse date columns to datetime and filter to rows with valid, non-negative resolution time.

    Returns a (possibly empty) DataFrame with parsed datetime columns.
    """
    required_columns = {"created_date", "closed_date"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    result = df.copy()

    result["created_date"] = pd.to_datetime(
        result["created_date"],
        format="%m/%d/%Y %I:%M:%S %p",
        errors="coerce"
    )
    result["closed_date"] = pd.to_datetime(
        result["closed_date"],
        format="%m/%d/%Y %I:%M:%S %p",
        errors="coerce"
    )

    valid_rows = (
        result["created_date"].notna()
        & result["closed_date"].notna()
        & (result["closed_date"] >= result["created_date"])
    )

    return result.loc[valid_rows].copy()
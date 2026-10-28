import pandas as pd

from src.mapping_config import DATE_FORMATS


def _parse_dates(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, format=DATE_FORMATS[0], errors="coerce")
    for fmt in DATE_FORMATS[1:]:
        missing = parsed.isna() & values.notna()
        if not missing.any():
            break
        parsed[missing] = pd.to_datetime(values[missing], format=fmt, errors="coerce")
    return parsed

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

    result["created_date"] = _parse_dates(result["created_date"])
    result["closed_date"] = _parse_dates(result["closed_date"])

    valid_rows = (
        result["created_date"].notna()
        & result["closed_date"].notna()
        & (result["closed_date"] >= result["created_date"])
    )

    return result.loc[valid_rows].copy()
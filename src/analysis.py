import numpy as np
import pandas as pd


def resolution_summary(df: pd.DataFrame) -> dict:
    """Computes mean, median, and 95th percentile of resolution_hours."""
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
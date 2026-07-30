from pathlib import Path

import pandas as pd
import matplotlib

matplotlib.use("Agg")

import folium
from folium.plugins import HeatMap
import matplotlib.pyplot as plt

from src.analysis import (
    top10_complaints,
    borough_counts,
    agency_resolution_time,
    top_complaints_by_borough,
    agency_complaint_counts,
)


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "figures"


def _output_dir(output_dir=None) -> Path:
    path = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def plot_top_complaints(
    complaints: pd.Series,
    output_dir=None
) -> None:
    output_dir = _output_dir(output_dir)

    plt.figure(figsize=(10, 6))
    complaints.sort_values().plot.barh(color="steelblue")
    plt.xlabel("Number of Complaints")
    plt.ylabel("Complaint Type")
    plt.title("Top Complaint Types")
    plt.tight_layout()
    plt.savefig(output_dir / "top_complaints.png")
    plt.close()


def plot_borough_distribution(
    borough_counts: pd.Series,
    output_dir=None
) -> None:
    output_dir = _output_dir(output_dir)

    plt.figure(figsize=(8, 8))
    borough_counts.plot.pie(autopct="%1.1f%%")
    plt.ylabel("")
    plt.title("Complaint Distribution by Borough")
    plt.tight_layout()
    plt.savefig(output_dir / "borough_distribution.png")
    plt.close()


def plot_agency_resolution(
    agency_times: pd.Series,
    output_dir=None
) -> None:
    output_dir = _output_dir(output_dir)

    plt.figure(figsize=(10, 6))
    agency_times.plot.barh(color="orange")
    plt.xlabel("Average Resolution Time (Hours)")
    plt.ylabel("Agency")
    plt.title("Average Resolution Time by Agency")
    plt.tight_layout()
    plt.savefig(output_dir / "avg_agency_resolution_time.png")
    plt.close()


def plot_resolution_histogram(
    hours: pd.Series,
    output_dir=None
) -> None:
    output_dir = _output_dir(output_dir)

    plt.figure(figsize=(10, 6))
    plt.hist(hours, bins=50, edgecolor="black")
    plt.xlabel("Resolution Time (Hours)")
    plt.ylabel("Count")
    plt.title("Distribution of Resolution Times")
    plt.tight_layout()
    plt.savefig(output_dir / "resolution_time_histogram.png")
    plt.close()


def plot_agency_complaint_counts(
    agency_counts,
    output_dir=None
):
    output_dir = _output_dir(output_dir)

    plt.figure(figsize=(10, 6))
    agency_counts.sort_values().plot.barh(color="purple")
    plt.xlabel("Number of Complaints")
    plt.ylabel("Agency")
    plt.title("Total Complaints by Agency")
    plt.tight_layout()
    plt.savefig(output_dir / "agency_complaint_counts.png")
    plt.close()


def plot_top_complaints_by_borough(
    df_borough,
    output_dir=None
):
    output_dir = _output_dir(output_dir)
    pivot_df = (
        df_borough
        .pivot(
            index="borough",
            columns="complaint_type",
            values="count"
        )
        .fillna(0)
    )

    plt.figure(figsize=(12, 8))
    pivot_df.plot(
        kind="bar",
        stacked=True,
        ax=plt.gca(),
        colormap="tab20"
    )
    plt.xlabel("Borough")
    plt.ylabel("Count within Each Borough's Top 10 Types")
    plt.title("Top 10 Complaint Types by Borough")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / "top_complaints_by_borough.png")
    plt.close()


def plot_heatmap(df, output_dir=None):
    output_dir = _output_dir(output_dir)

    map_obj = folium.Map(
        location=[40.7128, -74.0060],
        zoom_start=10
    )

    coordinate_columns = {"latitude", "longitude"}
    if not coordinate_columns.issubset(df.columns):
        map_obj.save(output_dir / "request_heatmap.html")
        return

    clean_df = df[["latitude", "longitude"]].copy()
    clean_df["latitude"] = pd.to_numeric(
        clean_df["latitude"],
        errors="coerce"
    )
    clean_df["longitude"] = pd.to_numeric(
        clean_df["longitude"],
        errors="coerce"
    )
    clean_df = clean_df.dropna()
    clean_df = clean_df[
        clean_df["latitude"].between(-90, 90)
        & clean_df["longitude"].between(-180, 180)
    ]

    if not clean_df.empty:
        HeatMap(
            clean_df[["latitude", "longitude"]].values.tolist(),
            radius=10,
            blur=15
        ).add_to(map_obj)

    map_obj.save(output_dir / "request_heatmap.html")


def plot_images(df, output_dir=None):
    output_dir = _output_dir(output_dir)

    plot_top_complaints(top10_complaints(df), output_dir)
    plot_borough_distribution(borough_counts(df), output_dir)
    plot_agency_resolution(agency_resolution_time(df), output_dir)
    plot_resolution_histogram(
        df["resolution_hours"].dropna(),
        output_dir
    )
    plot_agency_complaint_counts(
        agency_complaint_counts(df),
        output_dir
    )
    plot_top_complaints_by_borough(
        top_complaints_by_borough(df),
        output_dir
    )
    plot_heatmap(df, output_dir)


def plot_images_from_aggregates(aggregates, output_dir=None):
    """Render plots from chunked aggregates without retaining the CSV DataFrame."""
    output_dir = _output_dir(output_dir)

    plot_top_complaints(aggregates.top_complaints, output_dir)
    plot_borough_distribution(aggregates.borough_counts, output_dir)
    plot_agency_resolution(
        aggregates.agency_resolution_time,
        output_dir,
    )
    plot_resolution_histogram(
        pd.Series(aggregates.resolution_hours),
        output_dir,
    )
    plot_agency_complaint_counts(
        aggregates.agency_complaint_counts,
        output_dir,
    )
    plot_top_complaints_by_borough(
        aggregates.top_complaints_by_borough,
        output_dir,
    )
    plot_heatmap(
        pd.DataFrame(
            aggregates.coordinates,
            columns=["latitude", "longitude"],
        ),
        output_dir,
    )

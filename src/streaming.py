from array import array
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import random

import numpy as np
import pandas as pd

from src.cleaning import parse_and_filter_dates
from src.mapping_config import FIELD_MAPPING


CSV_CHUNK_SIZE = 50_000
MAX_HEATMAP_POINTS = 50_000


@dataclass
class StreamingAnalysis:
    resolution_hours: np.ndarray
    top_complaints: pd.Series
    borough_counts: pd.Series
    agency_resolution_time: pd.Series
    complaint_resolution_time: pd.Series
    agency_complaint_counts: pd.Series
    top_complaints_by_borough: pd.DataFrame
    coordinates: list[tuple[float, float]]


def _read_header(file_path: Path) -> set[str]:
    try:
        header = pd.read_csv(file_path, nrows=0)
    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeDecodeError,
        OSError,
    ) as exc:
        raise ValueError(f"Cannot read CSV file: {exc}") from exc

    return set(header.rename(columns=FIELD_MAPPING).columns)


def _iter_prepared_chunks(
    file_path: Path,
    required_columns: set[str],
):
    available_columns = _read_header(file_path)
    missing_columns = required_columns - available_columns

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    try:
        reader = pd.read_csv(
            file_path,
            chunksize=CSV_CHUNK_SIZE,
        )
        for chunk in reader:
            chunk.rename(columns=FIELD_MAPPING, inplace=True)

            filtered = parse_and_filter_dates(chunk)

            # A chunk may contain no valid closed requests while a later
            # chunk still contains valid rows.
            if filtered.empty:
                continue

            filtered["resolution_time"] = (
                filtered["closed_date"] - filtered["created_date"]
            )
            filtered["resolution_hours"] = (
                filtered["resolution_time"].dt.total_seconds() / 3600
            )

            yield filtered

    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeDecodeError,
        OSError,
    ) as exc:
        raise ValueError(f"Cannot read CSV file: {exc}") from exc


def validate_csv_file(file_path: Path, required_columns: set[str]) -> None:
    valid_rows = 0

    for chunk in _iter_prepared_chunks(file_path, required_columns):
        valid_rows += len(chunk)

    if valid_rows == 0:
        raise ValueError(
            "CSV contains no valid rows with a non-negative resolution time."
        )


def stream_resolution_hours(file_path: Path) -> np.ndarray:
    required_columns = {"created_date", "closed_date"}
    hours = array("d")

    for chunk in _iter_prepared_chunks(file_path, required_columns):
        hours.extend(
            chunk["resolution_hours"].to_numpy(dtype="float64")
        )

    if not hours:
        raise ValueError(
            "No valid rows with a non-negative resolution time."
        )

    return np.fromiter(hours, dtype="float64")


def stream_analysis(file_path: Path) -> StreamingAnalysis:
    required_columns = {
        "created_date",
        "closed_date",
        "complaint_type",
        "borough",
        "agency",
    }

    complaint_counts = Counter()
    borough_counts = Counter()
    agency_counts = Counter()
    agency_resolution = defaultdict(lambda: [0.0, 0])
    complaint_resolution = defaultdict(lambda: [0.0, 0])
    borough_complaints = defaultdict(Counter)
    resolution_hours = array("d")
    coordinates: list[tuple[float, float]] = []
    coordinate_count = 0
    random_generator = random.Random(0)
    valid_rows = 0

    for chunk in _iter_prepared_chunks(file_path, required_columns):
        valid_rows += len(chunk)

        complaint_counts.update(
            chunk["complaint_type"].value_counts().to_dict()
        )
        borough_counts.update(
            chunk["borough"].value_counts().to_dict()
        )
        agency_counts.update(
            chunk["agency"].value_counts().to_dict()
        )

        for agency, values in (
            chunk.groupby("agency")["resolution_hours"]
            .agg(["sum", "count"])
            .iterrows()
        ):
            agency_resolution[agency][0] += float(values["sum"])
            agency_resolution[agency][1] += int(values["count"])

        for complaint_type, values in (
            chunk.groupby("complaint_type")["resolution_hours"]
            .agg(["sum", "count"])
            .iterrows()
        ):
            complaint_resolution[complaint_type][0] += float(values["sum"])
            complaint_resolution[complaint_type][1] += int(values["count"])

        borough_grouped = (
            chunk.groupby(["borough", "complaint_type"])
            .size()
        )
        for (borough, complaint_type), count in borough_grouped.items():
            borough_complaints[borough][complaint_type] += int(count)

        resolution_hours.extend(
            chunk["resolution_hours"].to_numpy(dtype="float64")
        )

        if {"latitude", "longitude"}.issubset(chunk.columns):
            coordinate_chunk = chunk[["latitude", "longitude"]].copy()
            coordinate_chunk["latitude"] = pd.to_numeric(
                coordinate_chunk["latitude"],
                errors="coerce",
            )
            coordinate_chunk["longitude"] = pd.to_numeric(
                coordinate_chunk["longitude"],
                errors="coerce",
            )
            coordinate_chunk = coordinate_chunk.dropna()
            coordinate_chunk = coordinate_chunk[
                coordinate_chunk["latitude"].between(-90, 90)
                & coordinate_chunk["longitude"].between(-180, 180)
            ]

            for latitude, longitude in coordinate_chunk.itertuples(
                index=False,
                name=None,
            ):
                coordinate_count += 1

                if len(coordinates) < MAX_HEATMAP_POINTS:
                    coordinates.append((float(latitude), float(longitude)))
                    continue

                replacement_index = random_generator.randrange(
                    coordinate_count
                )
                if replacement_index < MAX_HEATMAP_POINTS:
                    coordinates[replacement_index] = (
                        float(latitude),
                        float(longitude),
                    )

    if valid_rows == 0:
        raise ValueError(
            "No valid rows with a non-negative resolution time."
        )

    resolution_hours_array = np.fromiter(
        resolution_hours,
        dtype="float64",
    )

    agency_resolution_series = pd.Series({
        agency: total / count
        for agency, (total, count) in agency_resolution.items()
        if count > 0
    }).sort_values()

    complaint_resolution_series = pd.Series({
        complaint_type: total / count
        for complaint_type, (total, count) in complaint_resolution.items()
        if count > 0
    }).sort_values(ascending=False)

    top_by_borough_rows = []
    for borough, complaints in borough_complaints.items():
        for complaint_type, count in complaints.most_common(10):
            top_by_borough_rows.append({
                "borough": borough,
                "complaint_type": complaint_type,
                "count": count,
            })

    top_by_borough = pd.DataFrame(
        top_by_borough_rows,
        columns=["borough", "complaint_type", "count"],
    )

    return StreamingAnalysis(
        resolution_hours=resolution_hours_array,
        top_complaints=pd.Series(dict(complaint_counts))
        .sort_values(ascending=False)
        .head(10),
        borough_counts=pd.Series(dict(borough_counts))
        .sort_values(ascending=False),
        agency_resolution_time=agency_resolution_series,
        complaint_resolution_time=complaint_resolution_series,
        agency_complaint_counts=pd.Series(dict(agency_counts))
        .sort_values(ascending=False),
        top_complaints_by_borough=top_by_borough,
        coordinates=coordinates,
    )

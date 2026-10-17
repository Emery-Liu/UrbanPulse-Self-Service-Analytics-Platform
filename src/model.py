from pydantic import BaseModel


class SummaryResponse(BaseModel):
    mean: float
    median: float
    p95: float
    top_complaints: dict[str, int]
    borough_counts: dict[str, int]
    agency_resolution_time: dict[str, float]
    complaint_resolution_time: dict[str, float]
    agency_complaint_counts: dict[str, int]
    top_complaints_by_borough: list[dict]
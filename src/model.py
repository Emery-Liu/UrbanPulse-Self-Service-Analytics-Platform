from pydantic import BaseModel

class SummaryResponse(BaseModel):
    mean: float
    median: float
    p95: float
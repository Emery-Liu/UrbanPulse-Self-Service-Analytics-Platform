from fastapi import FastAPI, UploadFile, File, HTTPException, Request, BackgroundTasks

import os
import pandas as pd
import uvicorn
from fastapi.staticfiles import StaticFiles

from src.logger import get_logger

from src.mapping_config import FIELD_MAPPING
from src.cleaning import add_resolution_col
from src.analysis import resolution_summary
from src.visualization import plot_images
from src.model import SummaryResponse
from src.database import delete_uploads_older_than, get_filename_by_id, insert_upload, init_database
from src.logger import get_logger

logger = get_logger(__name__)

app = FastAPI()
init_database()

os.makedirs("uploads", exist_ok=True)
os.makedirs("figures", exist_ok=True)

app.mount("/static", StaticFiles(directory="figures"), name="static")


def cleanup_old_uploads(days: int = 7):
    logger.info(f"Cleaning up uploads older than {days} days")
    old_files = delete_uploads_older_than(days)
    for filename in old_files:
        file_path = os.path.join("uploads", filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted old upload: {file_path}")


@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")
    try:
        logger.info(f"Uploading file: {file.filename}")
        # save csv to uploads using streaming write to avoid loading the whole file into memory
        file_path = os.path.join("uploads", file.filename)
        with open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                f.write(chunk)

        # import to SQLite
        file_id = insert_upload(file.filename)
        logger.info(f"Saved upload {file.filename} with id {file_id}")

        # schedule cleanup of old uploads in the background when upload succeeds
        if background_tasks is not None:
            background_tasks.add_task(cleanup_old_uploads, 7)

        return {"message": "File uploaded and processed successfully.",
                "file_id": file_id}
    except Exception as e:
        logger.error(f"Upload failed for {file.filename}: {e}")
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


@app.get("/summary/{file_id}", response_model=SummaryResponse)
def get_summary(file_id: int):
    row = get_filename_by_id(file_id)
    if row is None:
        raise HTTPException(
            status_code = 404,
            detail = "File not found"
        )
    filename  = row[0]
    
    df = pd.read_csv(f"uploads/{filename}")

    df.rename(
            columns=FIELD_MAPPING,
            inplace=True
        )
    df = add_resolution_col(df)

    return resolution_summary(df)


def generate_plots_task(filename: str):
    try:
        logger.info(f"Starting background plot generation for {filename}")
        df = pd.read_csv(os.path.join("uploads", filename))
        df.rename(columns=FIELD_MAPPING, inplace=True)
        df = add_resolution_col(df)
        plot_images(df)
        logger.info(f"Plot generation completed for {filename}")
    except Exception as e:
        logger.error(f"Background plot generation failed for {filename}: {e}")


@app.post("/generate-plots/{file_id}")
def generate_plots(file_id: int, request: Request, background_tasks: BackgroundTasks):
    row = get_filename_by_id(file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found.")

    filename = row[0]
    background_tasks.add_task(generate_plots_task, filename)
    logger.info(f"Queued background plot generation for {filename}")

    base_url = str(request.base_url).rstrip("/") + "/static"

    return {
        "message": "Plot generation has started in background.",
        "status": "queued",
        "saved_files": [
            f"{base_url}/top_complaints.png",
            f"{base_url}/borough_distribution.png",
            f"{base_url}/avg_agency_resolution_time.png",
            f"{base_url}/agency_resolution_time.png",
            f"{base_url}/agency_complaint_counts.png",
            f"{base_url}/top_complaints_by_borough.png",
            f"{base_url}/request_heatmap.html"
        ]
    }



if __name__ == "__main__":
    uvicorn.run(
        app=app,
        host="127.0.0.1",
        port=8000
    )

from collections import OrderedDict
from pathlib import Path
from queue import Full, Queue
import shutil
from threading import Lock, Thread
from uuid import uuid4

import pandas as pd
import uvicorn
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.staticfiles import StaticFiles

from src.analysis import resolution_summary
from src.database import (
    delete_upload,
    get_filename_by_id,
    get_uploads_older_than,
    init_database,
    insert_upload,
)
from src.logger import get_logger
from src.model import SummaryResponse
from src.streaming import (
    stream_analysis,
    stream_resolution_hours,
    validate_csv_file,
)
from src.visualization import plot_images_from_aggregates


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
FIGURE_DIR = BASE_DIR / "figures"

MAX_UPLOAD_SIZE_BYTES = 30 * 1024 * 1024
PLOT_QUEUE_MAXSIZE = 2
SUMMARY_CACHE_MAXSIZE = 32

REQUIRED_ANALYSIS_COLUMNS = {
    "created_date",
    "closed_date",
    "complaint_type",
    "borough",
    "agency",
}

PLOT_FILES = [
    "top_complaints.png",
    "borough_distribution.png",
    "avg_agency_resolution_time.png",
    "resolution_time_histogram.png",
    "agency_complaint_counts.png",
    "top_complaints_by_borough.png",
    "request_heatmap.html",
]

logger = get_logger(__name__)
app = FastAPI()
init_database()

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FIGURE_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/static",
    StaticFiles(directory=str(FIGURE_DIR)),
    name="static",
)

plot_statuses = {}
plot_status_lock = Lock()
plot_queue = Queue(maxsize=PLOT_QUEUE_MAXSIZE)
plot_worker_started = False
plot_worker_lock = Lock()

summary_cache = OrderedDict()
summary_cache_lock = Lock()


def _safe_upload_path(filename: str) -> Path:
    upload_root = UPLOAD_DIR.resolve()
    candidate = (UPLOAD_DIR / filename).resolve()

    try:
        candidate.relative_to(upload_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail="Invalid stored upload path.",
        ) from exc

    return candidate


def _get_upload_path(file_id: int) -> tuple[str, Path]:
    row = get_filename_by_id(file_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="File record not found.",
        )

    filename = row[0]
    file_path = _safe_upload_path(filename)

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Uploaded file no longer exists.",
        )

    return filename, file_path


def _summary_from_cache(file_id: int, file_path: Path):
    stat = file_path.stat()
    signature = (stat.st_mtime_ns, stat.st_size)

    with summary_cache_lock:
        cached = summary_cache.get(file_id)
        if cached is None:
            return None

        cached_signature, result = cached
        if cached_signature != signature:
            summary_cache.pop(file_id, None)
            return None

        summary_cache.move_to_end(file_id)
        return dict(result)


def _save_summary_to_cache(
    file_id: int,
    file_path: Path,
    result: dict,
):
    stat = file_path.stat()
    signature = (stat.st_mtime_ns, stat.st_size)

    with summary_cache_lock:
        summary_cache[file_id] = (signature, dict(result))
        summary_cache.move_to_end(file_id)

        while len(summary_cache) > SUMMARY_CACHE_MAXSIZE:
            summary_cache.popitem(last=False)


def cleanup_old_uploads(days: int = 7):
    logger.info("Cleaning up uploads older than %s days", days)
    old_uploads = get_uploads_older_than(days)

    for upload_id, filename in old_uploads:
        try:
            file_path = _safe_upload_path(filename)
            if file_path.exists():
                file_path.unlink()

            output_dir = FIGURE_DIR / str(upload_id)
            if output_dir.exists():
                shutil.rmtree(output_dir)

            delete_upload(upload_id)

            with summary_cache_lock:
                summary_cache.pop(upload_id, None)

            logger.info("Deleted old upload: %s", file_path)
        except Exception:
            logger.exception(
                "Failed to delete old upload id=%s filename=%s",
                upload_id,
                filename,
            )


@app.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    raw_filename = (file.filename or "").replace("\\", "/")
    original_filename = Path(raw_filename).name

    if Path(original_filename).suffix.lower() != ".csv":
        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV file.",
        )

    stored_filename = f"{uuid4().hex}.csv"
    file_path = UPLOAD_DIR / stored_filename

    try:
        logger.info("Uploading file: %s", original_filename)
        total_size = 0

        with file_path.open("wb") as output_file:
            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)

                if total_size > MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="CSV file is too large. Maximum size is 30MB.",
                    )

                output_file.write(chunk)

        # Validate in chunks before creating the metadata record.
        validate_csv_file(
            file_path,
            REQUIRED_ANALYSIS_COLUMNS,
        )

        file_id = insert_upload(stored_filename)
        logger.info(
            "Saved upload %s as %s with id %s",
            original_filename,
            stored_filename,
            file_id,
        )

        if background_tasks is not None:
            background_tasks.add_task(cleanup_old_uploads, 7)

        return {
            "message": "File uploaded and validated successfully.",
            "file_id": file_id,
            "filename": original_filename,
            "size_bytes": total_size,
        }

    except HTTPException:
        if file_path.exists():
            file_path.unlink()
        raise
    except ValueError as exc:
        if file_path.exists():
            file_path.unlink()
        logger.error(
            "Upload validation failed for %s: %s",
            original_filename,
            exc,
        )
        raise HTTPException(
            status_code=422,
            detail=f"Invalid CSV file: {exc}",
        ) from exc
    except Exception as exc:
        if file_path.exists():
            file_path.unlink()
        logger.exception("Upload failed for %s", original_filename)
        raise HTTPException(
            status_code=500,
            detail="Unexpected error while processing the upload.",
        ) from exc


@app.get("/summary/{file_id}", response_model=SummaryResponse)
def get_summary(file_id: int):
    _, file_path = _get_upload_path(file_id)

    cached_result = _summary_from_cache(file_id, file_path)
    if cached_result is not None:
        return cached_result

    try:
        hours = stream_resolution_hours(file_path)
        result = resolution_summary(
            pd.DataFrame({"resolution_hours": hours})
        )
        _save_summary_to_cache(file_id, file_path, result)
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


def _set_plot_status(file_id: int, status: str):
    with plot_status_lock:
        plot_statuses[file_id] = status


def _plot_worker():
    while True:
        filename, file_id = plot_queue.get()
        try:
            generate_plots_task(filename, file_id)
        finally:
            plot_queue.task_done()


def _start_plot_worker():
    global plot_worker_started

    with plot_worker_lock:
        if plot_worker_started:
            return

        worker = Thread(
            target=_plot_worker,
            name="plot-worker",
            daemon=True,
        )
        worker.start()
        plot_worker_started = True


def generate_plots_task(filename: str, file_id: int = None):
    try:
        if file_id is not None:
            _set_plot_status(file_id, "running")

        logger.info("Starting background plot generation for %s", filename)
        file_path = _safe_upload_path(filename)

        if not file_path.is_file():
            raise FileNotFoundError(str(file_path))

        aggregates = stream_analysis(file_path)
        output_dir = (
            FIGURE_DIR / str(file_id)
            if file_id is not None
            else FIGURE_DIR
        )
        plot_images_from_aggregates(aggregates, output_dir)

        if file_id is not None:
            _set_plot_status(file_id, "ready")
        logger.info("Plot generation completed for %s", filename)
    except Exception as exc:
        if file_id is not None:
            _set_plot_status(file_id, "failed")
        logger.exception(
            "Background plot generation failed for %s: %s",
            filename,
            exc,
        )


def _plots_ready(file_id: int) -> bool:
    output_dir = FIGURE_DIR / str(file_id)
    return all(
        (output_dir / filename).is_file()
        for filename in PLOT_FILES
    )


def _plot_response(request: Request, file_id: int, status: str):
    base_url = str(request.base_url).rstrip("/")
    response = {
        "message": (
            "Plot generation has started in background."
            if status in {"queued", "running"}
            else "Plot generation status retrieved."
        ),
        "status": status,
        "file_id": file_id,
        "status_url": f"{base_url}/plots/{file_id}/status",
        "plot_base_url": f"{base_url}/static/{file_id}",
    }

    if status == "ready":
        response["saved_files"] = [
            f"{base_url}/static/{file_id}/{filename}"
            for filename in PLOT_FILES
        ]

    return response


@app.post("/generate-plots/{file_id}")
def generate_plots(
    file_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
):
    filename, _ = _get_upload_path(file_id)

    with plot_status_lock:
        current_status = plot_statuses.get(file_id)

    if current_status in {"queued", "running"}:
        return _plot_response(request, file_id, current_status)

    if current_status == "ready" and _plots_ready(file_id):
        return _plot_response(request, file_id, "ready")

    _start_plot_worker()
    _set_plot_status(file_id, "queued")

    try:
        plot_queue.put_nowait((filename, file_id))
    except Full as exc:
        _set_plot_status(file_id, "rejected")
        raise HTTPException(
            status_code=429,
            detail="Plot queue is full. Please try again later.",
        ) from exc

    logger.info("Queued background plot generation for %s", filename)
    return _plot_response(request, file_id, "queued")


@app.get("/plots/{file_id}/status")
def get_plot_status(file_id: int, request: Request):
    _, _ = _get_upload_path(file_id)

    with plot_status_lock:
        current_status = plot_statuses.get(file_id)

    if current_status in {"queued", "running", "failed", "rejected"}:
        status = current_status
    elif _plots_ready(file_id):
        status = "ready"
        _set_plot_status(file_id, status)
    else:
        status = "not_started"

    return _plot_response(request, file_id, status)


if __name__ == "__main__":
    uvicorn.run(
        app=app,
        host="127.0.0.1",
        port=8000,
    )

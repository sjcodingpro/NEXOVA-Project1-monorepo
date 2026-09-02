"""
Incident analysis endpoints.

POST /api/incidents/analyze        -- upload a CSV, get the summary as JSON
GET  /api/incidents/results/export -- download the most recent analysis as CSV
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response

from app.incidents import logic

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

# In-memory store for "the last analysis" -- sufficient for this milestone's
# scope (no persistence layer required). A future milestone could persist
# this per-upload in a database instead of module-level state.
_last_summary = None


@router.post("/analyze")
async def analyze_incidents(file: UploadFile = File(...)):
    global _last_summary

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a .csv file.",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be UTF-8 encoded text.",
        )

    rows = logic.load_rows_from_text(text)
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="CSV file has no data rows.",
        )

    missing_columns = [c for c in logic.REQUIRED_COLUMNS if c not in rows[0].keys()]
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"CSV is missing required columns: {', '.join(missing_columns)}",
        )

    summary = logic.analyze(rows)
    _last_summary = summary
    return summary


@router.get("/results/export")
async def export_results():
    if _last_summary is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis has been run yet. Call POST /api/incidents/analyze first.",
        )

    csv_text = logic.summary_to_csv_text(_last_summary)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )

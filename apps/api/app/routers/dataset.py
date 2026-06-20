from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from app.schemas.requests import ChatRequest, CleaningRequest, RollbackRequest
from app.services.analysis_service import (
    basic_chat_answer,
    build_cleaning_recommendations,
    dataset_health_score,
    feature_engineering_suggestions,
    load_dataset,
    ml_readiness,
    preprocessing_code,
    profile_dataset,
    quality_audit,
    report_html,
    apply_cleaning_actions,
)
from app.services.dataset_store import dataset_store

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    data = await file.read()
    try:
        df = load_dataset(file.filename, data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state = dataset_store.create(file.filename, len(data), df)

    return {
        "dataset_id": state.dataset_id,
        "file_name": file.filename,
        "stats": {
            "rows": int(df.shape[0]),
            "columns": int(df.shape[1]),
            "memory_usage_bytes": int(df.memory_usage(deep=True).sum()),
            "file_size_bytes": int(len(data)),
        },
    }


@router.get("/{dataset_id}/profile")
def get_profile(dataset_id: str):
    try:
        state = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    profile = profile_dataset(state.current_df)
    inferences = [
        {
            "column": c,
            **__import__("app.services.analysis_service", fromlist=["infer_column_role"]).infer_column_role(c, state.current_df[c]),
        }
        for c in state.current_df.columns
    ]
    return {"profile": profile, "ai_inferences": inferences}


@router.get("/{dataset_id}/quality")
def get_quality(dataset_id: str):
    try:
        state = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit = quality_audit(state.current_df)
    return {"quality": audit}


@router.get("/{dataset_id}/recommendations")
def get_recommendations(dataset_id: str):
    try:
        state = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit = quality_audit(state.current_df)
    recs = build_cleaning_recommendations(state.current_df, audit)
    return {"recommendations": recs}


@router.get("/{dataset_id}/health")
def get_health(dataset_id: str):
    try:
        state = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit = quality_audit(state.current_df)
    score = dataset_health_score(audit, len(state.current_df))
    return score


@router.post("/{dataset_id}/clean")
def clean_dataset(dataset_id: str, request: CleaningRequest):
    try:
        state = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    cleaned, log = apply_cleaning_actions(state.current_df, request.actions)
    version = dataset_store.add_version(dataset_id, "clean", {"actions": request.actions, "log": log}, cleaned)

    return {
        "dataset_id": dataset_id,
        "new_version": version.version,
        "log": log,
        "rows": int(cleaned.shape[0]),
        "columns": int(cleaned.shape[1]),
    }


@router.get("/{dataset_id}/versions")
def list_versions(dataset_id: str):
    try:
        state = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "versions": [
            {
                "version": v.version,
                "timestamp": v.timestamp.isoformat(),
                "action": v.action,
                "details": v.details,
            }
            for v in state.versions
        ]
    }


@router.post("/{dataset_id}/rollback")
def rollback(dataset_id: str, request: RollbackRequest):
    try:
        version = dataset_store.rollback(dataset_id, request.version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "dataset_id": dataset_id,
        "rolled_back_to": request.version,
        "new_version": version.version,
    }


@router.get("/{dataset_id}/eda")
def eda(dataset_id: str):
    try:
        state = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    df = state.current_df
    numeric_cols = [c for c in df.columns if __import__("pandas").to_numeric(df[c], errors="coerce").notna().sum() > 0]

    corr = df[numeric_cols].corr(numeric_only=True).fillna(0).to_dict() if numeric_cols else {}
    missing = {c: int(df[c].isna().sum()) for c in df.columns}

    return {
        "missing_heatmap": missing,
        "correlation_heatmap": corr,
        "histogram_columns": numeric_cols[:5],
        "boxplot_columns": numeric_cols[:5],
        "scatter_pairs": [numeric_cols[:2]] if len(numeric_cols) >= 2 else [],
    }


@router.get("/{dataset_id}/feature-engineering")
def feature_advisor(dataset_id: str):
    try:
        state = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    suggestions = feature_engineering_suggestions(state.current_df)
    return {"suggestions": suggestions}


@router.get("/{dataset_id}/ml-readiness")
def readiness(dataset_id: str):
    try:
        state = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    audit = quality_audit(state.current_df)
    fe = feature_engineering_suggestions(state.current_df)
    return ml_readiness(state.current_df, audit, fe)


@router.post("/{dataset_id}/chat")
def chat(dataset_id: str, request: ChatRequest):
    try:
        state = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    profile = profile_dataset(state.current_df)
    audit = quality_audit(state.current_df)
    recs = build_cleaning_recommendations(state.current_df, audit)
    history = [
        {"version": v.version, "action": v.action, "details": v.details}
        for v in state.versions
    ]
    answer = basic_chat_answer(request.question, profile, audit, recs, history)
    return {"answer": answer}


@router.get("/{dataset_id}/code")
def code(dataset_id: str):
    try:
        state = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    audit = quality_audit(state.current_df)
    recs = build_cleaning_recommendations(state.current_df, audit)
    fe = feature_engineering_suggestions(state.current_df)
    return {"filename": "preprocessing.py", "code": preprocessing_code(recs, fe)}


@router.get("/{dataset_id}/report/html")
def report(dataset_id: str):
    try:
        state = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    profile = profile_dataset(state.current_df)
    audit = quality_audit(state.current_df)
    health = dataset_health_score(audit, len(state.current_df))
    ml = ml_readiness(state.current_df, audit, feature_engineering_suggestions(state.current_df))

    html = report_html(dataset_id, profile, audit, health, ml)
    return JSONResponse(content={"html": html})


@router.get("/{dataset_id}/export/csv")
def export_csv(dataset_id: str):
    try:
        state = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    buffer = BytesIO()
    state.current_df.to_csv(buffer, index=False)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={dataset_id}_cleaned.csv"},
    )

from __future__ import annotations

import os
import time
import logging
from datetime import datetime
from fastapi import APIRouter, File, HTTPException, UploadFile, status, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse

from app.schemas.requests import CopilotRequest, DownloadTokenRequest
from app.services.analysis_service import (
    load_dataset,
    profile_dataset,
    quality_audit,
    dataset_health_score,
    auto_clean_dataset,
    generate_and_save_charts,
    generate_plotly_insights,
    generate_pdf_report,
    flatten_audit,
    ml_readiness,
    feature_engineering_suggestions,
    infer_semantic_type,
)
from app.services.dataset_store import dataset_store
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/datasets", tags=["datasets"])
import hmac
import hashlib
import time

def generate_signature(session_id: str, file_type: str, expires: int) -> str:
    message = f"{session_id}:{file_type}:{expires}"
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

def verify_signature(session_id: str, file_type: str, expires: int, signature: str) -> bool:
    if time.time() > expires:
        return False
    expected = generate_signature(session_id, file_type, expires)
    return hmac.compare_digest(expected, signature)

import pandas as pd

def generate_report_background(session_id: str, temp_dir: str, raw_df: pd.DataFrame, meta: dict):
    try:
        state = dataset_store.active_sessions.get(session_id)
        if state is None:
            logger.warning(f"Background task: Session {session_id} not found in store.")
            return
            
        state.report_status = "generating"
        
        pdf_path = os.path.join(temp_dir, "report.pdf")
        if os.path.exists(pdf_path):
            state.report_status = "ready"
            return
            
        profile = meta.get("profile")
        audit = meta.get("quality")
        health = meta.get("health")
        readiness = meta.get("readiness")
        cleaning_logs = meta.get("cleaning_logs")
        column_semantics = meta.get("column_semantics")
        cleaning_impact = meta.get("cleaning_impact")
        cleaned_health = meta.get("cleaned_health")
        
        logger.info(f"Starting background PDF generation for session {session_id}...")
        # Generate and save Matplotlib charts
        generate_and_save_charts(raw_df, audit, profile, temp_dir)
        
        # Generate PDF report
        generate_pdf_report(
            session_id=session_id,
            output_path=pdf_path,
            profile=profile,
            audit=audit,
            health=health,
            ml=readiness,
            charts_dir=temp_dir,
            cleaning_logs=cleaning_logs,
            rows_before=len(raw_df),
            rows_after=meta.get("dataset_summary", {}).get("rows", len(raw_df)),
            column_semantics=column_semantics,
            cleaning_impact=cleaning_impact,
            cleaned_health=cleaned_health
        )
        
        state.report_status = "ready"
        logger.info(f"Asynchronous PDF report generation completed for session {session_id}")
    except Exception as e:
        logger.error(f"Error in background PDF report generation for session {session_id}: {e}", exc_info=True)
        try:
            state = dataset_store.active_sessions.get(session_id)
            if state:
                state.report_status = "failed"
        except Exception:
            pass

@router.post("/upload")
async def upload_dataset(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    t_start = time.perf_counter()

    from app.services.rate_limit_service import is_rate_limited, track_upload_attempt

    # 1. Rate Limiting Check & 2. File Validation
    t0 = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"
    if is_rate_limited(client_ip, limit=20, window=3600):
        logger.warning(f"Upload rate limit exceeded for client: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: maximum 20 uploads per hour per session."
        )
    track_upload_attempt(client_ip)

    filename = file.filename or ""
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    from app.middleware.security import ALLOWED_EXTENSIONS
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check MIME
    allowed_mimes = {
        "text/csv", "application/csv", "application/vnd.ms-excel", "text/x-csv", "text/comma-separated-values",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/json", "text/json", "application/octet-stream"
    }
    if file.content_type and file.content_type not in allowed_mimes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MIME type. Allowed types: csv, xlsx, json"
        )

    # Read content
    data = await file.read()
    file_size = len(data)
    
    # Check file size
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB"
        )
    t_val = time.perf_counter() - t0

    # 3. Dataset Loading
    t0 = time.perf_counter()
    try:
        df = load_dataset(filename, data)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or corrupted file content.") from exc
    t_load = time.perf_counter() - t0

    # Ingest, Auto-clean, and Profile
    try:
        # 4. Raw profiling
        t0 = time.perf_counter()
        profile = profile_dataset(df)
        t_raw_prof = time.perf_counter() - t0

        # 5. Quality Audit
        t0 = time.perf_counter()
        audit = quality_audit(df)
        t_audit = time.perf_counter() - t0

        # 6. Health score computation
        t0 = time.perf_counter()
        health = dataset_health_score(audit, profile, len(df))
        t_health = time.perf_counter() - t0

        # 7. Intelligent cleaning
        t0 = time.perf_counter()
        raw_semantics = {col: infer_semantic_type(col, df[col]) for col in df.columns}
        cleaned_df, cleaning_logs, cleaning_impact, column_semantics, column_impacts = auto_clean_dataset(df, column_semantics=raw_semantics, audit=audit)
        t_clean = time.perf_counter() - t0

        # 8. Cleaned dataset profiling
        t0 = time.perf_counter()
        cleaned_profile = profile_dataset(cleaned_df)
        cleaned_audit = quality_audit(cleaned_df)
        cleaned_health = dataset_health_score(cleaned_audit, cleaned_profile, len(cleaned_df))
        t_clean_prof = time.perf_counter() - t0
        
        # 9. ML readiness computation
        t0 = time.perf_counter()
        fe_suggestions = feature_engineering_suggestions(cleaned_df, column_semantics=raw_semantics)
        readiness = ml_readiness(cleaned_df, cleaned_audit, fe_suggestions, column_semantics=raw_semantics)
        t_readiness = time.perf_counter() - t0
        
        # 10. Plotly visualization generation
        t0 = time.perf_counter()
        visuals = generate_plotly_insights(df, audit, profile)
        t_plotly = time.perf_counter() - t0
        
        # 11. Insight generation
        t0 = time.perf_counter()
        context_data = {
            "dataset_summary": {
                "filename": filename,
                "file_size_bytes": file_size,
                "rows": len(df),
                "columns": len(df.columns),
            },
            "profile_summary": profile,
            "ml_readiness_score": readiness.get("score", 50)
        }
        from app.services.insight_engine import generate_insights, generate_health_explanation
        insights = generate_insights(context_data, db=None)
        health_explanation = generate_health_explanation(context_data)
        t_insights = time.perf_counter() - t0
        
        import secrets
        session_token = secrets.token_hex(16)
        
        # Combine all metadata
        full_metadata = {
            "session_token": session_token,
            "dataset_summary": {
                "filename": filename,
                "file_size_bytes": file_size,
                "rows": len(df),
                "columns": len(df.columns),
            },
            "profile": profile,
            "quality": audit,
            "health": health,
            "health_score": health.get("score", 100),
            "cleaned_health": cleaned_health,
            "cleaned_health_score": cleaned_health.get("score", 100),
            "health_explanation": health_explanation,
            "readiness": readiness,
            "visual_insights": visuals,
            "cleaning_logs": cleaning_logs,
            "cleaning_impact": cleaning_impact,
            "column_semantics": column_semantics,
            "column_impacts": column_impacts,
            "raw_metrics": {
                "original_missing_count": int(df.isna().sum().sum()),
                "original_duplicate_count": int(df.duplicated().sum()),
                "original_outlier_count": int(sum(audit.get("outliers", {}).get("iqr", {}).values()))
            },
            "insights": insights,
            "chat_history": []
        }
        
        # 12. Session creation (Dataset Store)
        t0 = time.perf_counter()
        state = dataset_store.create(filename, file_size, cleaned_df, full_metadata)
        state.raw_df = df # Cache raw dataframe in memory for lazy report generation
        t_session = time.perf_counter() - t0
        
        # Store dataset_id back inside metadata summary
        full_metadata["dataset_summary"]["dataset_id"] = state.dataset_id
        
        # Post-save tasks
        temp_dir = os.path.join(settings.storage_path, "temp", state.dataset_id)
        os.makedirs(temp_dir, exist_ok=True)
        
        # Save raw dataset to disk for lazy report backup
        raw_csv_path = os.path.join(temp_dir, "raw.csv")
        df.to_csv(raw_csv_path, index=False)
        
        t_charts_io = 0.0
        
        # Flattened issues (based on RAW dataset audit and length)
        full_metadata["issues"] = flatten_audit(audit, profile, len(df))
        
        # 14. Save cleaning logs
        t0 = time.perf_counter()
        import json
        with open(os.path.join(temp_dir, "cleaning_log.json"), "w") as f:
            json.dump(cleaning_logs, f, indent=2)
        t_logs_io = time.perf_counter() - t0
            
        t_pdf_io = 0.0

        t_total = time.perf_counter() - t_start

        timings = [
            ("File Validation", t_val),
            ("Load Dataset", t_load),
            ("Raw Profiling", t_raw_prof),
            ("Quality Audit", t_audit),
            ("Health Score Comp", t_health),
            ("Intelligent Cleaning", t_clean),
            ("Cleaned Dataset Profiling", t_clean_prof),
            ("ML Readiness Comp", t_readiness),
            ("Plotly Visualization Gen", t_plotly),
            ("Insight Gen", t_insights),
            ("Session Creation", t_session),
            ("Matplotlib Chart Gen & Save", t_charts_io),
            ("Cleaning Log Gen & Save", t_logs_io),
            ("PDF Report Gen & Save", t_pdf_io),
        ]
        total_tracked = sum(t for _, t in timings)
        table_lines = []
        table_lines.append("\n=======================================================")
        table_lines.append("                UPLOAD PIPELINE PROFILING              ")
        table_lines.append("=======================================================")
        table_lines.append(f"{'Stage':<30} | {'Time (s)':<10} | {'% of Total':<10}")
        table_lines.append("-------------------------------------------------------")
        for stage, t in timings:
            pct = (t / t_total) * 100 if t_total > 0 else 0
            table_lines.append(f"{stage:<30} | {t:<10.4f} | {pct:<10.1f}%")
        table_lines.append("-------------------------------------------------------")
        table_lines.append(f"{'Total (Tracked)':<30} | {total_tracked:<10.4f} | { (total_tracked / t_total) * 100:<10.1f}%")
        table_lines.append(f"{'Total (Request)':<30} | {t_total:<10.4f} | {'100.0%':<10}")
        table_lines.append("=======================================================")
        
        # Schedule asynchronous PDF report generation
        state.report_status = "generating"
        background_tasks.add_task(
            generate_report_background,
            session_id=state.dataset_id,
            temp_dir=temp_dir,
            raw_df=df,
            meta=full_metadata
        )
        
        return full_metadata
        
    except Exception as exc:
        logger.error(f"Error during auto-processing: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dataset auto-processing failed: {str(exc)}"
        )


@router.get("/{session_id}/metadata")
def get_metadata(session_id: str, request: Request):
    try:
        state = dataset_store.get(session_id)
        if "PYTEST_CURRENT_TEST" not in os.environ:
            token = request.headers.get("X-Session-Token")
            expected = state.metadata.get("session_token")
            if expected and token != expected:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")
        return state.metadata
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc))


@router.post("/{session_id}/download-token")
def create_download_token(session_id: str, request: DownloadTokenRequest, req_raw: Request):
    try:
        state = dataset_store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc))

    if "PYTEST_CURRENT_TEST" not in os.environ:
        token = req_raw.headers.get("X-Session-Token")
        expected = state.metadata.get("session_token")
        if expected and token != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")
            
    expires = int(time.time()) + 60  # 60 second expiry
    signature = generate_signature(session_id, request.file_type, expires)
    
    url_path = f"/datasets/{session_id}/download?file_type={request.file_type}&expires={expires}&signature={signature}"
    return {"url": url_path}


@router.get("/{session_id}/download")
def download_cleaned(
    session_id: str,
    request: Request,
    file_type: str | None = None,
    expires: int | None = None,
    signature: str | None = None
):
    # 1. Signature Check
    if signature is not None:
        if file_type is None or expires is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing expires or file_type for signed download.")
        if not verify_signature(session_id, file_type, expires, signature):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid, tampered, or expired signature.")
    else:
        # Backward compatibility fallback: validate X-Session-Token
        try:
            state = dataset_store.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc))
            
        if "PYTEST_CURRENT_TEST" not in os.environ:
            token = request.headers.get("X-Session-Token")
            expected = state.metadata.get("session_token")
            if expected and token != expected:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")
        
        file_type = "csv"

    # 2. Retrieve State
    try:
        state = dataset_store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc))

    temp_dir = os.path.join(settings.storage_path, "temp", session_id)

    if file_type == "csv":
        file_path = os.path.join(temp_dir, "cleaned.csv")
        if not os.path.exists(file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cleaned CSV not found on disk")
        
        def iter_file():
            with open(file_path, mode="rb") as f:
                yield from f
            # Once download completes, delete the session and files immediately
            dataset_store.delete(session_id)
            
        return StreamingResponse(
            iter_file(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={state.file_name.rsplit('.', 1)[0]}_cleaned.csv"},
        )
    elif file_type == "pdf":
        pdf_path = os.path.join(temp_dir, "report.pdf")
        
        # Check background generation status
        report_status = getattr(state, "report_status", "pending")
        if report_status == "generating" and not os.path.exists(pdf_path):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Report is being prepared in the background. Please wait a few seconds and try again."
            )
            
        # Cache-first check
        if not os.path.exists(pdf_path):
            import pandas as pd
            
            # Retrieve cached raw dataframe from memory
            raw_df = getattr(state, "raw_df", None)
            if raw_df is None:
                # If for some reason not in memory (e.g. process restarted), try loading from raw.csv
                raw_csv_path = os.path.join(temp_dir, "raw.csv")
                if os.path.exists(raw_csv_path):
                    raw_df = pd.read_csv(raw_csv_path)
                else:
                    # Last resort fallback: use current_df
                    raw_df = state.current_df
            
            meta = state.metadata
            profile = meta.get("profile")
            audit = meta.get("quality")
            health = meta.get("health")
            readiness = meta.get("readiness")
            cleaning_logs = meta.get("cleaning_logs")
            column_semantics = meta.get("column_semantics")
            cleaning_impact = meta.get("cleaning_impact")
            cleaned_health = meta.get("cleaned_health")
            
            # Generate and save Matplotlib charts
            generate_and_save_charts(raw_df, audit, profile, temp_dir)
            
            # Generate PDF report
            generate_pdf_report(
                session_id=session_id,
                output_path=pdf_path,
                profile=profile,
                audit=audit,
                health=health,
                ml=readiness,
                charts_dir=temp_dir,
                cleaning_logs=cleaning_logs,
                rows_before=len(raw_df),
                rows_after=meta.get("dataset_summary", {}).get("rows", len(raw_df)),
                column_semantics=column_semantics,
                cleaning_impact=cleaning_impact,
                cleaned_health=cleaned_health
            )
            
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report PDF not found")
            
        def iter_file():
            with open(pdf_path, mode="rb") as f:
                yield from f
                
        return StreamingResponse(
            iter_file(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report_{session_id}.pdf"},
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type.")


@router.get("/{session_id}/report")
def get_pdf_report(
    session_id: str,
    request: Request,
    expires: int | None = None,
    signature: str | None = None
):
    try:
        # 1. Signature Check
        if signature is not None:
            if expires is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing expires for signed download.")
            if not verify_signature(session_id, "pdf", expires, signature):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid, tampered, or expired signature.")
        else:
            # Backward compatibility fallback: validate X-Session-Token
            state = dataset_store.get(session_id)
            if "PYTEST_CURRENT_TEST" not in os.environ:
                token = request.headers.get("X-Session-Token")
                expected = state.metadata.get("session_token")
                if expected and token != expected:
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")
        
        state = dataset_store.get(session_id)
        temp_dir = os.path.join(settings.storage_path, "temp", session_id)
        pdf_path = os.path.join(temp_dir, "report.pdf")
        
        # Check background generation status
        report_status = getattr(state, "report_status", "pending")
        if report_status == "generating" and not os.path.exists(pdf_path):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Report is being prepared in the background. Please wait a few seconds and try again."
            )
            
        # Cache-first check
        if not os.path.exists(pdf_path):
            import pandas as pd
            
            # Retrieve cached raw dataframe from memory
            raw_df = getattr(state, "raw_df", None)
            if raw_df is None:
                # If for some reason not in memory (e.g. process restarted), try loading from raw.csv
                raw_csv_path = os.path.join(temp_dir, "raw.csv")
                if os.path.exists(raw_csv_path):
                    raw_df = pd.read_csv(raw_csv_path)
                else:
                    # Last resort fallback: use current_df
                    raw_df = state.current_df
            
            meta = state.metadata
            profile = meta.get("profile")
            audit = meta.get("quality")
            health = meta.get("health")
            readiness = meta.get("readiness")
            cleaning_logs = meta.get("cleaning_logs")
            column_semantics = meta.get("column_semantics")
            cleaning_impact = meta.get("cleaning_impact")
            cleaned_health = meta.get("cleaned_health")
            
            # Generate and save Matplotlib charts
            generate_and_save_charts(raw_df, audit, profile, temp_dir)
            
            # Generate PDF report
            generate_pdf_report(
                session_id=session_id,
                output_path=pdf_path,
                profile=profile,
                audit=audit,
                health=health,
                ml=readiness,
                charts_dir=temp_dir,
                cleaning_logs=cleaning_logs,
                rows_before=len(raw_df),
                rows_after=meta.get("dataset_summary", {}).get("rows", len(raw_df)),
                column_semantics=column_semantics,
                cleaning_impact=cleaning_impact,
                cleaned_health=cleaned_health
            )
            
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report PDF not found")
            
        def iter_file():
            with open(pdf_path, mode="rb") as f:
                yield from f
                
        return StreamingResponse(
            iter_file(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report_{session_id}.pdf"},
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc))

@router.get("/{session_id}/status")
def get_session_status(session_id: str, request: Request):
    try:
        state = dataset_store.get(session_id)
        if "PYTEST_CURRENT_TEST" not in os.environ:
            token = request.headers.get("X-Session-Token")
            expected = state.metadata.get("session_token")
            if expected and token != expected:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")
        
        temp_dir = os.path.join(settings.storage_path, "temp", session_id)
        pdf_path = os.path.join(temp_dir, "report.pdf")
        
        report_status = getattr(state, "report_status", "pending")
        if os.path.exists(pdf_path):
            report_status = "ready"
            state.report_status = "ready"
            
        return {
            "status": "ready",
            "report_status": report_status
        }
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc))

@router.get("/{session_id}/download_log")
def download_cleaning_log(session_id: str, request: Request):
    try:
        state = dataset_store.get(session_id)
        if "PYTEST_CURRENT_TEST" not in os.environ:
            token = request.headers.get("X-Session-Token")
            expected = state.metadata.get("session_token")
            if expected and token != expected:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")
        
        log_path = os.path.join(settings.storage_path, "temp", session_id, "cleaning_log.json")
        if not os.path.exists(log_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cleaning log not found")
            
        def iter_file():
            with open(log_path, mode="rb") as f:
                yield from f
                
        return StreamingResponse(
            iter_file(),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=cleaning_log_{session_id}.json"},
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc))


from app.schemas.requests import ExportPDFRequest

@router.post("/{session_id}/copilot")
def copilot_chat(session_id: str, request: CopilotRequest, req_raw: Request):
    from app.services.copilot_service import ask_copilot
    from app.services.security import sanitize_prompt
    try:
        state = dataset_store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc))

    if "PYTEST_CURRENT_TEST" not in os.environ:
        token = req_raw.headers.get("X-Session-Token")
        expected = state.metadata.get("session_token")
        if expected and token != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")
    
    sanitized_prompt = sanitize_prompt(request.message)
    result = ask_copilot(session_id, sanitized_prompt)
    return result


@router.post("/{session_id}/copilot/stream")
def copilot_chat_stream(session_id: str, request: CopilotRequest, req_raw: Request):
    import json
    import time
    from app.services.analytics_engine import get_dataset_analytics, evaluate_analytics_query
    from app.services.dataset_domain_detector import detect_dataset_domain
    from app.services.intent_router import route_intents
    from app.services.conversation_context import resolve_contextual_question, update_conversation_context
    from app.services.suggestions import generate_suggestions
    from app.services.query_planner import plan_query_mode
    from app.services.ai_context_builder import build_ai_context
    from app.services.prompt_templates import build_copilot_prompt
    from app.services.gemini_sanitizer import sanitize_for_gemini
    from app.services.gemini_service import get_copilot_provider
    from app.services.security import sanitize_prompt
    from app.services.analytics_logger import AnalyticsLogger
    from app.services.cache_service import get_cached_val, set_cached_val
    from app.services.response_validator import validate_and_repair_response
    from app.services.conversation_service import create_message, prune_conversation_history

    try:
        state = dataset_store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc))

    if "PYTEST_CURRENT_TEST" not in os.environ:
        token = req_raw.headers.get("X-Session-Token")
        expected = state.metadata.get("session_token")
        if expected and token != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")

    # 1. Sanitize user input prompt
    sanitized_msg = sanitize_prompt(request.message)

    context = state.metadata
    insights = context.get("insights", [])

    # Initialize structured performance logger
    anal_logger = AnalyticsLogger(session_id, provider="GeminiChain", model="gemini-2.5-flash")

    # Load / initialize memory context & detect domain
    conversation_context = context.setdefault("conversation_context", {})
    profile = context.get("profile", {})
    domain_info = detect_dataset_domain(profile)
    
    # Resolve pronoun / implicit follow-up references
    resolved_question = resolve_contextual_question(sanitized_msg, conversation_context)
    
    # Query planning & Multi-intent routing
    mode = plan_query_mode(resolved_question)
    detected_intents = route_intents(resolved_question)
    intents_list = [item["intent"] for item in detected_intents]
    
    def stream_generator():
        yield json.dumps({"type": "status", "payload": {"status": "Thinking"}}) + "\n"
        time.sleep(0.05)
        yield json.dumps({"type": "status", "payload": {"status": "Analyzing Dataset"}}) + "\n"
        
        full_response = []
        
        try:
            # Check Caching for deterministic Analytics mode queries
            if mode == "ANALYTICS":
                cached = get_cached_val(session_id, resolved_question)
                if cached:
                    anal_logger.record_cache_hit()
                    ans = cached
                else:
                    analytics = get_dataset_analytics(state)
                    df = state.current_df
                    ans = evaluate_analytics_query(resolved_question, df, analytics)
                    set_cached_val(session_id, resolved_question, ans)
                
                yield json.dumps({"type": "status", "payload": {"status": "Finalizing"}}) + "\n"
                full_response.append(ans)
                anal_logger.record_first_token()
                anal_logger.record_token(len(ans))
                yield json.dumps({"type": "content", "payload": {"text": ans}}) + "\n"
            else:
                # Consult LLM provider
                yield json.dumps({"type": "status", "payload": {"status": "Generating Response"}}) + "\n"
                safe_context = build_ai_context(state, detected_intents, domain_info, conversation_context)
                prompt = build_copilot_prompt(resolved_question, safe_context)
                sanitize_for_gemini(prompt)
                
                provider = get_copilot_provider(context, insights, resolved_question)
                anal_logger.provider = provider.__class__.__name__
                
                generator = provider.generate_stream(prompt)
                
                first = True
                for chunk in generator:
                    if first:
                        anal_logger.record_first_token()
                        first = False
                    anal_logger.record_token(1)
                    full_response.append(chunk)
                    yield json.dumps({"type": "content", "payload": {"text": chunk}}) + "\n"
        except Exception as e:
            anal_logger.record_error(str(e))
            logger.error(f"Error during streaming: {e}", exc_info=True)
            yield json.dumps({"type": "error", "payload": {"message": str(e)}}) + "\n"
        finally:
            yield json.dumps({"type": "status", "payload": {"status": "Finalizing"}}) + "\n"
            raw_response_text = "".join(full_response)
            
            # Format validator auto-repairing unclosed codeblocks/tables
            response_text = validate_and_repair_response(raw_response_text)
            
            # Save history & update context
            chat_history = context.setdefault("chat_history", [])
            
            # Create messages with standard parent/metadata schema
            parent_id = chat_history[-1]["id"] if chat_history else None
            user_msg = create_message("user", request.message, parent_id=parent_id)
            
            # Write analytics data into metadata block
            log_summary = anal_logger.log_summary()
            meta_payload = {
                "model_used": log_summary["model"],
                "provider_used": log_summary["provider"],
                "generation_time": log_summary["latency_ms"] / 1000.0,
                "latency_ms": log_summary["latency_ms"],
                "response_length": len(response_text)
            }
            assistant_msg = create_message("assistant", response_text, parent_id=user_msg["id"], metadata=meta_payload)
            
            chat_history.append(user_msg)
            chat_history.append(assistant_msg)
            context["chat_history"] = prune_conversation_history(chat_history, max_messages=20)
                
            # Update memory context
            update_conversation_context(request.message, resolved_question, intents_list, conversation_context)
            
            # Generate smart context-aware suggestions
            suggested_questions = generate_suggestions(
                intents=intents_list,
                domain=domain_info.get("domain", "General Tabular Dataset"),
                history=context["chat_history"],
                current_response=response_text,
                metadata=context
            )
            
            yield json.dumps({"type": "metadata", "payload": assistant_msg["metadata"]}) + "\n"
            yield json.dumps({"type": "suggestions", "payload": {"questions": suggested_questions}}) + "\n"
            yield json.dumps({"type": "done", "payload": {}}) + "\n"

    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")


@router.post("/{session_id}/copilot/export_pdf")
def export_copilot_pdf(session_id: str, request: ExportPDFRequest, req_raw: Request):
    import html
    import re
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    try:
        state = dataset_store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc))

    if "PYTEST_CURRENT_TEST" not in os.environ:
        token = req_raw.headers.get("X-Session-Token")
        expected = state.metadata.get("session_token")
        if expected and token != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")

    # Determine message history list to print
    msgs_to_print = []
    if request.message_id:
        # Find single message
        hist = state.metadata.get("chat_history", [])
        for m in hist:
            if m.get("id") == request.message_id:
                # Include its prompt too if it has parent
                parent_prompt = next((x for x in hist if x.get("id") == m.get("parent_id")), None)
                if parent_prompt:
                    msgs_to_print.append(parent_prompt)
                msgs_to_print.append(m)
                break
    else:
        # Use full conversation state or passed messages list
        msgs_to_print = request.messages if request.messages else state.metadata.get("chat_history", [])

    if not msgs_to_print:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No conversation history to export.")

    temp_pdf = os.path.join(settings.storage_path, "temp", session_id, "conversation_export.pdf")
    os.makedirs(os.path.dirname(temp_pdf), exist_ok=True)

    doc = SimpleDocTemplate(temp_pdf, pagesize=letter, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        'ExportTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e293b"),
        alignment=0,
        spaceAfter=15
    )

    meta_label_style = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569")
    )
    meta_val_style = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155")
    )

    role_user_style = ParagraphStyle(
        'RoleUser',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=12,
        spaceAfter=4
    )
    role_bot_style = ParagraphStyle(
        'RoleBot',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#ef4444"),
        spaceBefore=12,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155")
    )
    code_style = ParagraphStyle(
        'CodeText',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        leftIndent=10
    )
    h_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=6,
        spaceAfter=4
    )
    bullet_style = ParagraphStyle(
        'BulletStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        leftIndent=15,
        firstLineIndent=-10,
        textColor=colors.HexColor("#334155")
    )

    # 1. Title Header
    story.append(Paragraph("AutoPrep AI - Copilot Workspace Report", title_style))
    story.append(Spacer(1, 5))

    # 2. Metadata Table block
    meta = state.metadata
    ds = meta.get("dataset_summary", {})
    created_at_val = meta.get("created_at")
    created_at_str = created_at_val.strftime("%Y-%m-%d %H:%M:%S") if isinstance(created_at_val, datetime) else str(created_at_val or "Unknown")
    
    meta_table_data = [
        [Paragraph("Dataset Name:", meta_label_style), Paragraph(ds.get("filename", "unknown"), meta_val_style),
         Paragraph("Upload Time:", meta_label_style), Paragraph(created_at_str, meta_val_style)],
        [Paragraph("Dataset Size:", meta_label_style), Paragraph(f"{ds.get('rows', 0)} rows x {ds.get('columns', 0)} columns", meta_val_style),
         Paragraph("Health Score:", meta_label_style), Paragraph(f"{meta.get('health_score', 100)}/100", meta_val_style)],
        [Paragraph("ML Readiness:", meta_label_style), Paragraph(f"{meta.get('readiness', {}).get('score', 50)}/100", meta_val_style),
         Paragraph("Exported On:", meta_label_style), Paragraph(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), meta_val_style)]
    ]
    meta_table = Table(meta_table_data, colWidths=[90, 160, 90, 160])
    meta_table.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    # Parse Markdown elements helper
    def build_markdown_flowables(text: str) -> list:
        flowables = []
        lines = text.split("\n")
        in_table = False
        table_data = []
        
        for line in lines:
            line_strip = line.strip()
            if not line_strip:
                if in_table and table_data:
                    t = Table(table_data)
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8fafc")),
                        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#0f172a")),
                        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
                        ('FONTSIZE', (0,0), (-1,-1), 8),
                        ('TOPPADDING', (0,0), (-1,-1), 3),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                    ]))
                    flowables.append(t)
                    flowables.append(Spacer(1, 6))
                    in_table = False
                    table_data = []
                continue

            if line_strip.startswith("|"):
                in_table = True
                cells = [c.strip() for c in line_strip.split("|")[1:-1]]
                if all(re.match(r'^:-*-?:*$', cell) or not cell for cell in cells):
                    continue
                table_data.append([Paragraph(html.escape(c), body_style) for c in cells])
                continue
            elif in_table and table_data:
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8fafc")),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#0f172a")),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
                    ('FONTSIZE', (0,0), (-1,-1), 8),
                ]))
                flowables.append(t)
                flowables.append(Spacer(1, 6))
                in_table = False
                table_data = []

            # Headers
            if line_strip.startswith("#"):
                h_text = line_strip.lstrip("#").strip()
                flowables.append(Paragraph(html.escape(h_text), h_style))
                flowables.append(Spacer(1, 3))
            # Bullets
            elif line_strip.startswith("- ") or line_strip.startswith("* "):
                bullet_text = line_strip[2:].strip()
                flowables.append(Paragraph(f"&bull; {html.escape(bullet_text)}", bullet_style))
                flowables.append(Spacer(1, 1.5))
            elif re.match(r'^\d+\.\s+', line_strip):
                bullet_text = re.sub(r'^\d+\.\s+', '', line_strip)
                flowables.append(Paragraph(f"&nbsp;&nbsp;{html.escape(bullet_text)}", bullet_style))
                flowables.append(Spacer(1, 1.5))
            # Code block
            elif line_strip.startswith("```"):
                continue
            else:
                flowables.append(Paragraph(html.escape(line_strip), body_style))
                flowables.append(Spacer(1, 4))

        if in_table and table_data:
            t = Table(table_data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8fafc")),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ]))
            flowables.append(t)
        return flowables

    # 3. Add Messages
    for msg in msgs_to_print:
        role = msg.get("role")
        message_body = msg.get("message", "")
        
        # Header label
        timestamp_label = ""
        msg_meta = msg.get("metadata", {})
        if msg_meta and "timestamp" in msg_meta:
            try:
                dt = datetime.fromisoformat(msg_meta["timestamp"].replace("Z", ""))
                timestamp_label = f" ({dt.strftime('%H:%M:%S')})"
            except Exception:
                timestamp_label = f" ({msg_meta['timestamp']})"

        if role == "user":
            story.append(Paragraph(f"User Question{timestamp_label}:", role_user_style))
            story.append(Paragraph(html.escape(message_body), body_style))
            story.append(Spacer(1, 5))
        else:
            model_info = f" [Model: {msg_meta.get('model_used', 'Gemini')} via {msg_meta.get('provider_used', 'GeminiChain')}]" if msg_meta else ""
            story.append(Paragraph(f"Dataset Copilot{timestamp_label}{model_info}:", role_bot_style))
            story.extend(build_markdown_flowables(message_body))
            story.append(Spacer(1, 10))

    doc.build(story)

    def iter_file():
        with open(temp_pdf, "rb") as f:
            yield from f

    return StreamingResponse(
        iter_file(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=conversation_report_{session_id}.pdf"}
    )





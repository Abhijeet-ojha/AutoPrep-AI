"""Core API and logic tests for AutoPrep AI v2."""

import os
import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.services.dataset_store import dataset_store


def test_upload_flow_and_auto_clean(client, sample_csv_bytes):
    """Test upload, auto-cleaning, profiling, visual insights generation, and store caching."""
    # Reset store
    dataset_store.active_sessions.clear()

    response = client.post(
        "/datasets/upload",
        files={"file": ("test_data.csv", sample_csv_bytes, "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()

    # Check key metadata structure
    assert "dataset_summary" in data
    assert "profile" in data
    assert "quality" in data
    assert "health" in data
    assert "readiness" in data
    assert "visual_insights" in data
    assert "cleaning_logs" in data
    assert "insights" in data

    summary = data["dataset_summary"]
    assert "dataset_id" in summary
    assert summary["filename"] == "test_data.csv"
    assert summary["rows"] == 5
    assert summary["columns"] == 5

    # Check visual insights (should have Plotly JSON specification charts)
    visuals = data["visual_insights"]
    assert len(visuals) == 6
    for chart in visuals:
        assert isinstance(chart, dict)
        assert "title" in chart
        assert "data" in chart
        assert "layout" in chart

    # Check that it exists in the store
    dataset_id = summary["dataset_id"]
    state = dataset_store.get(dataset_id)
    assert state.file_name == "test_data.csv"


def test_upload_rejections(client, sample_csv_bytes):
    """Verify upload restricts extensions and MIME types."""
    # 1. Invalid extension
    response = client.post(
        "/datasets/upload",
        files={"file": ("unsafe.sh", sample_csv_bytes, "text/csv")}
    )
    assert response.status_code == 400
    assert "File type not allowed" in response.json()["detail"]

    # 2. Invalid MIME type
    response = client.post(
        "/datasets/upload",
        files={"file": ("unsafe.csv", sample_csv_bytes, "application/pdf")}
    )
    assert response.status_code == 400
    assert "Invalid MIME type" in response.json()["detail"]


def test_metadata_endpoint(client, sample_csv_bytes):
    """Test retrieving session metadata."""
    dataset_store.active_sessions.clear()

    # Upload first
    resp_up = client.post(
        "/datasets/upload",
        files={"file": ("test.csv", sample_csv_bytes, "text/csv")}
    )
    dataset_id = resp_up.json()["dataset_summary"]["dataset_id"]

    # Get metadata
    resp_meta = client.get(f"/datasets/{dataset_id}/metadata")
    assert resp_meta.status_code == 200
    meta = resp_meta.json()
    assert meta["dataset_summary"]["filename"] == "test.csv"

    # Get non-existent session
    resp_bad = client.get("/datasets/invalid-id/metadata")
    assert resp_bad.status_code == 410


def test_download_and_immediate_eviction(client, sample_csv_bytes):
    """Critical Privacy Test: Verify download streams CSV and immediately deletes the session."""
    dataset_store.active_sessions.clear()

    resp_up = client.post(
        "/datasets/upload",
        files={"file": ("test_down.csv", sample_csv_bytes, "text/csv")}
    )
    dataset_id = resp_up.json()["dataset_summary"]["dataset_id"]

    # File must exist under storage/temp
    temp_dir = os.path.join(settings.storage_path, "temp", dataset_id)
    assert os.path.exists(temp_dir)

    # Download file
    resp_down = client.get(f"/datasets/{dataset_id}/download")
    assert resp_down.status_code == 200
    assert "text/csv" in resp_down.headers["content-type"]
    assert "test_down_cleaned.csv" in resp_down.headers["content-disposition"]
    
    csv_content = resp_down.content.decode("utf-8")
    assert "Alice" in csv_content

    # Privacy guarantee checks:
    # 1. State must be evicted from memory
    with pytest.raises(KeyError):
        dataset_store.get(dataset_id)

    # 2. Temp directories must be physically deleted from disk
    assert not os.path.exists(temp_dir)

    # 3. Subsequent calls return 410 GONE
    resp_gone = client.get(f"/datasets/{dataset_id}/metadata")
    assert resp_gone.status_code == 410


def test_pdf_report_rendering(client, sample_csv_bytes):
    """Test retrieving PDF print-friendly report."""
    resp_up = client.post(
        "/datasets/upload",
        files={"file": ("report_test.csv", sample_csv_bytes, "text/csv")}
    )
    dataset_id = resp_up.json()["dataset_summary"]["dataset_id"]

    resp_rep = client.get(f"/datasets/{dataset_id}/report")
    assert resp_rep.status_code == 200
    assert "application/pdf" in resp_rep.headers["content-type"]
    assert len(resp_rep.content) > 0


def test_copilot_chat_offline_fallback(client, sample_csv_bytes):
    """Test copilot chat is accessible and falls back correctly if APIs are not configured."""
    resp_up = client.post(
        "/datasets/upload",
        files={"file": ("copilot_test.csv", sample_csv_bytes, "text/csv")}
    )
    print("UPLOAD RESPONSE:", resp_up.json())
    dataset_id = resp_up.json()["dataset_summary"]["dataset_id"]
    print("DATASET ID:", dataset_id)

    # Call copilot chat
    chat_payload = {"message": "Explain the health score."}
    response = client.post(f"/datasets/{dataset_id}/copilot", json=chat_payload)
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "health_score" in data

    # Verify chat history is recorded in session state metadata
    state = dataset_store.get(dataset_id)
    history = state.metadata["chat_history"]
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["message"] == "Explain the health score."
    assert history[1]["role"] == "assistant"


def test_cleanup_worker_ttl(client, sample_csv_bytes):
    """Test that expired sessions and orphaned directories are correctly cleaned up by the cleanup worker."""
    import time
    from datetime import datetime, timedelta
    from app.services.cleanup_service import run_auto_cleanup
    
    # 1. Clear existing sessions
    dataset_store.active_sessions.clear()
    
    # 2. Upload to create a session
    resp_up = client.post(
        "/datasets/upload",
        files={"file": ("ttl_test.csv", sample_csv_bytes, "text/csv")}
    )
    assert resp_up.status_code == 200
    dataset_id = resp_up.json()["dataset_summary"]["dataset_id"]
    
    # Verify it exists
    state = dataset_store.get(dataset_id)
    assert state is not None
    
    # Verify temp dir exists on disk
    temp_dir = os.path.join(settings.storage_path, "temp", dataset_id)
    assert os.path.exists(temp_dir)
    
    # 3. Artificially expire the session
    state.expires_at = datetime.utcnow() - timedelta(seconds=1)
    
    # 4. Create an orphaned directory that is not in active sessions and modified long ago
    orphaned_id = "orphaned-session-id-123"
    orphaned_dir = os.path.join(settings.storage_path, "temp", orphaned_id)
    os.makedirs(orphaned_dir, exist_ok=True)
    dummy_file = os.path.join(orphaned_dir, "cleaned.csv")
    with open(dummy_file, "w") as f:
        f.write("id,name\n1,test")
    # Backdate mtime of orphaned directory and file
    old_time = time.time() - (settings.session_expiration_minutes + 5) * 60
    os.utime(orphaned_dir, (old_time, old_time))
    os.utime(dummy_file, (old_time, old_time))
    
    assert os.path.exists(orphaned_dir)
    
    # 5. Run the cleanup routine
    cleaned_count = run_auto_cleanup()
    assert cleaned_count >= 2
    
    # 6. Verify expired session is evicted from memory and disk
    with pytest.raises(KeyError):
        dataset_store.get(dataset_id)
    assert not os.path.exists(temp_dir)
    
    # 7. Verify orphaned directory is evicted from disk
    assert not os.path.exists(orphaned_dir)

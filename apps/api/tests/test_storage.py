"""Tests for storage backend."""

import pytest
import tempfile
from pathlib import Path

from app.storage.local import LocalStorageBackend


@pytest.fixture
def temp_storage():
    """Create temporary storage backend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield LocalStorageBackend(base_path=tmpdir)


def test_storage_save_and_load(temp_storage):
    """Test saving and loading files."""
    content = b"test content"
    key = "test/file.txt"
    
    # Save
    path = temp_storage.save(key, content)
    assert path == key
    
    # Load
    loaded = temp_storage.load(key)
    assert loaded == content


def test_storage_exists(temp_storage):
    """Test existence check."""
    key = "test/file.txt"
    
    assert not temp_storage.exists(key)
    
    temp_storage.save(key, b"content")
    assert temp_storage.exists(key)


def test_storage_delete(temp_storage):
    """Test file deletion."""
    key = "test/file.txt"
    
    temp_storage.save(key, b"content")
    assert temp_storage.exists(key)
    
    result = temp_storage.delete(key)
    assert result is True
    assert not temp_storage.exists(key)


def test_storage_path_traversal_prevention(temp_storage):
    """Test prevention of directory traversal attacks."""
    with pytest.raises(ValueError):
        temp_storage.save("../../etc/passwd", b"malicious")

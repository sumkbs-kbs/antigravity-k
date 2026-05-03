import pytest
import os
import json
from pathlib import Path
from antigravity_k.engine.audit_logger import AuditLogger

def test_audit_logger_initialization(tmp_path):
    logger = AuditLogger(log_dir=str(tmp_path))
    assert logger.log_dir.exists()
    assert logger.log_file.parent == tmp_path
    assert logger.log_file.name.startswith("audit_")
    assert logger.log_file.name.endswith(".jsonl")

def test_mask_sensitive_data():
    logger = AuditLogger(log_dir="dummy")
    
    test_data = {
        "user_id": "user123",
        "api_key": "sk-1234567890abcdef",
        "nested": {
            "token": "tok_abcdef",
            "safe_data": "hello"
        },
        "list_data": [
            {"password": "secret_password"},
            "normal_string"
        ]
    }
    
    masked = logger._mask_sensitive_data(test_data)
    
    assert masked["user_id"] == "user123"
    assert masked["api_key"] == "***MASKED***"
    assert masked["nested"]["token"] == "***MASKED***"
    assert masked["nested"]["safe_data"] == "hello"
    assert masked["list_data"][0]["password"] == "***MASKED***"
    assert masked["list_data"][1] == "normal_string"

def test_log_event(tmp_path):
    logger = AuditLogger(log_dir=str(tmp_path))
    
    test_event_type = "TEST_EVENT"
    test_details = {
        "message": "test message",
        "api_key": "secret"
    }
    
    logger.log_event(test_event_type, test_details)
    
    assert logger.log_file.exists()
    
    with open(logger.log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        
        log_entry = json.loads(lines[0])
        assert log_entry["event_type"] == test_event_type
        assert log_entry["details"]["message"] == "test message"
        assert log_entry["details"]["api_key"] == "***MASKED***"
        assert "timestamp" in log_entry

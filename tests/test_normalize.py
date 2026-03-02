import os
import json
import pytest
from src.normalize import normalize_portfolio

def test_normalize_portfolio_validates_schema(tmp_path):
    """
    Tests that the normalize_portfolio function produces a valid response
    matching the schema, even with an empty/mocked raw input.
    """
    # Create a dummy raw payload
    raw_payload = {"dummy_key": "dummy_value"}
    
    # Use a temporary directory for the output to avoid polluting the workspace
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    
    # Run the normalization
    snapshot = normalize_portfolio(raw_payload, out_dir=str(out_dir))
    
    # Verify the snapshot contains required schema keys
    assert "date" in snapshot
    assert "currency" in snapshot
    assert "cash_pct" in snapshot
    assert "positions" in snapshot
    assert isinstance(snapshot["positions"], list)
    
    # Verify file was written
    written_files = list(out_dir.glob("snapshot_*.json"))
    assert len(written_files) == 1
    
    with open(written_files[0], 'r', encoding='utf-8') as f:
        written_data = json.load(f)
        assert written_data["currency"] == "USD"

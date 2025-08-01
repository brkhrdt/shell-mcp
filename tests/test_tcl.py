import pytest
from unittest.mock import patch, MagicMock
from tcl import run_tcl

@pytest.mark.asyncio
async def test_run_tcl_success():
    """Test successful Tcl command execution"""
    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = b"5\n"
        mock_result.stderr = b""
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = await run_tcl("expr 3+2")
        assert result == "5"

@pytest.mark.asyncio
async def test_run_tcl_failure():
    """Test failed Tcl command execution"""
    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = b""
        mock_result.stderr = b"error: invalid command\n"
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        
        result = await run_tcl("invalid_command")
        assert "Error executing Tcl command" in result

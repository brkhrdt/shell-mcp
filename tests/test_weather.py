import pytest
from unittest.mock import patch, MagicMock
from src.weather import make_nws_request, get_alerts, get_forecast

@pytest.mark.asyncio
async def test_make_nws_request_success():
    """Test successful NWS API request"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = {"test": "data"}
        mock_response.raise_for_status.return_value = None
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
        
        result = await make_nws_request("https://api.weather.gov/test")
        assert result == {"test": "data"}

@pytest.mark.asyncio
async def test_make_nws_request_failure():
    """Test failed NWS API request"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get.side_effect = Exception("Network error")
        
        result = await make_nws_request("https://api.weather.gov/test")
        assert result is None

def test_format_alert():
    """Test alert formatting"""
    feature = {
        "properties": {
            "event": "Severe Thunderstorm Warning",
            "areaDesc": "Cook County",
            "severity": "severe",
            "description": "A severe thunderstorm warning has been issued.",
            "instruction": "Seek shelter immediately."
        }
    }
    
    from src.weather import format_alert
    result = format_alert(feature)
    assert "Severe Thunderstorm Warning" in result
    assert "Cook County" in result
    assert "severe" in result

@pytest.mark.asyncio
async def test_get_alerts_no_data():
    """Test get_alerts with no data"""
    with patch('src.weather.make_nws_request') as mock_request:
        mock_request.return_value = None
        
        result = await get_alerts("CA")
        assert result == "Unable to fetch alerts or no alerts found."

@pytest.mark.asyncio
async def test_get_alerts_no_alerts():
    """Test get_alerts with no alerts"""
    with patch('src.weather.make_nws_request') as mock_request:
        mock_request.return_value = {"features": []}
        
        result = await get_alerts("CA")
        assert result == "No active alerts for this state."

@pytest.mark.asyncio
async def test_get_forecast_no_points():
    """Test get_forecast with no points data"""
    with patch('src.weather.make_nws_request') as mock_request:
        mock_request.return_value = None
        
        result = await get_forecast(41.8781, -87.6298)
        assert result == "Unable to fetch forecast data for this location."

@pytest.mark.asyncio
async def test_get_forecast_no_forecast():
    """Test get_forecast with no forecast data"""
    with patch('src.weather.make_nws_request') as mock_request:
        # First call returns points data
        mock_request.side_effect = [
            {
                "properties": {
                    "forecast": "https://api.weather.gov/forecast"
                }
            },
            None  # Second call returns None
        ]
        
        result = await get_forecast(41.8781, -87.6298)
        assert result == "Unable to fetch detailed forecast."

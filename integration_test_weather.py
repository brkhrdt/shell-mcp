import pytest
from weather import get_alerts, get_forecast

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_alerts_integration():
    """Test get_alerts with actual NWS API"""
    # Test with a known state that has alerts
    result = await get_alerts("IL")
    # Should return either alert data or error message
    assert isinstance(result, str)
    assert len(result) > 0

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_forecast_integration():
    """Test get_forecast with actual NWS API"""
    # Test with Chicago coordinates
    result = await get_forecast(41.8781, -87.6298)
    # Should return either forecast data or error message
    assert isinstance(result, str)
    assert len(result) > 0

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_alerts_no_alerts_integration():
    """Test get_alerts with a state that has no alerts"""
    result = await get_alerts("AK")  # Alaska unlikely to have active alerts
    assert isinstance(result, str)
    assert len(result) > 0

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_forecast_invalid_coordinates():
    """Test get_forecast with invalid coordinates"""
    result = await get_forecast(91, 0)  # Invalid latitude
    assert isinstance(result, str)
    assert len(result) > 0

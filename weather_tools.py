from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
from db import get_db_connection

NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

async def make_nws_request(url: str) -> dict[str, Any] | None:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json",
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=30.0)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

def format_alert(feature: dict) -> str:
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""

def register_weather_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_alerts(state: str) -> str:
        url = f"{NWS_API_BASE}/alerts/active/area/{state}"
        data = await make_nws_request(url)

        if not data or "features" not in data:
            return "Unable to fetch alerts or no alerts found."

        if not data["features"]:
            return "No active alerts for this state."

        alerts = [format_alert(f) for f in data["features"]]
        return "\n---\n".join(alerts)

    @mcp.tool()
    async def get_forecast(latitude: float, longitude: float) -> str:
        points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
        points_data = await make_nws_request(points_url)
        if not points_data:
            return "Unable to fetch forecast data for this location."

        forecast_url = points_data["properties"]["forecast"]
        forecast_data = await make_nws_request(forecast_url)
        if not forecast_data:
            return "Unable to fetch detailed forecast."

        periods = forecast_data["properties"]["periods"]
        parts = []
        for p in periods[:5]:
            parts.append(
                f"""
{p['name']}:
Temperature: {p['temperature']}°{p['temperatureUnit']}
Wind: {p['windSpeed']} {p['windDirection']}
Forecast: {p['detailedForecast']}
"""
            )
        return "\n---\n".join(parts)

    @mcp.tool()
    async def get_weather_by_city(city: str) -> str:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        async with httpx.AsyncClient() as client:
            geo_resp = await client.get(
                geo_url,
                params={"name": city, "count": 1},
                timeout=10.0,
            )

        if geo_resp.status_code != 200:
            return f"Failed to look up coordinates for '{city}'."

        data = geo_resp.json()
        results = data.get("results") or []
        if not results:
            return f"Couldn't find any location matching '{city}'."

        first = results[0]
        lat = first["latitude"]
        lon = first["longitude"]
        name = first.get("name", city)
        country = first.get("country", "")

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/geo+json",
        }

        async with httpx.AsyncClient() as client:
            points_resp = await client.get(
                f"{NWS_API_BASE}/points/{lat},{lon}",
                headers=headers,
                timeout=15.0,
                follow_redirects=True,
            )

        if points_resp.status_code != 200:
            return (
                f"Found coordinates for {name}, {country} ({lat}, {lon}), "
                f"but NWS metadata lookup failed (status {points_resp.status_code})."
            )

        points = points_resp.json()
        forecast_url = points.get("properties", {}).get("forecast")
        if not forecast_url:
            return (
                f"Found coordinates for {name}, {country} ({lat}, {lon}), "
                "but NWS did not provide a forecast URL for this location."
            )

        async with httpx.AsyncClient() as client:
            forecast_resp = await client.get(
                forecast_url,
                headers=headers,
                timeout=15.0,
                follow_redirects=True,
            )

        if forecast_resp.status_code != 200:
            return (
                f"Found coordinates for {name}, {country} ({lat}, {lon}), "
                f"but NWS forecast fetch failed (status {forecast_resp.status_code})."
            )

        forecast_data = forecast_resp.json()
        periods = forecast_data.get("properties", {}).get("periods", [])
        if not periods:
            return (
                f"NWS returned no forecast periods for {name}, {country} ({lat}, {lon})."
            )

        lines = [f"NWS forecast for {name}, {country} ({lat}, {lon}):", ""]
        for p in periods[:5]:
            lines.append(
                f"{p.get('name','Period')}: "
                f"{p.get('temperature')}°{p.get('temperatureUnit','')}, "
                f"{p.get('shortForecast','')}, "
                f"wind {p.get('windSpeed','')} {p.get('windDirection','')}"
            )
        return "\n".join(lines)

    @mcp.tool()
    async def test_db() -> str:
        try:
            conn = get_db_connection()
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    value = cur.fetchone()[0]
            conn.close()
            return f"DB connection OK ✅  SELECT 1 -> {value}"
        except Exception as e:
            return f"DB connection FAILED ❌: {e}"

    @mcp.tool()
    async def ping() -> str:
        return "weather MCP is alive 🚀"

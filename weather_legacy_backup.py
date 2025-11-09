from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
import os
import psycopg2
import google.generativeai as genai
import json

# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"
DATABASE_URL = "postgresql://postgres:$Anushka2013@localhost:5432/postgres"
GEMINI_API_KEY="AIzaSyC5oiPS7MQkhH2zP6g0cnN9bV9th1lJHm4"
genai.configure(api_key=GEMINI_API_KEY)

def get_db_connection():
    """
    Return a live connection to your PostgreSQL database.
    """
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(DATABASE_URL)

def get_wardrobe_item(garment_id: int) -> dict[str, Any]:
    """
    Fetch wardrobe row by id. Needs columns: id, image_path.
    """
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, image_path FROM wardrobe WHERE id = %s",
                    (garment_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Garment {garment_id} not found in wardrobe")
                return {"id": row[0], "image_path": row[1]}
    finally:
        conn.close()


def update_wardrobe_metadata(garment_id: int, meta: dict[str, Any]) -> None:
    """
    Update wardrobe metadata for given garment_id.
    Uses your existing columns, including 'occassion'.
    """
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE wardrobe
                    SET
                        name = %s,
                        type = %s,
                        color = %s,
                        fabric = %s,
                        style = %s,
                        occassion = %s
                    WHERE id = %s
                    """,
                    (
                        meta.get("name"),
                        meta.get("type"),
                        meta.get("color"),
                        meta.get("fabric"),
                        meta.get("style"),
                        meta.get("occassion"),
                        garment_id,
                    ),
                )
    finally:
        conn.close()


def extract_metadata_with_gemini(image_path: str) -> dict[str, Any]:
    """
    Use Gemini Vision to analyze ONE garment image and return:
    name, type, color, fabric, style, occassion
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found at {image_path}")

    model = genai.GenerativeModel("gemini-2.0-flash")

    with open(image_path, "rb") as f:
        img_bytes = f.read()

    prompt = """
You are tagging ONE clothing item for a digital wardrobe.

Return ONLY valid JSON with EXACTLY these keys:
name, type, color, fabric, style, occassion

- name: short label ("Blue Oversized T-Shirt")
- type: ("tshirt","shirt","jeans","hoodie","dress","sneakers", etc.)
- color: main color ("blue","black","white", etc.)
- fabric: best guess or null ("cotton","denim","polyester", etc.)
- style: "casual","formal","streetwear","ethnic","sport", etc.
- occassion: "everyday","office","party","wedding","gym", etc.

Example:
{"name":"Black Slim-Fit Shirt","type":"shirt","color":"black","fabric":"cotton","style":"formal","occassion":"office"}
"""

    result = model.generate_content(
        [
            prompt,
            {
                "mime_type": "image/jpeg",  # adjust if your uploads are png/webp
                "data": img_bytes,
            },
        ]
    )

    text = (result.text or "").strip()
    meta = json.loads(text)

    return {
        "name": meta.get("name"),
        "type": meta.get("type"),
        "color": meta.get("color"),
        "fabric": meta.get("fabric"),
        "style": meta.get("style"),
        "occassion": meta.get("occassion"),
    }


async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""

@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
{period['name']}:
Temperature: {period['temperature']}°{period['temperatureUnit']}
Wind: {period['windSpeed']} {period['windDirection']}
Forecast: {period['detailedForecast']}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)

@mcp.tool()
async def get_weather_by_city(city: str) -> str:
    """
    Given a city name like "Boston" or "Amherst", look up its coordinates
    and return the National Weather Service (NWS) forecast.

    Use this tool whenever the user asks for weather in a location by name
    instead of by coordinates.
    """
    # ---------- 1) Geocode city -> latitude, longitude ----------
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

    # ---------- 2) Use NWS points API to find forecast URL ----------
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

    # ---------- 3) Fetch NWS forecast ----------
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

    # Keep it compact: first few periods
    lines = [f"NWS forecast for {name}, {country} ({lat}, {lon}):", ""]
    for p in periods[:5]:
        period_name = p.get("name", "Period")
        temp = p.get("temperature")
        unit = p.get("temperatureUnit", "")
        short = p.get("shortForecast", "")
        wind = p.get("windSpeed", "")
        wind_dir = p.get("windDirection", "")
        lines.append(
            f"{period_name}: {temp}°{unit}, {short}, wind {wind} {wind_dir}"
        )

    return "\n".join(lines)

@mcp.tool()
async def test_db() -> str:
    """
    Check if the MCP server can connect to Postgres.
    """
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
    """
    Simple health-check tool.
    """
    return "weather MCP is alive 🚀"

def main():
    # Initialize and run the server
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()


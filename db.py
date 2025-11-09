from typing import Any
import os
import psycopg2

# Hackathon style: hardcoded fallback. You can keep your existing URL.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.ptttfoppythogoywjivi:MaheshG170505@aws-1-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require",
)

def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(DATABASE_URL)

def get_wardrobe_item(garment_id: int) -> dict[str, Any]:
    """
    Fetch wardrobe row by id. Expects columns: id, image_path.
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
                        occasion = %s
                    WHERE id = %s
                    """,
                    (
                        meta.get("name"),
                        meta.get("type"),
                        meta.get("color"),
                        meta.get("fabric"),
                        meta.get("style"),
                        meta.get("occasion"),
                        garment_id,
                    ),
                )
    finally:
        conn.close()

def create_wardrobe_item(
    name: str | None = None,
    type: str | None = None,
    color: str | None = None,
    fabric: str | None = None,
    style: str | None = None,
    occasion: str | None = None,
    image_path: str | None = None,
) -> int:
    """
    Insert a new wardrobe entry into Supabase and return the new garment ID.
    You can call this manually (from an MCP tool) or programmatically when adding clothes.
    """
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO wardrobe (name, type, color, fabric, style, occasion, image_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (name, type, color, fabric, style, occasion, image_path),
                )
                new_id = cur.fetchone()[0]
                return new_id
    finally:
        conn.close()


def add_wardrobe_item(
    name: str | None = None,
    type: str | None = None,
    color: str | None = None,
    fabric: str | None = None,
    style: str | None = None,
    occasion: str | None = None,
    image_path: str | None = None,
) -> dict[str, Any]:
    """
    Add a new wardrobe item into Supabase.

    You can provide full metadata or just image_path.
    Returns the created garment_id and stored values.
    """
    garment_id = create_wardrobe_item(
        name=name,
        type=type,
        color=color,
        fabric=fabric,
        style=style,
        occasion=occasion,
        image_path=image_path,
    )

    return {
        "garment_id": garment_id,
        "name": name,
        "type": type,
        "color": color,
        "fabric": fabric,
        "style": style,
        "occasion": occasion,
        "image_path": image_path,
        "message": "New wardrobe item added successfully."
    }

from mcp.server.fastmcp import FastMCP

def register_db_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def add_wardrobe_item_mcp(
        name: str | None = None,
        type: str | None = None,
        color: str | None = None,
        fabric: str | None = None,
        style: str | None = None,
        occasion: str | None = None,
        image_path: str | None = None,
    ) -> dict[str, Any]:
        return add_wardrobe_item(name, type, color, fabric, style, occasion, image_path)

    @mcp.tool()
    def add_and_tag_garment_mcp(image_path: str) -> dict[str, Any]:
        """
        One-shot tool:
        - Creates a new wardrobe entry with the given image_path
        - Uses Gemini Vision to extract metadata
        - Updates the same row in the database
        - Returns the garment_id + extracted fields
        """
        import os
        from gemini_client import extract_metadata_with_gemini

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at {image_path}")

        # Step 1: run Gemini Vision
        meta = extract_metadata_with_gemini(image_path)

        # Step 2: create a row
        garment_id = create_wardrobe_item(
            image_path=image_path,
            name=meta.get("name"),
            type=meta.get("type"),
            color=meta.get("color"),
            fabric=meta.get("fabric"),
            style=meta.get("style"),
            occasion=meta.get("occasion"),
        )

        return {
            "garment_id": garment_id,
            "image_path": image_path,
            "metadata": meta,
            "message": "Garment created and tagged successfully."
        }

    @mcp.tool()
    def list_wardrobe_mcp(
        occasion: str | None = None,
        type: str | None = None,
        limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Fetch wardrobe items from Supabase.

        You can filter by occasion (e.g. 'casual', 'formal') or type ('shirt', 'jacket').
        Returns up to `limit` items sorted by newest first.
        """
        conn = get_db_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    base_query = """
                        SELECT id, name, type, color, fabric, style, occasion, image_path
                        FROM wardrobe
                    """
                    filters = []
                    params = []

                    if occasion:
                        filters.append("occasion = %s")
                        params.append(occasion)
                    if type:
                        filters.append("type = %s")
                        params.append(type)

                    if filters:
                        base_query += " WHERE " + " AND ".join(filters)

                    base_query += " ORDER BY id DESC LIMIT %s"
                    params.append(limit)

                    cur.execute(base_query, tuple(params))
                    rows = cur.fetchall()

            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "type": r[2],
                    "color": r[3],
                    "fabric": r[4],
                    "style": r[5],
                    "occasion": r[6],
                    "image_path": r[7],
                }
                for r in rows
            ]
        finally:
            conn.close()

    @mcp.tool()
    def fashion_stylist_mcp(city: str, occasion: str | None = None, gender: str | None = None, style_preference: str | None = None) -> dict[str, Any]:
        """
        AI Fashion Stylist Tool 👗
        Suggests outfit combinations based on:
        - Your existing wardrobe (from Supabase)
        - Current weather and season
        - Global fashion trends
        - Occasion and personal style

        Returns a stylist-style JSON + human-readable recommendation.
        """
        import httpx, datetime, json
        import google.generativeai as genai


        # Step 1: Get wardrobe items
        conn = get_db_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT name, type, color, fabric, style, occasion, image_path
                        FROM wardrobe
                        ORDER BY id DESC
                    """)
                    wardrobe_rows = cur.fetchall()
        finally:
            conn.close()

        if not wardrobe_rows:
            return {"message": "Your wardrobe is empty — add clothes first!"}

        wardrobe = [
            {
                "name": r[0],
                "type": r[1],
                "color": r[2],
                "fabric": r[3],
                "style": r[4],
                "occasion": r[5],
                "image_path": r[6],
            }
            for r in wardrobe_rows
        ]

        # Step 2: Get weather (°F)
        weather_url = f"https://api.open-meteo.com/v1/forecast?current_weather=true&temperature_unit=fahrenheit&timezone=auto&name={city}"
        try:
            resp = httpx.get(weather_url, timeout=10.0)
            data = resp.json()
            temp_f = data["current_weather"]["temperature"]
        except Exception as e:
            temp_f = None

        # Step 3: Identify season
        month = datetime.datetime.now().month
        if month in [12, 1, 2]:
            season = "winter"
        elif month in [3, 4, 5]:
            season = "spring"
        elif month in [6, 7, 8]:
            season = "summer"
        else:
            season = "fall"
        
        # Step 4: Prepare stylist prompt
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_KEY"))
        model = genai.GenerativeModel("gemini-2.0-flash")

        wardrobe_json = json.dumps(wardrobe[:15])  # limit for context clarity

        prompt = f"""
        You are a professional fashion stylist.
        Based on my wardrobe below, suggest one outfit combination for me.

        Context:
        - City: {city}
        - Weather: {temp_f}°F
        - Season: {season}
        - Occasion: {occasion or "everyday casual"}
        - Gender: {gender or "unspecified"}
        - Style preference: {style_preference or "modern minimalist"}

        Wardrobe:
        {wardrobe_json}"""
        prompt +="""
        Please return your answer in **valid JSON** with the following fields:
        {{
          "outfit": {{
            "top": path attribute of the chosen top clothe object,
            "bottom":  path attribute of the chosen bottom clothe object,
            "outerwear": path attribute of chosen outerwear cloth object,
            "accessories": path attribute of chosen accessories cloth object
          }},
        }}
        """

        try:
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            result = json.loads(response.text)
        except Exception as e:
            return {"error": f"Gemini stylist failed: {e}"}

        # Step 5: Add metadata
        return {
            "city": city,
            "temperature_f": temp_f,
            "season": season,
            "occasion": occasion,
            "suggested_outfit": result.get("outfit"),
            "stylist_comment": result.get("stylist_comment"),
            "message": "Fashion stylist recommendation generated successfully 👗✨"
        }




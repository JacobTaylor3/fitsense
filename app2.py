import os
import json
import datetime

from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

import httpx
import google.generativeai as genai

from db import create_wardrobe_item, get_db_connection
from gemini_client import extract_metadata_with_gemini

# ------------------- Flask setup -------------------

app = Flask(__name__)

# where we store uploaded images locally
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# configure Gemini (use env var in real usage)
genai.configure(api_key=os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_KEY"))

# ------------------- Routes -------------------


@app.route("/")
def index():
    # make sure templates/index.html exists with the UI you pasted
    return render_template("index.html")


# 1) Upload + tag + store garment
@app.route("/api/upload-garment", methods=["POST"])
def upload_garment():
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "No image file provided."}), 400

    # safe + unique-ish filename
    filename = secure_filename(file.filename or "garment.jpg")
    base, ext = os.path.splitext(filename)
    if not ext:
        ext = ".jpg"
    filename = f"{base}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}{ext}"

    # save locally
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    # run Gemini Vision to extract metadata
    try:
        meta = extract_metadata_with_gemini(save_path)
    except Exception as e:
        return jsonify({"error": f"Gemini tagging failed: {e}"}), 500

    # optional hint from form
    occasion_hint = request.form.get("occasion_hint")
    if occasion_hint:
        meta["occasion"] = occasion_hint

    # store in DB
    try:
        garment_id = create_wardrobe_item(
            name=meta.get("name"),
            type=meta.get("type"),
            color=meta.get("color"),
            fabric=meta.get("fabric"),
            style=meta.get("style"),
            occasion=meta.get("occasion"),
            image_path=f"/static/uploads/{filename}",  # store web path
        )
    except Exception as e:
        return jsonify({"error": f"Failed to store in DB: {e}"}), 500

    image_url = f"/static/uploads/{filename}"

    return jsonify({
        "message": "Garment saved & tagged successfully.",
        "garment_id": garment_id,
        "image_url": image_url,
        "metadata": meta,
    })


# 2) Suggest outfit from stored wardrobe + weather
@app.route("/api/suggest-outfit", methods=["POST"])
def suggest_outfit():
    body = request.get_json(force=True) or {}

    city = body.get("location") or body.get("city") or "Boston"
    occasion = body.get("occasion") or "everyday casual"
    style_pref = body.get("style_preference") or "modern minimalist"
    gender = body.get("gender") or "unspecified"

    # --- load wardrobe from DB ---
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT name, type, color, fabric, style, occasion, image_path
                    FROM wardrobe
                    ORDER BY id DESC
                    LIMIT 30
                """)
                rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return jsonify({
            "city": city,
            "message": "Your wardrobe is empty — add some garments first.",
            "suggested_outfit": {},
        }), 200

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
        for r in rows
    ]

    # --- optional: get temperature using Open-Meteo ---
    temp_f = None
    try:
        geo = httpx.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
            timeout=5.0,
        ).json()
        if geo.get("results"):
            lat = geo["results"][0]["latitude"]
            lon = geo["results"][0]["longitude"]
            w = httpx.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current_weather": True,
                    "temperature_unit": "fahrenheit",
                },
                timeout=5.0,
            ).json()
            temp_f = w.get("current_weather", {}).get("temperature")
    except Exception:
        pass

    # --- season ---
    month = datetime.datetime.now().month
    if month in (12, 1, 2):
        season = "winter"
    elif month in (3, 4, 5):
        season = "spring"
    elif month in (6, 7, 8):
        season = "summer"
    else:
        season = "fall"

    # --- call Gemini to pick outfit from wardrobe ---
    model = genai.GenerativeModel("gemini-2.0-flash")
    wardrobe_json = json.dumps(wardrobe[:20])

    prompt = f"""
    You are a fashion stylist AI.

    From this wardrobe JSON, pick ONE outfit combination:
    {wardrobe_json}

    Context:
    - City: {city}
    - Temp_F: {temp_f}
    - Season: {season}
    - Occasion: {occasion}
    - Style preference: {style_pref}
    - Gender: {gender}

        Rules:
    - Only use items that exist in the wardrobe JSON above.
    - For "top", "bottom", "outerwear", and each entry in "accessories":
        - If you select a specific wardrobe item, set the value EXACTLY to its "image_path" from the JSON.
        - Do NOT invent new paths or folders.
        - Do NOT use "/static/Database-photo/..." or any external URLs.
    - If there is no suitable item for a slot, set that slot to "Not included in wardrobe".


    Return ONLY valid JSON:

    {{
      "outfit": {{
        "top": "<image_path or label of chosen top>",
        "bottom": "<image_path or label of chosen bottom>",
        "outerwear": "<image_path or label of chosen outerwear>",
        "accessories": ["<optional accessory>", "..."]
      }},
      "stylist_comment": "Short explanation of why this outfit fits the context.",
      "keep_this_with_you": "Optional: e.g. 'Carry a light jacket for the evening chill.'"
    }}
    """

    try:
        resp = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        result = json.loads(resp.text)
    except Exception as e:
        return jsonify({
            "city": city,
            "temperature_f": temp_f,
            "season": season,
            "message": f"Stylist failed: {e}",
            "suggested_outfit": {},
        }), 500

    outfit = result.get("outfit", {})

    return jsonify({
        "city": city,
        "temperature_f": temp_f,
        "season": season,
        "suggested_outfit": outfit,
        "stylist_comment": result.get("stylist_comment"),
        "keep_this_with_you": result.get("keep_this_with_you"),
        "message": "OK",
    })


# ------------------- Main -------------------

if __name__ == "__main__":
    # ensure DATABASE_URL + GEMINI_API_KEY are set in your env
    app.run(host="0.0.0.0", port=7100, debug=True)

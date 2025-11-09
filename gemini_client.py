from typing import Any
import os
import json
import google.generativeai as genai

# Hardcode or env; you already set this earlier
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyC5oiPS7MQkhH2zP6g0cnN9bV9th1lJHm4")
genai.configure(api_key=GEMINI_API_KEY)

def extract_metadata_with_gemini(image_path: str) -> dict[str, Any]:
    """
    Use Gemini Vision to analyze ONE garment image and return:
    name, type, color, fabric, style, occasion

    This mirrors your friend's get_meta_data() behavior.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found at {image_path}")

    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = """
    Describe the clothing item in the image and output your description in JSON format ONLY.
    The JSON must have exactly this shape:

    {
      "name": str,
      "type": str,
      "color": str,
      "fabric": str,
      "style": str,
      "occasion": str
    }

    Rules:
    - name: short description of the clothing item.
    - type: one-word category like "shirt", "tshirt", "jeans", "jacket", "dress", etc.
    - color: main overall color or simple pattern description.
    - fabric: material type if visible (e.g. "cotton", "denim", "polyester"); use a best guess.
    - style: stylistic description (e.g. "casual", "formal", "streetwear", "sporty").
    - occasion: one of "formal", "semi-formal", "casual", "business casual",
                "business formal", "party", "wedding", "gym", etc.

    Output:
    - A single JSON object.
    - No markdown.
    - No explanation.
    - No list.
    """

    # Read image bytes
    with open(image_path, "rb") as f:
        img_bytes = f.read()

    # Call Gemini: image + prompt, ask for JSON
    response = model.generate_content(
    contents=[
        {
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": img_bytes,
            }
        },
        prompt,
    ],
    generation_config={
        "response_mime_type": "application/json",
    },
)


    # response.text should now be raw JSON
    print(f"Gemini response for {image_path}: {response.text}")
    try:
        data = json.loads(response.text)
    except Exception as e:
        raise RuntimeError(f"Gemini returned invalid JSON: {response.text}") from e

    # Map friend's "occasion" to your DB column "occasion"
    return {
        "name": data.get("name") or os.path.basename(image_path),
        "type": data.get("type"),
        "color": data.get("color"),
        "fabric": data.get("fabric"),
        "style": data.get("style"),
        "occasion": data.get("occasion") or data.get("occasion"),
    }

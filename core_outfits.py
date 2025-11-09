from typing import Dict, Any

def compute_today_outfit(user_id: str, location: str | None = None) -> Dict[str, Any]:
    """
    Core business logic for picking today's outfit.
    This is the ONLY place you implement the logic.
    Safe to call from MCP tools, HTTP API, CLI, etc.
    """

    # TODO: later:
    # 1) wardrobe = get_user_wardrobe(user_id)
    # 2) weather = get_weather(location) if location else None
    # 3) suggestion = get_outfit_suggestion(wardrobe, weather)

    # TEMP: hard-coded example in the **final desired shape**
    top_path = "/static/Database-photo/crewneckBlack.webp"
    bottom_path = "/static/Database-photo/bluejeans.webp"
    outerwear_path = "/static/Database-photo/denimJacket.jpg"
    accessories_path = None  # or "/static/Database-photo/watch.png"

    return {
        "user_id": user_id,
        "location": location,
        "outfit": {
            "top": top_path,
            "bottom": bottom_path,
            "outerwear": outerwear_path,
            "accessories": accessories_path,
        },
    }

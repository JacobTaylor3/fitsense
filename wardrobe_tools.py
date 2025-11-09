from typing import Any
import os

from mcp.server.fastmcp import FastMCP
from db import get_wardrobe_item, update_wardrobe_metadata, create_wardrobe_item
from gemini_client import extract_metadata_with_gemini

def register_wardrobe_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    async def tag_garment(garment_id: int) -> dict[str, Any]:
        """
        Auto-tag a wardrobe item using Gemini Vision.

        - Reads image_path from wardrobe for this garment_id
        - Calls Gemini to extract metadata
        - Updates the same row in DB
        - Returns what was stored
        """
        item = get_wardrobe_item(garment_id)

        if not item:
            raise ValueError(f"No wardrobe item found for garment_id={garment_id}")

        image_path = item.get("image_path")
        if not image_path:
            raise ValueError(f"Garment {garment_id} has no image_path set")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at {image_path}")

        meta = extract_metadata_with_gemini(image_path)
        update_wardrobe_metadata(garment_id, meta)

        return {
            "garment_id": garment_id,
            "image_path": image_path,
            "metadata": meta,
        }

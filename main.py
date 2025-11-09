from mcp.server.fastmcp import FastMCP
from weather_tools import register_weather_tools
from wardrobe_tools import register_wardrobe_tools
from db import register_db_tools

mcp = FastMCP("weather-wardrobe")

# Register tool groups
register_weather_tools(mcp)
register_wardrobe_tools(mcp)
register_db_tools(mcp)

def main():
    print("✅ MCP server started (weather-wardrobe)")
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()

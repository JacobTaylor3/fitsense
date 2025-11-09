# app.py
import os
from flask import Flask, request, jsonify
from core_outfits import compute_today_outfit

app = Flask(__name__)

API_KEY = os.getenv("API_KEY", "dev-secret-key")

def check_auth(req) -> bool:
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    token = auth_header.split(" ", 1)[1]
    return token == API_KEY

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/api/suggest-outfit", methods=["POST"])
def suggest_outfit():
    if not check_auth(request):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True) or {}
    user_id = data.get("user_id")
    location = data.get("location")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    result = compute_today_outfit(user_id, location)
    return jsonify(result)

print(app.url_map)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

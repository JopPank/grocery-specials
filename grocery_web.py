import argparse
import os
from pathlib import Path
import re
import webbrowser

from flask import Flask, jsonify, request, send_file

from grocery_tracker import ALLOWED_STORES, DealSearchError, POSTAL_CODE, search_grocery_deals


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024
PAGE = Path(__file__).with_name("index.html")
POSTAL_CODE_PATTERN = re.compile(r"[A-Za-z]\d[A-Za-z] ?\d[A-Za-z]\d")


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    allowed_origins = {
        value.strip()
        for value in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
        if value.strip()
    }
    if origin and ("*" in allowed_origins or origin in allowed_origins):
        response.headers["Access-Control-Allow-Origin"] = (
            "*" if "*" in allowed_origins else origin
        )
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def index():
    return send_file(PAGE)


@app.get("/api-config.js")
def api_config():
    return send_file(PAGE.with_name("api-config.js"), mimetype="application/javascript")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "Search request is too large."}), 413


@app.get("/api/stores")
def stores():
    return jsonify({"stores": list(ALLOWED_STORES), "postal_code": POSTAL_CODE})


@app.post("/api/search")
def search():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send a JSON object containing foods and postal."}), 400

    foods = payload.get("foods")
    postal = payload.get("postal", POSTAL_CODE)
    if not isinstance(foods, str) or not isinstance(postal, str):
        return jsonify({"error": "Foods and postal code must be text."}), 400
    postal = postal.strip().upper()
    if not POSTAL_CODE_PATTERN.fullmatch(postal):
        return jsonify({"error": "Enter a Canadian postal code, such as J9J 3X7."}), 400
    if len(foods) > 300:
        return jsonify({"error": "Search up to 8 foods at a time (300 characters maximum)."}), 400

    terms = list(dict.fromkeys(term.strip() for term in foods.split(",") if term.strip()))
    if not terms:
        return jsonify({"error": "Enter at least one food to search for."}), 400
    if len(terms) > 8:
        return jsonify({"error": "Search up to 8 foods at a time (300 characters maximum)."}), 400

    results = []
    for term in terms:
        try:
            deals = search_grocery_deals(term, postal)
        except DealSearchError as exc:
            results.append({"item": term, "deals": [], "error": str(exc)})
            continue
        results.append({
            "item": term,
            "deals": [
                {
                    **deal,
                    "valid_from": deal["valid_from"].isoformat() if deal["valid_from"] else None,
                    "valid_to": deal["valid_to"].isoformat() if deal["valid_to"] else None,
                }
                for deal in deals
            ],
            "error": None,
        })
    return jsonify({"results": results})


def main():
    parser = argparse.ArgumentParser(description="Run the local grocery specials web app.")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Grocery Specials: {url}", flush=True)
    print("Keep this window open while searching. Close it when finished.", flush=True)
    if not args.no_browser and not webbrowser.open(url):
        print(f"Could not open a browser automatically. Open {url} in your browser.", flush=True)
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()

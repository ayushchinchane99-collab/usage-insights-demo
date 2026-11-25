"""Event collector: receives semantic usage events and appends them to a JSONL file.

Run:  python -m server.collector
Then open http://localhost:5000 to use the instrumented sample app.
"""
import json
import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from analytics.taxonomy import ACTIONS

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "sample_app"
DEFAULT_OUT = ROOT / "data" / "live_events.jsonl"

REQUIRED = {"session_id", "ts", "action"}


def create_app(out_path=None):
    app = Flask(__name__, static_folder=None)
    out = Path(out_path or os.environ.get("EVENTS_FILE", DEFAULT_OUT))
    out.parent.mkdir(parents=True, exist_ok=True)

    @app.get("/")
    def index():
        return send_from_directory(APP_DIR, "index.html")

    @app.get("/tracker.js")
    def tracker():
        return send_from_directory(APP_DIR, "tracker.js")

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/events")
    def events():
        # sendBeacon posts text/plain, so parse the raw body ourselves.
        try:
            event = json.loads(request.get_data(as_text=True))
        except json.JSONDecodeError:
            return jsonify(error="invalid JSON"), 400
        if not isinstance(event, dict) or not REQUIRED.issubset(event):
            return jsonify(error="missing fields"), 400
        if event["action"] not in ACTIONS:
            return jsonify(error="unknown action"), 400
        clean = {
            "session_id": str(event["session_id"])[:64],
            "ts": float(event["ts"]),
            "action": event["action"],
            "description": ACTIONS[event["action"]]["description"],
            "feature": ACTIONS[event["action"]]["feature"],
            "task": "checkout",
        }
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(clean) + "\n")
        return "", 204

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)

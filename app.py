"""Flask server: serves index.html and POST /api/chat on top of chat_core.chat."""

import os
import threading

import openai
from flask import Flask, jsonify, request, send_from_directory

import chat_core

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_MESSAGE_LEN = 4000

app = Flask(__name__)

# Conversation history per browser session, kept in memory.
SESSIONS: dict[str, list[dict]] = {}
SESSIONS_LOCK = threading.Lock()


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.post("/api/chat")
def api_chat():
    data = request.get_json(silent=True) or {}
    session_id = str(data.get("session_id") or "").strip()
    message = str(data.get("message") or "").strip()

    if not session_id or len(session_id) > 100:
        return jsonify(error="session_id puuttuu tai on virheellinen"), 400
    if not message:
        return jsonify(error="Viesti on tyhjä"), 400
    if len(message) > MAX_MESSAGE_LEN:
        return jsonify(error=f"Viesti on liian pitkä (max {MAX_MESSAGE_LEN} merkkiä)"), 400

    with SESSIONS_LOCK:
        # Work on a copy so a failed call doesn't leave a half-finished history.
        history = list(SESSIONS.get(session_id, []))
    history.append({"role": "user", "content": message})

    try:
        reply, searches = chat_core.chat(history)
    except openai.RateLimitError as exc:
        return jsonify(error=chat_core.describe_api_error(exc)), 429
    except Exception as exc:
        app.logger.exception("chat failed")
        return jsonify(error=chat_core.describe_api_error(exc)), 502

    with SESSIONS_LOCK:
        SESSIONS[session_id] = history

    return jsonify(reply=reply, searches=searches)


@app.post("/api/reset")
def api_reset():
    data = request.get_json(silent=True) or {}
    with SESSIONS_LOCK:
        SESSIONS.pop(str(data.get("session_id") or ""), None)
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)

from __future__ import annotations

from flask import Flask, jsonify, request
from flask_cors import CORS

from backend.chat_service import chat
from backend.config import SOURCE_URLS

app = Flask(__name__)

_ALLOWED_ORIGINS = [
    "https://mutualfundrag.vercel.app",
    "https://mutual-fund-rag.onrender.com",
]

CORS(app, resources={r"/*": {"origins": _ALLOWED_ORIGINS}})


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "Mutual Fund RAG API",
        "status": "ok",
        "endpoints": ["/chat", "/health", "/sources"],
    })


@app.route("/chat", methods=["POST"])
def chat_endpoint():
    """POST /chat  -  Main chat endpoint.

    Input JSON:  {"query": "...", "session_id": "..." (optional)}
    Output JSON: {"answer": "...", "source_link": "...",
                  "last_updated_from_sources": "...", "response_type": "..."}
    """
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "query is required"}), 400

    try:
        result = chat(query)
    except Exception as exc:
        return jsonify({"error": f"Internal error: {exc}"}), 500
    return jsonify(result)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/sources", methods=["GET"])
def sources():
    return jsonify({"sources": SOURCE_URLS})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

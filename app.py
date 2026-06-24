from __future__ import annotations

import traceback
import re as _re

from flask import Flask, jsonify, request
from flask_cors import CORS

from backend.chat_service import chat
from backend.config import SOURCE_URLS

app = Flask(__name__)

_ALLOWED_ORIGINS = [
    "https://mutualfundrag.vercel.app",
    "https://mutual-fund-rag.onrender.com",
    _re.compile(r"https://.*\.vercel\.app"),
    _re.compile(r"https://.*\.replit\.dev"),
    _re.compile(r"https://.*\.replit\.app"),
]

CORS(app, resources={r"/*": {"origins": _ALLOWED_ORIGINS}})


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "Mutual Fund RAG API",
        "status": "ok",
        "endpoints": ["/chat", "/health", "/sources", "/debug", "/test", "/test-retrieval"],
    })


@app.route("/chat", methods=["POST"])
def chat_endpoint():
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "query is required"}), 400

    try:
        result = chat(query)
        return jsonify(result)

    except Exception as exc:
        print("\n========== CHAT ERROR ==========")
        traceback.print_exc()
        print("================================\n")

        return jsonify({
            "error": str(exc),
            "type": type(exc).__name__
        }), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/sources", methods=["GET"])
def sources():
    return jsonify({"sources": SOURCE_URLS})


@app.route("/debug", methods=["GET"])
def debug():
    try:
        from backend.retriever import _get_collection

        c = _get_collection()

        return jsonify({
            "success": True,
            "collection": c.name
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route("/test", methods=["GET"])
def test():
    return jsonify({"working": True})


@app.route("/test-retrieval", methods=["GET"])
def test_retrieval():
    try:
        from backend.retriever import _get_collection

        c = _get_collection()

        return jsonify({
            "success": True,
            "collection": c.name
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

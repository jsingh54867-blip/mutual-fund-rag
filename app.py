from __future__ import annotations
import json
import traceback
import re as _re
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS
from backend.chat_service import chat
from backend.config import SOURCE_URLS

_PROCESSED_DIR = Path(__file__).parent / "phase_1_mvp" / "data" / "processed_pages"


def _load_fund_meta() -> dict[str, dict]:
    """Return a mapping of source_url -> {scheme_name, crawl_date} from processed pages."""
    meta: dict[str, dict] = {}
    if not _PROCESSED_DIR.exists():
        return meta
    for f in sorted(_PROCESSED_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            url = data.get("source_url", "")
            if url:
                meta[url] = {
                    "scheme_name": data.get("scheme_name", ""),
                    "crawl_date": data.get("crawl_date", ""),
                }
        except Exception:
            pass
    return meta

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
        "endpoints": ["/chat", "/health", "/sources"],
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


@app.route("/fund-meta", methods=["GET"])
def fund_meta():
    """Return per-fund metadata (scheme_name, crawl_date) keyed by source_url."""
    meta = _load_fund_meta()
    funds = []
    seen: set[str] = set()
    for url in SOURCE_URLS:
        if url in seen:
            continue
        seen.add(url)
        info = meta.get(url, {})
        funds.append({
            "source_url": url,
            "scheme_name": info.get("scheme_name", ""),
            "crawl_date": info.get("crawl_date", ""),
        })
    return jsonify({"funds": funds})

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

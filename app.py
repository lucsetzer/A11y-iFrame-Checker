"""
app.py — Flask entry point for A11y iFrame Checker.
Routes: /analyze, /scan, /settings, /export
"""
import csv
import io
import json
import os

from dotenv import load_dotenv, set_key
from flask import Flask, jsonify, render_template, request, send_file

from services import analyzer, embed_checker

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _error(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Analyze a single iframe snippet.
    Body (JSON):
        snippet       : str  — raw iframe HTML (required)
        src_override  : str  — optional source URL override
        llm_provider  : str  — optional LLM provider override
    """
    data = request.get_json(silent=True) or {}
    snippet = (data.get("snippet") or "").strip()
    src_override = (data.get("src_override") or "").strip() or None
    llm_provider = (data.get("llm_provider") or "").strip() or None

    if not snippet and not src_override:
        return _error("Provide an iframe snippet or source URL.")

    # If just a URL is provided (no HTML), wrap it
    if not snippet and src_override:
        snippet = f'<iframe src="{src_override}"></iframe>'

    result = analyzer.analyze_iframe(
        snippet=snippet,
        src_override=src_override,
        llm_provider=llm_provider,
    )
    return jsonify(result)


@app.route("/scan", methods=["POST"])
def scan():
    """
    Scan a page URL for all iframes and return a heuristic-only audit.
    Body (JSON):
        url : str
    """
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return _error("Provide a page URL to scan.")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    result = analyzer.scan_page(url)
    return jsonify(result)


@app.route("/settings", methods=["POST"])
def settings():
    """
    Update API keys in .env.
    Body (JSON): any subset of the key names defined in .env.template
    """
    data = request.get_json(silent=True) or {}
    allowed_keys = [
        "GEMINI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "DEFAULT_LLM_PROVIDER",
    ]
    updated = []
    # Ensure .env file exists
    if not os.path.exists(ENV_PATH):
        open(ENV_PATH, "w").close()

    for key in allowed_keys:
        val = data.get(key)
        if val is not None:
            set_key(ENV_PATH, key, str(val))
            os.environ[key] = str(val)
            updated.append(key)

    load_dotenv(override=True)
    return jsonify({"updated": updated, "message": "Settings saved successfully."})


@app.route("/check-embed", methods=["POST"])
def check_embed():
    """
    Run a WCAG 2.2 accessibility audit on any embedded content snippet.
    Supports: <iframe>, <object>, <embed>, <video>, <audio>
    Body (JSON):
        snippet : str — raw HTML snippet
    """
    data = request.get_json(silent=True) or {}
    snippet = (data.get("snippet") or "").strip()
    if not snippet:
        return _error("Provide an embed snippet to check.")
    result = embed_checker.check_embed(snippet)
    return jsonify(result)


@app.route("/export", methods=["POST"])
def export():
    """
    Export saved results as CSV or JSON.
    Body (JSON):
        format  : "csv" | "json"
        results : list of result dicts
    """
    data = request.get_json(silent=True) or {}
    fmt = (data.get("format") or "json").lower()
    results = data.get("results", [])

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Page URL / Snippet",
            "Platform",
            "Existing Title",
            "Audit Status",
            "Rank 1 Title",
            "Rank 2 Title",
            "Rank 3 Title",
            "Selected Title",
            "Corrected Snippet",
            "WCAG Rationale",
            "Provider Used",
        ])
        for r in results:
            candidates = r.get("candidates", [])
            titles = [c.get("title", "") for c in candidates]
            while len(titles) < 3:
                titles.append("")
            selected = r.get("selected_title", "")
            corrected = r.get("corrected_snippet", "")
            rationale = r.get("rationale", "")
            writer.writerow([
                r.get("source", ""),
                r.get("platform", ""),
                r.get("existing_title", ""),
                r.get("audit_status", ""),
                titles[0],
                titles[1],
                titles[2],
                selected,
                corrected,
                rationale,
                r.get("provider_used", ""),
            ])
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name="a11y-iframe-report.csv",
        )

    # Default: JSON
    return send_file(
        io.BytesIO(json.dumps(results, indent=2).encode("utf-8")),
        mimetype="application/json",
        as_attachment=True,
        download_name="a11y-iframe-report.json",
    )


if __name__ == "__main__":
    app.run(debug=True)

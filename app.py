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

from services import embed_checker

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


@app.route("/check-embed", methods=["POST"])
def check_embed():
    """
    Run WCAG 2.2 audits on a snippet OR scan a page URL for multiple embeds.
    Body (JSON):
        snippet : str — optional raw HTML snippet
        url     : str — optional page URL to scan
    """
    data = request.get_json(silent=True) or {}
    snippet = (data.get("snippet") or "").strip()
    url = (data.get("url") or "").strip()

    if not snippet and not url:
        return _error("Provide a snippet or a URL to check.")

    from services import browser_fetcher
    
    all_results = []
    evidence_url = None
    
    if url:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            found_items = browser_fetcher.get_embeds(url)
            for i, item in enumerate(found_items):
                s = item.get("snippet", "")
                # check_embed now returns a list (usually len 1 in URL mode)
                audit_list = embed_checker.check_embed(s, metadata=item)
                
                # Get evidence URL from the first item's summary
                if i == 0 and item.get("_scan_summary"):
                    evidence_url = item["_scan_summary"].get("evidence_url")
                
                for audit_res in audit_list:
                    # Add location and contextual metadata for frontend
                    audit_res["line"] = item.get("line")
                    audit_res["source_url"] = item.get("page_url") or item.get("frame_url") or url
                    audit_res["frame_url"] = item.get("frame_url")
                    
                    # Uniqueness
                    audit_res["is_duplicate"] = item.get("is_duplicate", False)
                    audit_res["duplicate_count"] = item.get("duplicate_count", 0)
                    audit_res["original_index"] = item.get("original_index")
                    audit_res["uniqueness_key"] = item.get("uniqueness_key")
                    audit_res["dom_path"] = item.get("dom_path")
                    # Use provided index or default to loop counter
                    audit_res["index"] = item.get("index") or (i + 1)
                    audit_res["src"] = item.get("src")
                    
                    all_results.append(audit_res)
        except Exception as e:
            return _error(f"Scan failed: {str(e)}")
    else:
        # Snippet Mode - can now return multiple results
        audit_list = embed_checker.check_embed(snippet)
        for i, audit_res in enumerate(audit_list):
            audit_res["index"] = i + 1
            all_results.append(audit_res)

    return jsonify({
        "findings": all_results, 
        "count": len(all_results),
        "evidence": evidence_url
    })


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

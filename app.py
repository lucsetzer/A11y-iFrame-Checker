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

from services import embed_checker, pdf_auditor

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _error(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


# ── Debug ─────────────────────────────────────────────────────────────────────

@app.route("/ping")
def ping():
    return "✅ Server is running!"

@app.route("/test-vue")
def test_vue():
    return """<!DOCTYPE html>
<html><head><script src="/static/js/vue.global.prod.js"></script></head>
<body style="font-family:sans-serif;padding:2rem;background:#f0f7f4">
  <h1 id="status" style="color:red">❌ Vue did NOT mount</h1>
  <div id="app">{{ message }}</div>
  <script>
    Vue.createApp({ data() { return { message: '✅ Vue is working!' }; } }).mount('#app');
    document.getElementById('status').style.color = 'green';
    document.getElementById('status').textContent = '✅ Vue loaded successfully';
  </script>
</body></html>"""


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


@app.route("/check-pdf", methods=["POST"])
def check_pdf():
    """
    Smart PDF checker:
    - If given a direct PDF URL → audit that PDF
    - If given an HTML page URL → find all PDFs on page and audit each
    - If file upload → audit that file
    """
    from playwright.sync_api import sync_playwright
    from services.pdf_auditor import audit_pdf
    from urllib.parse import urljoin
    import httpx
    
    # Case 1: File upload
    if 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            return _error("No file selected.")
        try:
            pdf_bytes = file.read()
            result = audit_pdf(pdf_bytes)
            return jsonify({
                "success": True,
                "type": "file",
                "filename": file.filename,
                "audit": result,
                "summary": result.get("summary", {}),
                "findings": result.get("findings", [])
            })
        except Exception as e:
            return _error(f"PDF upload audit failed: {str(e)}")
    
    # Case 2: URL (could be PDF or HTML page)
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    
    if not url:
        return _error("Provide a PDF URL, page URL, or upload a file.")
    
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    # Check if this is a direct PDF URL
    if url.lower().endswith('.pdf'):
        # Direct PDF URL - audit it directly
        try:
            with httpx.Client(follow_redirects=True, timeout=30.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                result = audit_pdf(resp.content)
                return jsonify({
                    "success": True,
                    "type": "direct_pdf",
                    "page_url": url,
                    "total_pdfs": 1,
                    "pdfs": [{
                        "url": url,
                        "audit": result,
                        "summary": result.get("summary", {})
                    }],
                    "combined_summary": result.get("summary", {})
                })
        except Exception as e:
            return _error(f"Failed to fetch PDF: {str(e)}")
    
    # Case 3: HTML page URL - find all PDFs
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000, wait_until="networkidle")
            
            # Find all PDF links
            pdf_links = page.locator('a[href$=".pdf" i]').all()
            
            # Find PDF iframes
            pdf_iframes = page.locator('iframe[src$=".pdf" i]').all()
            
            results = []
            
            # Process regular PDF links
            for link in pdf_links:
                href = link.get_attribute('href')
                if not href:
                    continue
                pdf_url = urljoin(url, href)
                
                try:
                    response = page.context.request.get(pdf_url)
                    if response.status == 200:
                        audit_result = audit_pdf(response.body())
                        results.append({
                            "url": pdf_url,
                            "type": "link",
                            "success": True,
                            "audit": audit_result,
                            "summary": audit_result.get("summary", {})
                        })
                    else:
                        results.append({
                            "url": pdf_url,
                            "type": "link",
                            "success": False,
                            "error": f"HTTP {response.status}"
                        })
                except Exception as e:
                    results.append({
                        "url": pdf_url,
                        "type": "link",
                        "success": False,
                        "error": str(e)
                    })
            
            # Process PDF iframes
            for iframe in pdf_iframes:
                src = iframe.get_attribute('src')
                if not src:
                    continue
                pdf_url = urljoin(url, src)
                
                try:
                    response = page.context.request.get(pdf_url)
                    if response.status == 200:
                        audit_result = audit_pdf(response.body())
                        results.append({
                            "url": pdf_url,
                            "type": "iframe",
                            "success": True,
                            "audit": audit_result,
                            "summary": audit_result.get("summary", {})
                        })
                    else:
                        results.append({
                            "url": pdf_url,
                            "type": "iframe",
                            "success": False,
                            "error": f"HTTP {response.status}"
                        })
                except Exception as e:
                    results.append({
                        "url": pdf_url,
                        "type": "iframe",
                        "success": False,
                        "error": str(e)
                    })
            
            browser.close()
            
            # Calculate combined totals
            total_critical = sum(r.get("summary", {}).get("critical", 0) for r in results if r.get("success"))
            total_warning = sum(r.get("summary", {}).get("warning", 0) for r in results if r.get("success"))
            total_manual = sum(r.get("summary", {}).get("manual", 0) for r in results if r.get("success"))
            
            return jsonify({
                "success": True,
                "type": "html_page",
                "page_url": url,
                "total_pdfs": len(results),
                "successful_scans": len([r for r in results if r.get("success")]),
                "pdfs": results,
                "combined_summary": {
                    "critical": total_critical,
                    "warning": total_warning,
                    "manual": total_manual,
                    "total_pdfs": len(results)
                }
            })
            
    except Exception as e:
        return _error(f"Page scan failed: {str(e)}")

@app.route("/scan-page-for-pdfs", methods=["POST"])
def scan_page_for_pdfs():
    """
    NEW ROUTE: Scan an HTML page for all PDF links and audit each one.
    Body: { "url": "https://example.com/page-with-pdfs" }
    """
    from playwright.sync_api import sync_playwright
    from services.pdf_auditor import audit_pdf
    from urllib.parse import urljoin
    
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    
    if not url:
        return _error("Provide a URL to scan for PDFs.")
    
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    results = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            
            # Find all PDF links
            pdf_links = page.locator('a[href$=".pdf" i]').all()
            
            for link in pdf_links:
                href = link.get_attribute('href')
                if not href:
                    continue
                
                pdf_url = urljoin(url, href)
                
                try:
                    # Fetch the PDF
                    response = page.context.request.get(pdf_url)
                    if response.status == 200:
                        pdf_bytes = response.body()
                        audit_result = audit_pdf(pdf_bytes)
                        results.append({
                            "url": pdf_url,
                            "success": True,
                            "audit": audit_result,
                            "summary": audit_result.get("summary", {})
                        })
                    else:
                        results.append({
                            "url": pdf_url,
                            "success": False,
                            "error": f"HTTP {response.status}"
                        })
                except Exception as e:
                    results.append({
                        "url": pdf_url,
                        "success": False,
                        "error": str(e)
                    })
            
            browser.close()
            
            # Calculate totals
            total_critical = sum(r.get("audit", {}).get("summary", {}).get("critical", 0) for r in results)
            total_warnings = sum(r.get("audit", {}).get("summary", {}).get("warning", 0) for r in results)
            total_manual = sum(r.get("audit", {}).get("summary", {}).get("manual", 0) for r in results)
            
            return jsonify({
                "success": True,
                "page_url": url,
                "total_pdfs": len(results),
                "total_critical": total_critical,
                "total_warnings": total_warnings,
                "total_manual": total_manual,
                "pdfs": results
            })
            
    except Exception as e:
        return _error(f"PDF page scan failed: {str(e)}")

@app.route("/export", methods=["POST"])
def export():
    """
    Export saved results as CSV, JSON, or PDF.
    """
    from datetime import datetime
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    import io
    
    data = request.get_json(silent=True) or {}
    fmt = (data.get("format") or "json").lower()
    results = data.get("results", [])
    
    # --- CSV Export (existing) ---
    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "File/Source", "Type", "Critical", "Warning", "Manual", "Issues", "Fix Instructions"
        ])
        for r in results:
            summary = r.get("summary", {})
            findings = r.get("findings", [])
            issues_text = "; ".join([f"{f.get('tier', 'Issue')}: {f.get('description', '')}" for f in findings[:3]])
            fixes_text = "; ".join([f.get('fix_hint', '') for f in findings[:3]])
            writer.writerow([
                r.get("source_url", r.get("filename", "Unknown")),
                r.get("element_type", "Document"),
                summary.get("critical", 0),
                summary.get("warning", 0),
                summary.get("manual", 0),
                issues_text,
                fixes_text
            ])
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"a11y-report-{datetime.now().strftime('%Y%m%d')}.csv",
        )
    
    # --- PDF Export (NEW) ---
    elif fmt == "pdf":
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)
        
        styles = getSampleStyleSheet()
        heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading1'], fontSize=16, spaceAfter=30, textColor=colors.HexColor('#005035'))
        subheading_style = ParagraphStyle('Subheading', parent=styles['Heading2'], fontSize=12, spaceAfter=12, textColor=colors.HexColor('#333333'))
        normal_style = styles['Normal']
        issue_style = ParagraphStyle('Issue', parent=styles['Normal'], fontSize=9, leftIndent=20, spaceAfter=8)
        
        story = []
        
        # Title
        story.append(Paragraph("Accessibility Audit Report", heading_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", normal_style))
        story.append(Spacer(1, 0.25 * inch))
        
        # Count total PDFs if this is a page scan
        total_pdfs = 0
        all_pdf_details = []
        
        for r in results:
            # Check if this result has pdfDetails embedded (from page scan)
            if r.get('pdfs') and len(r.get('pdfs', [])) > 0:
                total_pdfs += len(r.get('pdfs', []))
                all_pdf_details.extend(r.get('pdfs', []))
            elif r.get('pdf_details') and len(r.get('pdf_details', [])) > 0:
                total_pdfs += len(r.get('pdf_details', []))
                all_pdf_details.extend(r.get('pdf_details', []))
            elif r.get('findings') and len(r.get('findings', [])) > 0:
                # Single document result
                all_pdf_details.append(r)
        
        story.append(Paragraph(f"Total items scanned: {len(all_pdf_details)}", normal_style))
        story.append(Spacer(1, 0.5 * inch))
        
        if len(all_pdf_details) == 0:
            story.append(Paragraph("No results to display. Please save results before exporting.", normal_style))
        else:
            for idx, pdf in enumerate(all_pdf_details):
                # Get filename or URL
                filename = pdf.get('filename', pdf.get('url', 'Unknown'))
                if filename and '/' in filename:
                    filename = filename.split('/')[-1]
                
                story.append(Paragraph(f"{idx + 1}. {filename}", subheading_style))
                
                # Summary
                summary = pdf.get('summary', {})
                story.append(Paragraph(f"<b>Summary:</b> Critical: {summary.get('critical', 0)} | Warning: {summary.get('warning', 0)} | Manual: {summary.get('manual', 0)}", normal_style))
                story.append(Spacer(1, 0.1 * inch))
                
                # Findings - ALL expanded, no accordion
                findings = pdf.get('findings', [])
                if findings and len(findings) > 0:
                    story.append(Paragraph("<b>Issues Found:</b>", normal_style))
                    for f in findings:
                        tier = f.get('tier', 'Issue')
                        description = f.get('description', '')
                        fix_hint = f.get('fix_hint', '')
                        story.append(Paragraph(f"  • <b>{tier}:</b> {description}", issue_style))
                        story.append(Paragraph(f"    <i>Fix:</i> {fix_hint}", issue_style))
                    story.append(Spacer(1, 0.1 * inch))
                else:
                    story.append(Paragraph("✅ No accessibility issues found.", normal_style))
                
                story.append(Spacer(1, 0.2 * inch))
                
                # Add page break every 5 items
                if (idx + 1) % 5 == 0 and (idx + 1) < len(all_pdf_details):
                    story.append(PageBreak())
        
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"a11y-report-{datetime.now().strftime('%Y%m%d')}.pdf",
        )
    
    # --- JSON Export (default) ---
    else:
        return send_file(
            io.BytesIO(json.dumps(results, indent=2).encode('utf-8')),
            mimetype="application/json",
            as_attachment=True,
            download_name=f"a11y-report-{datetime.now().strftime('%Y%m%d')}.json",
        )


if __name__ == "__main__":
    app.run(debug=True, port=5050)

from typing import Optional, Union, List, Dict, Tuple
"""
page_auditor.py — Simple rule-based WCAG 2.2 auditor for HTML documents.
Audits: Headings, Images, Links, Buttons, Form Labels, and Language.
"""
from bs4 import BeautifulSoup
import re

def audit_page(soup: BeautifulSoup) -> list:
    """
    Run general WCAG 2.2 accessibility checks on a BeautifulSoup object.
    Returns a list of finding dicts: {type, severity, criterion, description, fix_hint, snippet}.
    """
    findings = []

    # Helper to truncate long snippets
    def _get_snippet(tag):
        s = str(tag)
        return s[:500] + "..." if len(s) > 500 else s

    # 1. Page Language (SC 3.1.1)
    html_tag = soup.find("html")
    if not html_tag or not html_tag.get("lang"):
        findings.append({
            "type": "language",
            "severity": "error",
            "criterion": "3.1.1",
            "description": "Missing 'lang' attribute on <html> element.",
            "fix_hint": "Add lang=\"en\" (or appropriate language code) to the <html> tag.",
            "snippet": _get_snippet(html_tag) if html_tag else "<html>"
        })

    # 2. Page Title (SC 2.4.2)
    title_tag = soup.find("title")
    if not title_tag or not title_tag.get_text().strip():
        findings.append({
            "type": "title",
            "severity": "error",
            "criterion": "2.4.2",
            "description": "Page is missing a non-empty <title> element.",
            "fix_hint": "Add a descriptive <title> in the <head>.",
            "snippet": _get_snippet(title_tag) if title_tag else "<title>Missing</title>"
        })
    elif title_tag.get_text().strip().lower() in ["untitled", "document", "new page"]:
        findings.append({
            "type": "title",
            "severity": "warning",
            "criterion": "2.4.2",
            "description": "Page title is generic (e.g., 'Untitled').",
            "fix_hint": "Use a unique and descriptive title.",
            "snippet": _get_snippet(title_tag)
        })

    # 3. Headings (SC 1.3.1, 2.4.1)
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    h1s = [h for h in headings if h.name == "h1"]
    
    if not h1s:
        findings.append({
            "type": "headings",
            "severity": "error",
            "criterion": "1.3.1",
            "description": "Missing <h1> heading.",
            "fix_hint": "Add a primary <h1> that describes the page content.",
            "snippet": "No <h1> found in document."
        })
    elif len(h1s) > 1:
        for h in h1s:
            findings.append({
                "type": "headings",
                "severity": "warning",
                "criterion": "1.3.1",
                "description": "Multiple <h1> headings found.",
                "fix_hint": "Use only one <h1> per page for best screen reader experience.",
                "snippet": _get_snippet(h)
            })

    # Check for skipped levels
    last_level = 0
    for h in headings:
        level = int(h.name[1])
        if level > last_level + 1 and last_level != 0:
            findings.append({
                "type": "headings",
                "severity": "warning",
                "criterion": "1.3.1",
                "description": f"Skipped heading level: <{h.name}> follows <h{last_level}>.",
                "fix_hint": "Nesting should be sequential (e.g., h2 followed by h3).",
                "snippet": _get_snippet(h)
            })
        if not h.get_text().strip() and not h.find("img", alt=True):
             findings.append({
                "type": "headings",
                "severity": "error",
                "criterion": "1.3.1",
                "description": f"Empty heading: <{h.name}> has no text.",
                "fix_hint": "Ensure headings have descriptive text.",
                "snippet": _get_snippet(h)
            })
        last_level = level

    # 4. Images (SC 1.1.1)
    images = soup.find_all("img")
    for img in images:
        alt = img.get("alt")
        if alt is None:
            findings.append({
                "type": "image",
                "severity": "error",
                "criterion": "1.1.1",
                "description": f"Image missing alt attribute: {img.get('src', 'unknown')}",
                "fix_hint": "Add alt=\"\" for decorative images content, or a description for informative ones.",
                "snippet": _get_snippet(img)
            })
        elif alt.strip() and re.search(r"\b(Union[image, picture]|Union[photo, graphic]) of\b", alt.lower()):
            findings.append({
                "type": "image",
                "severity": "warning",
                "criterion": "1.1.1",
                "description": f"Redundant alt text: '{alt}' contains 'image of'.",
                "fix_hint": "Alt text shouldn't repeat 'image of' as screen readers already announce it's an image.",
                "snippet": _get_snippet(img)
            })

    # 5. Controls - Links & Buttons (SC 4.1.2)
    links = soup.find_all("a")
    for a in links:
        has_text = bool(a.get_text().strip())
        has_label = bool(a.get("aria-label") or a.get("aria-labelledby") or a.get("title"))
        has_img_alt = bool(a.find("img", alt=True))
        
        if not (has_text or has_label or has_img_alt):
            findings.append({
                "type": "link",
                "severity": "error",
                "criterion": "4.1.2",
                "description": f"Link with no accessible name (href: {a.get('href', '#')}).",
                "fix_hint": "Add descriptive text or an aria-label to the link.",
                "snippet": _get_snippet(a)
            })

    buttons = soup.find_all("button")
    for b in buttons:
        has_text = bool(b.get_text().strip())
        has_label = bool(b.get("aria-label") or b.get("aria-labelledby") or b.get("title"))
        
        if not (has_text or has_label):
            findings.append({
                "type": "button",
                "severity": "error",
                "criterion": "4.1.2",
                "description": "Button with no accessible name.",
                "fix_hint": "Add text content or an aria-label to the button.",
                "snippet": _get_snippet(b)
            })

    # 6. Form Labels (SC 4.1.2, 1.3.1)
    inputs = soup.find_all(["input", "select", "textarea"])
    for inp in inputs:
        if inp.get("type") in ["hidden", "submit", "reset", "button"]:
            continue
            
        inp_id = inp.get("id")
        has_label = False
        if inp_id:
            if soup.find("label", attrs={"for": inp_id}):
                has_label = True
        
        # Parent label check
        if not has_label:
            if inp.find_parent("label"):
                has_label = True
        
        if not has_label:
            if not (inp.get("aria-label") or inp.get("aria-labelledby") or inp.get("title")):
                findings.append({
                    "type": "form",
                    "severity": "error",
                    "criterion": "4.1.2",
                    "description": f"Input field missing label (name: {inp.get('name', 'unnamed')}).",
                    "fix_hint": "Add a <label for=\"...\"> or an aria-label to the input.",
                    "snippet": _get_snippet(inp)
                })

    return findings

    return findings

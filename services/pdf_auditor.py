import io
import fitz  # PyMuPDF
import pdfplumber
from typing import Dict, Any

def audit_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Perform an accessibility audit on a PDF.
    Accepts raw bytes (from file upload or URL fetch).
    Returns a dict with findings, summary, and metadata
    matching the frontend's expected field names.
    """
    findings = []
    passes = []

    try:
        # ── 1. Open with PyMuPDF for metadata + structure checks ──────────────
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        raw_meta = doc.metadata or {}

        # Check 1 — Document Title (WCAG 2.4.2)
        title = raw_meta.get("title", "").strip()
        if not title:
            findings.append(_finding(
                criterion="WCAG 2.4.2",
                tier="Critical",
                description="Document title is missing from metadata.",
                fix_hint="Open Document Properties → Description and add a descriptive title."
            ))
        else:
            passes.append(f"Title present: \"{title}\"")

        # Check 2 — Language declaration (WCAG 3.1.1)
        catalog_keys = doc.xref_get_keys(doc.pdf_catalog())
        doc_lang = ""
        if "Lang" in catalog_keys:
            try:
                doc_lang = doc.pdf_catalog_get_key("Lang")
            except Exception:
                pass

        if not doc_lang:
            findings.append(_finding(
                criterion="WCAG 3.1.1",
                tier="Warning",
                description="Document primary language is not declared.",
                fix_hint="Set the document language (e.g. 'en-US') in PDF properties or via Acrobat → Accessibility → Set Language."
            ))
        else:
            passes.append(f"Language declared: {doc_lang}")

        # Check 3 — Tagged PDF (PDF/UA-1 — critical for screen readers)
        is_tagged = False
        try:
            mark_info = doc.pdf_catalog_get_key("MarkInfo")
            is_tagged = "Marked true" in str(mark_info)
        except Exception:
            pass

        if not is_tagged:
            findings.append(_finding(
                criterion="PDF/UA-1",
                tier="Critical",
                description="PDF is not tagged. Screen readers cannot determine reading order.",
                fix_hint="Use 'Save as Tagged PDF' in your authoring tool, or remediate with Adobe Acrobat's Accessibility Checker."
            ))
        else:
            passes.append("Document is tagged (reading order accessible)")

        # Check 4 — Author / creator (best practice)
        author = raw_meta.get("author", "").strip()
        if not author:
            findings.append(_finding(
                criterion="Best Practice",
                tier="Manual",
                description="Document author/creator is not set in metadata.",
                fix_hint="Set the Author field in Document Properties for provenance and discoverability."
            ))
        else:
            passes.append(f"Author set: \"{author}\"")

        # ── 2. Open with pdfplumber for content-level analysis ────────────────
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            total_pages = len(pdf.pages)
            total_images = sum(len(page.images) for page in pdf.pages)

            if total_images > 0:
                findings.append(_finding(
                    criterion="WCAG 1.1.1",
                    tier="Manual",
                    description=f"Found {total_images} image(s) across {total_pages} page(s). Verify all informative images have alternative text.",
                    fix_hint="Each <Figure> tag in the PDF structure tree must have an /Alt entry describing the image."
                ))

        doc.close()

        # ── Summary ───────────────────────────────────────────────────────────
        summary = {
            "critical": sum(1 for f in findings if f["tier"] == "Critical"),
            "warning":  sum(1 for f in findings if f["tier"] == "Warning"),
            "manual":   sum(1 for f in findings if f["tier"] == "Manual"),
            "passes":   len(passes),
            "total":    len(findings),
        }
        all_clear = summary["critical"] == 0 and summary["warning"] == 0

        return {
            "element_type": "PDF",
            "findings": findings,
            "passes": passes,
            "summary": summary,
            "all_clear": all_clear,
            "metadata": {
                "title":      title,
                "author":     author,
                "pages":      total_pages,
                "is_tagged":  is_tagged,
            },
            "error": None
        }

    except Exception as e:
        return {
            "element_type": "PDF",
            "findings": [],
            "passes": [],
            "summary": {"critical": 0, "warning": 0, "manual": 0, "passes": 0, "total": 0},
            "all_clear": False,
            "metadata": None,
            "error": f"PDF audit failed: {str(e)}"
        }


def _finding(criterion: str, tier: str, description: str, fix_hint: str) -> dict:
    return {
        "criterion": criterion,
        "tier":       tier,
        "description": description,
        "fix_hint":    fix_hint,
    }

"""
pdf_auditor.py — Complete PDF accessibility auditor
Checks: Title, Language, Tags, Headings, Tables, Forms, Images, Color Contrast
"""
import io
import fitz  # PyMuPDF
import pdfplumber
from typing import Dict, Any, List

def audit_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Perform a comprehensive accessibility audit on a PDF.
    Returns findings with plain-English fix instructions.
    """
    findings = []
    passes = []
    warnings = []
    
    try:
        # ── 1. Open with PyMuPDF ──────────────────────────────────────────────
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        raw_meta = doc.metadata or {}
        
        # ── 2. Document Title (WCAG 2.4.2) ─────────────────────────────────────
        title = raw_meta.get("title", "").strip()
        if not title:
            findings.append(_finding(
                criterion="WCAG 2.4.2",
                tier="Critical",
                description="Document title is missing from metadata.",
                fix_hint="Open Document Properties (File → Properties) and add a descriptive title under 'Title' field."
            ))
        else:
            passes.append(f"Title present: \"{title}\"")
        
        # ── 3. Language Declaration (WCAG 3.1.1) ───────────────────────────────
        doc_lang = ""
        try:
            catalog_keys = doc.xref_get_keys(doc.pdf_catalog())
            if "Lang" in catalog_keys:
                doc_lang = doc.pdf_catalog_get_key("Lang")
        except Exception:
            pass
        
        if not doc_lang:
            findings.append(_finding(
                criterion="WCAG 3.1.1",
                tier="Critical",
                description="Document language is not declared. Screen readers cannot determine pronunciation.",
                fix_hint="Set document language in Properties → Advanced → Language, or use File → Properties → Language."
            ))
        else:
            passes.append(f"Language declared: {doc_lang}")
        
        # ── 4. Tagged PDF (PDF/UA-1) ──────────────────────────────────────────
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
                fix_hint="In Adobe Acrobat: Tools → Accessibility → Add Tags to Document. Or re-save as 'Tagged PDF' from source."
            ))
        else:
            passes.append("Document is tagged (accessible reading order)")
        
        # ── 5. Heading Structure (WCAG 1.3.1) ─────────────────────────────────
        heading_count = 0
        heading_hierarchy_issue = False
        try:
            # Check for heading tags in the structure tree
            toc = doc.get_toc()
            if toc:
                heading_count = len(toc)
                # Check if headings follow hierarchy (H1 → H2 → H3)
                prev_level = 0
                for item in toc:
                    level = item[0]
                    if level > prev_level + 1:
                        heading_hierarchy_issue = True
                        break
                    prev_level = level
            else:
                findings.append(_finding(
                    criterion="WCAG 1.3.1",
                    tier="Warning",
                    description="No heading structure found. Screen readers cannot navigate the document.",
                    fix_hint="Use heading styles (Heading 1, Heading 2, etc.) in your authoring tool. In Acrobat: Tags panel → Create tags from headings."
                ))
        except Exception:
            pass
        
        if heading_count > 0 and heading_hierarchy_issue:
            findings.append(_finding(
                criterion="WCAG 1.3.1",
                tier="Warning",
                description="Heading hierarchy is broken (e.g., H2 followed by H4, or H3 with no H2 before it).",
                fix_hint="Ensure headings follow logical order: H1, then H2, then H3. Don't skip levels."
            ))
        elif heading_count > 0 and not heading_hierarchy_issue:
            passes.append(f"Heading structure found: {heading_count} headings in correct hierarchy")
        
        # ── 6. Table Headers (WCAG 1.3.1) ──────────────────────────────────────
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            total_pages = len(pdf.pages)
            total_images = 0
            table_issues = 0
            
            for page_num, page in enumerate(pdf.pages, 1):
                # Check tables
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) > 0:
                        # Check if first row might be headers
                        first_row = table[0] if table else []
                        has_headers = any(cell and str(cell).strip() for cell in first_row)
                        if not has_headers:
                            table_issues += 1
                            if table_issues <= 3:  # Limit duplicate warnings
                                findings.append(_finding(
                                    criterion="WCAG 1.3.1",
                                    tier="Warning",
                                    description=f"Table on page {page_num} appears to have no header row.",
                                    fix_hint="Designate the first row as headers in your authoring tool. In Acrobat: Tags panel → Table Editor → mark header cells."
                                ))
                
                # Count images
                total_images += len(page.images)
        
        # ── 7. Form Field Labels (WCAG 3.3.2, 4.1.2) ───────────────────────────
        form_field_count = 0
        unlabeled_fields = 0
        try:
            # Check for form fields (widget annotations)
            for page_num in range(len(doc)):
                page = doc[page_num]
                widgets = page.widgets()
                if widgets:
                    for widget in widgets:
                        form_field_count += 1
                        # Check if field has a label/tooltip
                        if not widget.field_label and not widget.field_name:
                            unlabeled_fields += 1
                            if unlabeled_fields <= 3:  # Limit duplicate warnings
                                findings.append(_finding(
                                    criterion="WCAG 3.3.2",
                                    tier="Warning",
                                    description=f"Form field on page {page_num + 1} has no label. Screen readers can't identify its purpose.",
                                    fix_hint="In Acrobat: Forms → Edit → right-click field → Properties → General tab → add Tooltip or Name."
                                ))
        except Exception:
            pass
        
        if form_field_count > 0 and unlabeled_fields == 0:
            passes.append(f"All {form_field_count} form fields have labels")
        elif form_field_count > 0:
            passes.append(f"Found {form_field_count} form fields, {unlabeled_fields} need labels")
        
        # ── 8. Color Contrast Warning (WCAG 1.4.3) ─────────────────────────────
        # Note: Full color contrast requires analysis of all text colors
        # This is a placeholder for a more comprehensive check
        findings.append(_finding(
            criterion="WCAG 1.4.3",
            tier="Manual",
            description="Color contrast cannot be fully automated. Text must have sufficient contrast against background.",
            fix_hint="Use a color contrast checker (like WebAIM's) to verify text meets 4.5:1 ratio for normal text, 3:1 for large text."
        ))
        
        # ── 9. Image Alt Text (WCAG 1.1.1) ────────────────────────────────────
        if total_images > 0:
            # Check if images have alt text (requires tagged PDF structure)
            # This is a simplified check
            findings.append(_finding(
                criterion="WCAG 1.1.1",
                tier="Manual",
                description=f"Found {total_images} image(s) across {total_pages} page(s). Verify each has meaningful alternative text.",
                fix_hint="In Acrobat: Tags panel → find each <Figure> tag → right-click → Properties → add Alt text describing the image."
            ))
        else:
            passes.append("No images detected")
        
        # ── 10. Reading Order (WCAG 1.3.2) ────────────────────────────────────
        if not is_tagged:
            # Already flagged above
            pass
        else:
            passes.append("Document is tagged — reading order can be verified")
        
        # ── 11. Author/Creator (Best practice) ───────────────────────────────
        author = raw_meta.get("author", "").strip()
        if not author:
            warnings.append("Author field is empty (best practice for document provenance)")
        
        # ── Summary ───────────────────────────────────────────────────────────
        summary = {
            "critical": sum(1 for f in findings if f["tier"] == "Critical"),
            "warning": sum(1 for f in findings if f["tier"] == "Warning"),
            "manual": sum(1 for f in findings if f["tier"] == "Manual"),
            "passes": len(passes),
            "total": len(findings),
        }
        all_clear = summary["critical"] == 0 and summary["warning"] == 0
        
        doc.close()
        
        return {
            "element_type": "PDF",
            "findings": findings,
            "warnings": warnings,
            "passes": passes,
            "summary": summary,
            "all_clear": all_clear,
            "metadata": {
                "title": title,
                "author": author,
                "pages": total_pages,
                "is_tagged": is_tagged,
                "has_headings": heading_count > 0,
                "has_form_fields": form_field_count > 0,
                "image_count": total_images
            },
            "error": None
        }
        
    except Exception as e:
        return {
            "element_type": "PDF",
            "findings": [],
            "warnings": [],
            "passes": [],
            "summary": {"critical": 0, "warning": 0, "manual": 0, "passes": 0, "total": 0},
            "all_clear": False,
            "metadata": None,
            "error": f"PDF audit failed: {str(e)}"
        }


def _finding(criterion: str, tier: str, description: str, fix_hint: str) -> dict:
    """Build a standardized finding dict with plain-English fix instructions."""
    return {
        "criterion": criterion,
        "tier": tier,
        "description": description,
        "fix_hint": fix_hint,
    }
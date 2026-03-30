"""
dom_analyzer.py — Extracts descriptive context from the HTML surrounding
an <iframe> element. Walks parent and sibling elements up to two levels
to find headings, figcaptions, labels, or paragraphs that describe the iframe.
"""
from bs4 import BeautifulSoup, Tag
from typing import Optional, Dict, List

CONTEXT_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6",
                "figcaption", "label", "p", "caption", "legend"]


def extract_context(html_snippet: str) -> dict:
    """
    Given an HTML snippet (may include surrounding HTML or just the iframe),
    return the best contextual descriptor.

    Returns:
        {
          "context_text": Optional[str],
          "context_source": Optional[str],  # e.g. "h2", "figcaption"
        }
    """
    if not html_snippet:
        return {"context_text": None, "context_source": None}

    soup = BeautifulSoup(html_snippet, "lxml")
    iframe = soup.find("iframe")

    if not iframe:
        return {"context_text": None, "context_source": None}

    # 1. Check existing aria-label or title on the iframe itself
    for attr in ("aria-label", "title"):
        val = iframe.get(attr, "").strip()
        if val:
            return {"context_text": val, "context_source": attr}

    # 2. Walk parent elements (up to 2 levels)
    candidates = []
    parent = iframe.parent
    for _ in range(2):
        if parent is None or not isinstance(parent, Tag):
            break
        for tag_name in CONTEXT_TAGS:
            found = parent.find(tag_name)
            if found:
                text = found.get_text(separator=" ", strip=True)
                if text:
                    candidates.append((tag_name, text))
        parent = parent.parent

    # 3. Check preceding and following siblings
    for sibling in list(iframe.previous_siblings) + list(iframe.next_siblings):
        if not isinstance(sibling, Tag):
            continue
        if sibling.name in CONTEXT_TAGS:
            text = sibling.get_text(separator=" ", strip=True)
            if text:
                candidates.append((sibling.name, text))
        # Check children of sibling
        for tag_name in CONTEXT_TAGS:
            found = sibling.find(tag_name)
            if found:
                text = found.get_text(separator=" ", strip=True)
                if text:
                    candidates.append((tag_name, text))

    if candidates:
        # Prefer headings, then figcaption/label, then p
        priority = ["h1", "h2", "h3", "figcaption", "caption", "legend",
                    "label", "h4", "h5", "h6", "p"]
        candidates.sort(key=lambda c: priority.index(c[0])
                        if c[0] in priority else 99)
        source, text = candidates[0]
        # Truncate if very long
        if len(text) > 200:
            text = text[:197] + "..."
        return {"context_text": text, "context_source": source}

    return {"context_text": None, "context_source": None}

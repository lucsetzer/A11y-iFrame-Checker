"""
sanitizer.py — Strips scripts, styles, event handlers, and PII patterns
from HTML before passing it to any downstream service.
"""
import re
import bleach

# Tags allowed through for context analysis (no executable content)
ALLOWED_TAGS = [
    "a", "abbr", "b", "blockquote", "br", "caption", "cite", "code",
    "col", "colgroup", "dd", "del", "dfn", "div", "dl", "dt", "em",
    "figcaption", "figure", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "i", "img", "ins", "kbd", "li", "mark", "ol", "p",
    "pre", "q", "s", "samp", "section", "small", "span", "strong",
    "sub", "sup", "table", "tbody", "td", "th", "thead", "time",
    "tr", "u", "ul", "var", "wbr", "iframe", "frame", "frameset",
]

ALLOWED_ATTRIBUTES = {
    "*": ["class", "id", "lang", "dir", "aria-label", "aria-labelledby",
          "aria-describedby", "role"],
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "width", "height"],
    "iframe": ["src", "title", "name", "id", "width", "height",
               "frameborder", "allowfullscreen", "loading", "allow",
               "sandbox"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan", "scope"],
    "time": ["datetime"],
}

# PII patterns to redact before LLM submission
_PII_PATTERNS = [
    # Email addresses
    (re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'), "[EMAIL]"),
    # US phone numbers
    (re.compile(r'\b(\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b'), "[PHONE]"),
    # US SSN
    (re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'), "[SSN]"),
    # Credit card-like patterns
    (re.compile(r'\b(?:\d[ \-]?){13,16}\b'), "[CARD]"),
]


def sanitize_html(raw_html: str) -> str:
    """
    Clean HTML: strip scripts/styles/events, then redact PII.
    Returns a safe string suitable for LLM submission.
    """
    if not raw_html:
        return ""
    cleaned = bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
        strip_comments=True,
    )
    return redact_pii(cleaned)


def redact_pii(text: str) -> str:
    """Replace PII patterns with safe placeholders."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text

"""
embed_checker.py — WCAG 2.2 accessibility audit for embedded content elements.
Supports: <iframe>, <object>, <embed>, <video>, <audio>

For each element, runs applicable WCAG 2.2 checks and returns:
  - findings: list of {criterion, level, severity, description, technique, fix}
  - element_type: str
  - minimal_fix: str   (safe attribute additions only — never breaks vendor code)
  - full_fix: str      (wrapper + all recommended attributes)
  - summary: {errors, warnings, passes, total}
"""
import re
from bs4 import BeautifulSoup, Tag

# ── WCAG references ───────────────────────────────────────────────────────────

WCAG_BASE = "https://www.w3.org/WAI/WCAG22/Understanding/"

CRITERIA = {
    "1.1.1": {"name": "Non-text Content",       "level": "A",  "url": WCAG_BASE + "non-text-content"},
    "1.2.1": {"name": "Audio-only / Video-only", "level": "A",  "url": WCAG_BASE + "audio-only-and-video-only-prerecorded"},
    "1.2.2": {"name": "Captions (Prerecorded)",  "level": "A",  "url": WCAG_BASE + "captions-prerecorded"},
    "1.2.3": {"name": "Audio Description / Media Alternative", "level": "A", "url": WCAG_BASE + "audio-description-or-media-alternative-prerecorded"},
    "1.2.4": {"name": "Captions (Live)",         "level": "AA", "url": WCAG_BASE + "captions-live"},
    "1.2.5": {"name": "Audio Description",       "level": "AA", "url": WCAG_BASE + "audio-description-prerecorded"},
    "1.3.1": {"name": "Info and Relationships",  "level": "A",  "url": WCAG_BASE + "info-and-relationships"},
    "2.1.1": {"name": "Keyboard",                "level": "A",  "url": WCAG_BASE + "keyboard"},
    "4.1.2": {"name": "Name, Role, Value",       "level": "A",  "url": WCAG_BASE + "name-role-value"},
}

GENERIC_TITLES = {
    "iframe", "frame", "embedded", "embed", "content", "widget",
    "banner", "ad", "advertisement", "untitled", "video", "audio",
    "object", "media", "player",
}


def _finding(criterion, severity, description, technique, fix_hint):
    """Build a standardized finding dict."""
    c = CRITERIA.get(criterion, {})
    return {
        "criterion":   criterion,
        "criterion_name": c.get("name", ""),
        "level":       c.get("level", "A"),
        "url":         c.get("url", ""),
        "severity":    severity,          # "error" | "warning" | "pass" | "info"
        "description": description,
        "technique":   technique,
        "fix_hint":    fix_hint,
    }


def _is_generic_title(title: str) -> bool:
    return not title or title.strip().lower() in GENERIC_TITLES or len(title.strip()) < 4


# ── Element-specific checkers ─────────────────────────────────────────────────

def _check_iframe(el: Tag) -> list[dict]:
    findings = []
    title = (el.get("title") or "").strip()

    if not title:
        findings.append(_finding(
            "4.1.2", "error",
            "Missing title attribute. Screen readers cannot identify the purpose of this frame.",
            "H64",
            'Add title="[Descriptive purpose]" to the <iframe> tag.',
        ))
    elif _is_generic_title(title):
        findings.append(_finding(
            "4.1.2", "warning",
            f'Title attribute "{title}" is too generic. It must describe the specific content or purpose.',
            "H64",
            f'Replace title="{title}" with a specific description, e.g. title="2025 Campus Map — Google Maps".',
        ))
    else:
        findings.append(_finding(
            "4.1.2", "pass",
            f'title="{title}" is present and appears descriptive.',
            "H64", "",
        ))

    # Keyboard: tabindex=-1 blocks keyboard users from entering the frame
    tabindex = el.get("tabindex", "")
    if str(tabindex).strip() == "-1":
        findings.append(_finding(
            "2.1.1", "error",
            'tabindex="-1" prevents keyboard users from accessing iframe content.',
            "G202",
            'Remove tabindex="-1" unless the iframe is purely decorative and also has aria-hidden="true".',
        ))

    return findings


def _check_object(el: Tag) -> list[dict]:
    findings = []
    title = (el.get("title") or "").strip()

    if not title:
        findings.append(_finding(
            "4.1.2", "error",
            "Missing title attribute on <object>. Screen readers cannot identify the embedded content.",
            "H27",
            'Add title="[Descriptive label]" to the <object> tag.',
        ))
    elif _is_generic_title(title):
        findings.append(_finding(
            "4.1.2", "warning",
            f'title="{title}" is too generic.',
            "H27",
            "Replace with a specific description of the embedded content.",
        ))
    else:
        findings.append(_finding(
            "4.1.2", "pass",
            f'title="{title}" is present and appears descriptive.',
            "H27", "",
        ))

    # Fallback content check
    inner_text = el.get_text(strip=True)
    inner_html = el.decode_contents().strip()
    has_fallback = bool(inner_text or inner_html)

    if not has_fallback:
        findings.append(_finding(
            "1.1.1", "error",
            "No fallback content between <object> tags. If the plugin/media cannot load, users receive nothing.",
            "H27",
            "Add a text alternative or link between the opening and closing <object> tags.",
        ))
    else:
        findings.append(_finding(
            "1.1.1", "pass",
            "Fallback content is present between <object> tags.",
            "H27", "",
        ))

    return findings


def _check_embed(el: Tag) -> list[dict]:
    findings = []
    title = (el.get("title") or "").strip()

    if not title:
        findings.append(_finding(
            "4.1.2", "error",
            "Missing title attribute on <embed>. Screen readers cannot identify the embedded content.",
            "H64",
            'Add title="[Descriptive label]" to the <embed> tag.',
        ))
    elif _is_generic_title(title):
        findings.append(_finding(
            "4.1.2", "warning",
            f'title="{title}" is too generic.',
            "H64",
            "Replace with a specific description.",
        ))
    else:
        findings.append(_finding(
            "4.1.2", "pass",
            f'title="{title}" present and descriptive.',
            "H64", "",
        ))

    # Note: <embed> is a void element — no fallback content is possible
    findings.append(_finding(
        "1.1.1", "info",
        "<embed> cannot contain fallback content (void element). Consider using <object> instead if a text alternative is needed.",
        "H27",
        "Wrap in <object> if fallback content is required; or ensure title is highly descriptive.",
    ))

    return findings


def _check_video(el: Tag) -> list[dict]:
    findings = []

    # Captions — SC 1.2.2 (Level A)
    tracks = el.find_all("track")
    caption_tracks = [t for t in tracks if (t.get("kind") or "").lower() in ("captions", "subtitles")]
    desc_tracks    = [t for t in tracks if (t.get("kind") or "").lower() == "descriptions"]

    if not caption_tracks:
        findings.append(_finding(
            "1.2.2", "error",
            "No captions track found. Prerecorded video with audio must have synchronized captions.",
            "G87",
            'Add <track kind="captions" src="captions.vtt" srclang="en" label="English" default> inside the <video> element.',
        ))
    else:
        src = caption_tracks[0].get("src", "")
        findings.append(_finding(
            "1.2.2", "pass",
            f'Captions track found ({src or "inline"}).',
            "G87", "",
        ))

    # Audio description — SC 1.2.5 (Level AA) / 1.2.3 (Level A alternative)
    if not desc_tracks:
        findings.append(_finding(
            "1.2.5", "warning",
            "No audio description track found. Visual information not conveyed in the audio should have an audio description (Level AA).",
            "G78",
            'Add <track kind="descriptions" src="descriptions.vtt" srclang="en" label="Audio Description">.',
        ))
    else:
        findings.append(_finding(
            "1.2.5", "pass",
            "Audio description track present.",
            "G78", "",
        ))

    # Keyboard access — controls attribute
    if el.get("controls") is None:
        findings.append(_finding(
            "2.1.1", "error",
            'Missing controls attribute. Without it, keyboard users cannot pause, stop, or adjust volume.',
            "G202",
            "Add the controls attribute: <video controls ...>",
        ))
    else:
        findings.append(_finding(
            "2.1.1", "pass",
            "controls attribute present — keyboard users can operate the player.",
            "G202", "",
        ))

    # Autoplay warning
    if el.get("autoplay") is not None and el.get("muted") is None:
        findings.append(_finding(
            "1.2.2", "warning",
            "autoplay without muted may start audio unexpectedly, which can disorient screen reader users.",
            "G171",
            'Add muted to the autoplay video, or remove autoplay. If autoplay is required, ensure a stop mechanism is available.',
        ))

    # Accessible name
    aria_label = (el.get("aria-label") or "").strip()
    aria_labelledby = (el.get("aria-labelledby") or "").strip()
    title = (el.get("title") or "").strip()
    if not aria_label and not aria_labelledby and not title:
        findings.append(_finding(
            "4.1.2", "warning",
            "No accessible name on <video>. Add aria-label or title so screen readers can identify the content.",
            "ARIA14",
            'Add aria-label="[Descriptive title]" to the <video> element.',
        ))
    else:
        findings.append(_finding(
            "4.1.2", "pass",
            "Accessible name present on <video>.",
            "ARIA14", "",
        ))

    return findings


def _check_audio(el: Tag) -> list[dict]:
    findings = []

    # Keyboard access
    if el.get("controls") is None:
        findings.append(_finding(
            "2.1.1", "error",
            "Missing controls attribute. Keyboard users cannot operate the audio player.",
            "G202",
            "Add the controls attribute: <audio controls ...>",
        ))
    else:
        findings.append(_finding(
            "2.1.1", "pass",
            "controls attribute present.",
            "G202", "",
        ))

    # Transcript advisory — SC 1.2.1 (Level A)
    findings.append(_finding(
        "1.2.1", "info",
        "Prerecorded audio-only content requires a text transcript (SC 1.2.1, Level A). Verify that a link to a transcript is provided near this element in the page.",
        "G158",
        "Add a visible link to a full text transcript adjacent to the <audio> element.",
    ))

    # Autoplay
    if el.get("autoplay") is not None:
        findings.append(_finding(
            "1.2.4", "warning",
            "autoplay on <audio> can disrupt screen reader users who rely on the audio channel to navigate.",
            "G171",
            "Remove autoplay, or provide a mechanism to stop audio within the first 3 seconds.",
        ))

    # Accessible name
    aria_label = (el.get("aria-label") or "").strip()
    title = (el.get("title") or "").strip()
    if not aria_label and not title:
        findings.append(_finding(
            "4.1.2", "warning",
            "No accessible name on <audio>. Add aria-label or title.",
            "ARIA14",
            'Add aria-label="[Descriptive title]" to the <audio> element.',
        ))
    else:
        findings.append(_finding(
            "4.1.2", "pass",
            "Accessible name present.",
            "ARIA14", "",
        ))

    return findings


# ── Fix generators ────────────────────────────────────────────────────────────

def _inject_attr(el: Tag, attr: str, value: str) -> Tag:
    """Safely set an attribute on a BS4 tag (non-destructive to others)."""
    el[attr] = value
    return el


def _generate_minimal_fix(el: Tag, element_type: str, findings: list[dict]) -> str:
    """
    Apply ONLY safe attribute additions/changes.
    Never alters src, data, type, or any functional vendor attribute.
    """
    import copy
    fixed = copy.copy(el)

    errors_warnings = [f for f in findings if f["severity"] in ("error", "warning")]

    for f in errors_warnings:
        crit = f["criterion"]

        if crit == "4.1.2" and not (el.get("title") or "").strip():
            fixed["title"] = "[Add descriptive title here]"

        elif crit == "2.1.1":
            if element_type in ("video", "audio") and el.get("controls") is None:
                fixed["controls"] = True
            # Don't fix tabindex here — removing attrs is riskier

        elif crit == "1.2.2" and element_type == "video":
            # Will be handled in full fix (need to add child <track>)
            pass

    return str(fixed)


def _generate_full_fix(el: Tag, element_type: str, findings: list[dict]) -> str:
    """
    Full accessible version: wrapper + all recommended attributes.
    The original vendor embed attributes are preserved unchanged.
    """
    import copy
    fixed = copy.copy(el)

    # Ensure accessible name
    if not (fixed.get("title") or fixed.get("aria-label") or "").strip():
        if element_type in ("iframe", "embed", "object"):
            fixed["title"] = "[Add descriptive title here]"
        else:
            fixed["aria-label"] = "[Add descriptive title here]"

    # Video-specific
    if element_type == "video":
        if fixed.get("controls") is None:
            fixed["controls"] = True
        # Add track placeholders if not present
        soup_inner = BeautifulSoup(str(fixed), "lxml")
        vid = soup_inner.find("video")
        if vid:
            has_captions = any(
                (t.get("kind") or "").lower() in ("captions", "subtitles")
                for t in vid.find_all("track")
            )
            has_desc = any(
                (t.get("kind") or "").lower() == "descriptions"
                for t in vid.find_all("track")
            )
            if not has_captions:
                new_track = soup_inner.new_tag("track", kind="captions", src="captions.vtt",
                                               srclang="en", label="English", default=True)
                vid.append(new_track)
            if not has_desc:
                new_track = soup_inner.new_tag("track", kind="descriptions",
                                               src="descriptions.vtt", srclang="en",
                                               label="Audio Description")
                vid.append(new_track)

            inner_html = str(vid)
            label = vid.get("aria-label") or "[Add descriptive title here]"
            return (
                f'<div role="region" aria-label="{label}">\n'
                f'  {inner_html}\n'
                f'  <p><a href="transcript.html">View full transcript</a></p>\n'
                f'</div>'
            )

    # Audio-specific
    if element_type == "audio":
        if fixed.get("controls") is None:
            fixed["controls"] = True
        label = fixed.get("aria-label") or "[Add descriptive title here]"
        return (
            f'<div role="region" aria-label="{label}">\n'
            f'  {str(fixed)}\n'
            f'  <p><a href="transcript.html">View full transcript</a></p>\n'
            f'</div>'
        )

    # Object: add fallback if missing
    if element_type == "object":
        inner = el.decode_contents().strip()
        if not inner:
            title_val = fixed.get("title") or "[Descriptive label]"
            fixed.clear()
            fallback_text = f"<p>Embedded content: {title_val}. <a href='#'>View alternative version</a></p>"
            return str(fixed).replace("></object>", f">{fallback_text}</object>")

    return str(fixed)


# ── Main entry point ──────────────────────────────────────────────────────────

SUPPORTED_ELEMENTS = ("iframe", "object", "embed", "video", "audio")

CHECKER_MAP = {
    "iframe":  _check_iframe,
    "object":  _check_object,
    "embed":   _check_embed,
    "video":   _check_video,
    "audio":   _check_audio,
}


def check_embed(snippet: str) -> dict:
    """
    Run a full WCAG 2.2 accessibility audit on an embedded content snippet.

    Returns:
        {
          element_type: str,
          findings: list[dict],
          minimal_fix: str,
          full_fix: str,
          summary: {errors, warnings, passes, info, total},
          error: str | None   (parse errors)
        }
    """
    if not snippet or not snippet.strip():
        return {"error": "No snippet provided.", "element_type": None, "findings": [],
                "minimal_fix": "", "full_fix": "", "summary": {}}

    soup = BeautifulSoup(snippet.strip(), "lxml")

    # Detect element
    el = None
    element_type = None
    for tag_name in SUPPORTED_ELEMENTS:
        el = soup.find(tag_name)
        if el:
            element_type = tag_name
            break

    if not el or not element_type:
        return {
            "error": (
                f"No supported embed element found. "
                f"Supported: {', '.join(f'<{t}>' for t in SUPPORTED_ELEMENTS)}."
            ),
            "element_type": None,
            "findings": [],
            "minimal_fix": "",
            "full_fix": "",
            "summary": {},
        }

    # Run checks
    checker = CHECKER_MAP[element_type]
    findings = checker(el)

    # Generate fixes
    minimal_fix = _generate_minimal_fix(el, element_type, findings)
    full_fix = _generate_full_fix(el, element_type, findings)

    # Summary counts
    summary = {
        "errors":   sum(1 for f in findings if f["severity"] == "error"),
        "warnings": sum(1 for f in findings if f["severity"] == "warning"),
        "passes":   sum(1 for f in findings if f["severity"] == "pass"),
        "info":     sum(1 for f in findings if f["severity"] == "info"),
        "total":    len(findings),
    }

    return {
        "element_type": element_type,
        "findings": findings,
        "minimal_fix": minimal_fix,
        "full_fix": full_fix,
        "summary": summary,
        "error": None,
    }

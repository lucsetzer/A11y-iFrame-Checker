"""
heuristics.py — Primary layer: pattern-match known iframe platforms and
extract title candidates without any LLM call.

Returns:
    {
      "confidence": "high" | "medium" | "low",
      "platform": Optional[str],
      "candidates": [ {"title": str, "rationale": str} ],
    }
"""
import re
from urllib.parse import urlparse, parse_qs
from typing import Union, Optional, Tuple, List, Dict
from services.fetcher import fetch_oembed_title

# ── Platform detection patterns ──────────────────────────────────────────────

PLATFORM_PATTERNS = [
    {
        "platform": "youtube",
        "patterns": [
            re.compile(r"youtube\.com/embed/([A-Za-z0-9_\-]+)"),
            re.compile(r"youtube-nocookie\.com/embed/([A-Za-z0-9_\-]+)"),
        ],
        "oembed": True,
    },
    {
        "platform": "vimeo",
        "patterns": [
            re.compile(r"player\.vimeo\.com/video/(\d+)"),
        ],
        "oembed": True,
    },
    {
        "platform": "google_maps",
        "patterns": [
            re.compile(r"google\.com/maps/embed"),
        ],
        "oembed": False,
    },
    {
        "platform": "google_forms",
        "patterns": [
            re.compile(r"docs\.google\.com/forms/"),
        ],
        "oembed": False,
    },
    {
        "platform": "google_docs",
        "patterns": [
            re.compile(r"docs\.google\.com/document/"),
        ],
        "oembed": False,
    },
    {
        "platform": "google_slides",
        "patterns": [
            re.compile(r"docs\.google\.com/presentation/"),
        ],
        "oembed": False,
    },
    {
        "platform": "google_calendar",
        "patterns": [
            re.compile(r"calendar\.google\.com/"),
        ],
        "oembed": False,
    },
    {
        "platform": "tableau",
        "patterns": [
            re.compile(r"public\.tableau\.com/"),
            re.compile(r"tableau\.com/"),
        ],
        "oembed": False,
    },
    {
        "platform": "arcgis",
        "patterns": [
            re.compile(r"arcgis\.com/"),
            re.compile(r"esri\.com/"),
        ],
        "oembed": False,
    },
    {
        "platform": "microsoft_forms",
        "patterns": [
            re.compile(r"forms\.office\.com/"),
            re.compile(r"forms\.microsoft\.com/"),
        ],
        "oembed": False,
    },
    {
        "platform": "microsoft_stream",
        "patterns": [
            re.compile(r"stream\.microsoft\.com/"),
        ],
        "oembed": False,
    },
    {
        "platform": "panopto",
        "patterns": [
            re.compile(r"panopto\.com/"),
            re.compile(r"\.hosted\.panopto\.com/"),
        ],
        "oembed": False,
    },
    {
        "platform": "kaltura",
        "patterns": [
            re.compile(r"kaltura\.com/"),
        ],
        "oembed": False,
    },
    {
        "platform": "libcal",
        "patterns": [
            re.compile(r"libcal\.com/"),
        ],
        "oembed": False,
    },
    {
        "platform": "springshare",
        "patterns": [
            re.compile(r"libguides\.com/"),
            re.compile(r"springshare\.com/"),
        ],
        "oembed": False,
    },
    {
        "platform": "sway",
        "patterns": [
            re.compile(r"sway\.office\.com/"),
        ],
        "oembed": False,
    },
]

# ── Human-readable platform labels ───────────────────────────────────────────

PLATFORM_LABELS = {
    "youtube":           "YouTube Video",
    "vimeo":             "Vimeo Video",
    "google_maps":       "Google Maps",
    "google_forms":      "Google Form",
    "google_docs":       "Google Document",
    "google_slides":     "Google Slides Presentation",
    "google_calendar":   "Google Calendar",
    "tableau":           "Tableau Interactive Visualization",
    "arcgis":            "ArcGIS Interactive Map",
    "microsoft_forms":   "Microsoft Form",
    "microsoft_stream":  "Microsoft Stream Video",
    "panopto":           "Panopto Video",
    "kaltura":           "Kaltura Video",
    "libcal":            "Library Appointment Scheduling Calendar",
    "springshare":       "LibGuides Research Guide",
    "sway":              "Microsoft Sway Presentation",
}

WCAG_RATIONALE = (
    "WCAG 2.2 Success Criterion 4.1.2 (Name, Role, Value) and "
    "Technique H64 require that all <iframe> elements have a "
    "meaningful title attribute that describes the embedded content "
    "to screen reader users."
)


def _detect_platform(src: str) -> Tuple[Optional[str], Optional[dict]]:
    """Return (platform_key, pattern_config) or (None, None)."""
    for config in PLATFORM_PATTERNS:
        for pat in config["patterns"]:
            if pat.search(src):
                return config["platform"], config
    return None, None


def _extract_maps_query(src: str) -> Optional[str]:
    """Try to extract a location query from a Google Maps embed URL."""
    parsed = urlparse(src)
    params = parse_qs(parsed.query)
    for key in ("q", "query", "place"):
        vals = params.get(key, [])
        if vals:
            return vals[0]
    # Try to find embedded 'q' in the pb parameter (complex encoded URL)
    return None


def _slug_to_label(text: str) -> str:
    """Convert a URL slug or attribute value to a readable label."""
    text = re.sub(r"[_\-.]", " ", text)
    text = re.sub(r"\s+", " ", text).strip().title()
    return text


def run(iframe_attrs: dict) -> dict:
    """
    iframe_attrs: dict with keys like 'src', 'title', 'name', 'id'
    Returns heuristic result with confidence, platform, candidates.
    """
    src = iframe_attrs.get("src", "").strip()
    existing_title = iframe_attrs.get("title", "").strip()
    name_attr = iframe_attrs.get("name", "").strip()
    id_attr = iframe_attrs.get("id", "").strip()

    platform, config = _detect_platform(src)

    # ── HIGH CONFIDENCE: Known platform ──────────────────────────────────────
    if platform:
        label = PLATFORM_LABELS.get(platform, platform.replace("_", " ").title())
        candidates = []

        # Try oEmbed for YouTube/Vimeo
        if config and config.get("oembed"):
            # Build the canonical watch URL from the embed URL for oEmbed
            match = config["patterns"][0].search(src)
            media_id = match.group(1) if match else None
            oembed_title = None
            if media_id:
                if platform == "youtube":
                    watch_url = f"https://www.youtube.com/watch?v={media_id}"
                    oembed_title = fetch_oembed_title("youtube", watch_url)
                elif platform == "vimeo":
                    watch_url = f"https://vimeo.com/{media_id}"
                    oembed_title = fetch_oembed_title("vimeo", watch_url)

            if oembed_title:
                candidates.append({
                    "title": f"{oembed_title} — {label}",
                    "rationale": f"{WCAG_RATIONALE} The oEmbed API provided the exact media title.",
                })
                candidates.append({
                    "title": f"Embedded {label}: {oembed_title}",
                    "rationale": f"{WCAG_RATIONALE} 'Embedded' prefix clarifies this is a frame.",
                })
            else:
                candidates.append({
                    "title": f"Embedded {label}",
                    "rationale": f"{WCAG_RATIONALE} Platform-matched title; video title unavailable.",
                })

        elif platform == "google_maps":
            location = _extract_maps_query(src)
            if location:
                candidates.append({
                    "title": f"Google Maps — {location}",
                    "rationale": f"{WCAG_RATIONALE} Location extracted from embed URL parameters.",
                })
                candidates.append({
                    "title": f"Interactive Map: {location}",
                    "rationale": f"{WCAG_RATIONALE} Describes content type and location.",
                })
            else:
                candidates.append({
                    "title": "Embedded Google Maps",
                    "rationale": f"{WCAG_RATIONALE} Platform detected as Google Maps.",
                })

        elif platform == "google_forms":
            candidates.append({
                "title": "Embedded Google Form",
                "rationale": f"{WCAG_RATIONALE} Platform detected as Google Forms.",
            })

        elif platform == "microsoft_forms":
            candidates.append({
                "title": "Embedded Microsoft Form",
                "rationale": f"{WCAG_RATIONALE} Platform detected as Microsoft Forms.",
            })

        else:
            candidates.append({
                "title": f"Embedded {label}",
                "rationale": f"{WCAG_RATIONALE} Platform automatically detected.",
            })

        # Generic platform fallback as 3rd candidate
        candidates.append({
            "title": label,
            "rationale": f"{WCAG_RATIONALE} Minimal but unambiguous platform label.",
        })

        return {
            "confidence": "high",
            "platform": platform,
            "candidates": candidates[:3],
        }

    # ── MEDIUM CONFIDENCE: Readable slug from src/name/id ────────────────────
    medium_candidates = []
    if src:
        path = urlparse(src).path.rstrip("/")
        slug = path.split("/")[-1] if "/" in path else path
        slug = re.sub(r"\.[a-zA-Z0-9]+$", "", slug)  # strip extension
        if slug and len(slug) > 2:
            label = _slug_to_label(slug)
            medium_candidates.append({
                "title": f"Embedded {label}",
                "rationale": f"{WCAG_RATIONALE} Title derived from URL path segment.",
            })

    for attr_val in [name_attr, id_attr]:
        if attr_val and len(attr_val) > 2:
            label = _slug_to_label(attr_val)
            medium_candidates.append({
                "title": f"Embedded {label}",
                "rationale": f"{WCAG_RATIONALE} Title derived from iframe attribute value.",
            })

    if medium_candidates:
        return {
            "confidence": "medium",
            "platform": None,
            "candidates": medium_candidates[:2],
        }

    # ── LOW CONFIDENCE: Cannot determine from heuristics alone ───────────────
    return {
        "confidence": "low",
        "platform": None,
        "candidates": [],
    }

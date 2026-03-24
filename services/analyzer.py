"""
analyzer.py — Orchestrator: runs the full title-generation pipeline for
a single iframe. Returns ranked candidates, corrected snippet, WCAG rationale.
"""
import re
from bs4 import BeautifulSoup
from services import heuristics, fetcher, dom_analyzer, llm_service

WCAG_CRITERION = (
    "WCAG 2.2 Success Criterion 4.1.2 (Name, Role, Value) — "
    "Technique H64 requires all <iframe> elements to have a descriptive title attribute."
)


def _parse_iframe_attrs(snippet: str) -> dict:
    """Extract attributes from an iframe HTML snippet."""
    soup = BeautifulSoup(snippet, "lxml")
    iframe = soup.find("iframe")
    if not iframe:
        return {}
    return {
        "src": iframe.get("src", ""),
        "title": iframe.get("title", ""),
        "name": iframe.get("name", ""),
        "id": iframe.get("id", ""),
        "raw_tag": str(iframe),
    }


def _inject_title(snippet: str, title: str) -> str:
    """Inject (or replace) the title attribute in an iframe HTML snippet."""
    soup = BeautifulSoup(snippet, "lxml")
    iframe = soup.find("iframe")
    if not iframe:
        return snippet
    iframe["title"] = title
    # Return just the iframe tag, not the full HTML document BeautifulSoup adds
    return str(iframe)


def _pass_fail(existing_title: str) -> dict:
    """
    Heuristic-only audit result for the Scan tab.
    Returns status and a short reason.
    """
    if not existing_title or not existing_title.strip():
        return {"status": "fail", "reason": "No title attribute present"}
    t = existing_title.strip().lower()
    generic = {"iframe", "frame", "embedded", "embed", "content", "widget",
               "banner", "ad", "advertisement", "untitled"}
    if t in generic or len(t) < 4:
        return {"status": "warning", "reason": "Title is too generic or too short"}
    return {"status": "pass", "reason": "Title attribute present and appears descriptive"}


def analyze_iframe(
    snippet: str,
    src_override: str | None = None,
    llm_provider: str | None = None,
) -> dict:
    """
    Full pipeline for a single iframe.

    Args:
        snippet:       Raw HTML (may be just the <iframe> tag or surrounding HTML)
        src_override:  Optional URL override if the user typed a standalone URL
        llm_provider:  LLM provider name (or None to use env default)

    Returns a dict with:
        - candidates: list of {rank, title, corrected_snippet, rationale}
        - platform: str | None
        - confidence: str
        - metadata: dict (fetched source metadata)
        - dom_context: str | None
        - provider_used: str | None
        - error: str | None
        - existing_title: str
        - audit: dict (pass/fail for scan view)
    """
    # 1. Parse iframe attributes
    attrs = _parse_iframe_attrs(snippet)
    if src_override:
        attrs["src"] = src_override

    existing_title = attrs.get("title", "")

    # 2. Heuristics (always run first)
    heuristic_result = heuristics.run(attrs)
    confidence = heuristic_result["confidence"]
    platform = heuristic_result["platform"]
    h_candidates = heuristic_result["candidates"]

    # 3. DOM context (always extract, cheap)
    dom_ctx = dom_analyzer.extract_context(snippet)
    dom_context_text = dom_ctx.get("context_text")

    # 4. Fetch source metadata
    src = attrs.get("src", "")
    metadata = {}
    if src:
        metadata = fetcher.fetch_iframe_metadata(src)

    # 5. If heuristics are confident, use them; otherwise call LLM
    provider_used = None
    llm_error = None

    if confidence == "high":
        raw_candidates = h_candidates
    else:
        # Supplement heuristic medium candidates with metadata before LLM
        if confidence == "medium" and h_candidates:
            # Use the heuristic slug as a hint but still call LLM for 3 options
            pass

        llm_result = llm_service.generate_titles(
            iframe_html=attrs.get("raw_tag", snippet),
            metadata=metadata,
            dom_context=dom_context_text,
            provider=llm_provider,
        )
        provider_used = llm_result.get("provider_used")
        llm_error = llm_result.get("error")
        raw_candidates = llm_result.get("candidates", [])

    # 6. Build final candidates with corrected snippets
    final_candidates = []
    for i, cand in enumerate(raw_candidates[:3]):
        title = cand.get("title", "Embedded Content")
        rationale = cand.get("rationale", WCAG_CRITERION)
        corrected = _inject_title(snippet, title)
        final_candidates.append({
            "rank": i + 1,
            "title": title,
            "corrected_snippet": corrected,
            "rationale": rationale,
        })

    return {
        "candidates": final_candidates,
        "platform": platform,
        "confidence": confidence,
        "metadata": metadata,
        "dom_context": dom_context_text,
        "provider_used": provider_used,
        "error": llm_error,
        "existing_title": existing_title,
        "audit": _pass_fail(existing_title),
        "src": src,
    }


def scan_page(page_url: str) -> dict:
    """
    Fetch a page URL and run a heuristic-only audit on all iframes found.

    Returns:
        {
            "url": str,
            "total": int,
            "iframes": [ { "index", "snippet", "src", "platform",
                           "existing_title", "audit" } ],
            "summary": { "pass": int, "warn": int, "fail": int },
            "error": str | None
        }
    """
    result = fetcher.fetch_iframe_metadata(page_url)
    # We need the raw page HTML, not just metadata — re-fetch for full HTML
    import httpx
    iframes_data = []
    error = None

    try:
        resp = httpx.get(
            page_url,
            headers={"User-Agent": "A11yiFrameChecker/1.0"},
            timeout=12,
            follow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        iframes = soup.find_all("iframe")

        for idx, iframe in enumerate(iframes):
            snippet = str(iframe)
            attrs = {
                "src": iframe.get("src", ""),
                "title": iframe.get("title", ""),
                "name": iframe.get("name", ""),
                "id": iframe.get("id", ""),
            }
            h_result = heuristics.run(attrs)
            audit = _pass_fail(attrs["title"])
            iframes_data.append({
                "index": idx + 1,
                "snippet": snippet,
                "src": attrs["src"],
                "platform": h_result.get("platform"),
                "confidence": h_result.get("confidence"),
                "existing_title": attrs["title"],
                "audit": audit,
            })

    except httpx.TimeoutException:
        error = "Page request timed out"
    except httpx.HTTPStatusError as exc:
        error = f"HTTP {exc.response.status_code} fetching page"
    except Exception as exc:
        error = str(exc)

    total = len(iframes_data)
    summary = {
        "pass": sum(1 for f in iframes_data if f["audit"]["status"] == "pass"),
        "warn": sum(1 for f in iframes_data if f["audit"]["status"] == "warning"),
        "fail": sum(1 for f in iframes_data if f["audit"]["status"] == "fail"),
    }

    return {
        "url": page_url,
        "total": total,
        "iframes": iframes_data,
        "summary": summary,
        "error": error,
    }

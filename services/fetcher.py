"""
fetcher.py — Server-side HTTP fetch of iframe source URLs.
Extracts <title>, <meta name="description">, and <h1> content.
All HTML is passed through sanitizer before parsing.
"""
import httpx
from bs4 import BeautifulSoup
from services.sanitizer import sanitize_html, redact_pii

TIMEOUT = 8  # seconds
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; A11yiFrameChecker/1.0; "
        "+https://github.com/a11y-iframe-checker)"
    )
}


def fetch_iframe_metadata(url: str) -> dict:
    """
    Fetch the iframe source URL and extract accessible metadata.

    Returns a dict with keys:
        - title: str | None
        - description: str | None
        - h1: str | None
        - error: str | None
        - fetched: bool
    """
    result = {"title": None, "description": None, "h1": None,
              "error": None, "fetched": False}

    if not url or not url.startswith(("http://", "https://")):
        result["error"] = "Invalid or missing URL"
        return result

    try:
        response = httpx.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            result["error"] = f"Non-HTML response ({content_type})"
            return result

        raw_html = response.text
        safe_html = sanitize_html(raw_html)
        soup = BeautifulSoup(safe_html, "lxml")

        # <title>
        title_tag = soup.find("title")
        if title_tag and title_tag.get_text(strip=True):
            result["title"] = redact_pii(title_tag.get_text(strip=True))

        # <meta name="description">
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            result["description"] = redact_pii(meta_desc["content"].strip())

        # First <h1>
        h1_tag = soup.find("h1")
        if h1_tag and h1_tag.get_text(strip=True):
            result["h1"] = redact_pii(h1_tag.get_text(strip=True))

        result["fetched"] = True

    except httpx.TimeoutException:
        result["error"] = "Request timed out"
    except httpx.HTTPStatusError as exc:
        result["error"] = f"HTTP {exc.response.status_code}"
    except Exception as exc:
        result["error"] = str(exc)

    return result


def fetch_oembed_title(platform: str, url: str) -> str | None:
    """
    Fetch a human-readable title from YouTube or Vimeo oEmbed endpoints.
    No API key required.
    """
    endpoints = {
        "youtube": f"https://www.youtube.com/oembed?url={url}&format=json",
        "vimeo": f"https://vimeo.com/api/oembed.json?url={url}",
    }
    endpoint = endpoints.get(platform)
    if not endpoint:
        return None
    try:
        resp = httpx.get(endpoint, timeout=TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        return data.get("title")
    except Exception:
        return None

import asyncio
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def get_embeds(url: str) -> list:
    """
    Use Playwright to load a URL, bypass CSP/Web Security, and extract 
    all embed tags with rich runtime metadata (visibility, dimensions, context).
    """
    embeds = []
    try:
        with sync_playwright() as p:
            # Bypass CSP and cross-origin restrictions for better inspection
            browser = p.chromium.launch(headless=True, args=['--disable-web-security'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800}
            )
            page = context.new_page()
            
            # Navigate and wait for content
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(3000) # Deeper wait for dynamic embeds
            
            # Global page context for specificity audit
            page_title = page.title()
            page_h1 = page.inner_text("h1") if page.query_selector("h1") else ""
            
            # 1. Extract IFRAMES via page.frames() for nested coverage
            all_frames = page.frames[1:] # Skip main page frame
            for frame in all_frames:
                try:
                    el = frame.frame_element()
                    if not el: continue
                    
                    is_visible = el.is_visible()
                    box = el.bounding_box() or {'width': 0, 'height': 0}
                    snippet = el.evaluate("el => el.outerHTML")
                    aria_hidden = el.get_attribute("aria-hidden")
                    tabindex = el.get_attribute("tabindex")
                    
                    interactive_count = 0
                    try:
                        interactive_count = frame.evaluate("""() => {
                            return document.querySelectorAll('a, button, input, select, textarea, [tabindex="0"]').length;
                        }""")
                    except: pass

                    embeds.append({
                        "snippet": snippet,
                        "line": None,
                        "url": url,
                        "is_visible": is_visible,
                        "width": box['width'],
                        "height": box['height'],
                        "aria_hidden": aria_hidden,
                        "tabindex": tabindex,
                        "page_title": page_title,
                        "page_h1": page_h1,
                        "interactive_count": interactive_count,
                        "element_type": "iframe" # Explicit for this loop
                    })
                except Exception as fe:
                    print(f"Error extracting frame: {fe}")

            # 2. Extract other media tags via query_selector_all
            other_tags = ["video", "audio", "object", "embed"]
            for tag_name in other_tags:
                elements = page.query_selector_all(tag_name)
                for el in elements:
                    try:
                        # Runtime checks
                        is_visible = el.is_visible()
                        box = el.bounding_box() or {'width': 0, 'height': 0}
                        snippet = el.evaluate("el => el.outerHTML")
                        aria_hidden = el.get_attribute("aria-hidden")
                        tabindex = el.get_attribute("tabindex")

                        embeds.append({
                            "snippet": snippet,
                            "line": None,
                            "url": url,
                            "is_visible": is_visible,
                            "width": box['width'],
                            "height": box['height'],
                            "aria_hidden": aria_hidden,
                            "tabindex": tabindex,
                            "page_title": page_title,
                            "page_h1": page_h1,
                            "interactive_count": 0, # Usually no nested frames for these tags
                            "element_type": tag_name
                        })
                    except Exception as inner_e:
                        print(f"Error extracting element {tag_name}: {inner_e}")
            
            browser.close()
    except Exception as e:
        print(f"Playwright error: {e}")
        
    return embeds

import asyncio
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import hashlib
from urllib.parse import urlparse

def get_embeds(url: str) -> list:
    """
    Use Playwright to load a URL, bypass CSP/Web Security, and extract 
    all embed tags with rich runtime metadata (visibility, dimensions, context).
    """
    embeds = []
    # Use dictionaries to track unique iframes and duplicates
    unique_iframes = {}  # key -> iframe data
    duplicate_tracker = {}  # track duplicates for reporting
    
    try:
        with sync_playwright() as p:
            # Bypass CSP and cross-origin restrictions for better inspection
            browser = p.chromium.launch(headless=True, args=['--disable-web-security'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800}
            )
            page = context.new_page()
            
            # Enable frame monitoring
            frame_events = []
            page.on("frameattached", lambda frame: frame_events.append(("attached", frame)))
            page.on("framedetached", lambda frame: frame_events.append(("detached", frame)))
            
            # Navigate and wait for content
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(3000) # Deeper wait for dynamic embeds
            
            # ── Capture Scan Evidence with Visual Markers ─────────────────────
            import os
            import time
            
            # Inject visual markers for ALL supported elements to "prove" the scan
            page.evaluate("""() => {
                const elements = document.querySelectorAll('iframe, video, audio, object, embed');
                elements.forEach((el, i) => {
                    el.style.border = '4px solid #cc0000';
                    el.style.boxSizing = 'border-box';
                    const badge = document.createElement('div');
                    badge.textContent = '#' + (i + 1);
                    badge.style.position = 'absolute';
                    badge.style.background = '#cc0000';
                    badge.style.color = 'white';
                    badge.style.padding = '2px 6px';
                    badge.style.fontSize = '12px';
                    badge.style.fontWeight = 'bold';
                    badge.style.zIndex = '2147483647';
                    const rect = el.getBoundingClientRect();
                    badge.style.top = (rect.top + window.scrollY) + 'px';
                    badge.style.left = (rect.left + window.scrollX) + 'px';
                    document.body.appendChild(badge);
                });
            }""")
            
            scan_dir = os.path.join("static", "scans")
            os.makedirs(scan_dir, exist_ok=True)
            screenshot_filename = f"scan_{int(time.time())}.png"
            screenshot_path = os.path.join(scan_dir, screenshot_filename)
            page.screenshot(path=screenshot_path)
            evidence_url = f"/static/scans/{screenshot_filename}"
            # ──────────────────────────────────────────────────────────────────
            
            # Global page context for specificity audit
            page_title = page.title()
            page_h1 = page.inner_text("h1") if page.query_selector("h1") else ""
            
            # Track seen iframes by multiple identifiers
            seen_frames = {}  # frame_id -> frame_data
            frame_counter = 0
            
            # 1. Extract IFRAMES via page.frames() for nested coverage
            all_frames = page.frames[1:] # Skip main page frame
            
            for frame in all_frames:
                try:
                    el = frame.frame_element()
                    if not el: 
                        continue
                    
                    # Generate unique identifiers for this iframe
                    frame_id = frame._impl_obj._guid if hasattr(frame, '_impl_obj') else str(id(frame))
                    
                    # Get the iframe's URL (may be empty for same-origin iframes)
                    frame_url = frame.url
                    
                    # Get the iframe element's outerHTML to compare
                    snippet = el.evaluate("el => el.outerHTML")
                    
                    # Get the src attribute specifically
                    src_attr = el.get_attribute("src") or ""
                    
                    # Get the element's position in DOM (XPath-like path)
                    dom_path = get_element_path(el)
                    
                    # Get parent frame info
                    parent_frame = frame.parent_frame
                    parent_info = {
                        "url": parent_frame.url if parent_frame else "main",
                        "is_main": parent_frame is None
                    }
                    
                    # Check if iframe has been reloaded (by comparing content)
                    content_hash = None
                    try:
                        # Try to get content hash to detect duplicate iframes
                        frame_content = frame.content()
                        content_hash = hashlib.md5(frame_content.encode()).hexdigest()
                    except:
                        pass
                    
                    # Create a uniqueness key
                    uniqueness_key = create_uniqueness_key({
                        "src": src_attr,
                        "url": frame_url,
                        "dom_path": dom_path,
                        "content_hash": content_hash,
                        "parent_url": parent_info["url"]
                    })
                    
                    # Runtime checks
                    is_visible = el.is_visible()
                    box = el.bounding_box() or {'width': 0, 'height': 0}
                    aria_hidden = el.get_attribute("aria-hidden")
                    tabindex = el.get_attribute("tabindex")
                    
                    interactive_count = 0
                    try:
                        interactive_count = frame.evaluate("""() => {
                            return document.querySelectorAll('a, button, input, select, textarea, [tabindex="0"]').length;
                        }""")
                    except: 
                        pass
                    
                    frame_data = {
                        "snippet": snippet,
                        "src": src_attr,
                        "frame_url": frame_url,
                        "line": None,
                        "page_url": url,
                        "is_visible": is_visible,
                        "width": box['width'],
                        "height": box['height'],
                        "aria_hidden": aria_hidden,
                        "tabindex": tabindex,
                        "page_title": page_title,
                        "page_h1": page_h1,
                        "interactive_count": interactive_count,
                        "element_type": "iframe",
                        "dom_path": dom_path,
                        "parent_info": parent_info,
                        "uniqueness_key": uniqueness_key,
                        "frame_id": frame_id,
                        "content_hash": content_hash
                    }
                    
                    # Check if we've seen this iframe before
                    if uniqueness_key in unique_iframes:
                        # This is a duplicate report of the same iframe
                        duplicate_tracker[uniqueness_key] = duplicate_tracker.get(uniqueness_key, 0) + 1
                        
                        # Add a flag to indicate this is a duplicate
                        frame_data["is_duplicate"] = True
                        frame_data["duplicate_count"] = duplicate_tracker[uniqueness_key] + 1
                        frame_data["original_index"] = unique_iframes[uniqueness_key]["index"]
                        
                        # Still add to embeds but with duplicate flag
                        embeds.append(frame_data)
                    else:
                        # New unique iframe
                        frame_counter += 1
                        frame_data["is_duplicate"] = False
                        frame_data["index"] = frame_counter
                        frame_data["duplicate_count"] = 1
                        
                        unique_iframes[uniqueness_key] = {
                            "data": frame_data,
                            "index": frame_counter,
                            "count": 1
                        }
                        embeds.append(frame_data)
                        
                except Exception as fe:
                    print(f"Error extracting frame: {fe}")
                    embeds.append({
                        "error": str(fe),
                        "element_type": "iframe_error",
                        "is_duplicate": False
                    })

            # 2. Extract other media tags via query_selector_all
            other_tags = ["video", "audio", "object", "embed"]
            for tag_name in other_tags:
                elements = page.query_selector_all(tag_name)
                for idx, el in enumerate(elements):
                    try:
                        # Generate unique key for non-iframe elements
                        snippet = el.evaluate("el => el.outerHTML")
                        src_attr = el.get_attribute("src") or el.get_attribute("data") or ""
                        dom_path = get_element_path(el)
                        
                        uniqueness_key = f"{tag_name}:{src_attr}:{dom_path}"
                        
                        # Runtime checks
                        is_visible = el.is_visible()
                        box = el.bounding_box() or {'width': 0, 'height': 0}
                        aria_hidden = el.get_attribute("aria-hidden")
                        tabindex = el.get_attribute("tabindex")
                        
                        embed_data = {
                            "snippet": snippet,
                            "src": src_attr,
                            "line": None,
                            "page_url": url,
                            "is_visible": is_visible,
                            "width": box['width'],
                            "height": box['height'],
                            "aria_hidden": aria_hidden,
                            "tabindex": tabindex,
                            "page_title": page_title,
                            "page_h1": page_h1,
                            "interactive_count": 0,
                            "element_type": tag_name,
                            "dom_path": dom_path,
                            "uniqueness_key": uniqueness_key
                        }
                        
                        # Check for duplicates in non-iframe elements too
                        if uniqueness_key in unique_iframes:
                            duplicate_tracker[uniqueness_key] = duplicate_tracker.get(uniqueness_key, 0) + 1
                            embed_data["is_duplicate"] = True
                            embed_data["duplicate_count"] = duplicate_tracker[uniqueness_key] + 1
                        else:
                            frame_counter += 1
                            embed_data["is_duplicate"] = False
                            embed_data["index"] = frame_counter
                            unique_iframes[uniqueness_key] = {"data": embed_data, "index": frame_counter}
                        
                        embeds.append(embed_data)
                        
                    except Exception as inner_e:
                        print(f"Error extracting element {tag_name}: {inner_e}")
            
            # Add summary info to the result
            summary = {
                "total_entries": len(embeds),
                "unique_iframes": len(unique_iframes),
                "duplicate_entries": len(embeds) - len(unique_iframes),
                "duplicate_breakdown": duplicate_tracker,
                "has_duplicates": len(embeds) > len(unique_iframes),
                "evidence_url": evidence_url # Pass the screenshot URL
            }
            
            # Attach summary to the first embed or return separately
            if embeds:
                embeds[0]["_scan_summary"] = summary
            
            browser.close()
            
    except Exception as e:
        print(f"Playwright error: {e}")
        embeds.append({
            "error": str(e),
            "element_type": "scan_error"
        })
        
    return embeds

def get_element_path(element):
    """Generate a unique DOM path for an element to help identify duplicates"""
    try:
        path = element.evaluate("""(el) => {
            const getPath = (element) => {
                if (!element || element === document.body) return '';
                let path = '';
                if (element.id) {
                    path = '#' + element.id;
                } else {
                    let index = 1;
                    let sibling = element;
                    while (sibling.previousElementSibling) {
                        sibling = sibling.previousElementSibling;
                        if (sibling.tagName === element.tagName) index++;
                    }
                    path = element.tagName.toLowerCase() + ':nth-of-type(' + index + ')';
                }
                const parentPath = getPath(element.parentElement);
                return parentPath ? parentPath + ' > ' + path : path;
            };
            return getPath(el);
        }""")
        return path
    except:
        return "unknown"

def create_uniqueness_key(frame_info):
    """Create a unique key to identify if this is the same iframe or a different one"""
    key_parts = []
    
    # Primary identifier: src attribute
    if frame_info.get("src"):
        key_parts.append(f"src:{frame_info['src']}")
    
    # Secondary: frame URL (may be different from src after redirects)
    if frame_info.get("url"):
        key_parts.append(f"url:{frame_info['url']}")
    
    # Tertiary: DOM position
    if frame_info.get("dom_path"):
        key_parts.append(f"path:{frame_info['dom_path']}")
    
    # Parent frame context
    if frame_info.get("parent_url"):
        key_parts.append(f"parent:{frame_info['parent_url']}")
    
    # Content hash if available (most reliable for detecting duplicates)
    if frame_info.get("content_hash"):
        key_parts.append(f"hash:{frame_info['content_hash']}")
    
    return "|".join(key_parts) if key_parts else f"unknown:{frame_info.get('frame_id', '')}"

def analyze_scan_results(embeds):
    """Helper function to analyze and report on duplicates vs unique issues"""
    if not embeds:
        return "No embeds found"
    
    # Check if we have summary info
    summary = embeds[0].get("_scan_summary", {})
    
    print("\n" + "="*60)
    print("IFRAME/EMBED SCAN ANALYSIS")
    print("="*60)
    
    if summary:
        print(f"\n📊 SCAN SUMMARY:")
        print(f"   Total reports generated: {summary['total_entries']}")
        print(f"   Unique iframes/embeds: {summary['unique_iframes']}")
        print(f"   Duplicate reports: {summary['duplicate_entries']}")
        print(f"   Has duplicates: {'YES ⚠️' if summary['has_duplicates'] else 'NO ✓'}")
        
        if summary['duplicate_breakdown']:
            print(f"\n🔄 DUPLICATE BREAKDOWN:")
            for key, count in summary['duplicate_breakdown'].items():
                print(f"   {key}: {count} duplicate reports")
    
    print(f"\n🔍 DETAILED ANALYSIS:")
    unique_items = {}
    
    for idx, embed in enumerate(embeds):
        if embed.get("_scan_summary"):
            continue  # Skip the summary entry
            
        element_type = embed.get("element_type", "unknown")
        is_duplicate = embed.get("is_duplicate", False)
        
        if not is_duplicate:
            # Track unique items
            key = embed.get("uniqueness_key", f"item_{idx}")
            unique_items[key] = embed
            
            print(f"\n📌 UNIQUE ITEM #{embed.get('index', idx+1)}:")
            print(f"   Type: {element_type}")
            print(f"   Src: {embed.get('src', 'N/A')[:100]}")
            print(f"   Visible: {embed.get('is_visible', 'N/A')}")
            print(f"   Dimensions: {embed.get('width', 0)}x{embed.get('height', 0)}")
            print(f"   DOM Path: {embed.get('dom_path', 'N/A')}")
            
            if embed.get('interactive_count', 0) > 0:
                print(f"   Interactive elements inside: {embed['interactive_count']}")
            
            if embed.get('aria_hidden'):
                print(f"   aria-hidden: {embed['aria_hidden']}")
            
            if embed.get('tabindex'):
                print(f"   tabindex: {embed['tabindex']}")
        else:
            # This is a duplicate report
            print(f"\n⚠️ DUPLICATE REPORT #{idx+1}:")
            print(f"   Same as item #{embed.get('original_index', 'unknown')}")
            print(f"   Duplicate count: {embed.get('duplicate_count', 1)}")
            print(f"   Type: {element_type}")
            print(f"   Src: {embed.get('src', 'N/A')[:100]}")
    
    print("\n" + "="*60)
    print("CONCLUSION:")
    
    if summary and summary['has_duplicates']:
        print(f"⚠️ Your {summary['total_entries']} results represent {summary['unique_iframes']} UNIQUE iframes/embeds")
        print(f"   The remaining {summary['duplicate_entries']} reports are DUPLICATES of the same elements")
        print("\n   🎯 ACTION ITEM: Fix your scanner to prevent duplicate reporting")
        print("   💡 SUGGESTION: Use the uniqueness_key field to group reports by actual iframe")
    else:
        print("✓ All reports appear to be unique iframes/embeds")
        print("   🎯 ACTION ITEM: Address each of these unique issues individually")
    
    return unique_items

# Example usage
if __name__ == "__main__":
    test_url = "https://example.com"  # Replace with your URL
    results = get_embeds(test_url)
    
    # Analyze and differentiate duplicates vs unique issues
    unique_embeds = analyze_scan_results(results)
    
    # Now you can work with unique embeds only
    print(f"\n✅ Ready to fix {len(unique_embeds)} unique issues")
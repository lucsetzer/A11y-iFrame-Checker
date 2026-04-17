#!/usr/bin/env python3
"""
Simple test to prove Playwright can find and audit PDFs.
Run this from terminal: python test_pdf_scanner.py
"""

from playwright.sync_api import sync_playwright
from services.pdf_auditor import audit_pdf
import base64
import os

def test_pdf_scan(url, demo_mode=True):
    """Test a single URL for PDFs and show exactly what happens."""
    
    print(f"\n{'='*60}")
    print(f"🔍 SCANNING: {url}")
    print(f"{'='*60}\n")
    
    results = []
    
    with sync_playwright() as p:
        # Launch browser (headed so YOU can see it)
        browser = p.chromium.launch(headless=not demo_mode, slow_mo=500)
        page = browser.new_page()
        
        print("📡 Loading page...")
        page.goto(url, timeout=30000)
        
        # Take a screenshot so you can see what Playwright saw
        screenshot_path = "test_screenshot.png"
        page.screenshot(path=screenshot_path)
        print(f"📸 Screenshot saved: {screenshot_path}")
        
        # Find all PDF links
        pdf_links = page.locator('a[href$=".pdf" i]').all()
        print(f"\n📄 Found {len(pdf_links)} PDF link(s) on the page\n")
        
        if not pdf_links:
            print("⚠️ No PDF links found. Try a page that definitely has PDFs.")
            print("   Example: https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf")
        
        for i, link in enumerate(pdf_links):
            try:
                href = link.get_attribute('href')
                print(f"  [{i+1}] PDF URL: {href}")
                
                # Try to fetch the PDF
                print(f"      ⏳ Fetching PDF...")
                response = page.context.request.get(href)
                
                if response.status == 200:
                    pdf_bytes = response.body()
                    print(f"      ✅ PDF downloaded ({len(pdf_bytes)} bytes)")
                    
                    # Run the audit
                    print(f"      🔬 Running accessibility audit...")
                    audit_result = audit_pdf(pdf_bytes)
                    
                    # Show summary
                    summary = audit_result.get('summary', {})
                    print(f"      📊 Results: {summary.get('critical', 0)} Critical, "
                          f"{summary.get('warning', 0)} Warning, "
                          f"{summary.get('manual', 0)} Manual")
                    
                    # Show first finding as example
                    findings = audit_result.get('findings', [])
                    if findings:
                        print(f"      📋 Example finding: {findings[0].get('description', '')[:80]}...")
                    
                    results.append({
                        'url': href,
                        'success': True,
                        'audit': audit_result
                    })
                else:
                    print(f"      ❌ Failed to fetch: HTTP {response.status}")
                    results.append({'url': href, 'success': False, 'error': f'HTTP {response.status}'})
                    
            except Exception as e:
                print(f"      ❌ Error: {str(e)[:100]}")
                results.append({'url': href, 'success': False, 'error': str(e)})
        
        browser.close()
    
    # Print final summary
    print(f"\n{'='*60}")
    print(f"📊 FINAL SUMMARY")
    print(f"{'='*60}")
    success_count = sum(1 for r in results if r.get('success'))
    print(f"PDFs found: {len(results)}")
    print(f"Successfully audited: {success_count}")
    
    if results:
        print(f"\n✅ To see full audit details, inspect the 'results' variable")
    
    return results

if __name__ == "__main__":
    # CHANGE THIS URL to a page that has PDFs you control
    TEST_URL = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    
    print("\n🎯 PDF TESTER")
    print("This will open a browser window so you can SEE what Playwright does.\n")
    
    input("Press Enter to start the test...")
    
    results = test_pdf_scan(TEST_URL, demo_mode=True)
    
    print("\n✨ Test complete. Check the output above.")
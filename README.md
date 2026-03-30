# A11y iFrame Checker — Vue 3 Embed Auditor

A high-fidelity accessibility auditing and remediation tool for web embeds (iframes, video, audio, object). It provides a reactive, modern interface powered by **Vue 3** and a robust Python backend for deep DOM inspection.

---

## ✨ Key Features

### 1. Unified Embed Auditor
*   **Snippet Audit**: Paste raw HTML for instant WCAG 2.2 analysis.
*   **Playwright URL Scan**: Scan a live page to find all media embeds, including dynamic and nested ones.
*   **Nested Depth**: Using `page.frames()` to find accessibility issues at any level of nesting.

### 2. Professional 3-Tier Reporting
Results are prioritized into actionable tiers:
*   🔴 **Critical**: Accessibility blockers (e.g., missing titles, keyboard traps, hidden but focusable content).
*   🟠 **Warning**: Best practices and potential issues (e.g., generic titles, tracking pixels).
*   🔵 **Manual Check**: Context-dependent items requiring human verification (e.g., complex captions).

### 3. Smart Remediation
*   **Tracking Pixel Detection**: Automatically identifies tracking pixels (1x1) and suggests hiding them from screen readers.
*   **Instant Fixes**: Generates "Minimal" (safe attributes) and "Full" (accessible wrapper) code snippets for every finding.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.9+
- Playwright (Chromium)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/your-username/A11y-iFrame-Checker.git
cd A11y-iFrame-Checker

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 3. Running the App
```bash
python app.py
```
Open `http://127.0.0.1:5000` in your browser.

---

## 🛠 Technical Architecture

- **Frontend**: **Vue 3** (Reactive UI) & CSS (University-branded interface).
- **Backend**: Flask (Python)
- **Engine**: 
    - `Playwright`: For live DOM scanning and runtime metadata extraction.
    - `BeautifulSoup4`: For structural HTML analysis.

---

## 🛡 Security & Best Practices
- **Non-Destructive Fixes**: The tool never modifies vendor code; it only injects standard accessibility attributes.
- **Sanitization**: All input HTML is sanitized (via `bleach`) to remove scripts and event handlers before processing on the server.
- **CORS & CSP Bypass**: Playwright is configured to bypass strict Content Security Policies to inspect cross-origin embeds for accessibility metadata.

---

## ⚖️ License
MIT License. Created for the University of North Carolina at Charlotte.

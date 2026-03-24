# A11y iFrame Checker

> **WCAG 2.2 Accessibility Audit Tool for Embedded Content**  
> Built for university web teams to identify and fix accessibility issues in `<iframe>`, `<video>`, `<audio>`, `<object>`, and `<embed>` elements.

---

## What It Does

This tool helps you comply with **WCAG 2.2** (the standard required by most U.S. universities as of 2025) by:

1. **Generating title attributes** for `<iframe>` elements using a smart heuristic-first approach
2. **Auditing any embed snippet** (`<iframe>`, `<video>`, `<audio>`, `<object>`, `<embed>`) against all applicable WCAG 2.2 criteria
3. **Scanning a full page URL** to instantly audit every iframe on the page
4. **Exporting results** as CSV or JSON for reporting

---

## Features

| Feature | Tab | Uses AI? |
|---|---|---|
| Generate WCAG-compliant `title` attributes for iframes | **Analyze iFrame** | Only for unknown/custom platforms |
| Full WCAG 2.2 audit: captions, controls, accessible name, fallback | **Embed Checker** | No — rule-based |
| Page-wide iframe scan with pass/warn/fail table | **Scan Page** | No — heuristics only |
| Export results (CSV + JSON) | All tabs | No |

---

## When Does AI Get Used?

The tool uses a **layered approach** for the Analyze iFrame tab:

1. **Heuristics first** — recognizes 16 known platforms (YouTube, Vimeo, Google Maps, Google Forms, Tableau, Kaltura, Panopto, etc.) and fetches live titles via oEmbed when possible. **No AI needed.**
2. **Metadata fetch** — if the platform isn't recognized, it fetches the source URL's page title, `<h1>`, and meta description. **No AI needed.**
3. **LLM fallback** — only if both above steps yield low confidence (e.g. a Blackboard module, a custom university widget, or any opaque embed), an AI model generates WCAG-appropriate title suggestions.

> **In practice:** YouTube, Vimeo, Google Maps, Forms, and 12 other platforms never need AI. Only truly opaque/custom embeds trigger the LLM. If no API key is configured, the tool still works using heuristics + metadata only.

---

## Supported Elements (Embed Checker)

| Element | What's Checked | WCAG Criteria |
|---|---|---|
| `<iframe>` | `title` attribute, keyboard access | SC 4.1.2 |
| `<embed>` | `title` attribute | SC 4.1.2 |
| `<object>` | `title` attribute, fallback content | SC 4.1.2, 1.1.1 |
| `<video>` | Captions track, audio description, `controls`, accessible name, `autoplay` | SC 1.2.2, 1.2.5, 2.1.1, 4.1.2 |
| `<audio>` | `controls`, transcript advisory, `autoplay` | SC 1.2.1, 2.1.1, 4.1.2 |

---

## Prerequisites

- **Python 3.10+**
- **pip** (comes with Python)
- Git (optional, for cloning)

---

## Setup Instructions

### 1. Clone or download the repository

```bash
git clone https://github.com/YOUR-ORG/a11y-iframe-checker.git
cd a11y-iframe-checker
```

Or download the ZIP from GitHub and extract it.

### 2. Create a virtual environment

```bash
python3 -m venv .venv
```

Activate it:

- **Mac/Linux:** `source .venv/bin/activate`
- **Windows:** `.venv\Scripts\activate`

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your environment file

```bash
cp .env.template .env
```

Open `.env` and add your API key(s) if you want AI-powered title generation for unknown iframes. **This is optional** — the tool works without any keys for all rule-based features.

```env
# Only needed for the AI fallback in the Analyze iFrame tab.
# You only need ONE key — the tool tries providers in order.
GEMINI_API_KEY=your-key-here
# ANTHROPIC_API_KEY=your-claude-key
# OPENAI_API_KEY=your-openai-key
DEFAULT_LLM_PROVIDER=gemini
```

### 5. Run the app

```bash
python -m flask run --port 5050
```

Then open **http://127.0.0.1:5050** in your browser.

---

## Running on Windows

The steps are the same. Use `.venv\Scripts\activate` instead of `source .venv/bin/activate`.

---

## Updating API Keys Without Restarting

You can update API keys at any time from the **⚙️ Settings** panel in the app header — no restart required.

---

## Project Structure

```
a11y-iframe-checker/
├── app.py                      # Flask app and routes
├── requirements.txt            # Python dependencies
├── .env.template               # Copy to .env and add your keys
├── services/
│   ├── analyzer.py             # Orchestrates the iframe analysis pipeline
│   ├── heuristics.py           # 16-platform pattern matcher (YouTube, Vimeo, etc.)
│   ├── embed_checker.py        # WCAG 2.2 rule-based audit for all embed types
│   ├── fetcher.py              # Fetches source URL metadata + oEmbed titles
│   ├── dom_analyzer.py         # Extracts surrounding headings/figcaptions
│   ├── llm_service.py          # Multi-LLM client (Gemini, Claude, OpenAI, etc.)
│   └── sanitizer.py            # Strips scripts and PII from HTML
├── templates/
│   └── index.html              # Main UI template
└── static/
    ├── css/style.css           # University-branded styles
    └── js/app.js               # Client-side JavaScript
```

---

## Supported LLM Providers (for AI fallback)

Only needed for the Analyze iFrame tab's LLM fallback:

| Provider | Key in `.env` |
|---|---|
| Google Gemini | `GEMINI_API_KEY` |
| Anthropic Claude | `ANTHROPIC_API_KEY` |
| OpenAI / ChatGPT | `OPENAI_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |
| Azure OpenAI | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` |

The tool automatically falls back to the next available provider if your first choice fails.

---

## Exporting Results

Both tabs support **CSV** and **JSON** export. Click **Save to Export** on any result, then use the export bar at the bottom of the page to download.

The CSV format is designed for pasting into a spreadsheet or sending to your accessibility reporting team.

---

## WCAG 2.2 References

- [SC 4.1.2 — Name, Role, Value](https://www.w3.org/WAI/WCAG22/Understanding/name-role-value)
- [SC 1.2.2 — Captions (Prerecorded)](https://www.w3.org/WAI/WCAG22/Understanding/captions-prerecorded)
- [SC 1.2.5 — Audio Description](https://www.w3.org/WAI/WCAG22/Understanding/audio-description-prerecorded)
- [SC 2.1.1 — Keyboard](https://www.w3.org/WAI/WCAG22/Understanding/keyboard)
- [SC 1.1.1 — Non-text Content](https://www.w3.org/WAI/WCAG22/Understanding/non-text-content)
- [H64 — Using the title attribute for iframes](https://www.w3.org/WAI/WCAG22/Techniques/html/H64)

---

## Troubleshooting

**Port already in use:**
```bash
flask run --port 5051
```

**`ModuleNotFoundError`:**  
Make sure your virtual environment is activated before running pip or flask.

**AI suggestions not appearing:**  
Check that your `.env` file has a valid API key and `DEFAULT_LLM_PROVIDER` is set. You can also update keys in the ⚙️ Settings panel without restarting.

---

## License

MIT — free to use and modify for university and non-commercial purposes.

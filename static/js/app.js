/* app.js — A11y iFrame Checker client-side logic */
'use strict';

// ── State ──────────────────────────────────────────────────────────────────
const state = {
    savedResults: [],
    currentResult: null,
    selectedCandidateIndex: 0,
};

// ── DOM Refs ───────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const el = {
    // Tabs
    tabAnalyze: $('tab-analyze'),
    tabScan: $('tab-scan'),
    tabChecker: $('tab-checker'),
    panelAnalyze: $('panel-analyze'),
    panelScan: $('panel-scan'),
    panelChecker: $('panel-checker'),

    // Analyze form
    analyzeForm: $('analyze-form'),
    iframeSnippet: $('iframe-snippet'),
    srcOverride: $('src-override'),
    llmProviderSel: $('llm-provider-override'),
    analyzeBtn: $('analyze-btn'),
    analyzeClear: $('analyze-clear'),

    // Results
    resultsPlaceholder: $('results-placeholder'),
    resultsPanel: $('results-panel'),
    analyzeLoading: $('analyze-loading'),
    analyzeError: $('analyze-error'),
    analyzeErrorMsg: $('analyze-error-msg'),
    resultConfidence: $('result-confidence-badge'),
    resultPlatform: $('result-platform'),
    resultProvider: $('result-provider'),
    candidatesFieldset: $('candidates-fieldset'),
    correctedSnippet: $('corrected-snippet'),
    wcagRationale: $('wcag-rationale'),
    copyBtn: $('copy-btn'),
    saveResultBtn: $('save-result-btn'),
    saveCount: $('save-count'),

    // Export bar
    exportBar: $('export-bar'),
    exportCountLabel: $('export-count-label'),
    exportCsvBtn: $('export-csv-btn'),
    exportJsonBtn: $('export-json-btn'),
    clearExportBtn: $('clear-export-btn'),

    // Scan tab
    scanForm: $('scan-form'),
    scanUrl: $('scan-url'),
    scanBtn: $('scan-btn'),
    scanLoading: $('scan-loading'),
    scanError: $('scan-error'),
    scanErrorMsg: $('scan-error-msg'),
    scanResults: $('scan-results'),
    scanSummary: $('scan-summary'),
    auditTableBody: $('audit-table-body'),

    // Embed Checker tab
    checkerForm: $('checker-form'),
    checkerSnippet: $('checker-snippet'),
    checkerBtn: $('checker-btn'),
    checkerClear: $('checker-clear'),
    checkerLoading: $('checker-loading'),
    checkerError: $('checker-error'),
    checkerErrorMsg: $('checker-error-msg'),
    checkerPlaceholder: $('checker-placeholder'),
    checkerResultsPanel: $('checker-results-panel'),
    checkerScoreBar: $('checker-score-bar'),
    checkerElementBadge: $('checker-element-badge'),
    findingsList: $('findings-list'),
    minimalFixBlock: $('minimal-fix-block'),
    fullFixBlock: $('full-fix-block'),
    copyMinimalBtn: $('copy-minimal-btn'),
    copyFullBtn: $('copy-full-btn'),
    saveCheckerBtn: $('save-checker-btn'),
    checkerSaveCount: $('checker-save-count'),

    // Settings
    settingsToggle: $('settings-toggle'),
    settingsClose: $('settings-close'),
    settingsPanel: $('settings-panel'),
    settingsOverlay: $('settings-overlay'),
    settingsForm: $('settings-form'),
    settingsStatus: $('settings-status'),

    // SR announce
    srAnnounce: $('sr-announce'),
};

// ── Accessibility helpers ───────────────────────────────────────────────────
function announce(msg) {
    el.srAnnounce.textContent = '';
    requestAnimationFrame(() => { el.srAnnounce.textContent = msg; });
}

// ── Tabs ───────────────────────────────────────────────────────────────────
function activateTab(tab) {
    const tabs = [
        { id: 'analyze', btn: el.tabAnalyze, panel: el.panelAnalyze },
        { id: 'scan', btn: el.tabScan, panel: el.panelScan },
        { id: 'checker', btn: el.tabChecker, panel: el.panelChecker },
    ];
    tabs.forEach(t => {
        const active = t.id === tab;
        t.btn.setAttribute('aria-selected', active);
        t.btn.classList.toggle('active', active);
        t.panel.classList.toggle('active', active);
        t.panel.hidden = !active;
    });
}

el.tabAnalyze.addEventListener('click', () => activateTab('analyze'));
el.tabScan.addEventListener('click', () => activateTab('scan'));
el.tabChecker.addEventListener('click', () => activateTab('checker'));

// Keyboard tab navigation
const allTabs = [el.tabAnalyze, el.tabScan, el.tabChecker];
allTabs.forEach((btn, i, arr) => {
    btn.addEventListener('keydown', e => {
        if (e.key === 'ArrowRight') { arr[(i + 1) % arr.length].focus(); arr[(i + 1) % arr.length].click(); }
        if (e.key === 'ArrowLeft') { arr[(i - 1 + arr.length) % arr.length].focus(); arr[(i - 1 + arr.length) % arr.length].click(); }
    });
});

// ── Settings panel ─────────────────────────────────────────────────────────
function openSettings() {
    el.settingsPanel.hidden = false;
    el.settingsOverlay.hidden = false;
    el.settingsToggle.setAttribute('aria-expanded', 'true');
    setTimeout(() => el.settingsPanel.focus(), 50);
}
function closeSettings() {
    el.settingsPanel.hidden = true;
    el.settingsOverlay.hidden = true;
    el.settingsToggle.setAttribute('aria-expanded', 'false');
    el.settingsToggle.focus();
}

el.settingsToggle.addEventListener('click', openSettings);
el.settingsClose.addEventListener('click', closeSettings);
el.settingsOverlay.addEventListener('click', closeSettings);
document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !el.settingsPanel.hidden) closeSettings();
});

el.settingsForm.addEventListener('submit', async e => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(el.settingsForm).entries());
    el.settingsStatus.textContent = 'Saving…';
    try {
        const resp = await fetch('/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const json = await resp.json();
        if (resp.ok) {
            el.settingsStatus.textContent = '✓ Saved';
            announce('Settings saved successfully');
            setTimeout(() => { el.settingsStatus.textContent = ''; }, 3000);
        } else {
            el.settingsStatus.textContent = json.error || 'Error saving';
        }
    } catch {
        el.settingsStatus.textContent = 'Network error';
    }
});

// ── Analyze form ───────────────────────────────────────────────────────────
function showAnalyzeLoading(on) {
    el.analyzeLoading.hidden = !on;
    el.analyzeBtn.disabled = on;
    if (on) {
        el.resultsPlaceholder.hidden = true;
        el.resultsPanel.hidden = true;
        el.analyzeError.hidden = true;
    }
}

function showAnalyzeError(msg) {
    el.analyzeErrorMsg.textContent = msg;
    el.analyzeError.hidden = false;
    el.analyzeLoading.hidden = true;
    announce('Error: ' + msg);
}

function renderResults(data) {
    state.currentResult = data;
    state.selectedCandidateIndex = 0;

    // Status bar
    const conf = data.confidence || 'low';
    el.resultConfidence.textContent = conf.charAt(0).toUpperCase() + conf.slice(1) + ' Confidence';
    el.resultConfidence.className = 'badge badge-' + conf;

    if (data.platform) {
        el.resultPlatform.textContent = '· ' + data.platform.replace(/_/g, ' ');
    } else {
        el.resultPlatform.textContent = '';
    }

    if (data.provider_used) {
        el.resultProvider.textContent = 'via ' + data.provider_used;
    } else {
        el.resultProvider.textContent = data.confidence === 'high' ? 'via heuristics' : '';
    }

    // Candidates
    el.candidatesFieldset.innerHTML = '';
    const candidates = data.candidates || [];
    candidates.forEach((cand, idx) => {
        const optionEl = document.createElement('label');
        optionEl.className = 'candidate-option' + (idx === 0 ? ' selected' : '');
        optionEl.innerHTML = `
      <input type="radio" name="candidate" value="${idx}" ${idx === 0 ? 'checked' : ''} />
      <div class="candidate-info">
        <div class="candidate-rank">Option ${cand.rank || idx + 1}</div>
        <div class="candidate-title">${escHtml(cand.title)}</div>
        <div class="candidate-rationale">${escHtml(cand.rationale || '')}</div>
      </div>
    `;
        el.candidatesFieldset.appendChild(optionEl);
    });

    // Set initial snippet + rationale
    updateSnippetFromSelection(0);

    // Wire radio change
    el.candidatesFieldset.addEventListener('change', e => {
        if (e.target.name === 'candidate') {
            const idx = parseInt(e.target.value, 10);
            state.selectedCandidateIndex = idx;
            updateSnippetFromSelection(idx);
            // Update selected styling
            el.candidatesFieldset.querySelectorAll('.candidate-option').forEach((opt, i) => {
                opt.classList.toggle('selected', i === idx);
            });
        }
    });

    // Show panel
    el.resultsPlaceholder.hidden = true;
    el.analyzeLoading.hidden = true;
    el.analyzeError.hidden = true;
    el.resultsPanel.hidden = false;

    announce(`${candidates.length} title suggestions ready. Option 1 selected.`);
}

function updateSnippetFromSelection(idx) {
    const cand = (state.currentResult?.candidates || [])[idx];
    if (!cand) return;
    el.correctedSnippet.textContent = cand.corrected_snippet || '';
    el.wcagRationale.textContent = cand.rationale || '';
}

el.analyzeForm.addEventListener('submit', async e => {
    e.preventDefault();
    const snippet = el.iframeSnippet.value.trim();
    const srcOverride = el.srcOverride.value.trim();
    const llmProvider = el.llmProviderSel.value;

    if (!snippet && !srcOverride) {
        showAnalyzeError('Please provide an iframe HTML snippet or a source URL.');
        return;
    }

    showAnalyzeLoading(true);
    try {
        const resp = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ snippet, src_override: srcOverride, llm_provider: llmProvider || null }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Server error');
        renderResults(data);
    } catch (err) {
        showAnalyzeError(err.message || 'Unknown error occurred');
    } finally {
        showAnalyzeLoading(false);
    }
});

el.analyzeClear.addEventListener('click', () => {
    el.iframeSnippet.value = '';
    el.srcOverride.value = '';
    el.llmProviderSel.value = '';
    el.resultsPanel.hidden = true;
    el.analyzeError.hidden = true;
    el.resultsPlaceholder.hidden = false;
    el.iframeSnippet.focus();
    state.currentResult = null;
});

// ── Copy button ─────────────────────────────────────────────────────────────
el.copyBtn.addEventListener('click', async () => {
    const text = el.correctedSnippet.textContent;
    try {
        await navigator.clipboard.writeText(text);
        el.copyBtn.textContent = '✓ Copied!';
        announce('Snippet copied to clipboard');
        setTimeout(() => { el.copyBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg> Copy`; }, 2000);
    } catch {
        el.copyBtn.textContent = 'Copy failed';
    }
});

// ── Save to export ──────────────────────────────────────────────────────────
el.saveResultBtn.addEventListener('click', () => {
    if (!state.currentResult) return;
    const cand = state.currentResult.candidates[state.selectedCandidateIndex] || {};
    const entry = {
        source: el.iframeSnippet.value.trim() || el.srcOverride.value.trim(),
        platform: state.currentResult.platform || '',
        existing_title: state.currentResult.existing_title || '',
        audit_status: state.currentResult.audit?.status || '',
        candidates: state.currentResult.candidates,
        selected_title: cand.title || '',
        corrected_snippet: cand.corrected_snippet || '',
        rationale: cand.rationale || '',
        provider_used: state.currentResult.provider_used || 'heuristics',
        timestamp: new Date().toISOString(),
    };
    state.savedResults.push(entry);
    updateExportBar();
    announce(`Result saved. ${state.savedResults.length} result${state.savedResults.length !== 1 ? 's' : ''} ready to export.`);
});

function updateExportBar() {
    const n = state.savedResults.length;
    el.saveCount.textContent = n > 0 ? `${n} saved` : '';
    el.exportBar.hidden = n === 0;
    el.exportCountLabel.textContent = `${n} result${n !== 1 ? 's' : ''} ready to export`;
}

async function doExport(fmt) {
    if (!state.savedResults.length) return;
    try {
        const resp = await fetch('/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ format: fmt, results: state.savedResults }),
        });
        if (!resp.ok) throw new Error('Export failed');
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `a11y-iframe-report.${fmt}`;
        a.click();
        URL.revokeObjectURL(url);
        announce(`Exported ${state.savedResults.length} results as ${fmt.toUpperCase()}`);
    } catch (err) {
        alert('Export error: ' + err.message);
    }
}

el.exportCsvBtn.addEventListener('click', () => doExport('csv'));
el.exportJsonBtn.addEventListener('click', () => doExport('json'));
el.clearExportBtn.addEventListener('click', () => {
    state.savedResults = [];
    updateExportBar();
    announce('Export cleared');
});

// ── Scan tab ───────────────────────────────────────────────────────────────
function showScanLoading(on) {
    el.scanLoading.hidden = !on;
    el.scanBtn.disabled = on;
    if (on) {
        el.scanResults.hidden = true;
        el.scanError.hidden = true;
    }
}

function showScanError(msg) {
    el.scanErrorMsg.textContent = msg;
    el.scanError.hidden = false;
    el.scanLoading.hidden = true;
    announce('Scan error: ' + msg);
}

function renderScanResults(data) {
    const { iframes, summary, error } = data;

    if (error) { showScanError(error); return; }

    // Summary banner
    const total = data.total;
    const fails = summary.fail;
    const warns = summary.warn;

    if (total === 0) {
        el.scanSummary.textContent = 'No iframes found on this page.';
        el.scanSummary.className = 'scan-summary all-pass';
    } else if (fails === 0 && warns === 0) {
        el.scanSummary.textContent = `✓ All ${total} iframe${total !== 1 ? 's' : ''} have adequate title attributes.`;
        el.scanSummary.className = 'scan-summary all-pass';
    } else if (fails > 0) {
        el.scanSummary.innerHTML = `❌ <strong>${fails} of ${total}</strong> iframe${total !== 1 ? 's' : ''} ${fails !== 1 ? 'are' : 'is'} missing or have inadequate titles.${warns > 0 ? ` ⚠️ ${warns} ${warns !== 1 ? 'have' : 'has'} generic titles.` : ''}`;
        el.scanSummary.className = 'scan-summary has-failures';
    } else {
        el.scanSummary.innerHTML = `⚠️ <strong>${warns} of ${total}</strong> iframe${total !== 1 ? 's' : ''} ${warns !== 1 ? 'have' : 'has'} generic or insufficient titles.`;
        el.scanSummary.className = 'scan-summary has-warnings';
    }

    // Table rows
    el.auditTableBody.innerHTML = '';
    iframes.forEach(frame => {
        const tr = document.createElement('tr');
        const statusIcons = { pass: '✅', warning: '⚠️', fail: '❌' };
        const statusClasses = { pass: 'status-pass', warning: 'status-warning', fail: 'status-fail' };
        const icon = statusIcons[frame.audit.status] || '?';
        const statusClass = statusClasses[frame.audit.status] || '';
        const platformHtml = frame.platform
            ? `<span class="platform-badge">${escHtml(frame.platform.replace(/_/g, ' '))}</span>`
            : `<span class="platform-badge platform-unknown">Unknown</span>`;
        const titleHtml = frame.existing_title
            ? `<span class="title-cell" title="${escHtml(frame.existing_title)}">${escHtml(frame.existing_title)}</span>`
            : `<span class="title-cell empty">None</span>`;

        tr.innerHTML = `
      <td>${frame.index}</td>
      <td>${platformHtml}</td>
      <td>${titleHtml}</td>
      <td class="${statusClass}"><span class="status-icon" aria-hidden="true">${icon}</span>${escHtml(frame.audit.reason)}</td>
      <td><button class="btn btn-sm btn-secondary analyze-frame-btn" data-snippet="${escAttr(frame.snippet)}" aria-label="Analyze iframe ${frame.index}">Analyze</button></td>
    `;
        el.auditTableBody.appendChild(tr);
    });

    // Wire Analyze buttons
    el.auditTableBody.querySelectorAll('.analyze-frame-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const snippet = btn.dataset.snippet;
            el.iframeSnippet.value = snippet;
            el.srcOverride.value = '';
            activateTab('analyze');
            el.iframeSnippet.scrollIntoView({ behavior: 'smooth' });
            announce('iFrame loaded into Analyze tab. Submit to generate title suggestions.');
        });
    });

    el.scanResults.hidden = false;
    announce(`Scan complete. Found ${total} iframe${total !== 1 ? 's' : ''}. ${fails} failing, ${warns} warnings.`);
}

el.scanForm.addEventListener('submit', async e => {
    e.preventDefault();
    const url = el.scanUrl.value.trim();
    if (!url) { showScanError('Please enter a page URL.'); return; }
    showScanLoading(true);
    try {
        const resp = await fetch('/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Server error');
        renderScanResults(data);
    } catch (err) {
        showScanError(err.message || 'Could not scan page');
    } finally {
        showScanLoading(false);
    }
});

// ── Utilities ──────────────────────────────────────────────────────────────
function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
function escAttr(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/\n/g, '&#10;');
}

// ── Embed Checker tab ──────────────────────────────────────────────────────
const SEVERITY_ICONS = { error: '❌', warning: '⚠️', pass: '✅', info: 'ℹ️' };

function showCheckerLoading(on) {
    el.checkerLoading.hidden = !on;
    el.checkerBtn.disabled = on;
    if (on) {
        el.checkerPlaceholder.hidden = true;
        el.checkerResultsPanel.hidden = true;
        el.checkerError.hidden = true;
    }
}

function showCheckerError(msg) {
    el.checkerErrorMsg.textContent = msg;
    el.checkerError.hidden = false;
    el.checkerLoading.hidden = true;
    announce('Embed Checker error: ' + msg);
}

function renderCheckerResults(data) {
    const { element_type, findings, minimal_fix, full_fix, summary } = data;

    // Score bar
    el.checkerScoreBar.innerHTML = [
        summary.errors > 0 ? `<span class="score-pill score-pill-error">${SEVERITY_ICONS.error} ${summary.errors} Error${summary.errors !== 1 ? 's' : ''}</span>` : '',
        summary.warnings > 0 ? `<span class="score-pill score-pill-warning">${SEVERITY_ICONS.warning} ${summary.warnings} Warning${summary.warnings !== 1 ? 's' : ''}</span>` : '',
        summary.passes > 0 ? `<span class="score-pill score-pill-pass">${SEVERITY_ICONS.pass} ${summary.passes} Pass${summary.passes !== 1 ? 'es' : ''}</span>` : '',
        summary.info > 0 ? `<span class="score-pill score-pill-info">${SEVERITY_ICONS.info} ${summary.info} Info</span>` : '',
        `<span class="score-element-label">&lt;${escHtml(element_type)}&gt;</span>`,
    ].join('');

    el.checkerElementBadge.textContent = `— detected as <${element_type}>`;

    // Findings list
    el.findingsList.innerHTML = '';
    findings.forEach(f => {
        const li = document.createElement('li');
        li.className = `finding-item severity-${f.severity}`;
        li.innerHTML = `
      <span class="finding-icon" aria-hidden="true">${SEVERITY_ICONS[f.severity] || '·'}</span>
      <div class="finding-body">
        <div class="finding-header">
          <span class="finding-criterion">SC ${escHtml(f.criterion)}</span>
          <span class="finding-criterion-name">${escHtml(f.criterion_name)}</span>
          <span class="finding-level">Level ${escHtml(f.level)}</span>
        </div>
        <p class="finding-description">${escHtml(f.description)}</p>
        ${f.fix_hint ? `<p class="finding-fix-hint">Fix: ${escHtml(f.fix_hint)}</p>` : ''}
        ${f.url ? `<a class="finding-link" href="${escHtml(f.url)}" target="_blank" rel="noopener">WCAG 2.2 Understanding →</a>` : ''}
      </div>
    `;
        el.findingsList.appendChild(li);
    });

    el.minimalFixBlock.textContent = minimal_fix || '';
    el.fullFixBlock.textContent = full_fix || '';

    el.checkerPlaceholder.hidden = true;
    el.checkerLoading.hidden = true;
    el.checkerError.hidden = true;
    el.checkerResultsPanel.hidden = false;

    const errCount = summary.errors;
    announce(`Audit complete for <${element_type}>. ${errCount} error${errCount !== 1 ? 's' : ''}, ${summary.warnings} warning${summary.warnings !== 1 ? 's' : ''}, ${summary.passes} passed.`);
}

el.checkerForm.addEventListener('submit', async e => {
    e.preventDefault();
    const snippet = el.checkerSnippet.value.trim();
    if (!snippet) { showCheckerError('Please paste an embed snippet.'); return; }
    showCheckerLoading(true);
    try {
        const resp = await fetch('/check-embed', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ snippet }),
        });
        const data = await resp.json();
        if (!resp.ok || data.error) throw new Error(data.error || 'Server error');
        renderCheckerResults(data);
    } catch (err) {
        showCheckerError(err.message || 'Unknown error');
    } finally {
        showCheckerLoading(false);
    }
});

el.checkerClear.addEventListener('click', () => {
    el.checkerSnippet.value = '';
    el.checkerResultsPanel.hidden = true;
    el.checkerError.hidden = true;
    el.checkerPlaceholder.hidden = false;
    el.checkerSnippet.focus();
});

// Copy buttons for Embed Checker
async function copyCode(text, btn) {
    try {
        await navigator.clipboard.writeText(text);
        const orig = btn.textContent;
        btn.textContent = '✓ Copied!';
        announce('Code copied to clipboard');
        setTimeout(() => { btn.textContent = orig; }, 2000);
    } catch { btn.textContent = 'Copy failed'; }
}
el.copyMinimalBtn.addEventListener('click', () => copyCode(el.minimalFixBlock.textContent, el.copyMinimalBtn));
el.copyFullBtn.addEventListener('click', () => copyCode(el.fullFixBlock.textContent, el.copyFullBtn));

// Save checker result to export
el.saveCheckerBtn.addEventListener('click', () => {
    const snippet = el.checkerSnippet.value.trim();
    const elementType = el.checkerElementBadge.textContent.replace(/— detected as |[<>]/g, '').trim();
    const entry = {
        source: snippet.substring(0, 120),
        platform: elementType,
        existing_title: '',
        audit_status: '',
        candidates: [],
        selected_title: '',
        corrected_snippet: el.minimalFixBlock.textContent,
        rationale: 'Full accessible version: ' + el.fullFixBlock.textContent.substring(0, 200),
        provider_used: 'embed-checker',
        timestamp: new Date().toISOString(),
    };
    state.savedResults.push(entry);
    updateExportBar();
    announce(`Embed Checker result saved. ${state.savedResults.length} total ready to export.`);
});

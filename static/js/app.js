const { createApp } = Vue;

createApp({
    data() {
        return {
            activeTab: 'embed',  // 'embed' | 'pdf'
            mode: 'snippet',     // 'snippet' | 'url' | 'pdf'
            snippet: '',
            url: '',
            loading: false,
            error: null,
            results: [],
            selectedResult: null,
            savedResults: [],
            showDuplicates: false,
            evidenceUrl: null,
            pdfUrl: '',
            saveMessage: '',
            announcement: ''
        };
    },
    computed: {
        filteredResults() {
            if (this.showDuplicates) return this.results;
            return this.results.filter(r => !r.is_duplicate);
        }
    },
    methods: {
        switchTab(tab) {
            this.activeTab = tab;
            this.mode = tab === 'pdf' ? 'pdf' : 'snippet';
            this.results = [];
            this.selectedResult = null;
            this.error = null;
            this.evidenceUrl = null;
            this.announce(`Switched to ${tab === 'pdf' ? 'PDF' : 'Embed'} Auditor.`);
        },

        async runAudit() {
            this.error = null;
            this.results = [];
            this.selectedResult = null;
            this.evidenceUrl = null; // Clear old evidence at start of new run
            this.loading = true;
            this.announce('Audit started...');

            try {
                let response;
                if (this.mode === 'pdf') {
                    const fileInput = this.$refs.pdfFile;
                    if (fileInput && fileInput.files.length > 0) {
                        // File Upload
                        const formData = new FormData();
                        formData.append('file', fileInput.files[0]);
                        response = await fetch('/check-pdf', {
                            method: 'POST',
                            body: formData
                        });
                    } else if (this.pdfUrl) {
                        // URL Scan
                        response = await fetch('/check-pdf', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ url: this.pdfUrl })
                        });
                    } else {
                        throw new Error('Please provide a PDF URL or upload a file.');
                    }
                } else {
                    // Snippet or URL Mode
                    const payload = this.mode === 'snippet'
                        ? { snippet: this.snippet }
                        : { url: this.url };

                    response = await fetch('/check-embed', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                }

                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.error || 'Server error');
                }

                const data = await response.json();
                if (this.mode === 'pdf') {
                    this.results = [data]; // Wrap single PDF result in array
                } else {
                    this.results = data.findings || [];
                    this.evidenceUrl = data.evidence || null;
                }

                if (this.results.length === 0) {
                    this.error = "No media embeds found.";
                } else {
                    this.announce(`Audit complete. Found ${this.results.length} items.`);
                }
            } catch (err) {
                this.error = err.message;
                this.announce(`Error: ${err.message}`);
            } finally {
                this.loading = false;
            }
        },

        clear() {
            this.snippet = '';
            this.url = '';
            this.pdfUrl = '';
            if (this.$refs.pdfFile) this.$refs.pdfFile.value = '';
            this.results = [];
            this.selectedResult = null;
            this.evidenceUrl = null; // Clear evidence image
            this.error = null;
            this.announce('Audit cleared.');
        },

        selectResult(res) {
            this.selectedResult = res;
            this.announce(`Viewing details for ${res.element_type}.`);
        },

        getStatusClass(res) {
            const s = res.summary || {};
            if (s.critical > 0) return 'status-fail';
            if (s.warning > 0) return 'status-warn';
            if (s.manual > 0) return 'status-info';
            return 'status-pass';
        },

        getStatusText(res) {
            const s = res.summary || {};
            let status = '✅ Pass';
            if (s.critical > 0) status = '❌ Critical';
            else if (s.warning > 0) status = '⚠️ Warning';
            else if (s.manual > 0) status = '🔍 Manual Check';

            return res.is_duplicate ? `${status} (Duplicate)` : status;
        },

        getDisplaySrc(res) {
            if (!res.src && !res.frame_url) return 'Unknown Source';
            const url = res.src || res.frame_url;
            try {
                const u = new URL(url);
                let path = u.pathname;
                if (path.length > 20) path = '...' + path.slice(-17);
                return u.hostname + path;
            } catch (e) {
                return url.length > 30 ? url.substring(0, 27) + '...' : url;
            }
        },

        getTierClass(tier) {
            return (tier || 'info').toLowerCase().replace(' ', '-');
        },

        async copyText(text) {
            try {
                await navigator.clipboard.writeText(text);
                this.announce('Copied to clipboard.');
            } catch (err) {
                console.error('Copy failed:', err);
            }
        },

        saveResult(res) {
            this.savedResults.push(JSON.parse(JSON.stringify(res)));
            this.saveMessage = 'Item saved!';
            this.announce('Result saved for export.');
            setTimeout(() => { this.saveMessage = ''; }, 2000);
        },

        async exportData(format) {
            try {
                const response = await fetch('/export', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        format,
                        results: this.savedResults
                    })
                });

                if (!response.ok) throw new Error('Export failed');

                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `a11y-report.${format}`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                this.announce(`Downloading ${format.toUpperCase()} report.`);
            } catch (err) {
                alert('Export error: ' + err.message);
            }
        },

        announce(msg) {
            this.announcement = msg;
            setTimeout(() => { this.announcement = ''; }, 3000);
        }
    }
}).mount('#app');

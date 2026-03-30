const { createApp } = Vue;

createApp({
    data() {
        return {
            mode: 'snippet',
            snippet: '',
            url: '',
            loading: false,
            error: null,
            results: [],
            selectedResult: null,
            savedResults: [],
            saveMessage: '',
            announcement: ''
        };
    },
    methods: {
        async runAudit() {
            this.error = null;
            this.results = [];
            this.selectedResult = null;
            this.loading = true;
            this.announce('Audit started...');

            const payload = this.mode === 'snippet'
                ? { snippet: this.snippet }
                : { url: this.url };

            try {
                const response = await fetch('/check-embed', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.error || 'Server error');
                }

                const data = await response.json();
                this.results = data.findings || [];

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
            this.results = [];
            this.selectedResult = null;
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
            if (s.critical > 0) return '❌ Critical';
            if (s.warning > 0) return '⚠️ Warning';
            if (s.manual > 0) return '🔍 Manual Check';
            return '✅ Pass';
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

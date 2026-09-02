// Lobby JavaScript - Enhanced Poker Platform
class PokerLobby {
    // Offer a play-money reload when the bankroll is nearly gone (GitHub #10)
    async checkBankrollReload() {
        const btn = document.getElementById('reload-bankroll-btn');
        if (!btn || !window.currentUserId) return;
        try {
            const status = await (await fetch('/api/bankroll/reload-status')).json();
            btn.hidden = !(status.success && status.eligible);
        } catch (e) {
            btn.hidden = true;
        }
        if (btn.dataset.bound) return;
        btn.dataset.bound = '1';
        btn.addEventListener('click', async () => {
            try {
                const resp = await fetch('/api/bankroll/reload', { method: 'POST' });
                const data = await resp.json();
                if (!resp.ok || !data.success) {
                    this.showNotification(data.error || 'Reload not available', 'error');
                    return;
                }
                const el = document.querySelector('.user-info .bankroll');
                if (el) el.textContent = `$${data.bankroll}`;
                btn.hidden = true;
                this.showNotification(`Bankroll reloaded to $${data.bankroll}`, 'success');
            } catch (e) {
                this.showNotification('Reload not available', 'error');
            }
        });
    }

    // One-time orientation for a new account (GitHub #9). localStorage is a
    // per-browser convenience only, so guard every access.
    showFirstVisitBanner() {
        const banner = document.getElementById('first-visit-banner');
        if (!banner) return;
        let seen = false;
        try { seen = localStorage.getItem('pokerWelcomeSeen') === '1'; } catch (e) { /* ignore */ }
        if (seen) return;
        banner.hidden = false;
        const dismiss = document.getElementById('first-visit-dismiss');
        if (dismiss) {
            dismiss.addEventListener('click', () => {
                banner.hidden = true;
                try { localStorage.setItem('pokerWelcomeSeen', '1'); } catch (e) { /* ignore */ }
            });
        }
    }

    constructor() {
        this.socket = io();
        this.tables = [];
        this.userTables = [];  // Table IDs where current user is seated
        this.variants = [];    // Available game variants from API
        this.variantMap = {};   // variant_name -> display_name lookup
        this.CUSTOM_MIX_VALUE = '__custom_mix__';  // sentinel for the builder option
        this.customMixMode = false;
        this.savedMixes = [];   // user's saved custom mixes (Phase 9.3)
        this.CUSTOM_VARIANT_VALUE = '__custom_variant__';  // sentinel for the variant builder (9.5)
        this.CUSTOM_VARIANT_PREFIX = 'customvar:';         // dropdown value prefix for saved variants
        this.customVariantMode = false;
        this.savedVariants = [];        // user's saved custom variants (Phase 9.5)
        this.selectedCustomVariantId = null;  // library id to create a table from
        this.cvConfig = null;           // parsed config in the builder (JSON is source of truth)
        this.cvValidateTimer = null;    // debounce handle for editor validation
        this.filters = {
            variant: '',
            stakes: '',
            structure: '',
            players: ''
        };

        this.init();
    }

    init() {
        this.showFirstVisitBanner();
        this.checkBankrollReload();
        this.setupEventListeners();
        this.setupSocketEvents();
        this.loadVariants();
        this.loadTables();
        this.setupStakesConfiguration();
        this.loadSavedVariants();  // populates the "My Variants" dropdown group (9.5)
    }

    requireLogin() {
        if (window.isAuthenticated) return true;
        this.showNotification('Please log in to play', 'info');
        setTimeout(() => { window.location.href = '/auth/login'; }, 800);
        return false;
    }

    setupEventListeners() {
        // Action buttons
        document.getElementById('create-table-btn').addEventListener('click', () => {
            if (!this.requireLogin()) return;
            this.resetCustomMixBuilder();
            this.resetCustomVariantBuilder();
            this.showModal('create-table-modal');
        });

        document.getElementById('join-private-btn').addEventListener('click', () => {
            if (!this.requireLogin()) return;
            this.showModal('join-private-modal');
        });

        document.getElementById('refresh-tables-btn').addEventListener('click', () => {
            this.loadTables();
        });

        // Live search for the 300+ game variant list in the create form
        const variantSearch = document.getElementById('variant-search');
        if (variantSearch) {
            variantSearch.addEventListener('input', () => {
                this.populateVariantDropdowns(variantSearch.value);
            });
        }

        // Filter changes
        document.getElementById('variant-filter').addEventListener('change', (e) => {
            this.filters.variant = e.target.value;
            this.filterTables();
        });

        document.getElementById('stakes-filter').addEventListener('change', (e) => {
            this.filters.stakes = e.target.value;
            this.filterTables();
        });

        document.getElementById('structure-filter').addEventListener('change', (e) => {
            this.filters.structure = e.target.value;
            this.filterTables();
        });

        document.getElementById('players-filter').addEventListener('change', (e) => {
            this.filters.players = e.target.value;
            this.filterTables();
        });

        // Form submissions
        document.getElementById('create-table-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createTable();
        });

        document.getElementById('join-private-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.joinPrivateTable();
        });

        document.getElementById('edit-table-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitEditTable();
        });

        // Private table checkbox
        document.getElementById('is-private').addEventListener('change', (e) => {
            const privateOptions = document.getElementById('private-options');
            privateOptions.style.display = e.target.checked ? 'block' : 'none';
        });

        // Game variant change - update available betting structures and show rules link
        document.getElementById('game-variant').addEventListener('change', (e) => {
            if (e.target.value === this.CUSTOM_MIX_VALUE) {
                this.exitCustomVariantMode();
                this.enterCustomMixMode();
                return;
            }
            if (e.target.value === this.CUSTOM_VARIANT_VALUE) {
                this.exitCustomMixMode();
                this.enterCustomVariantMode();
                return;
            }
            this.exitCustomMixMode();
            this.exitCustomVariantMode();
            if (e.target.value.startsWith(this.CUSTOM_VARIANT_PREFIX)) {
                // A saved custom variant picked directly for table creation.
                this.selectCustomVariant(e.target.value.slice(this.CUSTOM_VARIANT_PREFIX.length));
                return;
            }
            this.selectedCustomVariantId = null;
            this.updateBettingStructureOptions(e.target.value);
            const rulesLink = document.getElementById('view-rules-link');
            if (rulesLink) {
                rulesLink.style.display = e.target.value ? 'inline' : 'none';
            }
        });

        // Custom variant builder controls (Phase 9.5)
        document.getElementById('cv-base-variant').addEventListener('change', (e) => {
            if (e.target.value) this.loadCvBase(e.target.value);
        });
        document.getElementById('cv-name').addEventListener('input', (e) => {
            if (this.cvConfig) {
                this.cvConfig.game = e.target.value;
                this.cvSyncEditor(false);
            }
        });
        document.getElementById('cv-json').addEventListener('input', () => this.cvJsonChanged());
        document.getElementById('cv-knobs').addEventListener('change', (e) => {
            const knob = e.target.closest('[data-knob]');
            if (knob) this.applyKnob(knob);
        });
        document.getElementById('cv-validate-btn').addEventListener('click', () => this.cvValidate(true));
        document.getElementById('cv-save-btn').addEventListener('click', () => this.saveCustomVariant());
        document.getElementById('saved-variant-select').addEventListener('change', (e) => this.loadSavedVariant(e.target.value));
        document.getElementById('delete-variant-btn').addEventListener('click', () => this.deleteSavedVariant());

        // Custom mix builder controls (Phase 9.3)
        document.getElementById('add-mix-leg').addEventListener('click', () => this.addMixLeg());
        document.getElementById('mix-dealers-choice').addEventListener('change', (e) => {
            // Relabel the leg list: a fixed rotation vs a pickable menu (Phase 9.4)
            document.getElementById('mix-legs-label').textContent = e.target.checked
                ? 'Allowed games (dealer picks one each orbit):'
                : 'Games in rotation (played in order, one per orbit):';
        });
        document.getElementById('save-mix-btn').addEventListener('click', () => this.saveCustomMix());
        document.getElementById('saved-mix-select').addEventListener('change', (e) => this.loadSavedMix(e.target.value));
        document.getElementById('delete-mix-btn').addEventListener('click', () => this.deleteSavedMix());
        // Delegated handlers for dynamically-rendered leg rows
        document.getElementById('mix-legs').addEventListener('click', (e) => {
            const row = e.target.closest('.mix-leg');
            if (!row) return;
            if (e.target.classList.contains('mix-leg-remove')) this.removeMixLeg(row);
            else if (e.target.classList.contains('mix-leg-up')) this.moveMixLeg(row, -1);
            else if (e.target.classList.contains('mix-leg-down')) this.moveMixLeg(row, 1);
        });
        document.getElementById('mix-legs').addEventListener('change', (e) => {
            if (e.target.classList.contains('mix-leg-variant')) {
                this.populateLegStructures(e.target.closest('.mix-leg'));
            }
        });

        // Betting structure change
        document.getElementById('betting-structure').addEventListener('change', (e) => {
            this.updateStakesInputs(e.target.value);
        });

        // Modal close on background click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal(modal.id);
                }
            });
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeAllModals();
            }
        });
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.showNotification('Connected to server', 'success');
            this.loadTables();
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.showNotification('Disconnected from server', 'error');
        });

        this.socket.on('table_list', (data) => {
            this.tables = data.tables || [];
            this.userTables = data.user_tables || [];  // Tables where user is seated
            this.renderTables();
        });

        this.socket.on('table_joined', (data) => {
            this.showNotification('Joined table successfully!', 'success');
            this.closeAllModals();

            // Redirect to the table
            if (data.table_id) {
                window.location.href = `/table/${data.table_id}`;
            }
        });

        this.socket.on('error', (data) => {
            this.showNotification(data.message || 'An error occurred', 'error');
        });

        this.socket.on('table_updated', (data) => {
            // Update specific table in the list
            const tableIndex = this.tables.findIndex(t => t.id === data.table.id);
            if (tableIndex !== -1) {
                this.tables[tableIndex] = data.table;
                this.renderTables();
            }
        });

        this.socket.on('table_list_updated', (data) => {
            // A table was created or deleted — reload the full table list
            this.loadTables();
        });
    }

    setupStakesConfiguration() {
        // Initialize with no-limit structure
        this.updateStakesInputs('no-limit');
    }

    async loadVariants() {
        try {
            const response = await fetch('/table/variants');
            const data = await response.json();
            if (data.success) {
                this.variants = data.variants;
                // Build lookup map
                this.variantMap = {};
                for (const v of this.variants) {
                    this.variantMap[v.name] = v.display_name;
                }
                this.populateVariantDropdowns();
            }
        } catch (error) {
            console.error('Failed to load variants:', error);
        }
    }

    populateVariantDropdowns(searchTerm = '') {
        // Group variants by category
        const categoryOrder = ['Mixed', "Hold'em", 'Omaha', 'Stud', 'Draw', 'Pineapple', 'Dramaha', 'Straight', 'Other'];
        const term = searchTerm.trim().toLowerCase();
        const grouped = {};
        for (const v of this.variants) {
            if (term && !v.display_name.toLowerCase().includes(term)) continue;
            const cat = v.category || 'Other';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(v);
        }

        // Build optgroup HTML for the create-table dropdown
        const createSelect = document.getElementById('game-variant');
        const previous = createSelect.value;
        let matchCount = 0;
        let createHtml = `<option value="">${term ? 'Matching games' : 'Select a variant'}</option>`;
        // Custom mix builder entry (Phase 9.3) — always offered, plus on "custom"/"mix" search
        if (!term || 'custom mix build'.includes(term)) {
            createHtml += `<option value="${this.CUSTOM_MIX_VALUE}">🎲 Build a Custom Mix…</option>`;
        }
        // Custom variant builder entry (Phase 9.5)
        if (!term || 'custom variant design'.includes(term)) {
            createHtml += `<option value="${this.CUSTOM_VARIANT_VALUE}">🛠️ Design a Custom Variant…</option>`;
        }
        // Saved custom variants (Phase 9.5) — playable directly from the dropdown
        const savedMatches = this.savedVariants.filter(
            v => !term || v.display_name.toLowerCase().includes(term)
        );
        if (savedMatches.length) {
            createHtml += '<optgroup label="My Variants">';
            for (const v of savedMatches) {
                createHtml += `<option value="${this.CUSTOM_VARIANT_PREFIX}${this.escapeHtml(v.id)}">${this.escapeHtml(v.display_name)}</option>`;
                matchCount++;
            }
            createHtml += '</optgroup>';
        }
        for (const cat of categoryOrder) {
            const games = grouped[cat];
            if (!games || games.length === 0) continue;
            createHtml += `<optgroup label="${cat}">`;
            for (const g of games) {
                createHtml += `<option value="${g.name}">${g.display_name}</option>`;
                matchCount++;
            }
            createHtml += '</optgroup>';
        }
        if (term && matchCount === 0) {
            createHtml = '<option value="">No games match</option>';
        }
        createSelect.innerHTML = createHtml;
        // Keep the selection if it survived the filter; auto-pick a single match
        if ([...createSelect.options].some(o => o.value === previous)) {
            createSelect.value = previous;
        } else if (term && matchCount === 1) {
            createSelect.selectedIndex = 1;
            createSelect.dispatchEvent(new Event('change'));
        }

        if (term) return; // the table filter dropdown always shows everything

        // Build flat list for filter dropdown (just unique variants seen in tables)
        const filterSelect = document.getElementById('variant-filter');
        let filterHtml = '<option value="">All Variants</option>';
        for (const cat of categoryOrder) {
            const games = grouped[cat];
            if (!games || games.length === 0) continue;
            filterHtml += `<optgroup label="${cat}">`;
            for (const g of games) {
                filterHtml += `<option value="${g.name}">${g.display_name}</option>`;
            }
            filterHtml += '</optgroup>';
        }
        filterSelect.innerHTML = filterHtml;
    }

    // --- Custom mix builder (Phase 9.3) ---------------------------------------

    singleVariants() {
        // Variants eligible as mix legs: real games only, never other mixes.
        return this.variants
            .filter(v => !v.is_mixed)
            .sort((a, b) => a.display_name.localeCompare(b.display_name));
    }

    enterCustomMixMode() {
        this.customMixMode = true;
        document.getElementById('custom-mix-builder').style.display = 'block';
        document.getElementById('betting-structure-group').style.display = 'none';
        const rulesLink = document.getElementById('view-rules-link');
        if (rulesLink) rulesLink.style.display = 'none';
        // Mixes use Limit base stakes; force the stakes inputs to Limit.
        document.getElementById('betting-structure').value = 'limit';
        this.updateStakesInputs('limit');
        if (document.getElementById('mix-legs').children.length === 0) {
            this.addMixLeg();
            this.addMixLeg();
        }
        this.loadSavedMixes();
    }

    exitCustomMixMode() {
        this.customMixMode = false;
        document.getElementById('custom-mix-builder').style.display = 'none';
        document.getElementById('betting-structure-group').style.display = '';
    }

    resetCustomMixBuilder() {
        this.exitCustomMixMode();
        document.getElementById('mix-name').value = '';
        document.getElementById('mix-legs').innerHTML = '';
        const dc = document.getElementById('mix-dealers-choice');
        if (dc) dc.checked = false;
        const label = document.getElementById('mix-legs-label');
        if (label) label.textContent = 'Games in rotation (played in order, one per orbit):';
        const sel = document.getElementById('saved-mix-select');
        if (sel) sel.value = '';
    }

    legVariantOptionsHtml(selected = '') {
        let html = '<option value="">Select game…</option>';
        for (const v of this.singleVariants()) {
            const sel = v.name === selected ? ' selected' : '';
            html += `<option value="${v.name}"${sel}>${v.display_name}</option>`;
        }
        return html;
    }

    addMixLeg(variant = '', structure = '') {
        const row = document.createElement('div');
        row.className = 'mix-leg';
        row.innerHTML = `
            <select class="mix-leg-variant">${this.legVariantOptionsHtml(variant)}</select>
            <select class="mix-leg-structure"><option value="">Structure…</option></select>
            <div class="mix-leg-buttons">
                <button type="button" class="mix-leg-up" title="Move up">▲</button>
                <button type="button" class="mix-leg-down" title="Move down">▼</button>
                <button type="button" class="mix-leg-remove" title="Remove">✕</button>
            </div>`;
        document.getElementById('mix-legs').appendChild(row);
        if (variant) this.populateLegStructures(row, structure);
    }

    populateLegStructures(row, selected = '') {
        const variantName = row.querySelector('.mix-leg-variant').value;
        const structSelect = row.querySelector('.mix-leg-structure');
        const variant = this.variants.find(v => v.name === variantName);
        if (!variant) {
            structSelect.innerHTML = '<option value="">Structure…</option>';
            return;
        }
        let html = '';
        for (const bs of variant.betting_structures) {
            const sel = bs === selected ? ' selected' : '';
            html += `<option value="${bs}"${sel}>${bs}</option>`;
        }
        structSelect.innerHTML = html;
        // Default to the first (or sole) supported structure when none chosen.
        if (!selected && variant.betting_structures.length) {
            structSelect.value = variant.betting_structures[0];
        }
    }

    removeMixLeg(row) {
        const legs = document.getElementById('mix-legs');
        if (legs.children.length <= 2) {
            this.showNotification('A mix needs at least 2 games', 'info');
            return;
        }
        row.remove();
    }

    moveMixLeg(row, dir) {
        const legs = document.getElementById('mix-legs');
        if (dir < 0 && row.previousElementSibling) {
            legs.insertBefore(row, row.previousElementSibling);
        } else if (dir > 0 && row.nextElementSibling) {
            legs.insertBefore(row.nextElementSibling, row);
        }
    }

    collectRotation() {
        const rotation = [];
        for (const row of document.querySelectorAll('#mix-legs .mix-leg')) {
            const variant = row.querySelector('.mix-leg-variant').value;
            const bettingStructure = row.querySelector('.mix-leg-structure').value;
            if (variant) rotation.push({ variant, bettingStructure });
        }
        return rotation;
    }

    async loadSavedMixes() {
        try {
            const res = await fetch('/api/custom-mixes');
            const data = await res.json();
            if (data.success) {
                this.savedMixes = data.mixes || [];
                this.renderSavedMixSelect();
            }
        } catch (e) {
            console.error('Failed to load saved mixes:', e);
        }
    }

    renderSavedMixSelect() {
        const group = document.getElementById('saved-mix-group');
        const sel = document.getElementById('saved-mix-select');
        if (!this.savedMixes.length) {
            group.style.display = 'none';
            return;
        }
        group.style.display = 'block';
        let html = '<option value="">— My Mixes —</option>';
        for (const m of this.savedMixes) {
            html += `<option value="${this.escapeHtml(m.id)}">${this.escapeHtml(m.display_name)}</option>`;
        }
        sel.innerHTML = html;
    }

    loadSavedMix(mixId) {
        if (!mixId) return;
        const mix = this.savedMixes.find(m => m.id === mixId);
        if (!mix) return;
        document.getElementById('mix-name').value = mix.display_name;
        document.getElementById('mix-legs').innerHTML = '';
        for (const leg of mix.rotation) {
            this.addMixLeg(leg.variant, leg.bettingStructure);
        }
    }

    async saveCustomMix() {
        const mixName = document.getElementById('mix-name').value.trim();
        const rotation = this.collectRotation();
        if (!mixName) {
            this.showNotification('Give your mix a name', 'error');
            return;
        }
        if (rotation.length < 2) {
            this.showNotification('A mix needs at least 2 games', 'error');
            return;
        }
        try {
            const res = await fetch('/api/custom-mixes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ display_name: mixName, rotation })
            });
            const data = await res.json();
            if (data.success) {
                this.showNotification('Mix saved to your library', 'success');
                await this.loadSavedMixes();
                document.getElementById('saved-mix-select').value = data.mix.id;
            } else {
                this.showNotification(data.error || 'Could not save mix', 'error');
            }
        } catch (e) {
            this.showNotification('Could not save mix', 'error');
        }
    }

    async deleteSavedMix() {
        const sel = document.getElementById('saved-mix-select');
        const mixId = sel.value;
        if (!mixId) {
            this.showNotification('Pick a saved mix to delete', 'info');
            return;
        }
        const mix = this.savedMixes.find(m => m.id === mixId);
        if (!confirm(`Delete "${mix ? mix.display_name : 'this mix'}" from your library?`)) return;
        try {
            const res = await fetch(`/api/custom-mixes/${mixId}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                this.showNotification('Mix deleted', 'success');
                await this.loadSavedMixes();
            } else {
                this.showNotification(data.error || 'Could not delete mix', 'error');
            }
        } catch (e) {
            this.showNotification('Could not delete mix', 'error');
        }
    }

    // --- Custom variant builder (Phase 9.5) -----------------------------------
    // The JSON editor is the source of truth (this.cvConfig mirrors it when it
    // parses); knobs rewrite cvConfig and re-serialize into the editor.

    enterCustomVariantMode() {
        this.customVariantMode = true;
        document.getElementById('custom-variant-builder').style.display = 'block';
        const rulesLink = document.getElementById('view-rules-link');
        if (rulesLink) rulesLink.style.display = 'none';
        this.populateCvBasePicker();
        this.loadSavedVariants();
    }

    exitCustomVariantMode() {
        this.customVariantMode = false;
        document.getElementById('custom-variant-builder').style.display = 'none';
    }

    resetCustomVariantBuilder() {
        this.exitCustomVariantMode();
        this.cvConfig = null;
        this.selectedCustomVariantId = null;
        document.getElementById('cv-name').value = '';
        document.getElementById('cv-json').value = '';
        document.getElementById('cv-knobs').innerHTML = '';
        document.getElementById('cv-base-variant').value = '';
        const sel = document.getElementById('saved-variant-select');
        if (sel) sel.value = '';
        this.cvShowValidation(null);
    }

    populateCvBasePicker() {
        const sel = document.getElementById('cv-base-variant');
        if (sel.options.length > 1) return; // already populated
        let html = '<option value="">Select a game to clone…</option>';
        for (const v of this.singleVariants()) {
            html += `<option value="${v.name}">${v.display_name}</option>`;
        }
        sel.innerHTML = html;
    }

    async loadCvBase(stem) {
        try {
            const res = await fetch(`/table/game-configs/${stem}`);
            const data = await res.json();
            if (!data.success) {
                this.showNotification(data.error || 'Could not load game config', 'error');
                return;
            }
            this.cvConfig = data.config;
            const base = this.variants.find(v => v.name === stem);
            const name = `${base ? base.display_name : this.cvConfig.game} (Custom)`;
            this.cvConfig.game = name;
            document.getElementById('cv-name').value = name;
            this.cvSyncEditor(true);
            this.cvScheduleValidate();
        } catch (e) {
            this.showNotification('Could not load game config', 'error');
        }
    }

    /** Re-serialize cvConfig into the editor; optionally re-render the knobs. */
    cvSyncEditor(renderKnobs = true) {
        document.getElementById('cv-json').value = JSON.stringify(this.cvConfig, null, 2);
        if (renderKnobs) this.renderVariantKnobs();
        this.cvSetKnobsEnabled(true);
    }

    cvJsonChanged() {
        const text = document.getElementById('cv-json').value;
        try {
            this.cvConfig = JSON.parse(text);
        } catch (e) {
            // Unparseable JSON: grey the knobs out and report locally, no server call.
            this.cvSetKnobsEnabled(false);
            this.cvShowValidation({ valid: false, errors: [{ stage: 'json', message: `JSON does not parse: ${e.message}` }], warnings: [] });
            return;
        }
        const nameInput = document.getElementById('cv-name');
        if (typeof this.cvConfig.game === 'string') nameInput.value = this.cvConfig.game;
        this.renderVariantKnobs();
        this.cvSetKnobsEnabled(true);
        this.cvScheduleValidate();
    }

    cvScheduleValidate() {
        clearTimeout(this.cvValidateTimer);
        this.cvValidateTimer = setTimeout(() => this.cvValidate(false), 800);
    }

    cvSetKnobsEnabled(enabled) {
        const knobs = document.getElementById('cv-knobs');
        knobs.classList.toggle('cv-knobs-disabled', !enabled);
        for (const el of knobs.querySelectorAll('select, input')) el.disabled = !enabled;
    }

    // Low-qualifier presets: N-or-better for a5_low is [1, C(N,5)] — the count of
    // distinct no-pair 5-card rank sets with high card ≤ N (matches omaha_x_or_better).
    static get QUALIFIER_PRESETS() {
        return { '': null, '9': [1, 126], '8': [1, 56], '7': [1, 21], '6': [1, 6], '5': [1, 1] };
    }

    static get DECK_TYPES() {
        return { standard: 52, short_27_ja: 40, short_6a: 36, short_ta: 20 };
    }

    renderVariantKnobs() {
        const container = document.getElementById('cv-knobs');
        const cfg = this.cvConfig;
        if (!cfg || typeof cfg !== 'object') {
            container.innerHTML = '';
            return;
        }
        let html = '';

        // Deck type knob
        const deckType = cfg.deck && cfg.deck.type;
        if (deckType in PokerLobby.DECK_TYPES) {
            const labels = { standard: 'Standard (52)', short_27_ja: 'Short 2-7 + JA (40)', short_6a: 'Short 6-A (36)', short_ta: 'Short T-A (20)' };
            html += `<div class="cv-knob"><label>Deck:</label><select data-knob="deck">`;
            for (const [t, n] of Object.entries(PokerLobby.DECK_TYPES)) {
                html += `<option value="${t}"${t === deckType ? ' selected' : ''}>${labels[t] || t} </option>`;
            }
            html += '</select></div>';
        }

        // Per-side knobs only when the config has a plain bestHand array
        const bestHands = Array.isArray(cfg.showdown && cfg.showdown.bestHand) ? cfg.showdown.bestHand : [];
        bestHands.forEach((bh, i) => {
            const label = this.escapeHtml(bh.name || `Hand ${i + 1}`);
            // Evaluation type select
            if (typeof bh.evaluationType === 'string' && Array.isArray(window.evaluationTypes) && window.evaluationTypes.length) {
                html += `<div class="cv-knob"><label>${label} evaluation:</label><select data-knob="evaltype" data-index="${i}">`;
                for (const et of window.evaluationTypes) {
                    html += `<option value="${et}"${et === bh.evaluationType ? ' selected' : ''}>${et}</option>`;
                }
                html += '</select></div>';
            }
            // Low qualifier presets (a5_low sides only — the classic X-or-better family)
            if (bh.evaluationType === 'a5_low') {
                const current = Array.isArray(bh.qualifier) ? String(this.qualifierToPreset(bh.qualifier)) : '';
                html += `<div class="cv-knob"><label>${label} qualifier:</label><select data-knob="qualifier" data-index="${i}">`;
                html += `<option value=""${current === '' ? ' selected' : ''}>None (always qualifies)</option>`;
                for (const n of ['9', '8', '7', '6', '5']) {
                    html += `<option value="${n}"${current === n ? ' selected' : ''}>${n}-or-better</option>`;
                }
                html += '</select></div>';
            }
        });

        container.innerHTML = html;
    }

    qualifierToPreset(qualifier) {
        for (const [preset, val] of Object.entries(PokerLobby.QUALIFIER_PRESETS)) {
            if (val && val[0] === qualifier[0] && val[1] === qualifier[1]) return preset;
        }
        return '';
    }

    applyKnob(el) {
        if (!this.cvConfig) return;
        const kind = el.dataset.knob;
        if (kind === 'deck') {
            this.cvConfig.deck = this.cvConfig.deck || {};
            this.cvConfig.deck.type = el.value;
            this.cvConfig.deck.cards = PokerLobby.DECK_TYPES[el.value];
        } else if (kind === 'evaltype' || kind === 'qualifier') {
            const bh = this.cvConfig.showdown && Array.isArray(this.cvConfig.showdown.bestHand)
                ? this.cvConfig.showdown.bestHand[Number(el.dataset.index)] : null;
            if (!bh) return;
            if (kind === 'evaltype') {
                bh.evaluationType = el.value;
            } else {
                const preset = PokerLobby.QUALIFIER_PRESETS[el.value];
                if (preset) bh.qualifier = preset;
                else delete bh.qualifier;
            }
        }
        this.cvSyncEditor(true);
        this.cvScheduleValidate();
    }

    async cvValidate(smoke) {
        if (!this.cvConfig) return null;
        try {
            const res = await fetch('/api/custom-variants/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config: this.cvConfig, smoke })
            });
            const data = await res.json();
            if (data.success) {
                this.cvShowValidation(data, smoke);
                return data;
            }
        } catch (e) {
            console.error('Validation request failed:', e);
        }
        return null;
    }

    cvShowValidation(result, smokeRan = false) {
        const panel = document.getElementById('cv-validation');
        if (!result) {
            panel.style.display = 'none';
            panel.innerHTML = '';
            return;
        }
        panel.style.display = 'block';
        if (result.valid) {
            const note = smokeRan ? ' — test hands played clean' : ' (schema + engine; Validate runs test hands)';
            let html = `<div class="cv-valid">✓ Config is valid${note}</div>`;
            for (const w of result.warnings || []) {
                html += `<div class="cv-warning">⚠ ${this.escapeHtml(w)}</div>`;
            }
            panel.innerHTML = html;
        } else {
            let html = '';
            for (const err of result.errors || []) {
                const path = err.json_path ? ` <code>${this.escapeHtml(err.json_path)}</code>` : '';
                html += `<div class="cv-error">✕ [${this.escapeHtml(err.stage)}] ${this.escapeHtml(err.message)}${path}</div>`;
            }
            panel.innerHTML = html;
        }
    }

    async loadSavedVariants() {
        if (!window.isAuthenticated) return;
        try {
            const res = await fetch('/api/custom-variants');
            const data = await res.json();
            if (data.success) {
                this.savedVariants = data.variants || [];
                this.renderSavedVariantSelect();
                this.populateVariantDropdowns();
            }
        } catch (e) {
            console.error('Failed to load saved variants:', e);
        }
    }

    renderSavedVariantSelect() {
        const group = document.getElementById('saved-variant-group');
        const sel = document.getElementById('saved-variant-select');
        if (!this.savedVariants.length) {
            group.style.display = 'none';
            return;
        }
        group.style.display = 'block';
        let html = '<option value="">— My Variants —</option>';
        for (const v of this.savedVariants) {
            html += `<option value="${this.escapeHtml(v.id)}">${this.escapeHtml(v.display_name)}</option>`;
        }
        sel.innerHTML = html;
    }

    loadSavedVariant(variantId) {
        if (!variantId) return;
        const v = this.savedVariants.find(x => x.id === variantId);
        if (!v) return;
        this.cvConfig = v.config;
        this.selectedCustomVariantId = v.id;
        document.getElementById('cv-name').value = v.display_name;
        this.cvSyncEditor(true);
        this.cvShowValidation(null);
        this.selectCustomVariant(v.id);
    }

    async deleteSavedVariant() {
        const sel = document.getElementById('saved-variant-select');
        const variantId = sel.value;
        if (!variantId) {
            this.showNotification('Pick a saved variant to delete', 'info');
            return;
        }
        const v = this.savedVariants.find(x => x.id === variantId);
        if (!confirm(`Delete "${v ? v.display_name : 'this variant'}" from your library? (Tables already using it keep playing.)`)) return;
        try {
            const res = await fetch(`/api/custom-variants/${variantId}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                this.showNotification('Variant deleted', 'success');
                if (this.selectedCustomVariantId === variantId) this.selectedCustomVariantId = null;
                await this.loadSavedVariants();
            } else {
                this.showNotification(data.error || 'Could not delete variant', 'error');
            }
        } catch (e) {
            this.showNotification('Could not delete variant', 'error');
        }
    }

    async saveCustomVariant() {
        const name = document.getElementById('cv-name').value.trim();
        if (!name) {
            this.showNotification('Give your variant a name', 'error');
            return;
        }
        if (!this.cvConfig) {
            this.showNotification('Pick a game to clone (or paste a config) first', 'error');
            return;
        }
        const saveBtn = document.getElementById('cv-save-btn');
        saveBtn.disabled = true;
        saveBtn.textContent = 'Validating…';
        try {
            const res = await fetch('/api/custom-variants', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    display_name: name,
                    base_variant: document.getElementById('cv-base-variant').value || null,
                    config: this.cvConfig
                })
            });
            const data = await res.json();
            if (data.success) {
                this.showNotification('Variant saved to your library', 'success');
                this.selectedCustomVariantId = data.variant.id;
                this.cvShowValidation({ valid: true, warnings: data.warnings || [] }, true);
                await this.loadSavedVariants();
                document.getElementById('saved-variant-select').value = data.variant.id;
                // Restrict the structure picker to what the saved variant supports.
                this.selectCustomVariant(data.variant.id);
            } else if (data.errors) {
                this.cvShowValidation({ valid: false, errors: data.errors, warnings: [] });
                this.showNotification('Validation failed — see details above the buttons', 'error');
            } else {
                this.showNotification(data.error || 'Could not save variant', 'error');
            }
        } catch (e) {
            this.showNotification('Could not save variant', 'error');
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save to My Variants';
        }
    }

    /** A saved variant was picked in the dropdown: restrict structures to its config. */
    selectCustomVariant(variantId) {
        const v = this.savedVariants.find(x => x.id === variantId);
        if (!v) return;
        this.selectedCustomVariantId = variantId;
        const structSelect = document.getElementById('betting-structure');
        const structMap = { 'No Limit': 'no-limit', 'Pot Limit': 'pot-limit', 'Limit': 'limit' };
        let html = '<option value="">Select structure</option>';
        for (const bs of v.betting_structures || []) {
            const val = structMap[bs] || bs.toLowerCase().replace(' ', '-');
            html += `<option value="${val}">${bs}</option>`;
        }
        structSelect.innerHTML = html;
        if ((v.betting_structures || []).length === 1) {
            structSelect.value = structMap[v.betting_structures[0]] || '';
            structSelect.dispatchEvent(new Event('change', { bubbles: true }));
        }
        const rulesLink = document.getElementById('view-rules-link');
        if (rulesLink) rulesLink.style.display = 'none';
    }

    updateBettingStructureOptions(variantName) {
        const structSelect = document.getElementById('betting-structure');
        const variant = this.variants.find(v => v.name === variantName);
        if (!variant) {
            // Reset to all structures
            structSelect.innerHTML = `
                <option value="">Select structure</option>
                <option value="no-limit">No Limit</option>
                <option value="pot-limit">Pot Limit</option>
                <option value="limit">Limit</option>
            `;
            return;
        }

        const structMap = {
            'No Limit': 'no-limit',
            'Pot Limit': 'pot-limit',
            'Limit': 'limit'
        };
        const displayMap = {
            'no-limit': 'No Limit',
            'pot-limit': 'Pot Limit',
            'limit': 'Limit'
        };

        let html = '<option value="">Select structure</option>';
        for (const bs of variant.betting_structures) {
            const val = structMap[bs] || bs.toLowerCase().replace(' ', '-');
            const label = displayMap[val] || bs;
            html += `<option value="${val}">${label}</option>`;
        }
        structSelect.innerHTML = html;

        // Auto-select if only one option
        if (variant.betting_structures.length === 1) {
            structSelect.value = structMap[variant.betting_structures[0]] || '';
            this.updateStakesInputs(structSelect.value);
        }
    }

    updateStakesInputs(structure) {
        const stakesInputs = document.getElementById('stakes-inputs');

        if (structure === 'limit') {
            stakesInputs.innerHTML = `
                <div class="form-group">
                    <label for="small-bet">Small Bet ($):</label>
                    <input type="number" id="small-bet" name="small_bet" value="10" min="1" step="1" required>
                </div>
                <div class="form-group">
                    <label for="big-bet">Big Bet ($):</label>
                    <input type="number" id="big-bet" name="big_bet" value="20" min="1" step="1" required>
                </div>
                <div class="form-group">
                    <label for="ante">Ante ($):</label>
                    <input type="number" id="ante" name="ante" value="0" min="0" step="0.01">
                </div>
            `;
        } else {
            stakesInputs.innerHTML = `
                <div class="form-group">
                    <label for="small-blind">Small Blind ($):</label>
                    <input type="number" id="small-blind" name="small_blind" value="1" min="0.01" step="0.01" required>
                </div>
                <div class="form-group">
                    <label for="big-blind">Big Blind ($):</label>
                    <input type="number" id="big-blind" name="big_blind" value="2" min="0.01" step="0.01" required>
                </div>
            `;
        }

        // Betting cap (BACKLOG 6.2.13): show the raise cap for Limit, the
        // per-hand money cap for No-Limit/Pot-Limit.
        const raiseCapGroup = document.getElementById('raise-cap-group');
        const handCapGroup = document.getElementById('hand-cap-group');
        if (raiseCapGroup && handCapGroup) {
            const isLimit = structure === 'limit';
            raiseCapGroup.style.display = isLimit ? '' : 'none';
            handCapGroup.style.display = isLimit ? 'none' : '';
        }
    }

    loadTables() {
        const refreshBtn = document.getElementById('refresh-tables-btn');
        refreshBtn.classList.add('loading');

        this.socket.emit('get_table_list', {});

        // Remove loading state after a delay
        setTimeout(() => {
            refreshBtn.classList.remove('loading');
        }, 1000);
    }

    renderTables() {
        const tableGrid = document.getElementById('table-grid');
        const tableCount = document.getElementById('table-count');

        // Filter tables based on current filters
        const filteredTables = this.getFilteredTables();

        tableCount.textContent = filteredTables.length;

        if (filteredTables.length === 0) {
            tableGrid.innerHTML = `
                <div class="no-tables" id="no-tables">
                    <div class="no-tables-icon">🎲</div>
                    <h3>No tables found</h3>
                    <p>Create a new table or adjust your filters to see available games.</p>
                </div>
            `;
            return;
        }

        tableGrid.innerHTML = filteredTables.map(table => this.renderTableCard(table)).join('');

        // Add event listeners to table cards
        this.setupTableCardEvents();
    }

    renderTableCard(table) {
        const isFull = table.current_players >= table.max_players;
        const statusClass = isFull ? 'full' : (table.current_players > 0 ? 'playing' : 'waiting');
        const statusText = isFull ? 'Full' : (table.current_players > 0 ? 'Playing' : 'Waiting');

        // Generate player indicators
        const playerDots = Array.from({ length: table.max_players }, (_, i) =>
            `<div class="player-dot ${i < table.current_players ? 'filled' : ''}"></div>`
        ).join('');

        // Format stakes display
        const stakesDisplay = this.formatStakes(table.stakes, table.betting_structure);

        return `
            <div class="table-card ${isFull ? 'full' : ''} ${table.is_private ? 'private' : ''} ${table.allow_bots ? 'has-bots' : ''}"
                 data-table-id="${table.id}">
                ${table.is_private ? '<div class="private-indicator">Private</div>' : ''}

                <div class="table-header-info">
                    <div>
                        <div class="table-name">${this.escapeHtml(table.name)}</div>
                        <div class="table-variant">${table.custom_mix ? this.escapeHtml(table.custom_mix.display_name) : (table.custom_variant ? this.escapeHtml(table.custom_variant.display_name) : this.formatVariantName(table.variant))} <span class="table-id-tag">#${table.id.substring(0, 6)}</span></div>
                    </div>
                    <div class="table-status">
                        <div class="status-badge status-${statusClass}">${statusText}</div>
                    </div>
                </div>

                <div class="table-details">
                    <div class="detail-item">
                        <div class="detail-label">Stakes</div>
                        <div class="detail-value stakes">${stakesDisplay}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Structure</div>
                        <div class="detail-value">${this.formatStructure(table.betting_structure)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Players</div>
                        <div class="detail-value players-count">
                            ${table.current_players}/${table.max_players}
                            <div class="players-indicator">${playerDots}</div>
                        </div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Buy-in</div>
                        <div class="detail-value">$${table.minimum_buyin} - $${table.maximum_buyin}</div>
                    </div>
                </div>

                <div class="table-actions">
                    ${this.userTables.includes(table.id) ? `
                        <button class="btn btn-success btn-small rejoin-table-btn"
                                data-table-id="${table.id}">
                            Rejoin
                        </button>
                        <button class="btn btn-danger btn-small leave-table-btn"
                                data-table-id="${table.id}">
                            Leave
                        </button>
                    ` : `
                        <button class="btn btn-primary btn-small join-table-btn"
                                data-table-id="${table.id}"
                                ${isFull ? 'disabled' : ''}>
                            ${isFull ? 'Full' : 'Join'}
                        </button>
                    `}
                    <button class="btn btn-outline btn-small spectate-btn"
                            data-table-id="${table.id}">
                        <i class="icon-eye"></i> Spectate
                    </button>
                    <button class="btn btn-secondary btn-small details-btn"
                            data-table-id="${table.id}">
                        Details
                    </button>
                    ${table.creator_id && table.creator_id === window.currentUserId ? `
                        <button class="btn btn-outline btn-small edit-table-btn"
                                data-table-id="${table.id}">
                            Edit
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }

    setupTableCardEvents() {
        // Join table buttons
        document.querySelectorAll('.join-table-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const tableId = btn.dataset.tableId;
                this.joinTable(tableId);
            });
        });

        // Rejoin table buttons (for users already at a table)
        document.querySelectorAll('.rejoin-table-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const tableId = btn.dataset.tableId;
                this.rejoinTable(tableId);
            });
        });

        // Leave table buttons (drop the seat without opening the table)
        document.querySelectorAll('.leave-table-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.leaveTable(btn.dataset.tableId);
            });
        });

        // Spectate buttons
        document.querySelectorAll('.spectate-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const tableId = btn.dataset.tableId;
                this.spectateTable(tableId);
            });
        });

        // Details buttons
        document.querySelectorAll('.details-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const tableId = btn.dataset.tableId;
                this.showTableDetails(tableId);
            });
        });

        // Edit buttons (creator only)
        document.querySelectorAll('.edit-table-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.openEditTableModal(btn.dataset.tableId);
            });
        });

        // Table card click (show details)
        document.querySelectorAll('.table-card').forEach(card => {
            card.addEventListener('click', () => {
                const tableId = card.dataset.tableId;
                this.showTableDetails(tableId);
            });
        });
    }

    getFilteredTables() {
        return this.tables.filter(table => {
            // Variant filter
            if (this.filters.variant && table.variant !== this.filters.variant) {
                return false;
            }

            // Stakes filter
            if (this.filters.stakes) {
                const stakes = this.getStakesCategory(table.stakes, table.betting_structure);
                if (stakes !== this.filters.stakes) {
                    return false;
                }
            }

            // Structure filter
            if (this.filters.structure && table.betting_structure !== this.filters.structure) {
                return false;
            }

            // Players filter
            if (this.filters.players) {
                switch (this.filters.players) {
                    case 'has-seats':
                        if (table.current_players >= table.max_players) return false;
                        break;
                    case 'heads-up':
                        if (table.max_players !== 2) return false;
                        break;
                    case 'short-handed':
                        if (table.max_players < 3 || table.max_players > 6) return false;
                        break;
                    case 'full-ring':
                        if (table.max_players < 7) return false;
                        break;
                }
            }

            return true;
        });
    }

    getStakesCategory(stakes, structure) {
        let bigBlind = 0;
        const struct = (structure || '').toLowerCase();

        if (struct === 'limit') {
            bigBlind = stakes.big_bet || 0;
        } else {
            bigBlind = stakes.big_blind || 0;
        }

        if (bigBlind <= 0.50) return 'micro';
        if (bigBlind <= 5) return 'low';
        if (bigBlind <= 25) return 'mid';
        return 'high';
    }

    formatStakes(stakes, structure) {
        const struct = (structure || '').toLowerCase();
        if (struct === 'limit') {
            return `$${stakes.small_bet || 0}/$${stakes.big_bet || 0}`;
        } else {
            return `$${stakes.small_blind || 0}/$${stakes.big_blind || 0}`;
        }
    }

    formatVariantName(variant) {
        if (this.variantMap[variant]) {
            return this.variantMap[variant];
        }
        // Fallback: convert underscores to spaces and title-case
        return variant.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    formatStructure(structure) {
        return structure.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    async createTable() {
        const form = document.getElementById('create-table-form');
        const formData = new FormData(form);

        // Collect stakes data
        const bettingStructure = formData.get('betting_structure');
        const stakes = {};

        if (bettingStructure === 'limit') {
            stakes.small_bet = parseFloat(formData.get('small_bet') || 10);
            stakes.big_bet = parseFloat(formData.get('big_bet') || 20);
            stakes.ante = parseFloat(formData.get('ante') || 0);
        } else {
            stakes.small_blind = parseFloat(formData.get('small_blind') || 1);
            stakes.big_blind = parseFloat(formData.get('big_blind') || 2);
        }

        const tableData = {
            name: formData.get('name'),
            variant: formData.get('variant'),
            betting_structure: bettingStructure,
            max_players: parseInt(formData.get('max_players')),
            stakes: stakes,
            is_private: formData.get('is_private') === 'on',
            password: formData.get('is_private') === 'on' ? (formData.get('password') || null) : null,
            allow_bots: formData.get('allow_bots') === 'on'
        };

        // Betting cap (BACKLOG 6.2.13) — only the control relevant to the structure.
        if (bettingStructure === 'limit') {
            tableData.raise_cap_override = formData.get('raise_cap_override') || 'standard';
        } else {
            tableData.hand_cap_bb = formData.get('hand_cap_bb') || '0';
        }

        // Custom mix (Phase 9.3): attach the composed rotation; server overrides variant.
        if (this.customMixMode) {
            const mixName = document.getElementById('mix-name').value.trim();
            const rotation = this.collectRotation();
            if (!mixName) {
                this.showNotification('Give your mix a name', 'error');
                return;
            }
            if (rotation.length < 2) {
                this.showNotification('A mix needs at least 2 games', 'error');
                return;
            }
            if (rotation.some(r => !r.variant || !r.bettingStructure)) {
                this.showNotification('Each game needs a variant and a betting structure', 'error');
                return;
            }
            const dealersChoice = document.getElementById('mix-dealers-choice').checked;
            tableData.custom_mix = { display_name: mixName, rotation, dealers_choice: dealersChoice };
        }

        // Custom variant (Phase 9.5): tables are created from a SAVED library entry.
        if (this.customVariantMode || (tableData.variant || '').startsWith(this.CUSTOM_VARIANT_PREFIX)) {
            if (!this.selectedCustomVariantId) {
                this.showNotification('Save your variant first, then create the table', 'error');
                return;
            }
            tableData.custom_variant_id = this.selectedCustomVariantId;
            tableData.variant = 'custom_variant';  // server re-derives from the library entry
        }

        // Validate required fields
        if (!tableData.name || !tableData.variant || !tableData.betting_structure) {
            this.showNotification('Please fill in all required fields', 'error');
            return;
        }

        // Validate stakes
        if (bettingStructure === 'limit') {
            if (stakes.small_bet <= 0 || stakes.big_bet <= 0 || stakes.big_bet <= stakes.small_bet) {
                this.showNotification('Invalid stakes configuration', 'error');
                return;
            }
        } else {
            if (stakes.small_blind <= 0 || stakes.big_blind <= 0 || stakes.big_blind <= stakes.small_blind) {
                this.showNotification('Invalid blinds configuration', 'error');
                return;
            }
        }

        try {
            const response = await fetch('/api/tables', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(tableData)
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('Table created successfully!', 'success');
                this.closeModal('create-table-modal');
                this.loadTables();

                // Auto-open seat selection so creator can join their table
                if (result.table_id) {
                    // Build a temporary table object from the form data for the modal
                    const createdTable = {
                        id: result.table_id,
                        name: tableData.name,
                        variant: tableData.variant,
                        betting_structure: tableData.betting_structure,
                        stakes: tableData.stakes,
                        max_players: tableData.max_players,
                        current_players: 0,
                        is_private: tableData.is_private
                    };
                    // Add to tables array so showSeatSelectionModal can find it
                    this.tables.push(createdTable);
                    this.showSeatSelectionModal(result.table_id);
                }
            } else {
                this.showNotification(result.error || 'Failed to create table', 'error');
            }
        } catch (error) {
            console.error('Error creating table:', error);
            this.showNotification('Failed to create table', 'error');
        }
    }

    joinTable(tableId) {
        if (!this.requireLogin()) return;
        const table = this.tables.find(t => t.id === tableId);
        if (!table) {
            this.showNotification('Table not found', 'error');
            return;
        }

        if (table.current_players >= table.max_players) {
            this.showNotification('Table is full', 'error');
            return;
        }

        // Check if private table
        if (table.is_private) {
            this.showNotification('This is a private table. Use the invite code to join.', 'warning');
            return;
        }

        // Show seat selection modal
        this.showSeatSelectionModal(tableId);
    }

    rejoinTable(tableId) {
        // Navigate directly to the table - user is already seated
        window.location.href = `/table/${tableId}`;
    }

    async leaveTable(tableId) {
        const table = this.tables.find(t => t.id === tableId);
        const name = table ? table.name : 'this table';
        if (!confirm(`Leave "${name}"? Your chips will be cashed out. If a hand is in progress you'll fold and be removed after it ends.`)) {
            return;
        }
        try {
            const resp = await fetch(`/api/tables/${tableId}/leave`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }
            });
            const data = await resp.json();
            if (resp.ok && data.success) {
                this.showNotification('Left table', 'success');
                this.userTables = this.userTables.filter(id => id !== tableId);
                this.loadTables();
            } else {
                this.showNotification(data.error || 'Failed to leave table', 'error');
            }
        } catch (err) {
            this.showNotification('Failed to leave table', 'error');
        }
    }

    openEditTableModal(tableId) {
        const table = this.tables.find(t => t.id === tableId);
        if (!table) {
            this.showNotification('Table not found', 'error');
            return;
        }
        document.getElementById('edit-table-id').value = tableId;
        document.getElementById('edit-table-name').value = table.name || '';
        document.getElementById('edit-allow-bots').checked = !!table.allow_bots;
        document.getElementById('edit-is-private').checked = !!table.is_private;
        this.showModal('edit-table-modal');
    }

    async submitEditTable() {
        const tableId = document.getElementById('edit-table-id').value;
        const settings = {
            name: document.getElementById('edit-table-name').value.trim(),
            allow_bots: document.getElementById('edit-allow-bots').checked,
            is_private: document.getElementById('edit-is-private').checked
        };
        if (!settings.name) {
            this.showNotification('Table name cannot be empty', 'error');
            return;
        }
        try {
            // Settings endpoint lives on table_bp (/table prefix), creator-only.
            const resp = await fetch(`/table/${tableId}/settings`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            const data = await resp.json();
            if (resp.ok && data.success) {
                this.showNotification('Table updated', 'success');
                this.closeModal('edit-table-modal');
                this.loadTables();
                if (settings.allow_bots) {
                    this.showNotification('Bots will fill empty seats when the table page loads', 'info');
                }
            } else {
                this.showNotification(data.error || 'Failed to update table', 'error');
            }
        } catch (err) {
            this.showNotification('Failed to update table', 'error');
        }
    }

    showSeatSelectionModal(tableId) {
        const table = this.tables.find(t => t.id === tableId);
        if (!table) return;

        // Show loading modal first
        this.showLoadingSeatModal(table);

        // Fetch actual seat data
        fetch(`/api/tables/${tableId}/seats`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.showSeatSelectionModalWithData(table, data);
                } else {
                    this.showNotification('Failed to load seat information', 'error');
                    closeModal('seat-selection-modal');
                }
            })
            .catch(error => {
                console.error('Error fetching seat data:', error);
                this.showNotification('Failed to load seat information', 'error');
                closeModal('seat-selection-modal');
            });
    }

    showLoadingSeatModal(table) {
        const modalHtml = `
            <div id="seat-selection-modal" class="modal show">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>Join ${table.name}</h3>
                        <button class="modal-close" onclick="closeModal('seat-selection-modal')">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="loading-seats">
                            <div class="loading-spinner"></div>
                            <p>Loading seat information...</p>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    showSeatSelectionModalWithData(table, seatData) {
        // Remove loading modal
        closeModal('seat-selection-modal');

        // Create seat selection modal HTML with real data
        const modalHtml = `
            <div id="seat-selection-modal" class="modal show">
                <div class="modal-content modal-compact">
                    <div class="modal-header">
                        <h3>Join ${table.name}</h3>
                        <button class="modal-close" onclick="closeModal('seat-selection-modal')">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="seat-modal-layout">
                            <div class="seat-modal-left">
                                <div class="table-info-compact">
                                    <div class="info-row">
                                        <span class="info-label">Game:</span>
                                        <span class="info-value">${this.formatVariantName(table.variant)}</span>
                                    </div>
                                    <div class="info-row">
                                        <span class="info-label">Stakes:</span>
                                        <span class="info-value">$${table.stakes.small_blind || table.stakes.small_bet}/${table.stakes.big_blind || table.stakes.big_bet}</span>
                                    </div>
                                    <div class="info-row">
                                        <span class="info-label">Players:</span>
                                        <span class="info-value">${seatData.current_players}/${seatData.max_players}</span>
                                    </div>
                                </div>

                                <div class="buy-in-section-compact">
                                    <label for="buy-in-amount">Buy-in Amount:</label>
                                    <input type="number" id="buy-in-amount" min="${seatData.minimum_buyin}" max="${seatData.maximum_buyin}" value="${seatData.minimum_buyin * 2}" step="1">
                                    <div class="buy-in-range">
                                        <small>$${seatData.minimum_buyin} - $${seatData.maximum_buyin}</small>
                                    </div>
                                </div>

                                <div class="seat-options">
                                    <label class="auto-assign-option" onclick="pokerLobby.selectAutoAssign()">
                                        <input type="radio" name="seat-choice" value="auto" checked>
                                        <span class="auto-assign-text">Auto-assign seat</span>
                                    </label>
                                </div>
                            </div>

                            <div class="seat-modal-right">
                                <div class="mini-poker-table">
                                    ${this.generateMiniPokerTable(seatData.seats, seatData.max_players)}
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="closeModal('seat-selection-modal')">Cancel</button>
                        <button type="button" class="btn btn-primary" onclick="pokerLobby.confirmJoinTable('${table.id}')">Join Table</button>
                    </div>
                </div>
            </div>
        `;

        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    generateSeatGridWithData(seats) {
        let seatHtml = '';

        seats.forEach(seat => {
            const isOccupied = !seat.is_available;
            const seatClass = isOccupied ? 'seat-occupied' : 'seat-available';
            const disabled = isOccupied ? 'disabled' : '';

            let seatContent;
            if (isOccupied) {
                seatContent = `
                    <div class="seat-number">Seat ${seat.seat_number}</div>
                    <div class="seat-player">${seat.player.username}</div>
                    <div class="seat-stack">$${seat.player.stack}</div>
                `;
            } else if (seat.player && seat.player.is_bot) {
                // Bot-held seat: still joinable, the bot gives it up
                seatContent = `
                    <div class="seat-number">Seat ${seat.seat_number}</div>
                    <div class="seat-player">🤖 ${seat.player.username}</div>
                    <div class="seat-empty">Take this seat</div>
                `;
            } else {
                seatContent = `
                    <div class="seat-number">Seat ${seat.seat_number}</div>
                    <div class="seat-empty">Available</div>
                `;
            }

            seatHtml += `
                <div class="seat-option ${seatClass}">
                    <label>
                        <input type="radio" name="seat-choice" value="${seat.seat_number}" ${disabled}>
                        <div class="seat-visual">
                            ${seatContent}
                        </div>
                    </label>
                </div>
            `;
        });

        return seatHtml;
    }

    generateMiniPokerTable(seats, maxPlayers) {
        // Create a mini version of the poker table for seat selection
        // Map to nearest supported CSS layout (2, 6, or 9)
        const layoutPlayers = maxPlayers <= 2 ? 2 : maxPlayers <= 6 ? 6 : 9;
        let tableHtml = `
            <div class="mini-table-container" data-max-players="${layoutPlayers}">
                <div class="mini-poker-table-felt">
                    <div class="mini-table-center">
                        <div class="mini-table-label">Select Your Seat</div>
                    </div>
                    <div class="mini-player-seats">
        `;

        seats.forEach(seat => {
            const isOccupied = !seat.is_available;
            const seatClass = isOccupied ? 'mini-seat-occupied' : 'mini-seat-available';

            let seatContent;
            if (isOccupied) {
                seatContent = `
                    <div class="mini-player-info occupied">
                        <div class="mini-player-name">${seat.player.username}</div>
                        <div class="mini-player-chips">$${seat.player.stack}</div>
                    </div>
                `;
            } else if (seat.player && seat.player.is_bot) {
                // Bot-held seat: joinable, the bot gives it up to a human
                seatContent = `
                    <div class="mini-player-info available bot-held" onclick="pokerLobby.selectSeat(${seat.seat_number})">
                        <div class="mini-seat-number">🤖 ${seat.player.username}</div>
                        <div class="mini-seat-status">Take seat</div>
                    </div>
                `;
            } else {
                seatContent = `
                    <div class="mini-player-info available" onclick="pokerLobby.selectSeat(${seat.seat_number})">
                        <div class="mini-seat-number">Seat ${seat.seat_number}</div>
                        <div class="mini-seat-status">Click to join</div>
                    </div>
                `;
            }

            tableHtml += `
                <div class="mini-player-seat ${seatClass}" data-position="${seat.seat_number - 1}" data-seat="${seat.seat_number}">
                    ${seatContent}
                </div>
            `;
        });

        tableHtml += `
                    </div>
                </div>
            </div>
        `;

        return tableHtml;
    }

    selectSeat(seatNumber) {
        // Uncheck auto-assign
        const autoRadio = document.querySelector('input[name="seat-choice"][value="auto"]');
        if (autoRadio) autoRadio.checked = false;

        // Clear any existing seat selection
        document.querySelectorAll('.mini-player-seat.selected').forEach(seat => {
            seat.classList.remove('selected');
        });

        // Select the clicked seat
        const seatElement = document.querySelector(`[data-seat="${seatNumber}"]`);
        if (seatElement) {
            seatElement.classList.add('selected');
        }

        // Store the selection
        this.selectedSeat = seatNumber;

        // Update the radio button selection (create hidden radio if needed)
        let seatRadio = document.querySelector(`input[name="seat-choice"][value="${seatNumber}"]`);
        if (!seatRadio) {
            seatRadio = document.createElement('input');
            seatRadio.type = 'radio';
            seatRadio.name = 'seat-choice';
            seatRadio.value = seatNumber;
            seatRadio.style.display = 'none';
            document.querySelector('.seat-options').appendChild(seatRadio);
        }
        seatRadio.checked = true;
    }

    selectAutoAssign() {
        // Clear any seat selection
        document.querySelectorAll('.mini-player-seat.selected').forEach(seat => {
            seat.classList.remove('selected');
        });

        // Clear stored selection
        this.selectedSeat = null;

        // Make sure auto-assign is checked
        const autoRadio = document.querySelector('input[name="seat-choice"][value="auto"]');
        if (autoRadio) autoRadio.checked = true;
    }

    // Keep the old method for backward compatibility
    generateSeatGrid(table) {
        let seatHtml = '';
        for (let i = 1; i <= table.max_players; i++) {
            const isOccupied = false; // For demo, assume all seats are available
            const seatClass = isOccupied ? 'seat-occupied' : 'seat-available';
            const disabled = isOccupied ? 'disabled' : '';

            seatHtml += `
                <div class="seat-option ${seatClass}">
                    <label>
                        <input type="radio" name="seat-choice" value="${i}" ${disabled}>
                        <div class="seat-visual">
                            <div class="seat-number">Seat ${i}</div>
                            ${isOccupied ? '<div class="seat-player">Occupied</div>' : '<div class="seat-empty">Available</div>'}
                        </div>
                    </label>
                </div>
            `;
        }
        return seatHtml;
    }

    confirmJoinTable(tableId) {
        const buyInAmount = parseInt(document.getElementById('buy-in-amount').value);
        const seatChoiceElement = document.querySelector('input[name="seat-choice"]:checked');

        if (!seatChoiceElement) {
            this.showNotification('Please select a seat or choose auto-assign', 'error');
            return;
        }

        const seatChoice = seatChoiceElement.value;

        const joinData = {
            table_id: tableId,
            buy_in_amount: buyInAmount
        };

        if (seatChoice !== 'auto') {
            joinData.seat_number = parseInt(seatChoice);
        }

        this.socket.emit('join_table', joinData);
        closeModal('seat-selection-modal');
    }

    spectateTable(tableId) {
        if (!this.requireLogin()) return;
        this.socket.emit('spectate_table', { table_id: tableId });
    }

    joinPrivateTable() {
        const form = document.getElementById('join-private-form');
        const formData = new FormData(form);

        const inviteCode = formData.get('invite_code');
        const password = formData.get('password');

        if (!inviteCode) {
            this.showNotification('Please enter an invite code', 'error');
            return;
        }

        this.socket.emit('join_private_table', {
            invite_code: inviteCode,
            password: password
        });
    }

    showTableDetails(tableId) {
        const table = this.tables.find(t => t.id === tableId);
        if (!table) {
            this.showNotification('Table not found', 'error');
            return;
        }

        const modal = document.getElementById('table-details-modal');
        const title = document.getElementById('table-details-title');
        const content = document.getElementById('table-details-content');
        const joinBtn = document.getElementById('join-table-btn');
        const spectateBtn = document.getElementById('spectate-table-btn');

        title.textContent = table.name;

        const stakesDisplay = this.formatStakes(table.stakes, table.betting_structure);
        const isFull = table.current_players >= table.max_players;
        const capRow = this.renderBettingCapRow(table);

        content.innerHTML = `
            <div class="table-detail-grid">
                <div class="detail-row">
                    <strong>Game Variant:</strong>
                    <span>${this.escapeHtml(table.custom_variant ? `${table.custom_variant.display_name} (custom)` : this.formatVariantName(table.variant))}</span>
                </div>
                <div class="detail-row">
                    <strong>Betting Structure:</strong>
                    <span>${this.formatStructure(table.betting_structure)}</span>
                </div>
                <div class="detail-row">
                    <strong>Stakes:</strong>
                    <span>${stakesDisplay}</span>
                </div>
                ${capRow}
                <div class="detail-row">
                    <strong>Players:</strong>
                    <span>${table.current_players}/${table.max_players}</span>
                </div>
                <div class="detail-row">
                    <strong>Buy-in Range:</strong>
                    <span>$${table.minimum_buyin} - $${table.maximum_buyin}</span>
                </div>
                <div class="detail-row">
                    <strong>Table Type:</strong>
                    <span>${table.is_private ? 'Private' : 'Public'}</span>
                </div>
                <div class="detail-row">
                    <strong>Bot Players:</strong>
                    <span>${table.allow_bots ? 'Allowed' : 'Not Allowed'}</span>
                </div>
                <div class="detail-row">
                    <strong>Created:</strong>
                    <span>${new Date(table.created_at).toLocaleString()}</span>
                </div>
            </div>
            ${this.renderRotationSection(table)}
            ${this.renderRulesLink(table)}
        `;

        // Attach the View Rules handler without an inline onclick (avoids HTML-injected handlers)
        content.querySelector('.view-rules-btn')
            ?.addEventListener('click', () => table.custom_variant
                ? window.showTableRulesCard(table.id)
                : window.showVariantRulesById(table.variant));

        // Configure action buttons
        joinBtn.disabled = isFull || table.is_private;
        joinBtn.textContent = isFull ? 'Table Full' : (table.is_private ? 'Private Table' : 'Join Table');

        joinBtn.onclick = () => {
            if (!isFull && !table.is_private) {
                this.joinTable(tableId);
            }
        };

        spectateBtn.onclick = () => {
            this.spectateTable(tableId);
        };

        this.showModal('table-details-modal');
    }

    // Betting cap row for the table details modal (omitted entirely when no cap set)
    renderBettingCapRow(table) {
        const raiseCap = table.raise_cap_override;
        const handCap = table.hand_cap_bb;
        let capText = '';
        if (raiseCap !== null && raiseCap !== undefined) {
            capText = raiseCap <= 0 ? 'Unlimited raises' : `Bet + ${raiseCap} raises`;
        } else if (handCap && handCap > 0) {
            capText = `Max loss ${handCap} BB / hand`;
        }
        if (!capText) return '';
        return `
            <div class="detail-row">
                <strong>Betting Cap:</strong>
                <span>${this.escapeHtml(capText)}</span>
            </div>
        `;
    }

    // Rotation section for mixed games (HORSE, 8-Game, etc.); empty for single variants.
    // Custom (user-authored) mixes carry their rotation inline on the table; file-based
    // mixes are looked up in the shared variants list.
    renderRotationSection(table) {
        if (!table.is_mixed_game) return '';
        const mix = table.custom_mix || this.variants.find(v => v.name === table.variant && v.is_mixed);
        if (!mix || !Array.isArray(mix.rotation) || mix.rotation.length === 0) return '';

        const isDC = !!(table.custom_mix && table.custom_mix.dealers_choice);
        let heading = 'Rotation';
        if (table.custom_mix) {
            const label = isDC ? '🃏 Dealer\'s Choice' : 'Rotation';
            heading = `${label} — ${this.escapeHtml(table.custom_mix.display_name)}`;
        }
        const letters = mix.rotation_letters || [];
        const pills = mix.rotation.map((name, i) => {
            const letter = letters[i] || (name ? name[0] : '?');
            return `<span class="rotation-letter" title="${this.escapeHtml(name)}">${this.escapeHtml(letter)}</span>`;
        }).join('');
        const list = mix.rotation.map((name, i) => {
            const letter = letters[i] ? `${this.escapeHtml(letters[i])} ` : '';
            return `<li>${letter}${this.escapeHtml(name)}</li>`;
        }).join('');

        return `
            <div class="detail-rotation">
                <div class="detail-rotation-header">
                    <strong>${heading}</strong>
                    <div class="rotation-tracker">${pills}</div>
                </div>
                <ol class="detail-rotation-list">${list}</ol>
                ${isDC ? '<p class="detail-rotation-note">The player on the button picks one of these games each orbit.</p>' : ''}
            </div>
        `;
    }

    // "View Rules" link for single variants (mixed games rotate, so no single rules card)
    // Listener is attached after insertion (see showTableDetails) to avoid an inline handler.
    renderRulesLink(table) {
        if (table.is_mixed_game) return '';
        return `
            <div class="detail-rules-link">
                <button type="button" class="btn btn-outline btn-small view-rules-btn">
                    View Rules
                </button>
            </div>
        `;
    }

    showModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.add('show');

        // Focus first input if available
        const firstInput = modal.querySelector('input, select');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 100);
        }
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.remove('show');

        // Reset form if it exists
        const form = modal.querySelector('form');
        if (form) {
            form.reset();

            // Reset stakes inputs to default
            if (modalId === 'create-table-modal') {
                this.updateStakesInputs('no-limit');
                document.getElementById('private-options').style.display = 'none';
            }
        }
    }

    closeAllModals() {
        document.querySelectorAll('.modal.show').forEach(modal => {
            this.closeModal(modal.id);
        });
    }

    showNotification(message, type = 'info', duration = 4000) {
        const container = document.getElementById('notification-container');

        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            ${this.escapeHtml(message)}
            <button class="notification-close" onclick="this.parentElement.remove()">&times;</button>
        `;

        container.appendChild(notification);

        // Animate in
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);

        // Auto-remove
        setTimeout(() => {
            if (notification.parentElement) {
                notification.classList.remove('show');
                setTimeout(() => {
                    if (notification.parentElement) {
                        notification.remove();
                    }
                }, 300);
            }
        }, duration);
    }

    filterTables() {
        this.renderTables();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global functions for modal management (called from HTML)
window.closeModal = function(modalId) {
    if (modalId === 'seat-selection-modal') {
        // Handle dynamically created modal
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.remove();
        }
    } else if (window.lobby) {
        window.lobby.closeModal(modalId);
    }
};

// Show variant rules modal for the create-table variant selector
window.showVariantRules = function() {
    const variantSelect = document.getElementById('game-variant');
    const variantId = variantSelect ? variantSelect.value : '';
    if (!variantId) return;
    window.showVariantRulesById(variantId);
};

// Show variant rules modal for a specific variant id (used from table details)
// Rules card for a specific table — works for inline custom variants (9.5), whose
// configs have no file under /table/variants/<id>/rules.
window.showTableRulesCard = function(tableId) {
    if (!tableId) return;

    const content = document.getElementById('game-rules-content');
    const title = document.getElementById('game-rules-title');
    if (!content) return;

    content.innerHTML = '<div style="text-align:center; padding: 20px;">Loading...</div>';
    if (window.lobby) window.lobby.showModal('game-rules-modal');

    fetch(`/table/${tableId}/rules-card`)
        .then(r => r.json())
        .then(data => {
            if (!data.success) {
                content.innerHTML = '<div>Could not load rules.</div>';
                return;
            }
            const rules = data.rules;
            if (title) title.textContent = rules.game;
            content.innerHTML = renderGameCard(rules);
        })
        .catch(() => {
            content.innerHTML = '<div>Failed to load rules.</div>';
        });
};

window.showVariantRulesById = function(variantId) {
    if (!variantId) return;

    const content = document.getElementById('game-rules-content');
    const title = document.getElementById('game-rules-title');
    if (!content) return;

    content.innerHTML = '<div style="text-align:center; padding: 20px;">Loading...</div>';
    if (window.lobby) window.lobby.showModal('game-rules-modal');

    fetch(`/table/variants/${variantId}/rules`)
        .then(r => r.json())
        .then(data => {
            if (!data.success) {
                content.innerHTML = '<div>Could not load rules.</div>';
                return;
            }
            const rules = data.rules;
            if (title) title.textContent = rules.game;
            content.innerHTML = renderGameCard(rules);
        })
        .catch(() => {
            content.innerHTML = '<div>Failed to load rules.</div>';
        });
};


// Global reference for seat selection
window.pokerLobby = null;

// Initialize lobby when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.lobby = new PokerLobby();
    window.pokerLobby = window.lobby; // For seat selection modal
});

// Add some CSS for table detail grid
const style = document.createElement('style');
style.textContent = `
    .table-detail-grid {
        display: grid;
        gap: 1rem;
    }

    .detail-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem;
        background: var(--light-color, #f8f9fa);
        border-radius: 4px;
    }

    .detail-row strong {
        color: var(--dark-color, #343a40);
    }

`;
document.head.appendChild(style);

/**
 * Admin Panel - Fetch-based data loading for admin pages.
 */
class AdminPanel {
    constructor() {
        this.currentPage = 1;
        this.currentSearch = '';
        this.currentSort = 'username';
        this.variantsData = [];
    }

    // --- Notifications ---

    showNotification(message, type = 'success') {
        const container = document.getElementById('notification-container');
        if (!container) return;
        const el = document.createElement('div');
        el.className = `notification ${type} show`;
        el.innerHTML = `${message}<button class="notification-close" onclick="this.parentElement.remove()">&times;</button>`;
        container.appendChild(el);
        setTimeout(() => el.remove(), 4000);
    }

    // --- Modal helpers ---

    openModal(id) {
        const modal = document.getElementById(id);
        if (modal) modal.classList.add('show');
    }

    closeModal(id) {
        const modal = document.getElementById(id);
        if (modal) modal.classList.remove('show');
    }

    // --- Formatting helpers ---

    formatDate(iso) {
        if (!iso) return 'Never';
        const d = new Date(iso);
        return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    formatCurrency(amount) {
        return '$' + Number(amount).toLocaleString();
    }

    formatStakes(stakes) {
        if (stakes.small_blind !== undefined) {
            return `$${stakes.small_blind}/$${stakes.big_blind}`;
        }
        if (stakes.small_bet !== undefined) {
            return `$${stakes.small_bet}/$${stakes.big_bet}`;
        }
        return '-';
    }

    formatVariantName(name) {
        return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    // --- Dashboard ---

    async loadDashboard() {
        try {
            const [statsRes, sessionsRes] = await Promise.all([
                fetch('/admin/api/stats'),
                fetch('/admin/api/sessions')
            ]);
            const statsData = await statsRes.json();
            const sessionsData = await sessionsRes.json();

            if (statsData.success) this.renderStats(statsData.stats);
            if (sessionsData.success) this.renderSessions(sessionsData.sessions);
        } catch (err) {
            this.showNotification('Failed to load dashboard data', 'error');
        }
    }

    renderStats(stats) {
        const grid = document.getElementById('stat-grid');
        if (!grid) return;

        const cards = [
            { label: 'Total Users', value: stats.total_users },
            { label: 'Active (7 days)', value: stats.active_users_7d },
            { label: 'Total Tables', value: stats.total_tables },
            { label: 'Live Sessions', value: stats.live_sessions },
            { label: 'Hands Today', value: stats.hands_today },
            { label: 'Hands This Week', value: stats.hands_week },
            { label: 'Total Bankroll', value: this.formatCurrency(stats.total_bankroll) },
            { label: 'Disabled Variants', value: stats.disabled_variants },
        ];

        grid.innerHTML = cards.map(c => `
            <div class="stat-card">
                <div class="stat-label">${c.label}</div>
                <div class="stat-value">${c.value}</div>
            </div>
        `).join('');
    }

    renderSessions(sessions) {
        const tbody = document.getElementById('sessions-body');
        if (!tbody) return;

        if (sessions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-row">No active sessions</td></tr>';
            return;
        }

        tbody.innerHTML = sessions.map(s => `
            <tr>
                <td>${this.escapeHtml(s.table_name)}</td>
                <td>${this.formatVariantName(s.variant)}</td>
                <td>${this.formatStakes(s.stakes)}</td>
                <td>${s.connected_players} / ${s.max_players}</td>
                <td><span class="badge ${s.is_paused ? 'badge-warning' : 'badge-success'}">${s.is_paused ? 'Paused' : s.game_state}</span></td>
                <td>${s.hands_played}</td>
                <td>${this.formatDate(s.created_at)}</td>
            </tr>
        `).join('');
    }

    // --- Users ---

    async loadUsers() {
        const searchInput = document.getElementById('user-search');
        const sortSelect = document.getElementById('user-sort');

        if (searchInput) {
            let timeout;
            searchInput.addEventListener('input', () => {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    this.currentSearch = searchInput.value;
                    this.currentPage = 1;
                    this.fetchUsers();
                }, 300);
            });
        }
        if (sortSelect) {
            sortSelect.addEventListener('change', () => {
                this.currentSort = sortSelect.value;
                this.fetchUsers();
            });
        }

        this.fetchUsers();
    }

    async fetchUsers() {
        try {
            const params = new URLSearchParams({
                search: this.currentSearch,
                page: this.currentPage,
                sort: this.currentSort
            });
            const res = await fetch(`/admin/api/users?${params}`);
            const data = await res.json();

            if (data.success) {
                this.renderUsers(data.users);
                this.renderPagination(data.page, data.total_pages);
            }
        } catch (err) {
            this.showNotification('Failed to load users', 'error');
        }
    }

    renderUsers(users) {
        const tbody = document.getElementById('users-body');
        if (!tbody) return;

        if (users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-row">No users found</td></tr>';
            return;
        }

        tbody.innerHTML = users.map(u => `
            <tr>
                <td><strong>${this.escapeHtml(u.username)}</strong>${u.is_admin ? ' <span class="badge badge-info">Admin</span>' : ''}</td>
                <td>${this.escapeHtml(u.email)}</td>
                <td>${this.formatCurrency(u.bankroll)}</td>
                <td>${this.formatDate(u.last_login)}</td>
                <td><span class="badge ${u.is_active ? 'badge-success' : 'badge-danger'}">${u.is_active ? 'Active' : 'Disabled'}</span></td>
                <td class="action-btns">
                    <button class="btn btn-sm btn-primary" onclick="adminPanel.openBankrollModal('${u.id}', '${this.escapeHtml(u.username)}', ${u.bankroll})">Adjust</button>
                    <button class="btn btn-sm ${u.is_active ? 'btn-danger' : 'btn-primary'}" onclick="adminPanel.toggleUserActive('${u.id}')">${u.is_active ? 'Disable' : 'Enable'}</button>
                </td>
            </tr>
        `).join('');
    }

    renderPagination(currentPage, totalPages) {
        const container = document.getElementById('users-pagination');
        if (!container || totalPages <= 1) {
            if (container) container.innerHTML = '';
            return;
        }

        let html = '';
        for (let i = 1; i <= totalPages; i++) {
            html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="adminPanel.goToPage(${i})">${i}</button>`;
        }
        container.innerHTML = html;
    }

    goToPage(page) {
        this.currentPage = page;
        this.fetchUsers();
    }

    openBankrollModal(userId, username, bankroll) {
        this._bankrollUserId = userId;
        document.getElementById('bankroll-username').textContent = username;
        document.getElementById('bankroll-current').textContent = this.formatCurrency(bankroll);
        document.getElementById('bankroll-amount').value = '';
        document.getElementById('bankroll-reason').value = '';
        document.getElementById('bankroll-submit').onclick = () => this.submitBankrollAdjust();
        this.openModal('bankroll-modal');
    }

    async submitBankrollAdjust() {
        const amount = parseInt(document.getElementById('bankroll-amount').value);
        const reason = document.getElementById('bankroll-reason').value || 'Admin adjustment';

        if (isNaN(amount) || amount === 0) {
            this.showNotification('Enter a valid non-zero amount', 'error');
            return;
        }

        try {
            const res = await fetch(`/admin/api/users/${this._bankrollUserId}/bankroll`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ amount, reason })
            });
            const data = await res.json();

            if (data.success) {
                this.showNotification(`Bankroll adjusted: ${this.formatCurrency(data.old_bankroll)} -> ${this.formatCurrency(data.new_bankroll)}`);
                this.closeModal('bankroll-modal');
                this.fetchUsers();
            } else {
                this.showNotification(data.message, 'error');
            }
        } catch (err) {
            this.showNotification('Failed to adjust bankroll', 'error');
        }
    }

    async toggleUserActive(userId) {
        try {
            const res = await fetch(`/admin/api/users/${userId}/toggle-active`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();

            if (data.success) {
                this.showNotification(`User ${data.is_active ? 'enabled' : 'disabled'}`);
                this.fetchUsers();
            } else {
                this.showNotification(data.message, 'error');
            }
        } catch (err) {
            this.showNotification('Failed to toggle user', 'error');
        }
    }

    // --- Tables ---

    async loadTables() {
        try {
            const res = await fetch('/admin/api/tables');
            const data = await res.json();

            if (data.success) this.renderTables(data.tables);
        } catch (err) {
            this.showNotification('Failed to load tables', 'error');
        }
    }

    renderTables(tables) {
        const tbody = document.getElementById('tables-body');
        if (!tbody) return;

        if (tables.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-row">No tables found</td></tr>';
            return;
        }

        tbody.innerHTML = tables.map(t => `
            <tr>
                <td><strong>${this.escapeHtml(t.name)}</strong></td>
                <td>${this.formatVariantName(t.variant)}</td>
                <td>${this.formatStakes(t.stakes)}</td>
                <td>${t.current_players} / ${t.max_players}</td>
                <td>${this.escapeHtml(t.creator_username)}</td>
                <td>${this.formatDate(t.last_activity)}</td>
                <td>${t.is_private ? '<span class="badge badge-warning">Private</span>' : 'Public'}</td>
                <td>
                    <button class="btn btn-sm btn-danger" onclick="adminPanel.closeTable('${t.id}', '${this.escapeHtml(t.name)}')">Close</button>
                </td>
            </tr>
        `).join('');
    }

    async closeTable(tableId, tableName) {
        if (!confirm(`Close table "${tableName}"? Players will be cashed out.`)) return;

        try {
            const res = await fetch(`/admin/api/tables/${tableId}/close`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();

            if (data.success) {
                this.showNotification(data.message);
                this.loadTables();
            } else {
                this.showNotification(data.message, 'error');
            }
        } catch (err) {
            this.showNotification('Failed to close table', 'error');
        }
    }

    // --- Variants ---

    async loadVariants() {
        const searchInput = document.getElementById('variant-search');
        const filterSelect = document.getElementById('variant-filter');

        if (searchInput) {
            let timeout;
            searchInput.addEventListener('input', () => {
                clearTimeout(timeout);
                timeout = setTimeout(() => this.filterVariants(), 200);
            });
        }
        if (filterSelect) {
            filterSelect.addEventListener('change', () => this.filterVariants());
        }

        try {
            const res = await fetch('/admin/api/variants');
            const data = await res.json();

            if (data.success) {
                this.variantsData = data.variants;
                this.renderVariantSummary();
                this.filterVariants();
            }
        } catch (err) {
            this.showNotification('Failed to load variants', 'error');
        }
    }

    renderVariantSummary() {
        const el = document.getElementById('variant-summary');
        if (!el) return;
        const total = this.variantsData.length;
        const disabled = this.variantsData.filter(v => v.disabled).length;
        el.textContent = `${total} variants total, ${total - disabled} enabled, ${disabled} disabled`;
    }

    filterVariants() {
        const search = (document.getElementById('variant-search')?.value || '').toLowerCase();
        const filter = document.getElementById('variant-filter')?.value || '';

        let filtered = this.variantsData;

        if (search) {
            filtered = filtered.filter(v =>
                v.display_name?.toLowerCase().includes(search) ||
                v.name.toLowerCase().includes(search) ||
                (v.category || '').toLowerCase().includes(search)
            );
        }

        if (filter === 'enabled') {
            filtered = filtered.filter(v => !v.disabled);
        } else if (filter === 'disabled') {
            filtered = filtered.filter(v => v.disabled);
        }

        this.renderVariants(filtered);
    }

    renderVariants(variants) {
        const tbody = document.getElementById('variants-body');
        if (!tbody) return;

        if (variants.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-row">No variants found</td></tr>';
            return;
        }

        tbody.innerHTML = variants.map(v => `
            <tr>
                <td><strong>${this.escapeHtml(v.display_name || v.name)}</strong></td>
                <td>${this.escapeHtml(v.category || '-')}</td>
                <td>${v.min_players || '-'} - ${v.max_players || '-'}</td>
                <td>${(v.betting_structures || []).join(', ') || '-'}</td>
                <td>
                    <label class="toggle-switch">
                        <input type="checkbox" ${v.disabled ? '' : 'checked'} onchange="adminPanel.toggleVariant('${this.escapeHtml(v.name)}', this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                    ${v.disabled && v.disabled_info?.reason ? `<br><small style="color: var(--secondary-color)">${this.escapeHtml(v.disabled_info.reason)}</small>` : ''}
                </td>
            </tr>
        `).join('');
    }

    async toggleVariant(name, enabled) {
        if (enabled) {
            // Re-enable
            try {
                const res = await fetch(`/admin/api/variants/${encodeURIComponent(name)}/enable`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await res.json();

                if (data.success) {
                    this.showNotification(data.message);
                    // Update local data
                    const v = this.variantsData.find(x => x.name === name);
                    if (v) { v.disabled = false; delete v.disabled_info; }
                    this.renderVariantSummary();
                } else {
                    this.showNotification(data.message, 'error');
                    this.filterVariants(); // Revert toggle
                }
            } catch (err) {
                this.showNotification('Failed to enable variant', 'error');
                this.filterVariants();
            }
        } else {
            // Show disable modal
            this._disableVariantName = name;
            document.getElementById('disable-variant-name').textContent = this.formatVariantName(name);
            document.getElementById('disable-reason').value = '';
            document.getElementById('disable-submit').onclick = () => this.submitDisableVariant();
            this.openModal('disable-modal');
            // Revert the checkbox until confirmed
            this.filterVariants();
        }
    }

    async submitDisableVariant() {
        const name = this._disableVariantName;
        const reason = document.getElementById('disable-reason').value;

        try {
            const res = await fetch(`/admin/api/variants/${encodeURIComponent(name)}/disable`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reason })
            });
            const data = await res.json();

            if (data.success) {
                this.showNotification(data.message);
                this.closeModal('disable-modal');
                // Update local data
                const v = this.variantsData.find(x => x.name === name);
                if (v) { v.disabled = true; v.disabled_info = { reason }; }
                this.renderVariantSummary();
                this.filterVariants();
            } else {
                this.showNotification(data.message, 'error');
            }
        } catch (err) {
            this.showNotification('Failed to disable variant', 'error');
        }
    }

    // --- Utilities ---

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

const adminPanel = new AdminPanel();

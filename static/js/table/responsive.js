// Touch, resize, orientation, and mobile layout handlers
class PokerResponsive {
    constructor(onQuickAction, store) {
        this._onQuickAction = onQuickAction;
        this._store = store;
        this.isPhone = window.innerWidth <= 430;
        this.isMobile = window.innerWidth <= 768;
        this.isLandscape = window.innerHeight < window.innerWidth;
        this._headerAutoHideTimer = null;
        this._headerAutoHidden = false;
    }

    setupTouchSupport() {
        if (!('ontouchstart' in window)) return;

        document.addEventListener('touchstart', (e) => {
            if (e.target.classList.contains('action-btn')) {
                e.target.classList.add('touch-active');
            }
        });

        document.addEventListener('touchend', (e) => {
            if (e.target.classList.contains('action-btn')) {
                e.target.classList.remove('touch-active');
            }
        });

        let touchStartX = 0;
        let touchStartY = 0;

        document.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        });

        document.addEventListener('touchend', (e) => {
            if (!this._store.isMyTurn) return;

            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;
            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;

            if (!e.target.closest('.poker-table')) return;

            if (Math.abs(deltaX) < 50 && Math.abs(deltaY) < 50) return;

            if (Math.abs(deltaX) > Math.abs(deltaY)) {
                if (deltaX > 0) {
                    this._onQuickAction('call');
                } else {
                    this._onQuickAction('fold');
                }
            } else {
                if (deltaY < 0) {
                    this._onQuickAction('raise');
                }
            }
        });
    }

    setupResponsiveHandlers() {
        this.updateResponsiveLayout();
        this.adjustCardSizes();

        if (this.isMobile) {
            this.optimizeTouchTargets();
        }

        this._updateHeaderAutoHide();
    }

    handleResize() {
        const wasPhone = this.isPhone;
        const wasMobile = this.isMobile;
        this.isPhone = window.innerWidth <= 430;
        this.isMobile = window.innerWidth <= 768;
        this.isLandscape = window.innerHeight < window.innerWidth;

        if (wasPhone !== this.isPhone || wasMobile !== this.isMobile) {
            this.updateResponsiveLayout();
            this.adjustCardSizes();

            if (this.isMobile) {
                this.optimizeTouchTargets();
            }
        }

        this._updateHeaderAutoHide();
    }

    handleOrientationChange() {
        this.isLandscape = window.innerHeight < window.innerWidth;
        this.updateResponsiveLayout();

        if (this.isMobile && this.isLandscape) {
            const table = document.querySelector('.poker-table');
            if (table) {
                table.style.height = '';  // Let CSS handle it
            }
        }

        this._updateHeaderAutoHide();
    }

    _isPhoneLandscape() {
        return window.innerHeight <= 500 && this.isLandscape;
    }

    _updateHeaderAutoHide() {
        const header = document.querySelector('.table-header');
        const revealZone = document.getElementById('header-reveal-zone');
        if (!header || !revealZone) return;

        if (this._isPhoneLandscape()) {
            this._setupHeaderAutoHide(header, revealZone);
        } else {
            this._teardownHeaderAutoHide(header, revealZone);
        }
    }

    _setupHeaderAutoHide(header, revealZone) {
        // Auto-hide after 3 seconds
        this._scheduleHeaderHide(header);

        // Reveal zone touch handler
        if (!revealZone._hasListener) {
            revealZone.addEventListener('touchstart', () => {
                this._showHeader(header);
            });
            revealZone._hasListener = true;
        }

        // Hide again when tapping the table
        const tableEl = document.querySelector('.poker-table');
        if (tableEl && !tableEl._headerHideListener) {
            tableEl.addEventListener('touchstart', () => {
                if (this._isPhoneLandscape() && !header.classList.contains('auto-hidden')) {
                    this._scheduleHeaderHide(header);
                }
            });
            tableEl._headerHideListener = true;
        }
    }

    _teardownHeaderAutoHide(header, revealZone) {
        clearTimeout(this._headerAutoHideTimer);
        header.classList.remove('auto-hidden');
        this._headerAutoHidden = false;
    }

    _scheduleHeaderHide(header) {
        clearTimeout(this._headerAutoHideTimer);
        this._headerAutoHideTimer = setTimeout(() => {
            if (this._isPhoneLandscape()) {
                header.classList.add('auto-hidden');
                this._headerAutoHidden = true;
            }
        }, 3000);
    }

    _showHeader(header) {
        clearTimeout(this._headerAutoHideTimer);
        header.classList.remove('auto-hidden');
        this._headerAutoHidden = false;
        // Auto-hide again after 4 seconds
        this._headerAutoHideTimer = setTimeout(() => {
            if (this._isPhoneLandscape()) {
                header.classList.add('auto-hidden');
                this._headerAutoHidden = true;
            }
        }, 4000);
    }

    updateResponsiveLayout() {
        const app = document.getElementById('app');

        if (this.isPhone) {
            app.classList.add('phone-layout');
            app.classList.add('mobile-layout');
        } else if (this.isMobile) {
            app.classList.remove('phone-layout');
            app.classList.add('mobile-layout');
        } else {
            app.classList.remove('phone-layout');
            app.classList.remove('mobile-layout');
        }
    }

    adjustCardSizes() {
        const root = document.documentElement;

        if (this.isPhone) {
            root.style.setProperty('--card-width', '30px');
            root.style.setProperty('--card-height', '42px');
        } else if (this.isMobile) {
            root.style.setProperty('--card-width', '45px');
            root.style.setProperty('--card-height', '63px');
        } else {
            root.style.setProperty('--card-width', '60px');
            root.style.setProperty('--card-height', '84px');
        }
    }

    optimizeTouchTargets() {
        const actionButtons = document.querySelectorAll('.action-btn');
        actionButtons.forEach(btn => {
            btn.style.minHeight = '60px';
            btn.style.fontSize = '1.1rem';
        });
    }

}

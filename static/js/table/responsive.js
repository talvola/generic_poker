// Touch, resize, orientation, and mobile layout handlers
class PokerResponsive {
    constructor(onQuickAction, store) {
        this._onQuickAction = onQuickAction;
        this._store = store;
        this.isMobile = window.innerWidth <= 768;
        this.isLandscape = window.innerHeight < window.innerWidth;
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
    }

    handleResize() {
        const wasMobile = this.isMobile;
        this.isMobile = window.innerWidth <= 768;

        if (wasMobile !== this.isMobile) {
            this.updateResponsiveLayout();
            this.adjustCardSizes();

            if (this.isMobile) {
                this.optimizeTouchTargets();
            }
        }
    }

    handleOrientationChange() {
        this.isLandscape = window.innerHeight < window.innerWidth;
        this.updateResponsiveLayout();

        if (this.isMobile && this.isLandscape) {
            const table = document.querySelector('.poker-table');
            if (table) {
                table.style.height = '250px';
            }
        }
    }

    updateResponsiveLayout() {
        const app = document.getElementById('app');

        if (this.isMobile) {
            app.classList.add('mobile-layout');
        } else {
            app.classList.remove('mobile-layout');
        }
    }

    adjustCardSizes() {
        const root = document.documentElement;

        if (this.isMobile) {
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

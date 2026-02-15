// Modal, notification, and loading overlay utilities
class PokerModals {
    static showModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.add('show');

        const firstInput = modal.querySelector('input, button');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 100);
        }
    }

    static closeModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.remove('show');
    }

    static closeAllModals() {
        document.querySelectorAll('.modal.show').forEach(modal => {
            PokerModals.closeModal(modal.id);
        });
    }

    static showNotification(message, type = 'info', duration = 4000) {
        const container = document.getElementById('notification-container');

        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            ${PokerModals.escapeHtml(message)}
            <button class="notification-close" onclick="this.parentElement.remove()">&times;</button>
        `;

        container.appendChild(notification);

        setTimeout(() => {
            notification.classList.add('show');
        }, 10);

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

    static showLoadingOverlay(text = 'Loading...') {
        const overlay = document.getElementById('loading-overlay');
        const loadingText = document.querySelector('.loading-text');

        if (loadingText) {
            loadingText.textContent = text;
        }

        overlay.classList.remove('hidden');
    }

    static hideLoadingOverlay() {
        const overlay = document.getElementById('loading-overlay');
        overlay.classList.add('hidden');
    }

    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

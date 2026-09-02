// Shared "rules card" renderer for a variant's deal/bet timeline.
// Loaded by both the lobby (View Rules) and the table page (Rules button), so the
// card lives here rather than in lobby.js (GitHub #9).

function renderGameCard(rules) {
    // Subtitle tags
    const subtitle = rules.tags.join(' &bull; ');

    // Timeline
    let tlHtml = '';
    for (const elem of rules.timeline) {
        if (elem.type === 'individual') {
            const labelHtml = (elem.label || '').split('\n').join('<br>');
            if (elem.total_cards <= 1 && elem.has_up) {
                tlHtml += `<div class="gc-tl-group"><div class="gc-card-single gc-card-up">I</div><div class="gc-label">${labelHtml}</div></div>`;
            } else if (elem.total_cards <= 1 && elem.has_down) {
                tlHtml += `<div class="gc-tl-group"><div class="gc-card-single gc-card-down">I</div><div class="gc-label">${labelHtml}</div></div>`;
            } else {
                tlHtml += `<div class="gc-tl-group"><div class="gc-card-stack"><div class="gc-back gc-b1"></div><div class="gc-back gc-b2"></div><div class="gc-back gc-b3"></div><div class="gc-front">I</div></div><div class="gc-label">${labelHtml}</div></div>`;
            }
        } else if (elem.type === 'community') {
            let cards = '';
            for (let i = 0; i < Math.min(elem.count, 6); i++) {
                cards += '<div class="gc-comm">C</div>';
            }
            tlHtml += `<div class="gc-tl-group"><div class="gc-comm-row">${cards}</div></div>`;
        } else if (elem.type === 'bet') {
            tlHtml += '<div class="gc-tl-group gc-bet-group"><div class="gc-bet">Bet</div></div>';
        } else {
            const labelHtml = (elem.label || elem.type.toUpperCase()).split('\n').join('<br>');
            const cls = `gc-action gc-action-${elem.type}`;
            tlHtml += `<div class="gc-tl-group"><div class="${cls}">${labelHtml}</div></div>`;
        }
    }

    // Final hand
    let finalHtml = '';
    if (rules.final_hands.length === 1) {
        const desc = rules.final_hands[0].replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        finalHtml = `<div class="gc-final"><strong>Final Hand:</strong> ${desc}</div>`;
    } else {
        const parts = rules.final_hands.map(d => d.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')).join('<br>');
        finalHtml = `<div class="gc-final"><strong>Final Hands:</strong><br>${parts}</div>`;
    }

    // Split pot
    let splitHtml = '';
    if (rules.split_pot) {
        splitHtml = `<div class="gc-split"><strong>Split Pot:</strong> ${rules.split_pot}</div>`;
    }

    // Wild cards
    let wildHtml = '';
    if (rules.wild_cards && rules.wild_cards.length) {
        for (const w of rules.wild_cards) {
            if (w.includes('Bug')) {
                wildHtml += '<div class="gc-wild">Bug completes straight or flush, otherwise acts as an Ace.</div>';
            } else {
                wildHtml += `<div class="gc-wild">${w}.</div>`;
            }
        }
    }

    return `
        <div class="gc-subtitle">${subtitle}</div>
        <div class="gc-timeline">${tlHtml}</div>
        ${wildHtml}
        ${finalHtml}
        ${splitHtml}
    `;
}

window.renderGameCard = renderGameCard;

// Fetch a rules card from an endpoint returning {success, rules} and render it
// into the given title/content elements.
window.loadRulesCardInto = function (url, titleEl, contentEl) {
    if (contentEl) contentEl.innerHTML = '<p>Loading rules...</p>';
    fetch(url)
        .then(r => r.json())
        .then(data => {
            if (!data.success) {
                if (contentEl) contentEl.innerHTML = `<p>${data.error || 'Rules not available'}</p>`;
                return;
            }
            if (titleEl) titleEl.textContent = data.rules.game || 'Rules';
            if (contentEl) contentEl.innerHTML = renderGameCard(data.rules);
        })
        .catch(() => {
            if (contentEl) contentEl.innerHTML = '<p>Rules not available</p>';
        });
};

(function injectRulesCardStyles() {
    const style = document.createElement('style');
    style.textContent = `
    /* Game Card styles for rules modal */
    .gc-subtitle { text-align: center; color: #666; font-size: 0.85rem; margin-bottom: 14px; font-weight: 500; }
    .gc-timeline { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 6px; justify-content: center; margin-bottom: 14px; min-height: 70px; padding: 8px 0; }
    .gc-tl-group { display: flex; flex-direction: column; align-items: center; gap: 4px; }
    .gc-card-stack { position: relative; width: 44px; height: 60px; }
    .gc-back { position: absolute; width: 40px; height: 56px; border: 2px solid #888; border-radius: 4px; background: repeating-linear-gradient(135deg, #ccc, #ccc 4px, #ddd 4px, #ddd 8px); }
    .gc-b1 { top: 0; left: 0; }
    .gc-b2 { top: 2px; left: 2px; }
    .gc-b3 { top: 4px; left: 4px; }
    .gc-front { position: absolute; top: 4px; left: 4px; width: 40px; height: 56px; border: 2px solid #333; border-radius: 4px; background: #fff; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.2rem; z-index: 1; }
    .gc-card-single { width: 40px; height: 56px; border: 2px solid #333; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.2rem; }
    .gc-card-up { background: #fff; }
    .gc-card-down { background: repeating-linear-gradient(135deg, #ccc, #ccc 4px, #ddd 4px, #ddd 8px); border-color: #888; color: #555; }
    .gc-label { font-size: 0.6rem; text-align: center; color: #555; font-weight: 600; line-height: 1.2; max-width: 60px; }
    .gc-comm-row { display: flex; gap: 3px; }
    .gc-comm { width: 34px; height: 48px; border: 2px solid #333; border-radius: 3px; background: #fff; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1rem; }
    .gc-bet-group { align-self: flex-end; margin: 0 2px; }
    .gc-bet { width: 34px; height: 34px; border-radius: 50%; border: 3px solid #333; background: #f5f5f5; display: flex; align-items: center; justify-content: center; font-size: 0.55rem; font-weight: 700; }
    .gc-action { border: 2px solid #555; border-radius: 4px; padding: 5px 7px; font-size: 0.6rem; font-weight: 700; text-align: center; line-height: 1.3; min-width: 48px; background: #f9f9f9; }
    .gc-action-draw { border-color: #2563eb; color: #2563eb; }
    .gc-action-discard { border-color: #dc2626; color: #dc2626; }
    .gc-action-expose { border-color: #059669; color: #059669; }
    .gc-action-pass { border-color: #7c3aed; color: #7c3aed; }
    .gc-action-separate { border-color: #d97706; color: #d97706; }
    .gc-action-declare { border-color: #be185d; color: #be185d; }
    .gc-action-choose { border-color: #0891b2; color: #0891b2; }
    .gc-wild { font-size: 0.82rem; color: #555; margin-bottom: 6px; font-style: italic; }
    .gc-final { font-size: 0.85rem; margin-bottom: 4px; line-height: 1.4; }
    .gc-split { font-size: 0.85rem; margin-bottom: 4px; line-height: 1.4; }
`;
    document.head.appendChild(style);
})();

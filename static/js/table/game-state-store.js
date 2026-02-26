// Centralized game state store
class GameStateStore {
    constructor() {
        this.gameState = null;     // Raw server data
        this.currentUser = null;
        this.players = {};
        this.isMyTurn = false;
        this.validActions = [];
        this.potAmount = 0;
        this.handNumber = 1;
        this.tableId = null;
    }

    update(data) {
        this.gameState = data;
        this.currentUser = data.current_user;

        // Convert players array to seat-indexed object for proper rendering
        if (Array.isArray(data.players)) {
            this.players = {};
            data.players.forEach(p => { this.players[p.seat_number] = p; });
        } else {
            this.players = data.players || {};
        }

        this.isMyTurn = data.current_player === this.currentUser?.id;
        // Normalize valid actions: server sends action_type, frontend also uses type
        this.validActions = (data.valid_actions || []).map(a => ({
            ...a,
            type: a.action_type || a.type,
            action_type: a.action_type || a.type
        }));
        this.potAmount = data.pot_info?.total_pot || data.pot_amount || 0;
        this.handNumber = data.hand_number != null ? data.hand_number : this.handNumber;
    }

    findPlayerByUserId(userId) {
        const key = Object.keys(this.players).find(k => this.players[k].user_id === userId);
        return key ? this.players[key] : null;
    }
}

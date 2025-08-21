# Design Document

## Overview

This design document outlines the architecture for transforming the existing generic poker engine's web interface into a comprehensive online poker platform. The platform will support multiple concurrent games, persistent user accounts, and all poker variants supported by the engine. The design emphasizes scalability, real-time communication, and maintainability while building upon the existing poker engine foundation.

## Architecture

### High-Level Architecture

The platform follows a client-server architecture with real-time WebSocket communication:

```
┌─────────────────┐    WebSocket/HTTP    ┌─────────────────┐
│   Web Client    │ ◄─────────────────► │   Flask Server  │
│   (Browser)     │                     │   + SocketIO    │
└─────────────────┘                     └─────────────────┘
                                                 │
                                                 ▼
                                        ┌─────────────────┐
                                        │   Database      │
                                        │   (SQLite)      │
                                        └─────────────────┘
```

### Technology Stack

- **Backend**: Python Flask + Flask-SocketIO for real-time communication
- **Database**: SQLite for development, PostgreSQL for production
- **Frontend**: HTML5, CSS3, JavaScript with WebSocket support
- **Game Engine**: Existing generic_poker module (unchanged)
- **Authentication**: Flask-Login with session management
- **Real-time**: Socket.IO for bidirectional communication

## Components and Interfaces

### 1. User Management System

#### UserManager Class
```python
class UserManager:
    def create_user(username: str, email: str, password: str) -> User
    def authenticate_user(username: str, password: str) -> Optional[User]
    def get_user_by_id(user_id: str) -> Optional[User]
    def update_user_bankroll(user_id: str, amount: int) -> bool
    def get_user_statistics(user_id: str) -> UserStats
```

#### User Model
```python
@dataclass
class User:
    id: str
    username: str
    email: str
    password_hash: str
    bankroll: int
    created_at: datetime
    last_login: datetime
    is_active: bool
```

### 2. Table Management System

#### TableManager Class
```python
class TableManager:
    def create_table(creator_id: str, config: TableConfig) -> Table
    def get_public_tables() -> List[TableInfo]
    def get_table_by_id(table_id: str) -> Optional[PokerTable]
    def join_table(user_id: str, table_id: str, buy_in: int) -> bool
    def leave_table(user_id: str, table_id: str) -> int  # returns chips
    def close_inactive_tables() -> None
```

#### PokerTable Class
```python
@dataclass
class PokerTable:
    id: str
    name: str
    variant: str
    betting_structure: str
    stakes: Dict[str, int]
    max_players: int
    is_private: bool
    invite_code: Optional[str]
    creator_id: str
    game_instance: Game
    players: Dict[str, TablePlayer]
    spectators: Set[str]
    created_at: datetime
    last_activity: datetime
```

### 3. Enhanced Game Management

#### GameOrchestrator Class
```python
class GameOrchestrator:
    def __init__(self):
        self.active_games: Dict[str, GameSession] = {}
        self.table_manager = TableManager()
        self.user_manager = UserManager()
        
    def start_game_session(table_id: str) -> GameSession
    def handle_player_action(table_id: str, user_id: str, action: PlayerAction) -> ActionResult
    def process_game_events(table_id: str) -> List[GameEvent]
    def cleanup_completed_games() -> None
```

#### GameSession Class
```python
@dataclass
class GameSession:
    table_id: str
    game: Game
    players: Dict[str, SessionPlayer]
    state: GameSessionState
    hand_number: int
    last_action_time: datetime
    
    def add_player(user_id: str, buy_in: int) -> bool
    def remove_player(user_id: str) -> int
    def process_action(user_id: str, action: PlayerAction) -> ActionResult
    def get_game_state_for_player(user_id: str) -> GameStateView
    def check_hand_completion() -> bool
    def start_next_hand() -> None
    def handle_all_but_one_folded() -> None
```

#### Hand Progression Design

The system implements automatic hand progression to ensure continuous gameplay:

**Hand Completion Detection:**
- Monitor game state for `GameState.COMPLETE` 
- Detect when all but one player has folded during any betting round
- Trigger immediate hand ending and pot distribution

**Next Hand Initialization:**
- Reset game state to step 0 after brief result display period (3-5 seconds)
- Advance dealer button to next active player
- Include all seated players with sufficient chips for forced bets
- Exclude players who left during previous hand
- Start new hand automatically without manual intervention

**Continuous Play Flow:**
```
Hand Complete → Display Results → Advance Dealer → Reset State → Start Next Hand
     ↑                                                                    ↓
     └────────────────── Continuous Loop ──────────────────────────────────┘
```

### 4. Real-Time Communication System

#### WebSocketManager Class
```python
class WebSocketManager:
    def __init__(self, socketio):
        self.socketio = socketio
        self.user_sessions: Dict[str, str] = {}  # user_id -> session_id
        
    def join_table_room(user_id: str, table_id: str) -> None
    def leave_table_room(user_id: str, table_id: str) -> None
    def broadcast_to_table(table_id: str, event: str, data: Dict) -> None
    def send_to_user(user_id: str, event: str, data: Dict) -> None
    def handle_disconnect(session_id: str) -> None
```

#### Event Types
```python
class GameEvent:
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    GAME_STATE_UPDATE = "game_state_update"
    PLAYER_ACTION = "player_action"
    HAND_COMPLETE = "hand_complete"
    CHAT_MESSAGE = "chat_message"
    PLAYER_DISCONNECTED = "player_disconnected"
    PLAYER_RECONNECTED = "player_reconnected"
```

### 5. Bot Player System

#### BotManager Class
```python
class BotManager:
    def create_bot(table_id: str, difficulty: BotDifficulty) -> BotPlayer
    def remove_bot(table_id: str, bot_id: str) -> None
    def process_bot_action(bot_id: str, game_state: GameState) -> PlayerAction
    def update_bot_strategies() -> None
```

#### BotPlayer Class
```python
@dataclass
class BotPlayer:
    id: str
    name: str
    difficulty: BotDifficulty
    playing_style: PlayingStyle
    decision_engine: BotDecisionEngine
    
    def make_decision(game_state: GameState, valid_actions: List[PlayerAction]) -> PlayerAction
    def calculate_action_timing() -> float
```

### 6. UI Layout and Card Visibility System

#### GameLayoutManager Class
```python
class GameLayoutManager:
    def __init__(self):
        self.layout_configs: Dict[str, GameLayoutConfig] = {}
        
    def get_layout_config(variant: str) -> GameLayoutConfig
    def get_community_card_layout(variant: str) -> CommunityCardLayout
    def get_player_card_layout(variant: str) -> PlayerCardLayout
    def should_show_community_cards(variant: str) -> bool
```

#### GameLayoutConfig Class
```python
@dataclass
class GameLayoutConfig:
    variant: str
    community_card_layout: CommunityCardLayout
    player_card_layout: PlayerCardLayout
    has_community_cards: bool
    stud_style_display: bool
```

#### CommunityCardLayout Class
```python
@dataclass
class CommunityCardLayout:
    max_cards: int
    layout_style: str  # "standard", "none", "custom"
    positions: List[CardPosition]
    
@dataclass
class CardPosition:
    x: int
    y: int
    label: Optional[str] = None
```

#### PlayerCardLayout Class
```python
@dataclass
class PlayerCardLayout:
    display_style: str  # "single_row", "stud_two_row"
    max_face_up: int
    max_face_down: int
    show_face_down_to_owner: bool
```

#### CardVisibilityManager Class
```python
class CardVisibilityManager:
    def get_card_visibility(player_id: str, target_player_id: str, card: Card, card_state: str) -> CardVisibility
    def should_show_card(viewer_id: str, owner_id: str, card: Card, is_community: bool, card_state: str) -> bool
    def get_debug_visibility(admin_user_id: str) -> bool
    def format_card_for_display(card: Card, visible: bool, is_wild: bool) -> DisplayCard

@dataclass
class CardVisibility:
    visible: bool
    show_rank: bool
    show_suit: bool
    is_wild: bool
    wild_represents: Optional[str] = None

@dataclass
class DisplayCard:
    card_id: str
    display_rank: str
    display_suit: str
    is_face_up: bool
    is_wild: bool
    wild_represents: Optional[str]
    css_classes: List[str]
```

#### PlayerActionManager Class
```python
class PlayerActionManager:
    def __init__(self, game_engine):
        self.game_engine = game_engine
        self.timeout_manager = ActionTimeoutManager()
        
    def get_available_actions(player_id: str, game_state: GameState) -> List[PlayerActionOption]
    def validate_action(player_id: str, action: PlayerAction, amount: Optional[int]) -> ActionValidation
    def process_player_action(player_id: str, action: PlayerAction, amount: Optional[int]) -> ActionResult
    def start_action_timer(player_id: str, timeout_seconds: int) -> None
    def handle_action_timeout(player_id: str) -> ActionResult

@dataclass
class PlayerActionOption:
    action_type: PlayerAction
    min_amount: Optional[int]
    max_amount: Optional[int]
    default_amount: Optional[int]
    display_text: str
    button_style: str

@dataclass
class ActionValidation:
    is_valid: bool
    error_message: Optional[str]
    suggested_amount: Optional[int]

class ActionTimeoutManager:
    def set_timeout(player_id: str, seconds: int, callback: Callable) -> None
    def cancel_timeout(player_id: str) -> None
    def get_remaining_time(player_id: str) -> int
```

### 7. Rules Management System

#### RulesManager Class
```python
class RulesManager:
    def __init__(self):
        self.rules_cache: Dict[str, GeneratedRules] = {}
        self.manual_rules: Dict[str, str] = {}
        
    def get_rules_for_variant(variant: str) -> RulesPresentation
    def generate_rules_from_config(config_path: str) -> GeneratedRules
    def cache_generated_rules(variant: str, rules: GeneratedRules) -> None
    def get_manual_rules(variant: str) -> Optional[str]
    def set_manual_rules(variant: str, rules_text: str) -> None
    def clear_rules_cache() -> None
```

#### RulesGenerator Class
```python
class RulesGenerator:
    def __init__(self):
        self.config_parser = GameConfigParser()
        self.markdown_formatter = MarkdownFormatter()
        
    def generate_from_json(config: Dict) -> GeneratedRules
    def parse_game_flow(gameplay: List[Dict]) -> List[GameStep]
    def format_betting_structure(betting_info: Dict) -> str
    def format_showdown_rules(showdown: Dict) -> str
    def generate_statistics_table(config: Dict) -> str
    def format_dealing_sequence(deal_steps: List[Dict]) -> List[str]
```

#### GameConfigParser Class
```python
class GameConfigParser:
    def parse_config_file(file_path: str) -> Dict
    def extract_game_metadata(config: Dict) -> GameMetadata
    def extract_gameplay_steps(config: Dict) -> List[GameplayStep]
    def extract_showdown_rules(config: Dict) -> ShowdownRules
    def validate_config_structure(config: Dict) -> ConfigValidation

@dataclass
class GameMetadata:
    name: str
    references: List[str]
    min_players: int
    max_players: int
    deck_type: str
    deck_size: int
    betting_structures: List[str]

@dataclass
class GameplayStep:
    step_type: str  # "bet", "deal", "showdown", "discard", etc.
    name: str
    details: Dict
    description: str

@dataclass
class ShowdownRules:
    order: str
    starting_from: str
    cards_required: str
    best_hand: List[Dict]
    evaluation_type: str
```

#### MarkdownFormatter Class
```python
class MarkdownFormatter:
    def format_rules_document(rules: GeneratedRules) -> str
    def format_game_overview(metadata: GameMetadata) -> str
    def format_statistics_table(metadata: GameMetadata) -> str
    def format_gameplay_steps(steps: List[GameplayStep]) -> str
    def format_showdown_section(showdown: ShowdownRules) -> str
    def format_betting_rounds(betting_steps: List[GameplayStep]) -> str
    def format_dealing_sequence(dealing_steps: List[GameplayStep]) -> str
```

#### Data Models for Rules

```python
@dataclass
class GeneratedRules:
    variant: str
    metadata: GameMetadata
    overview: str
    statistics_table: str
    gameplay_steps: List[str]
    showdown_rules: str
    generated_at: datetime
    markdown_content: str

@dataclass
class RulesPresentation:
    variant: str
    title: str
    content: str
    content_type: str  # "generated", "manual", "fallback"
    last_updated: datetime
    has_visual_aids: bool = False

@dataclass
class ConfigValidation:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    missing_fields: List[str]
```

#### RulesAPI Class
```python
class RulesAPI:
    def __init__(self, rules_manager: RulesManager):
        self.rules_manager = rules_manager
        
    def get_variant_rules(variant: str) -> RulesPresentation
    def get_rules_list() -> List[VariantSummary]
    def search_rules(query: str) -> List[VariantSummary]
    def regenerate_rules(variant: str) -> GeneratedRules
    def update_manual_rules(variant: str, content: str) -> bool

@dataclass
class VariantSummary:
    variant: str
    display_name: str
    players: str
    cards: int
    betting_rounds: int
    complexity: str  # "Simple", "Moderate", "Complex"
    has_rules: bool
```

### 8. Future Enhancement: Visual Rules System

#### VisualRulesGenerator Class (Future Implementation)
```python
class VisualRulesGenerator:
    def __init__(self):
        self.diagram_generator = DiagramGenerator()
        self.layout_analyzer = GameLayoutAnalyzer()
        
    def generate_visual_rules(variant: str, config: Dict) -> VisualRules
    def create_dealing_diagram(dealing_steps: List[Dict]) -> DiagramSVG
    def create_betting_flow_diagram(betting_steps: List[Dict]) -> DiagramSVG
    def create_table_layout_diagram(player_count: int, variant: str) -> DiagramSVG
    def create_card_visibility_diagram(variant: str) -> DiagramSVG

@dataclass
class VisualRules:
    variant: str
    diagrams: List[DiagramSVG]
    interactive_elements: List[InteractiveElement]
    accessibility_text: str

@dataclass
class DiagramSVG:
    diagram_type: str
    svg_content: str
    alt_text: str
    caption: str
```

### 9. Future Enhancement: External Database Integration

#### ExternalGameImporter Class (Future Implementation)
```python
class ExternalGameImporter:
    def __init__(self):
        self.github_client = GitHubClient()
        self.converter = GameDefinitionConverter()
        
    def import_from_poker_db(repo_url: str) -> ImportResult
    def analyze_game_compatibility(external_game: Dict) -> CompatibilityReport
    def convert_external_game(external_game: Dict) -> Optional[Dict]
    def validate_converted_game(converted_config: Dict) -> ValidationResult

@dataclass
class ImportResult:
    total_games: int
    successfully_imported: int
    failed_imports: int
    compatibility_report: CompatibilityReport
    imported_games: List[str]
    failed_games: List[FailedImport]

@dataclass
class CompatibilityReport:
    supported_features: List[str]
    unsupported_features: List[str]
    coverage_percentage: float
    missing_capabilities: List[str]

@dataclass
class FailedImport:
    game_name: str
    reason: str
    missing_features: List[str]
    raw_definition: Dict
```

### 10. Database Layer

#### Database Schema

**Users Table**
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    bankroll INTEGER DEFAULT 1000,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

**Tables Table**
```sql
CREATE TABLE poker_tables (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    variant TEXT NOT NULL,
    betting_structure TEXT NOT NULL,
    stakes TEXT NOT NULL,  -- JSON
    max_players INTEGER NOT NULL,
    is_private BOOLEAN DEFAULT FALSE,
    invite_code TEXT,
    creator_id TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Game History Table**
```sql
CREATE TABLE game_history (
    id TEXT PRIMARY KEY,
    table_id TEXT REFERENCES poker_tables(id),
    hand_number INTEGER NOT NULL,
    players TEXT NOT NULL,  -- JSON
    actions TEXT NOT NULL,  -- JSON
    results TEXT NOT NULL,  -- JSON
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Transactions Table**
```sql
CREATE TABLE transactions (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    amount INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    table_id TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Game Rules Table**
```sql
CREATE TABLE game_rules (
    id TEXT PRIMARY KEY,
    variant TEXT UNIQUE NOT NULL,
    rules_type TEXT NOT NULL,  -- 'generated', 'manual', 'fallback'
    content TEXT NOT NULL,
    markdown_content TEXT,
    generated_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

**Rules Generation Cache Table**
```sql
CREATE TABLE rules_cache (
    variant TEXT PRIMARY KEY,
    config_hash TEXT NOT NULL,
    generated_rules TEXT NOT NULL,
    metadata TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);
```

## Data Models

### Core Data Models

#### TableConfig
```python
@dataclass
class TableConfig:
    name: str
    variant: str
    betting_structure: str
    stakes: Dict[str, int]
    max_players: int
    is_private: bool
    allow_bots: bool
    password: Optional[str] = None
```

#### GameStateView
```python
@dataclass
class GameStateView:
    table_id: str
    players: List[PlayerView]
    community_cards: Dict[str, List[str]]
    pot_info: PotInfo
    current_player: Optional[str]
    valid_actions: List[ActionOption]
    game_phase: str
    hand_number: int
    is_spectator: bool
```

#### PlayerView
```python
@dataclass
class PlayerView:
    user_id: str
    username: str
    position: str
    chip_stack: int
    current_bet: int
    cards: List[str]  # Hidden for other players
    is_active: bool
    is_current_player: bool
    is_bot: bool
```

## Error Handling

### Error Categories

1. **Authentication Errors**: Invalid credentials, expired sessions
2. **Game Logic Errors**: Invalid actions, insufficient chips
3. **Network Errors**: Connection timeouts, WebSocket failures
4. **Database Errors**: Transaction failures, constraint violations
5. **Validation Errors**: Invalid input data, malformed requests

### Error Response Format
```python
@dataclass
class ErrorResponse:
    error_code: str
    message: str
    details: Optional[Dict] = None
    timestamp: datetime = field(default_factory=datetime.now)
```

### Retry and Recovery Mechanisms

- **Connection Recovery**: Automatic reconnection with exponential backoff
- **Game State Recovery**: Restore player state on reconnection
- **Transaction Rollback**: Atomic operations for chip transfers
- **Graceful Degradation**: Continue game with disconnected players

## API Endpoints

### Rules Management Endpoints

```python
# Get rules for a specific variant
GET /api/rules/{variant}
Response: RulesPresentation

# Get list of all variants with rule availability
GET /api/rules/
Response: List[VariantSummary]

# Search rules by game name or features
GET /api/rules/search?q={query}
Response: List[VariantSummary]

# Regenerate rules for a variant (admin only)
POST /api/rules/{variant}/regenerate
Response: GeneratedRules

# Update manual rules for a variant (admin only)
PUT /api/rules/{variant}/manual
Body: {"content": "markdown content"}
Response: {"success": bool, "message": str}

# Get raw game configuration (debug/admin)
GET /api/rules/{variant}/config
Response: Dict (raw JSON config)
```

### Integration with Existing Endpoints

The rules system integrates with existing table and lobby endpoints:

```python
# Enhanced table creation with rules preview
POST /api/tables/create
Body: {
    "variant": str,
    "show_rules_preview": bool,  # New optional field
    ...existing fields
}
Response: {
    "table": TableInfo,
    "rules_preview": Optional[str]  # First 200 chars of rules
}

# Enhanced lobby with rules availability
GET /api/lobby
Response: {
    "tables": List[TableInfo],
    "variants": List[{
        "name": str,
        "display_name": str,
        "has_rules": bool,
        "complexity": str
    }]
}
```

## Testing Strategy

### Unit Testing
- **Game Logic**: Test all poker variants with predetermined card sequences
- **User Management**: Authentication, bankroll operations
- **Table Management**: Creation, joining, leaving operations
- **Bot Behavior**: Decision-making algorithms and timing
- **Rules Generation**: Test automatic rule generation from JSON configs
- **Rules Formatting**: Validate markdown output and content structure
- **Config Parsing**: Test parsing of all 192+ game configuration files

### Integration Testing
- **WebSocket Communication**: Real-time event handling
- **Database Operations**: CRUD operations and transactions
- **Multi-table Scenarios**: Concurrent game management
- **Cross-browser Compatibility**: Desktop and mobile browsers
- **Rules API Integration**: Test rules endpoints with frontend components
- **Rules Cache Performance**: Validate caching behavior and cache invalidation
- **Config File Processing**: Test bulk processing of all game configuration files

### End-to-End Testing
- **Complete Game Flows**: Full hands from start to finish
- **User Journeys**: Registration, table creation, gameplay
- **Performance Testing**: Multiple concurrent users and games
- **Security Testing**: Authentication and authorization

### Test Data Management
- **Mock Decks**: Predetermined card sequences for consistent testing
- **Test Users**: Pre-created accounts with various bankroll levels
- **Test Tables**: Various configurations for different scenarios
- **Sample Configs**: Representative game configurations for rules testing
- **Expected Rules**: Golden master files for rules generation validation
- **Edge Case Configs**: Unusual or complex game configurations for robustness testing

## Security Considerations

### Authentication and Authorization
- **Password Security**: Bcrypt hashing with salt
- **Session Management**: Secure session tokens with expiration
- **Role-based Access**: Table creators have additional privileges
- **Rate Limiting**: Prevent abuse of API endpoints

### Game Integrity
- **Server-side Validation**: All game actions validated on server
- **Cryptographic RNG**: Secure random number generation for shuffling
- **Action Verification**: Prevent impossible or invalid actions
- **Audit Trail**: Complete logging of all game actions

### Data Protection
- **Input Sanitization**: Prevent XSS and injection attacks
- **HTTPS Enforcement**: Encrypted communication in production
- **Database Security**: Parameterized queries, connection encryption
- **Privacy Protection**: User data handling compliance

## Performance Optimization

### Scalability Strategies
- **Connection Pooling**: Efficient database connection management
- **Event Batching**: Group related events for efficient transmission
- **Memory Management**: Cleanup of completed games and old data
- **Caching**: Redis for session data and frequently accessed information

### Real-time Performance
- **WebSocket Optimization**: Efficient message serialization
- **Game State Compression**: Minimize data transfer
- **Selective Updates**: Send only changed data to clients
- **Connection Management**: Handle disconnections gracefully

### Database Optimization
- **Indexing Strategy**: Optimize queries for user and table lookups
- **Data Archival**: Move old game history to archive tables
- **Query Optimization**: Efficient joins and aggregations
- **Connection Pooling**: Manage database connections efficiently

## Deployment Architecture

### Development Environment
- **Local SQLite**: Simple setup for development
- **Hot Reload**: Automatic server restart on code changes
- **Debug Mode**: Detailed error messages and logging
- **Test Data**: Pre-populated with sample users and tables

### Production Environment
- **PostgreSQL**: Robust database for production workloads
- **Load Balancing**: Multiple server instances behind load balancer
- **SSL Termination**: HTTPS encryption for all communications
- **Monitoring**: Application performance and error tracking
- **Backup Strategy**: Regular database backups and recovery procedures

### Containerization
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0"]
```

This design provides a solid foundation for building a comprehensive online poker platform while leveraging the existing poker engine and maintaining scalability for future enhancements.
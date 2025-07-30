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

### 6. Database Layer

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

## Testing Strategy

### Unit Testing
- **Game Logic**: Test all poker variants with predetermined card sequences
- **User Management**: Authentication, bankroll operations
- **Table Management**: Creation, joining, leaving operations
- **Bot Behavior**: Decision-making algorithms and timing

### Integration Testing
- **WebSocket Communication**: Real-time event handling
- **Database Operations**: CRUD operations and transactions
- **Multi-table Scenarios**: Concurrent game management
- **Cross-browser Compatibility**: Desktop and mobile browsers

### End-to-End Testing
- **Complete Game Flows**: Full hands from start to finish
- **User Journeys**: Registration, table creation, gameplay
- **Performance Testing**: Multiple concurrent users and games
- **Security Testing**: Authentication and authorization

### Test Data Management
- **Mock Decks**: Predetermined card sequences for consistent testing
- **Test Users**: Pre-created accounts with various bankroll levels
- **Test Tables**: Various configurations for different scenarios

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
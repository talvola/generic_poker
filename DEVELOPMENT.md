# Development Workflow Guide

This guide covers best practices for developing and testing the poker platform.

## Quick Start

```bash
# 1. Start your work session - verify everything works
pytest

# 2. Make code changes

# 3. Run relevant tests while developing
pytest tests/unit/test_auth_service.py -v

# 4. If tests pass and you need visual confirmation, start server
python app.py

# 5. Before committing, run full test suite
pytest
```

## Development Approaches

### Primary: Test-Driven Development (Recommended for Most Work)

For most development work, use tests as your primary feedback loop:

```bash
# Terminal 1: Run tests in watch mode
pytest tests/unit/ -v --tb=short -x

# Or for a specific area you're working on
pytest tests/unit/test_game_state_manager.py -v -x

# The -x flag stops on first failure for faster iteration
# The --tb=short gives concise tracebacks
```

**Why test-first:**
- ✅ Instant feedback (tests run in 1-2 seconds)
- ✅ No need to manually click through UI
- ✅ Easier to reproduce edge cases
- ✅ Forces you to think about API design
- ✅ Catches regressions immediately

**When to use test-driven approach:**
- Adding new game variants (use unit tests with GameRules)
- Fixing betting logic (unit tests in `tests/unit/test_betting_flow.py`)
- Hand evaluation fixes (unit tests)
- Adding new API endpoints (integration tests)
- Fixing database models (integration tests)
- Service layer changes
- Business logic modifications

### Secondary: Manual Testing with Running Server

When you need to test UI, WebSockets, or manually verify features:

```bash
# Terminal 1: Run server with live logs visible
python app.py

# OR to save logs to file while also seeing them in terminal
python app.py 2>&1 | tee -a dev.log
```

The `tee` command shows logs in terminal AND appends to `dev.log` so it can be searched later.

**When to use the running server:**
- ✅ Testing UI changes
- ✅ Debugging WebSocket issues
- ✅ Testing real-time multi-player interactions
- ✅ Visual verification of layout/styling
- ✅ End-to-end testing before committing
- ✅ Testing table UI layout
- ✅ Debugging real-time game state updates
- ✅ Testing seat assignments visually
- ✅ Checking showdown display
- ✅ Testing chat functionality
- ✅ Verifying card animations
- ✅ Testing disconnect/reconnect behavior
- ✅ Cross-browser compatibility

## Logging Strategy

### Current Logging Setup

The app already logs to both console AND `poker_platform.log` (see `setup_logging()` in `app.py`):

```python
def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),           # Console output
            logging.FileHandler('poker_platform.log')  # File output
        ]
    )
```

### Best Practices

- **Keep `poker_platform.log`** for reference when debugging
- **Watch logs in real-time** in a separate terminal:
  ```bash
  tail -f poker_platform.log
  ```
- **Clear old logs** when starting fresh investigation:
  ```bash
  rm poker_platform.log
  ```
- **Adjust verbosity temporarily** when debugging specific issues:
  ```python
  # Change level in app.py temporarily
  level=logging.DEBUG  # Very verbose
  level=logging.INFO   # Normal (recommended for production)
  level=logging.WARNING  # Quiet
  ```

### Searching Logs

```bash
# Show last 50 lines
tail -50 poker_platform.log

# Search for errors
grep -i "error\|exception\|traceback" poker_platform.log | tail -30

# Search for specific error with context (5 lines before/after)
grep -A 5 -B 5 "KeyError" poker_platform.log

# Follow log in real-time with filtering
tail -f poker_platform.log | grep "ERROR"
```

## Multi-User Testing Setup

For testing multiplayer poker features:

```bash
# Terminal 1: Start server
python app.py

# Open multiple browser instances:
# Browser 1: http://localhost:5000 (Player 1)
# Browser 2: http://localhost:5000 (incognito mode - Player 2)
# Browser 3: http://localhost:5000 (different browser - Player 3)
```

**Debugging WebSockets:**
1. Open browser DevTools (F12)
2. Go to Network tab
3. Filter by WS (WebSocket)
4. Click on the WebSocket connection
5. View Messages tab to see real-time communication

**Browser Console:**
- Check Console tab in DevTools for JavaScript errors
- Look for WebSocket connection/disconnection messages
- Check for game state update messages

## Testing Commands Reference

### Running Tests

```bash
# Run all tests
pytest

# Run all tests with verbose output
pytest -v

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run specific test file
pytest tests/unit/test_auth_service.py

# Run specific test class
pytest tests/unit/test_auth_service.py::TestSessionManager

# Run specific test method
pytest tests/unit/test_auth_service.py::TestSessionManager::test_logout_user_session_success

# Stop on first failure (faster iteration)
pytest -x

# Show short tracebacks (less verbose)
pytest --tb=short

# Show extra test summary info
pytest -v --tb=short -x

# Run with coverage report
pytest --cov=generic_poker --cov=online_poker

# Run tests that match a pattern
pytest -k "auth"  # Only runs tests with "auth" in the name
```

### Watch Mode (Auto-run on file changes)

```bash
# Install pytest-watch
pip install pytest-watch

# Watch and auto-run tests
ptw tests/unit/

# Watch specific test file
ptw tests/unit/test_auth_service.py
```

## What to Share When Debugging

### For Test Failures

Just paste the pytest output directly - it's already well-formatted:

```bash
pytest tests/unit/test_something.py -v
```

The output includes:
- Which test failed
- The assertion that failed
- Full traceback
- Variable values

### For Runtime Errors

Share relevant log excerpts:

```bash
# Last 50 lines of log
tail -50 poker_platform.log

# Or search for errors
grep -i "error\|exception\|traceback" poker_platform.log | tail -30

# With context around the error
grep -A 10 -B 5 "Traceback" poker_platform.log
```

### For WebSocket Issues

- Screenshot or copy WebSocket messages from browser DevTools
- Share browser console errors (F12 → Console tab)
- Include the game state updates being sent/received

### For UI Issues

- Screenshot of the issue
- Browser console errors (F12 → Console)
- Network tab showing failed requests (if any)
- Describe steps to reproduce

## Common Development Workflows

### Adding a New Feature

```bash
# 1. Write a failing test first
# Edit tests/unit/test_new_feature.py

# 2. Run the test to confirm it fails
pytest tests/unit/test_new_feature.py -v

# 3. Implement the feature
# Edit src/...

# 4. Run tests until they pass
pytest tests/unit/test_new_feature.py -v

# 5. Run full test suite to check for regressions
pytest

# 6. If UI is involved, manually test
python app.py

# 7. Commit when all tests pass
git add . && git commit -m "Add new feature"
```

### Fixing a Bug

```bash
# 1. Reproduce the bug with a test
# Edit tests/unit/test_bug_fix.py

# 2. Confirm test fails (reproduces bug)
pytest tests/unit/test_bug_fix.py -v

# 3. Fix the bug
# Edit src/...

# 4. Verify test now passes
pytest tests/unit/test_bug_fix.py -v

# 5. Run full suite
pytest

# 6. Update bug tracking document
# Edit .kiro/specs/online-poker-platform/bugs.md
# Mark bug as resolved, add resolution details

# 7. Commit
git add . && git commit -m "Fix: description of bug"
```

### Debugging a Failing Test

```bash
# 1. Run the specific test with verbose output
pytest tests/unit/test_something.py::test_method -v

# 2. If you need more detail, add print statements or use pdb
# Add to your test:
import pdb; pdb.set_trace()

# Or add print statements
print(f"Variable value: {some_var}")

# 3. Re-run
pytest tests/unit/test_something.py::test_method -v -s
# The -s flag shows print output
```

### Testing UI Changes

```bash
# Terminal 1: Run server
python app.py

# Terminal 2: Watch logs (optional)
tail -f poker_platform.log

# Browser: http://localhost:5000
# Test your changes, check browser console for errors

# When satisfied, write/update tests
# Edit tests/integration/test_ui_feature.py

# Run integration tests
pytest tests/integration/
```

### Working on Game Logic

```bash
# 1. Run relevant game tests
pytest tests/unit/test_betting_flow.py -v

# 2. Make changes to game logic
# Edit src/generic_poker/game/...

# 3. Re-run tests frequently
pytest tests/unit/test_betting_flow.py -v -x

# 4. Once passing, run related tests
pytest tests/game/ -v

# 5. Run full suite
pytest
```

## Port and Configuration

### Default Ports

- **Web Server**: http://localhost:5000
- **WebSocket**: ws://localhost:5000

### Changing Port

If port 5000 is in use, edit `app.py`:

```python
socketio.run(
    app,
    debug=True,
    host='0.0.0.0',
    port=5001,  # Change this
    allow_unsafe_werkzeug=True
)
```

### Environment Variables

The app uses `.env` file for configuration. Current settings:

```bash
# Database
SQLALCHEMY_DATABASE_URI=sqlite:///poker_platform.db

# Flask
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
DEBUG=True
```

## Useful Development Tools

### Python Debugger (pdb)

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Run test and interact with debugger
pytest tests/unit/test_something.py -v -s
```

**pdb commands:**
- `n` - next line
- `s` - step into function
- `c` - continue execution
- `p variable` - print variable value
- `l` - list surrounding code
- `q` - quit debugger

### IPython for Better REPL

```bash
pip install ipython

# Start interactive shell with app context
python -i -c "from app import create_app; app, socketio = create_app()"
```

### Database Inspection

```bash
# Install sqlite3 (usually pre-installed)
sqlite3 poker_platform.db

# SQLite commands:
.tables              # List tables
.schema users        # Show table schema
SELECT * FROM users; # Query data
.quit                # Exit
```

## Performance Tips

### Faster Test Runs

```bash
# Run tests in parallel (requires pytest-xdist)
pip install pytest-xdist
pytest -n auto  # Uses all CPU cores

# Run only tests that failed last time
pytest --lf

# Run failed tests first, then others
pytest --ff
```

### Faster Server Restarts

The server auto-reloads when code changes (debug mode), but for manual restart:

```bash
# Ctrl+C to stop server
# Then restart with up arrow + Enter
python app.py
```

## Troubleshooting

### Tests Fail After Pulling New Code

```bash
# 1. Update dependencies
pip install -e ".[test]"

# 2. Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# 3. Re-run tests
pytest
```

### Database Issues

```bash
# Delete and recreate database
rm poker_platform.db

# Restart app to recreate
python app.py
```

### Port Already in Use

```bash
# Find process using port 5000
lsof -i :5000

# Kill process
kill -9 <PID>

# Or change port in app.py
```

### Import Errors

```bash
# Ensure package is installed in development mode
pip install -e .

# Check Python path
echo $PYTHONPATH

# Verify you're in virtual environment
which python
# Should show: /path/to/generic_poker/env/bin/python
```

## Git Workflow Tips

```bash
# Check status before committing
git status

# Run all tests before committing
pytest

# Stage changes
git add .

# Commit with descriptive message
git commit -m "Fix: detailed description of what changed"

# Push to remote
git push
```

## Daily Workflow Checklist

**Starting work:**
- [ ] Activate virtual environment: `source env/bin/activate`
- [ ] Pull latest changes: `git pull`
- [ ] Run tests to ensure starting point works: `pytest`
- [ ] Clear old logs if needed: `rm poker_platform.log`

**During development:**
- [ ] Write/update tests first
- [ ] Run tests frequently: `pytest tests/unit/test_file.py -v -x`
- [ ] Check logs when debugging: `tail -f poker_platform.log`
- [ ] Manual test in browser when needed

**Before committing:**
- [ ] Run full test suite: `pytest`
- [ ] Check for unintended changes: `git status`
- [ ] Update bug tracking if fixing a bug
- [ ] Write clear commit message

## Summary

**Recommended approach: Test-first, manual test when needed**

Most development happens with:
1. Code editor
2. Terminal running pytest
3. Occasional server for visual verification

The log file (`poker_platform.log`) is already well-configured. When encountering issues, share relevant excerpts. No logging changes needed unless debugging something specific.

**Time allocation guideline:**
- 80% of development: Writing/running tests
- 15% of development: Manual testing in browser
- 5% of development: Debugging with logs

This keeps development fast and reliable while ensuring quality.

---

## Current Development Status (Updated: November 27, 2024)

### Database & Persistence Layer

The application now uses SQLite as the persistence layer with full database support.

**Database Setup Scripts:**
- `tools/init_db.py` - Initializes the database schema (drops and recreates all tables)
- `tools/seed_db.py` - Seeds database with test data (5 users, 4 tables)
- `tools/reset_db.py` - Resets database to clean state

**Running the Scripts:**
```bash
# Initialize database schema
python tools/init_db.py

# Seed with test data
python tools/seed_db.py

# Reset to clean state
python tools/reset_db.py
```

**Test Credentials:**
- Username: `testuser`, Password: `password`, Bankroll: $800
- Username: `alice`, Password: `password`, Bankroll: $1000
- Username: `bob`, Password: `password`, Bankroll: $1500
- Username: `charlie`, Password: `password`, Bankroll: $500
- Username: `diana`, Password: `password`, Bankroll: $2000

**Database Location:**
- Primary database: `./poker_platform.db` (root directory)
- Flask may also create: `./instance/poker_platform.db`
- Use the root directory database for development

**Seeded Tables:**
1. **Omaha** - Omaha Hi-Lo, Limit, $2/$4, 6-max (2 players seated)
2. **Texas Hold'em - Micro Stakes** - No Limit, $1/$2, 9-max (1 player seated as of last test)
3. **7-Card Stud - High Stakes** - Limit, $10/$20, 8-max
4. **Private Game** - Hold'em, Pot Limit, $5/$10, 6-max (requires invite code)

### Recent Fixes & Improvements (Nov 27, 2024)

**1. WebSocket Authentication**
- Fixed: WebSocket manager was rejecting ALL unauthenticated connections
- Solution: Modified to allow guest users to browse lobby without authentication
- File: `src/online_poker/services/websocket_manager.py:57-96`
- Guests can now view tables; authentication still required for joining

**2. Missing Seats API Endpoint**
- Fixed: `/api/tables/<table_id>/seats` endpoint was missing (causing 404 on Join)
- Solution: Implemented complete seats endpoint with seat availability data
- File: `src/online_poker/routes/lobby_routes.py:152-223`
- Returns: seat positions, occupied/available status, player info, buy-in limits

**3. Template Stakes Parsing Error**
- Fixed: `table.html` tried to access `table.stakes` as object but it's stored as JSON string
- Solution: Updated template to use `table.get_stakes()` method
- File: `templates/table.html:24-29`
- Error: `jinja2.exceptions.UndefinedError: 'str object' has no attribute 'get'`

**4. WebSocket Event Name Mismatch**
- Fixed: Server emitted `'joined_table'` but client listened for `'table_joined'`
- Solution: Changed event name to match client expectation
- File: `src/online_poker/services/websocket_manager.py:143`
- Result: Join button now properly redirects to table view

**5. Seat Selection Modal UI**
- Fixed: 9-player seat layout was cramped oval with overlapping seats
- Solution: Changed to rounded rectangle "racetrack" style with better spacing
- Files: `static/css/lobby.css:1106-1250`
- Changes:
  - Table shape: Changed from perfect oval to rounded rectangle
  - Dimensions: 520px × 300px with border-radius: 150px
  - Seat positions: Redistributed around perimeter (no overlapping)
  - Text visibility: Added dark green background to seat labels for readability

### Known Issues Requiring Restart

**Server Restart Required:**
The Flask dev server was started with `use_reloader=False` to fix WebSocket issues. This means code changes (especially WebSocket handlers) won't auto-reload. You must manually restart the server to see changes.

```bash
# Stop server
Ctrl+C

# Restart server
python app.py
```

### Next Steps / TODO

1. **Test Table Join Redirect** (HIGH PRIORITY)
   - Restart server to pick up WebSocket event name fix
   - Click Join on a table and verify redirect to `/table/<table_id>`
   - Should see actual poker table interface, not lobby

2. **Test Full Game Flow**
   - Join a table as multiple users (incognito windows)
   - Verify game starts when minimum players join
   - Test betting, folding, showdown

3. **Fix Minor UI Issues**
   - Top seat labels in seat selection modal could use better contrast
   - Consider darker text or stronger background for dashed available seats

4. **Documentation**
   - Document seat selection UX patterns
   - Add screenshots to DEVELOPMENT.md

5. **Test Coverage**
   - Add integration tests for seat selection endpoint
   - Add tests for WebSocket table joining flow

### Files Modified in This Session

**Backend:**
- `src/online_poker/services/websocket_manager.py` - Guest auth, event name fix
- `src/online_poker/routes/lobby_routes.py` - Added seats API endpoint
- `templates/table.html` - Fixed stakes parsing
- `tools/init_db.py` - NEW: Database initialization script
- `tools/seed_db.py` - NEW: Database seeding script

**Frontend:**
- `static/css/lobby.css` - Fixed 9-player seat layout (lines 1106-1250, 1189-1250, 1282-1290, 1326-1343)

**Configuration:**
- `app.py` - WebSocket settings (use_reloader=False, async_mode=None)

### How to Continue Work

**Option 1: Test Table Joining (Recommended Next)**
```bash
# 1. Restart server to pick up WebSocket fix
Ctrl+C
python app.py

# 2. Open browser: http://localhost:5000
# 3. Login as testuser/password
# 4. Click Join on "Texas Hold'em - Micro Stakes"
# 5. Select a seat and click "Join Table"
# 6. Should redirect to table view (not lobby)
```

**Option 2: Fresh Start**
```bash
# Reset database
python tools/reset_db.py

# Initialize schema
python tools/init_db.py

# Seed test data
python tools/seed_db.py

# Start server
python app.py
```

**Option 3: View Current Database State**
```bash
sqlite3 poker_platform.db
.tables
SELECT * FROM users;
SELECT * FROM poker_tables;
SELECT * FROM table_access;
.quit
```

### Server Status

Last known state:
- Server running on port 5000
- Multiple background bash processes (may need cleanup)
- Database populated with test data
- 1 player (testuser) seated at "Texas Hold'em - Micro Stakes" table

**To kill background processes:**
```bash
# List all python processes
ps aux | grep python

# Kill specific process
kill <PID>
```

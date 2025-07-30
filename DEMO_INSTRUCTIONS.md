# 🎲 Poker Platform Demo Instructions

## Quick Start

### 1. Install Dependencies
Make sure you have Python 3.8+ installed, then install the required packages:

```bash
# Activate your virtual environment
source env/bin/activate  # On Linux/Mac
# or
env\Scripts\activate     # On Windows

# Install required packages
pip install flask flask-socketio flask-login
```

### 2. Start the Demo Server
```bash
python run_server.py
```

You should see output like:
```
🎲 Starting Poker Platform Demo Server...
📍 Access the lobby at: http://localhost:5000
🔧 Demo mode: Simple in-memory storage
👤 Login with any username to test the lobby
```

### 3. Access the Lobby
1. Open your web browser
2. Go to: `http://localhost:5000`
3. Enter any username (e.g., "TestPlayer") to login
4. You'll be taken to the poker lobby!

## What You Can Test

### ✅ **Lobby Features**
- **Browse Tables**: See demo tables with different variants and stakes
- **Filter Tables**: Use the filter dropdowns to narrow down tables
- **Create Tables**: Click "Create Table" to make a new table
- **Table Details**: Click on any table to see detailed information
- **Join Tables**: Try joining public tables (demo mode)
- **Private Tables**: Use invite code "DEMO0001" to join the private table

### ✅ **Responsive Design**
- Resize your browser window to see mobile responsiveness
- Try on different devices/screen sizes

### ✅ **Real-time Updates**
- Open multiple browser tabs/windows
- Create a table in one tab and see it appear in others
- Tables update in real-time via WebSocket

## Demo Limitations

This is a **lobby-only demo**. The following are not yet implemented:
- ❌ Actual poker gameplay (clicking "Join" shows a demo message)
- ❌ Real user authentication (any username works)
- ❌ Database persistence (data resets when server restarts)
- ❌ Real money/chip management
- ❌ Bot players

## Demo Tables Included

The server starts with 3 demo tables:

1. **Beginner Hold'em** - No Limit, $1/$2 blinds, 2/6 players
2. **High Stakes Omaha** - Pot Limit, $5/$10 blinds, 7/9 players  
3. **Private Game** - Limit Hold'em, invite code: `DEMO0001`

## Troubleshooting

### Port Already in Use
If port 5000 is busy, edit `run_server.py` and change the port:
```python
socketio.run(app, debug=True, host='0.0.0.0', port=5001)  # Use 5001 instead
```

### Missing Dependencies
Install any missing packages:
```bash
pip install flask flask-socketio flask-login python-socketio
```

### Browser Console Errors
Open browser developer tools (F12) to see any JavaScript errors. The lobby should work in modern browsers (Chrome, Firefox, Safari, Edge).

## Next Steps

This demo shows the lobby interface working. The next development phases would be:

1. **Complete Authentication System** - Real user accounts and login
2. **Database Integration** - Persistent storage for users and tables  
3. **Game Engine Integration** - Connect the existing poker game engine
4. **Real-time Game Interface** - Build the actual poker table UI
5. **Bot Players** - Add computer opponents
6. **Mobile App** - Native mobile applications

## File Structure

```
├── run_server.py          # Demo server (simple Flask app)
├── templates/
│   └── lobby.html         # Lobby HTML template
├── static/
│   ├── css/
│   │   └── lobby.css      # Lobby styling
│   └── js/
│       └── lobby.js       # Lobby JavaScript
└── src/                   # Full platform code (for future integration)
```

## Feedback

Try out the lobby and let me know:
- Does the interface feel intuitive?
- Are there any bugs or issues?
- What features would you like to see next?
- How does the mobile experience feel?

The lobby demonstrates the core table discovery and creation functionality that will be the foundation for the full poker platform!
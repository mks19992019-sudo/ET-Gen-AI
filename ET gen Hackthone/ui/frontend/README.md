# HireSignal Frontend Dashboard

A complete, responsive, real-time dashboard UI for the **HireSignal Autonomous HR Hiring Intelligence Agent** built with pure HTML, CSS, and JavaScript (no frameworks).

## 📋 Overview

HireSignal Frontend is a single-page application (SPA) that provides:
- Real-time dashboard with hiring signals and team metrics
- Live agent log with WebSocket streaming
- Hiring decisions management with approval/rejection workflows
- Job description management
- Comprehensive audit trail
- Workforce data visualization

## 🎨 Design

- **Dark Professional Theme**: Dark background (#0f1117) with purple accent (#6366f1)
- **Responsive Layout**: Sidebar navigation + main content area
- **Mobile-First**: Fully responsive from mobile to desktop
- **Smooth Animations**: Fade-ins, slide-ups, and hover effects
- **Zero Dependencies**: Pure CSS and vanilla JavaScript

## 📁 File Structure

```
frontend/
├── index.html      # Complete HTML structure with 6 pages and modals
├── style.css       # Dark theme, responsive design, animations
├── app.js          # State management, API integration, page logic
└── README.md       # This file
```

## 🚀 Quick Start

1. **Serve the frontend** (requires a simple HTTP server):
   ```bash
   cd frontend
   python3 -m http.server 8080
   # OR
   npx http-server
   ```

2. **Open in browser**: http://localhost:8080

3. **Backend URL**: Update `CONFIG.BASE_URL` in `app.js` if backend is on different port:
   ```javascript
   const CONFIG = {
     BASE_URL: "http://localhost:8000",
     WS_URL: "ws://localhost:8000/ws/agent-live"
   };
   ```

## 📄 Pages

### 1. **Dashboard** (Default)
- 4 metric cards: Total Employees, Teams Monitored, Open Hiring Requests, Jobs Posted
- Signal Health section with team signal cards
- Each signal shows: Overload %, Recent Exits, Capacity Gap %, Attrition, Skill Gap
- Color-coded status badges: CRITICAL (red), WARNING (amber), NORMAL (green)
- "Run Agent Now" button to trigger agent pipeline
- Agent status indicator with animated spinner

### 2. **Live Agent Log**
- Real-time stream of agent actions via WebSocket
- Color-coded by status: SUCCESS (green), ERROR (red), WARNING (amber), CLAUDE (purple)
- Auto-scrolls to latest entries
- Connection status indicator
- Clear Logs button
- "Reconnecting..." message if disconnected

### 3. **Hiring Decisions**
- Table of all hiring decisions with columns:
  - Date, Department, Role, Urgency badge, Reason, Status, Actions
- Status options: PENDING HR APPROVAL, APPROVED, REJECTED, JD GENERATED, POSTED
- PENDING rows show Approve (green) and Reject (red) buttons
- Modal confirmations for approve/reject actions
- Reject modal includes reason text input

### 4. **Job Descriptions**
- Grid of JD cards with: Role, Department, Urgency, Generated Date, Status
- "View JD" button opens modal with full JD text
- "Approve JD" button (if PENDING REVIEW) posts to LinkedIn
- Posted JDs show green "Live on LinkedIn" badge
- Status color-coded: PENDING REVIEW, HR APPROVED, POSTED TO LINKEDIN

### 5. **Audit Trail**
- Timeline view of all agent decisions
- Each entry: timestamp, agent name, action description, outcome
- Filters: All / Today / This Week + Agent Name dropdown
- Color-coded outcomes: green for success, red for error
- Export button (demo functionality)

### 6. **Workforce Data**
- Left panel: Teams table
  - Columns: Team Name, Department, Headcount, Min Required, Avg Hours/Week, Status
- Right panel: Recent Employee Changes
  - Columns: Name, Role, Department, Change Type, Date
- Shows 10 most recent employee changes

## 🔌 API Integration

All data comes from the FastAPI backend. No mock data anywhere in the codebase.

### API Endpoints Called

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/teams` | GET | Teams list for stats and workforce page |
| `/api/employees` | GET | Employees for total count and changes table |
| `/api/signals` | GET | Team signals for dashboard cards |
| `/api/agent/status` | GET | Current agent status + spinner animation |
| `/api/hiring/decisions` | GET | All hiring decisions table |
| `/api/hiring/approve` | POST | Approve a decision |
| `/api/hiring/reject` | POST | Reject a decision with reason |
| `/api/jd/{id}` | GET | Get full job description text |
| `/api/jd/{id}/approve` | POST | Approve JD and post to LinkedIn |
| `/api/agent/run` | POST | Start agent pipeline manually |
| `/api/audit` | GET | All audit trail entries |

### WebSocket

**URL**: `ws://localhost:8000/ws/agent-live`

**Message Format**:
```json
{
  "timestamp": "2024-03-18T12:34:56Z",
  "agent": "HiringAgent",
  "action": "Analyzed team overload signals",
  "status": "SUCCESS"
}
```

**Status Values**: `SUCCESS`, `ERROR`, `WARNING`, `CLAUDE`

## 🎯 Key Features

### ✨ Responsive Design
- Sidebar collapses on mobile
- Flexible grids adapt to screen size
- Touch-friendly buttons and modals

### ⚡ Loading States
- CSS spinner in every section during data fetch
- Loading indicators on buttons
- Placeholder text while data loads

### 🎨 Error Handling
- Graceful error states with helpful messages
- "Backend not reachable" message if API fails
- Console logging for debugging

### 🔔 Notifications
- Toast notifications (success, error, warning)
- Auto-dismiss after 3 seconds
- Bottom-right corner positioning

### 🔄 Auto-Refresh
- Agent status polled every 5 seconds
- WebSocket auto-reconnect every 5 seconds (up to 5 attempts)
- Real-time updates without page refresh

### 📱 Modals & Interactions
- Smooth fade-in/fade-out animations
- Approve/Reject decision modals with confirmations
- View JD modal with full text display
- Close on background click

## 🧮 Code Architecture

### State Management (`state` object)
```javascript
{
  currentPage,           // Current active page
  agentStatus,          // IDLE / RUNNING / COMPLETED
  agentRunId,           // Current agent run ID
  teams, employees,     // Fetched data
  signals, etc.         // Other data collections
}
```

### Key Functions

**Navigation**
- `navigateTo(page)` - Switch pages
- `initializeNavigation()` - Setup click handlers

**API Functions**
- `fetchTeams()`, `fetchEmployees()`, `fetchSignals()`, etc.
- All wrapped in try/catch with error handling
- Return early on network errors

**Rendering**
- `renderSignalCards()`, `renderHiringDecisionsTable()`, etc.
- Map data to HTML
- Handle empty/null states

**Modals**
- `openModal(id)`, `closeModal(id)`
- Manage approval/rejection workflows

**Notifications**
- `showSuccessToast()`, `showErrorToast()`, `showWarningToast()`
- Auto-dismiss with CSS animations

**WebSocket**
- `connectWebSocket()` - Establish connection
- `addLiveLogEntry()` - Add log to live stream
- Auto-reconnect logic

## 🎨 Styling System

### CSS Variables (Easy to customize)
```css
--bg-primary: #0f1117          /* Main background */
--bg-secondary: #1a1d27        /* Cards background */
--accent-primary: #6366f1      /* Purple accent */
--status-success: #3fb950       /* Green */
--status-warning: #f0883e       /* Amber */
--status-error: #f85149         /* Red */
```

### Key Classes
- `.container` - Main flex layout
- `.sidebar` - Left navigation
- `.main-content` - Right content area
- `.page` - Individual pages (show/hide)
- `.stats-row` - Metric cards grid
- `.signals-grid` - Team signal cards
- `.data-table` - Styled tables
- `.modal` - Modal overlay
- `.toast` - Toast notifications

## 🛠️ Development

### Adding a New API Endpoint
1. Add function in `app.js` with comment explaining the endpoint
2. Wrap in try/catch with error handling
3. Update `state` object with data
4. Call from appropriate page loader function

### Adding a New Page
1. Add HTML section in `index.html` with unique ID
2. Add sidebar link with `data-page` attribute
3. Create load function in `app.js`
4. Add case in `navigateTo()` switch
5. Create render function to populate content

### Styling Updates
- All colors in `:root` CSS variables
- Responsive breakpoints at 1024px, 768px, 480px
- Use `var(--color-name)` throughout CSS

## 🐛 Debugging

### Console Errors
- All fetch errors logged to console
- WebSocket errors logged with stack traces
- Check browser DevTools Console tab

### Network Issues
- Verify backend is running at `CONFIG.BASE_URL`
- Check CORS headers from backend
- Use browser Network tab to see requests/responses

### WebSocket Issues
- Check WS_URL matches backend
- Look for "Reconnecting..." message
- Verify backend WebSocket endpoint exists

## 📦 Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Mobile)

Requires ES6+ support (arrow functions, async/await, fetch API)

## 📝 Notes

- **No external libraries** - Uses vanilla JS, CSS, HTML only
- **No build step** - Open directly in browser or via HTTP server
- **No backend data mocked** - Every field comes from API
- **Production ready** - Error handling, loading states, responsive design included

## 🤝 Integration with Backend

Backend developers should:
1. Implement all endpoints listed in API Integration section
2. Ensure JSON responses match expected field names
3. Support WebSocket connection at `/ws/agent-live`
4. Include CORS headers for frontend domain
5. Return proper HTTP status codes (200, 400, 500, etc.)

## 📞 Support

For issues or questions, check:
1. Browser console for errors
2. Backend logs for API issues
3. Network tab in DevTools for request/response
4. WebSocket connection status indicator

# HireSignal Frontend - Setup & Launch Guide

## 📋 What Was Built

A complete, responsive, dark-themed dashboard UI for the HireSignal Autonomous HR Hiring Intelligence Agent:

✅ **273 lines** of semantic HTML  
✅ **1,086 lines** of responsive CSS with animations  
✅ **926 lines** of clean, well-commented JavaScript  

**Total: 2,285 lines of production-ready code**

## 🎯 6 Pages Implemented

1. **Dashboard** - Metric cards, signal health, agent status
2. **Live Agent Log** - Real-time WebSocket stream
3. **Hiring Decisions** - Management table with approve/reject
4. **Job Descriptions** - Card grid with modals
5. **Audit Trail** - Timeline with filters and export
6. **Workforce Data** - Teams & employee changes tables

## 🚀 Quick Launch

### Option 1: Python HTTP Server
```bash
cd /Users/All\ file\ hear/runing\ project/ET\ gen\ Hackthone/ui/frontend
python3 -m http.server 8080
```

### Option 2: Node.js HTTP Server
```bash
cd /Users/All\ file\ hear/runing\ project/ET\ gen\ Hackthone/ui/frontend
npx http-server
```

### Option 3: VS Code Live Server
- Install "Live Server" extension
- Right-click `index.html` → "Open with Live Server"

Then open: **http://localhost:8080**

## ⚙️ Configuration

Edit the first lines of `frontend/app.js`:

```javascript
const CONFIG = {
  BASE_URL: "http://localhost:8000",      // FastAPI backend URL
  WS_URL: "ws://localhost:8000/ws/agent-live"  // WebSocket endpoint
};
```

## 🔌 Backend API Requirements

The frontend expects these endpoints:

```
GET    /api/teams                    → Array of teams
GET    /api/employees               → Array of employees  
GET    /api/signals                 → Array of signal objects
GET    /api/agent/status            → {status, last_run, current_step}
GET    /api/hiring/decisions        → Array of decisions
POST   /api/hiring/approve          ← {decision_id}
POST   /api/hiring/reject           ← {decision_id, reason}
GET    /api/jd/{id}                 → {id, role, jd_text, ...}
POST   /api/jd/{id}/approve         ← {}
POST   /api/agent/run               ← {}
GET    /api/audit                   → Array of audit entries
WS     /ws/agent-live               → Streaming logs
```

**All data must come from backend - no mock data in frontend.**

## 🎨 Design System

### Colors
- **Background**: `#0f1117` (dark navy)
- **Cards**: `#1a1d27` (darker navy)
- **Accent**: `#6366f1` (purple)
- **Success**: `#3fb950` (green)
- **Warning**: `#f0883e` (amber)
- **Error**: `#f85149` (red)

### Responsive Breakpoints
- Desktop: 1024px+
- Tablet: 768px - 1023px
- Mobile: < 768px

## 📦 Features Included

✅ Sidebar navigation with active highlighting  
✅ 4 metric stat cards on dashboard  
✅ 5-signal team health cards with color badges  
✅ Real-time WebSocket log streaming  
✅ Hiring decisions table with approve/reject buttons  
✅ Modal confirmations for actions  
✅ Job description cards with full-text modals  
✅ Audit trail timeline with date/agent filters  
✅ Workforce data with teams and employee changes  
✅ Toast notifications (success/error/warning)  
✅ Loading spinners for all sections  
✅ Error states with helpful messages  
✅ Auto-refresh agent status (5s polling)  
✅ WebSocket auto-reconnect  
✅ Smooth animations and transitions  
✅ Fully responsive mobile design  
✅ Keyboard accessible forms and buttons  

## 🔍 Key Features

### Live Updates
- Agent status updates every 5 seconds
- WebSocket connection for live logs
- Auto-reconnect if disconnected
- Real-time badge updates

### User Actions
- Run agent pipeline with one click
- Approve/reject hiring decisions with confirmation modal
- View full JD text in modal
- Approve JDs to post to LinkedIn
- Filter audit trail by date and agent
- Export audit trail (demo)

### Error Handling
- All API calls wrapped in try/catch
- Graceful error messages
- Loading states for all data fetches
- Backend not running → shows helpful error
- Network errors → toasts with details

## 📱 Browser Compatibility

| Browser | Version | Status |
|---------|---------|--------|
| Chrome | 90+ | ✅ Full Support |
| Firefox | 88+ | ✅ Full Support |
| Safari | 14+ | ✅ Full Support |
| Edge | 90+ | ✅ Full Support |
| Mobile Chrome | Latest | ✅ Full Support |
| Mobile Safari | Latest | ✅ Full Support |

## 🎓 Code Quality

### Organization
- Single `CONFIG` object for all settings
- Clear state management in `state` object
- Logical function grouping with comments
- Descriptive variable and function names

### Documentation
- Comment above every API function explaining:
  - Endpoint URL
  - Response format
  - Usage in UI
- Every major function has a comment
- Inline comments for complex logic

### No External Dependencies
- **No npm packages required**
- **No build step needed**
- **Zero framework overhead**
- Pure vanilla JavaScript (ES6+)

## 🚨 Troubleshooting

### "Backend not reachable" error
1. Verify backend is running on http://localhost:8000
2. Check `CONFIG.BASE_URL` matches backend URL
3. Ensure backend has CORS enabled
4. Check browser DevTools Network tab

### WebSocket "Reconnecting..." message
1. Verify WebSocket endpoint: ws://localhost:8000/ws/agent-live
2. Check browser console for connection errors
3. Backend may need WebSocket support
4. Try reloading page

### No data loading
1. Check browser DevTools Network tab
2. Verify backend endpoints return proper JSON
3. Look for API errors in console
4. Ensure field names match response data

### Modal not closing
1. Press Escape key
2. Click outside modal background
3. Check browser console for JS errors

## 📚 File Reference

```
frontend/
├── index.html          # 273 lines - HTML structure
│                       # 6 pages + modals + toast container
│
├── style.css          # 1,086 lines - Complete styling
│                      # Variables, theme, animations, responsive
│
├── app.js             # 926 lines - Application logic
│                      # State, API, WebSocket, rendering
│
├── README.md          # Full documentation
└── SETUP.md           # This file
```

## 💡 Tips

1. **Open DevTools**: F12 or Cmd+Option+I
2. **Check Console**: Look for any red errors
3. **Network Tab**: See API requests/responses
4. **Application Tab**: View localStorage/cookies
5. **Mobile View**: Cmd+Shift+M to test responsive design

## 🎯 Next Steps

1. ✅ Save all 3 files to `/frontend` folder
2. ✅ Launch HTTP server in frontend directory
3. ✅ Open browser to http://localhost:8080
4. ✅ Verify backend is running on port 8000
5. ✅ Test each page for data loading
6. ✅ Check WebSocket connection for live logs

## 📞 Quick Support

**Issue**: Files not loading  
**Solution**: Ensure HTTP server is running (not opening file:// directly)

**Issue**: Data not showing  
**Solution**: Backend may not be running - check if http://localhost:8000 is accessible

**Issue**: WebSocket errors  
**Solution**: Backend needs to support ws://localhost:8000/ws/agent-live

**Issue**: CORS errors  
**Solution**: Backend needs: `Access-Control-Allow-Origin: *` (or frontend domain)

---

**Built with ❤️ for HireSignal**  
Pure HTML • Pure CSS • Pure JavaScript  
No frameworks • No dependencies • 100% vanilla web standards

# AI Money Mentor — Run Guide

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env
# add your ANTHROPIC_API_KEY to .env
```

## Run (two terminals)

### Terminal 1 — MCP Tools Server
```bash
cd backend
python -m tools.mcp_server
# runs on http://localhost:8001
```

### Terminal 2 — FastAPI
```bash
cd backend
uvicorn api.main:app --reload --port 8000
# runs on http://localhost:8000
```

## Test it
```bash
# Send a message
curl -X POST http://localhost:8000/chat/user123 \
  -H "Content-Type: application/json" \
  -d '{"message": "I earn 18 lakh per year, want to retire at 45"}' \
  --no-buffer

# Check profile (see what agent extracted)
curl http://localhost:8000/profile/user123

# Reset profile
curl -X DELETE http://localhost:8000/profile/user123
```

## File structure
```
backend/
├── graph/
│   ├── state.py                  ← MoneyState + UserProfile
│   ├── supervisor.py             ← LangGraph wiring
│   ├── edges.py                  ← routing logic
│   ├── nodes/
│   │   ├── profile_extractor.py  ← silently builds user profile
│   │   ├── intent_classifier.py  ← picks the right agent
│   │   └── clarifier.py          ← asks for missing info
│   └── agents/
│       ├── fire_agent.py         ← ReAct: retirement planning
│       ├── tax_agent.py          ← ReAct: tax saving
│       ├── health_agent.py       ← ReAct: financial health score
│       ├── mf_agent.py           ← ReAct: MF portfolio analysis
│       └── life_event_agent.py   ← ReAct: bonus/marriage/baby
├── tools/
│   └── mcp_server.py             ← all financial calculations
├── db/
│   └── store.py                  ← load/save user profiles
└── api/
    └── main.py                   ← FastAPI + SSE endpoints
```

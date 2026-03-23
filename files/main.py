"""
FastAPI App
────────────
Two endpoints:
  POST /chat/{user_id}   → main chat, returns SSE stream
  GET  /profile/{user_id} → get current user profile (for UI)
  DELETE /profile/{user_id} → reset profile (for testing)
"""

import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .graph.supervisor import graph
from .db.store import load_profile, save_profile, load_message_history, save_message

app = FastAPI(title="AI Money Mentor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


@app.post("/chat/{user_id}")
async def chat(user_id: str, body: ChatRequest):
    """
    Main chat endpoint.
    Loads user profile + history → runs graph → streams response → saves back.
    """

    async def event_stream():
        # 1. Load everything we know about this user
        profile  = await load_profile(user_id)
        history  = await load_message_history(user_id)

        # 2. Save their new message to history
        await save_message(user_id, "user", body.message)

        # 3. Build initial state for this graph run
        state = {
            "messages":     [*history, {"role": "user", "content": body.message}],
            "user_id":      user_id,
            "profile":      profile,
            "intent":       "",
            "missing_field": None,
            "final_output": {},
        }

        # 4. Run graph — stream each node's output as it completes
        final_profile = profile
        final_text    = ""

        async for chunk in graph.astream(state, stream_mode="updates"):
            # chunk = {"node_name": {state_updates}}
            for node_name, node_output in chunk.items():

                # Stream node progress to frontend (so user sees "thinking...")
                yield f"data: {json.dumps({'type': 'node', 'node': node_name})}\n\n"

                # If this node updated the profile — track it
                if "profile" in node_output:
                    final_profile = node_output["profile"]

                # If this is the final response — stream the text
                if "final_output" in node_output:
                    text = node_output["final_output"].get("text", "")
                    if text:
                        final_text = text
                        yield f"data: {json.dumps({'type': 'response', 'text': text})}\n\n"

                # If messages were updated — get the last assistant message
                if "messages" in node_output:
                    msgs = node_output["messages"]
                    for msg in reversed(msgs):
                        if isinstance(msg, dict) and msg.get("role") == "assistant":
                            final_text = msg["content"]
                            yield f"data: {json.dumps({'type': 'response', 'text': final_text})}\n\n"
                            break

        # 5. Save updated profile back to DB
        await save_profile(user_id, final_profile)

        # 6. Save assistant response to history
        if final_text:
            await save_message(user_id, "assistant", final_text)

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",     # nginx: disable buffering
        }
    )


@app.get("/profile/{user_id}")
async def get_profile(user_id: str):
    """Return current known profile for a user."""
    profile = await load_profile(user_id)
    return {"user_id": user_id, "profile": profile}


@app.delete("/profile/{user_id}")
async def reset_profile(user_id: str):
    """Reset profile — useful for testing."""
    await save_profile(user_id, {
        "age": None, "income": None, "expenses": None,
        "risk": None, "tax_bracket": None, "goals": [],
        "investments": {}, "insurance": {}, "employer": None, "city": None,
    })
    return {"status": "reset", "user_id": user_id}


@app.get("/health")
async def health():
    return {"status": "ok"}

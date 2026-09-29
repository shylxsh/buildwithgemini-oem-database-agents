"""FastAPI local bridge for the power-fetch agent and UI.
Connects the browser frontend directly to the local agent and the mock DB service.
"""

import json
import os
import uuid
import httpx
from typing import Dict, Any, List
from dotenv import load_dotenv
from pathlib import Path

# Load power-fetch .env for Vertex AI authentication
PROJECT_ROOT = Path(__file__).parent
load_dotenv(PROJECT_ROOT / ".env")

import sys
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from app.agent import root_agent

app = FastAPI(title="Power-Fetch Web UI")

session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    session_service=session_service,
    app_name="power_fetch_app"
)

DB_BASE_URL = os.environ.get("DB_BASE_URL", "http://127.0.0.1:8001")
_sessions: Dict[str, str] = {}


@app.get("/api/projects")
async def get_projects():
    """Proxy to fetch available OEM projects for the clickable buttons."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{DB_BASE_URL}/projects", timeout=5.0)
            return resp.json()
    except Exception:
        return []


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "").strip()
    user_id = body.get("user_id") or "web-user"

    if not message:
        return JSONResponse({"parts": [{"kind": "text", "text": "Please provide a query."}]})

    if user_id not in _sessions:
        session = await session_service.create_session(
            app_name="power_fetch_app",
            user_id=user_id,
        )
        _sessions[user_id] = session.id
    
    session_id = _sessions[user_id]

    text_replies = []
    endpoint_cited = None
    raw_json_doc = None
    is_fuzzy = False

    try:
        user_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=message)]
        )

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_content
        ):
            if hasattr(event, "content") and event.content:
                parts = getattr(event.content, "parts", [])
                for p in parts:
                    fn_call = getattr(p, "function_call", None)
                    if fn_call and fn_call.name == "fuzzy_match_query":
                        is_fuzzy = True

                    fn_resp = getattr(p, "function_response", None)
                    if fn_resp and fn_resp.response:
                        resp_data = fn_resp.response
                        if isinstance(resp_data, dict):
                            if "endpoint" in resp_data:
                                endpoint_cited = resp_data.get("endpoint")
                            if "raw_json" in resp_data:
                                raw_json_doc = resp_data.get("raw_json")

                    text = getattr(p, "text", None)
                    if text:
                        text_replies.append(text)

        full_reply = "".join(text_replies).strip()
        if not full_reply:
            full_reply = "Completed query."

        response_payload = {
            "parts": [
                {"kind": "text", "text": full_reply}
            ],
            "details_card": {
                "has_details": bool(endpoint_cited or raw_json_doc or is_fuzzy),
                "endpoint": endpoint_cited,
                "raw_json": raw_json_doc,
                "is_fuzzy": is_fuzzy
            }
        }
        return JSONResponse(response_payload)

    except Exception as e:
        return JSONResponse({
            "parts": [{"kind": "text", "text": f"Error running query: {str(e)}"}],
            "details_card": {"has_details": False}
        })


static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

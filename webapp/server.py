"""OmniVox FastAPI Server: browser mic -> STT -> multi-agent orchestrator -> MCP tools -> TTS -> browser audio.

This serves the OmniVox web interface and REST/voice endpoints.
It enables OmniVox to be operated via speech from any browser or deployed as a cloud service.

State is kept in an in-memory session store keyed by a client session ID.

SECURITY NOTE: OmniVox connects to real Gmail (read/send) and Notion workspaces
via Model Context Protocol (MCP). If AUTH_PASSWORD is set, all routes (including the web UI)
require HTTP Basic Auth.
"""
import base64
import os
import secrets
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from langchain.messages import HumanMessage

from omnivox import config
from omnivox.agent import build_agent
from omnivox.logging_utils import log_stage
from omnivox.speech_to_text import transcribe_audio
from omnivox.text_to_speech import synthesize_speech

config.validate()

_agent = None
_sessions: dict[str, list] = {}
_MAX_HISTORY_MESSAGES = 20

_AUTH_USERNAME = os.getenv("AUTH_USERNAME", "demo")
_AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")
_basic_auth = HTTPBasic(auto_error=False)


def _require_auth(credentials: HTTPBasicCredentials | None = Depends(_basic_auth)) -> None:
    """No-op if AUTH_PASSWORD isn't set; otherwise requires matching HTTP Basic Auth.

    auto_error=False on HTTPBasic means a missing Authorization header comes
    back as None instead of an immediate 401 - that's what lets local dev
    (no AUTH_PASSWORD set) skip auth entirely rather than always prompting.
    """
    if not _AUTH_PASSWORD:
        return
    valid = credentials is not None and (
        secrets.compare_digest(credentials.username, _AUTH_USERNAME)
        and secrets.compare_digest(credentials.password, _AUTH_PASSWORD)
    )
    if not valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Basic"},
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent
    _agent = await build_agent()
    yield


app = FastAPI(title="OmniVox — Voice AI Executive Assistant", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", dependencies=[Depends(_require_auth)])
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


async def _run_agent_turn(session_id: str, transcript: str) -> str:
    log_stage("User -> Orchestrator", input=transcript)
    messages = _sessions.setdefault(session_id, [])
    messages.append(HumanMessage(content=transcript))
    result = await _agent.ainvoke({"messages": messages})
    messages = result["messages"][-_MAX_HISTORY_MESSAGES:]
    _sessions[session_id] = messages
    reply = messages[-1].content
    log_stage("Orchestrator -> User", output=reply)
    return reply


@app.post("/api/chat", dependencies=[Depends(_require_auth)])
async def chat(message: str = Form(...), session_id: str = Form(...)) -> JSONResponse:
    """Text turn: returns text reply and synthesized speech audio."""
    reply = await _run_agent_turn(session_id, message)
    audio_b64 = None
    try:
        speech_path = synthesize_speech(reply)
        if speech_path and os.path.exists(speech_path):
            with open(speech_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("ascii")
            try:
                os.remove(speech_path)
            except Exception:
                pass
    except Exception as exc:
        print(f"[chat] TTS failed: {exc}")

    return JSONResponse({"transcript": message, "reply": reply, "audio_base64": audio_b64})


@app.post("/api/voice", dependencies=[Depends(_require_auth)])
async def voice(audio: UploadFile = File(...), session_id: str = Form(...)) -> JSONResponse:
    """Voice turn: browser sends a recorded clip, we return transcribed text + spoken reply."""
    suffix = Path(audio.filename or "command.webm").suffix or ".webm"
    tmp_path = str(Path(tempfile.gettempdir()) / f"{uuid.uuid4()}{suffix}")
    audio_bytes = await audio.read()
    with open(tmp_path, "wb") as f:
        f.write(audio_bytes)

    print(
        f"[voice] received {len(audio_bytes)} bytes, "
        f"filename={audio.filename!r}, content_type={audio.content_type!r}, saved to {tmp_path}"
    )

    try:
        transcript = transcribe_audio(tmp_path)
    except Exception as exc:
        print(f"[voice] transcription failed or not configured: {exc}")
        transcript = ""
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    print(f"[voice] transcript: {transcript!r}")

    if not transcript:
        return JSONResponse(
            {
                "transcript": "",
                "reply": "I couldn't hear or transcribe any voice input. Please check your mic and try again.",
                "audio_base64": None,
            }
        )

    reply = await _run_agent_turn(session_id, transcript)

    audio_b64 = None
    try:
        speech_path = synthesize_speech(reply)
        if speech_path and os.path.exists(speech_path):
            with open(speech_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("ascii")
            try:
                os.remove(speech_path)
            except Exception:
                pass
    except Exception as exc:
        print(f"[voice] TTS failed: {exc}")

    return JSONResponse({"transcript": transcript, "reply": reply, "audio_base64": audio_b64})


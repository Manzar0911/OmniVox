"""OmniVox FastAPI Server: browser mic -> STT -> multi-agent orchestrator -> MCP/User tools -> TTS -> browser audio.

Features:
- Mandatory authentication for all executive voice & chat capabilities
- Live active credential verification for Gmail & Notion before saving
- Dynamic multi-agent routing scoped to each authenticated user's linked accounts
- High-speed STT and zero-cost Neural TTS synthesis
"""
import base64
import json
import os
import secrets
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Security, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from langchain.messages import HumanMessage
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from omnivox import config
from omnivox.agent import build_agent
from omnivox.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from omnivox.db import ChatMessage, ConversationSession, User, UserIntegration, get_db, init_db
from omnivox.logging_utils import log_stage
from omnivox.speech_to_text import transcribe_audio
from omnivox.text_to_speech import synthesize_speech
from omnivox.tools.gmail_dynamic import validate_gmail_credentials
from omnivox.tools.notion_dynamic import validate_notion_credentials
from omnivox.user_agent import build_user_agent

config.validate()

_global_agent = None
_sessions: dict[str, list] = {}
_MAX_HISTORY_MESSAGES = 20

_AUTH_USERNAME = os.getenv("AUTH_USERNAME", "demo")
_AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")
_basic_auth = HTTPBasic(auto_error=False)


def _require_auth(credentials: HTTPBasicCredentials | None = Depends(_basic_auth)) -> None:
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
    global _global_agent
    await init_db()
    _global_agent = await build_agent()
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


# ==========================================
# Authentication Schemas & Endpoints
# ==========================================

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class GmailConnectRequest(BaseModel):
    email: str
    app_password: str


class NotionConnectRequest(BaseModel):
    token: str
    workspace_name: Optional[str] = None


@app.post("/api/auth/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    clean_email = req.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    existing = await db.execute(select(User).where(User.email == clean_email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    new_user = User(
        email=clean_email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name or clean_email.split("@")[0],
    )
    db.add(new_user)
    await db.flush()

    token = create_access_token(new_user.id, new_user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": new_user.to_dict(),
    }


@app.post("/api/auth/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email & password and receive a JWT Bearer token."""
    clean_email = req.email.strip().lower()
    result = await db.execute(select(User).where(User.email == clean_email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled.")

    token = create_access_token(user.id, user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict(),
    }


@app.get("/api/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    """Get the currently logged-in user profile."""
    return {"user": user.to_dict()}


# ==========================================
# User Integrations Management (Active Verification)
# ==========================================

@app.get("/api/integrations")
async def get_user_integrations_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all integrations connected by the current user."""
    stmt = select(UserIntegration).where(UserIntegration.user_id == user.id)
    result = await db.execute(stmt)
    integrations = result.scalars().all()

    status_map = {
        "gmail": {"connected": False, "account": None},
        "notion": {"connected": False, "account": None},
    }
    for item in integrations:
        if item.is_active:
            status_map[item.provider.lower()] = {
                "connected": True,
                "account": item.account_identifier or "Connected",
                "updated_at": item.updated_at.isoformat() if item.updated_at else item.created_at.isoformat(),
            }
    return status_map


@app.get("/api/integrations/gmail/auth-url")
async def get_google_auth_url(user: User = Depends(get_current_user)):
    """Generate official Google OAuth 2.0 authorization URL for Gmail access."""
    if not config.GOOGLE_CLIENT_ID or not config.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail="Google OAuth is not configured on the server. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.",
        )
    redirect_uri = config.GOOGLE_REDIRECT_URI
    scopes = "https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile"
    state = create_access_token(user.id, user.email)
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={config.GOOGLE_CLIENT_ID}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope={scopes}&"
        f"access_type=offline&"
        f"prompt=consent&"
        f"state={state}"
    )
    return {"auth_url": auth_url}


@app.get("/api/integrations/gmail/callback")
async def google_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Google OAuth 2.0 callback: exchanges authorization code for tokens and saves to DB."""
    if error or not code:
        return FileResponse(STATIC_DIR / "index.html")

    from omnivox.auth import decode_access_token
    payload = decode_access_token(state) if state else None
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=400, detail="Invalid OAuth state parameter.")

    user_id = int(payload["sub"])
    redirect_uri = config.GOOGLE_REDIRECT_URI

    # Exchange code for access & refresh tokens
    import requests
    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Google token exchange failed: {token_resp.text}")

    token_data = token_resp.json()
    access_token = token_data.get("access_token")

    # Fetch userinfo to get Gmail address
    userinfo_resp = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    email_addr = "Google Account"
    if userinfo_resp.status_code == 200:
        email_addr = userinfo_resp.json().get("email", email_addr)

    creds_blob = json.dumps({
        "email": email_addr,
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token"),
        "client_id": config.GOOGLE_CLIENT_ID,
        "client_secret": config.GOOGLE_CLIENT_SECRET,
    })

    stmt = select(UserIntegration).where(
        UserIntegration.user_id == user_id,
        UserIntegration.provider == "gmail",
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.account_identifier = email_addr
        existing.credentials_json = creds_blob
        existing.is_active = True
    else:
        new_integ = UserIntegration(
            user_id=user_id,
            provider="gmail",
            account_identifier=email_addr,
            credentials_json=creds_blob,
            is_active=True,
        )
        db.add(new_integ)

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/?connected=gmail")


@app.post("/api/integrations/gmail")
async def connect_gmail(
    req: GmailConnectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actively verify and connect user's personal Gmail account via App Password or Token."""
    clean_email = req.email.strip().lower()
    clean_pwd = req.app_password.replace(" ", "").strip()

    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="Please enter a valid Gmail address.")
    if not clean_pwd:
        raise HTTPException(status_code=400, detail="Please provide your Google App Password or Access Token.")

    # 1. Actively test IMAP credentials against Google
    valid, message = validate_gmail_credentials(clean_email, clean_pwd)
    if not valid:
        raise HTTPException(status_code=400, detail=message)

    creds_blob = json.dumps({
        "email": clean_email,
        "app_password": clean_pwd,
    })

    stmt = select(UserIntegration).where(
        UserIntegration.user_id == user.id,
        UserIntegration.provider == "gmail",
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.account_identifier = clean_email
        existing.credentials_json = creds_blob
        existing.is_active = True
    else:
        new_integ = UserIntegration(
            user_id=user.id,
            provider="gmail",
            account_identifier=clean_email,
            credentials_json=creds_blob,
            is_active=True,
        )
        db.add(new_integ)

    return {"status": "success", "message": f"Gmail ({clean_email}) verified & connected successfully."}



@app.post("/api/integrations/notion")
async def connect_notion(
    req: NotionConnectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Actively verify and connect user's Notion workspace via Internal Integration Token."""
    token = req.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Notion Integration Token is required.")

    # 1. Actively test token against Notion API
    valid, message, bot_name = validate_notion_credentials(token)
    if not valid:
        raise HTTPException(status_code=400, detail=message)

    workspace_name = req.workspace_name.strip() if req.workspace_name else (bot_name or "Notion Workspace")

    stmt = select(UserIntegration).where(
        UserIntegration.user_id == user.id,
        UserIntegration.provider == "notion"
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.account_identifier = workspace_name
        existing.credentials_json = token
        existing.is_active = True
    else:
        new_integ = UserIntegration(
            user_id=user.id,
            provider="notion",
            account_identifier=workspace_name,
            credentials_json=token,
            is_active=True,
        )
        db.add(new_integ)

    return {"status": "success", "message": f"Notion workspace '{workspace_name}' verified & connected successfully."}


@app.delete("/api/integrations/{provider}")
async def disconnect_integration(
    provider: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Disconnect and remove an integration (gmail, notion)."""
    clean_provider = provider.strip().lower()
    await db.execute(
        delete(UserIntegration).where(
            UserIntegration.user_id == user.id,
            UserIntegration.provider == clean_provider
        )
    )
    return {"status": "success", "message": f"{clean_provider.capitalize()} disconnected."}


from omnivox.cache import query_cache
from omnivox.guardrails import GuardrailStatus, guardrails_manager


async def _run_agent_turn(
    session_id: str,
    transcript: str,
    user: User,
    db: AsyncSession
) -> str:
    log_stage("User -> Orchestrator", input=transcript)

    # 1. Input Guardrails (Prompt injection, jailbreaks, PII redaction, harmful content)
    guard_res = guardrails_manager.validate_input(transcript)
    if not guard_res.is_safe:
        refusal_msg = f"I cannot process this request. {guard_res.reason or 'Security policy violation detected.'}"
        log_stage("Guardrails -> User (BLOCKED)", reason=guard_res.reason)
        return refusal_msg

    sanitized_transcript = guard_res.sanitized_text

    user_session_key = f"user_{user.id}_{session_id}"
    messages = _sessions.setdefault(user_session_key, [])

    # 2. Conversational Intent Cache Check (for standalone repeat questions without pending history)
    if len(messages) == 0:
        cached_reply = query_cache.get(sanitized_transcript, user_id=user.id)
        if cached_reply:
            log_stage("QueryCache -> User (HIT)", query=sanitized_transcript)
            messages.append(HumanMessage(content=sanitized_transcript))
            return cached_reply

    messages.append(HumanMessage(content=sanitized_transcript))

    # Build agent scoped dynamically with user's verified Gmail & Notion credentials
    agent_executor = await build_user_agent(db=db, user_id=user.id)

    callbacks = []
    if config.LANGSMITH_API_KEY and config.LANGSMITH_TRACING:
        callbacks.append(LangChainTracer(project_name=config.LANGSMITH_PROJECT))

    run_config = RunnableConfig(
        run_name=f"OmniVox Turn ({user.email})",
        tags=["omnivox", "voice_assistant", "production", "guardrails_enabled"],
        metadata={
            "user_id": user.id,
            "user_email": user.email,
            "session_id": session_id,
            "conversation_id": user_session_key,
            "guardrail_applied": guard_res.applied_rules,
        },
        callbacks=callbacks if callbacks else None,
    )

    result = await agent_executor.ainvoke({"messages": messages}, config=run_config)
    messages = result["messages"][-_MAX_HISTORY_MESSAGES:]
    _sessions[user_session_key] = messages
    raw_reply = messages[-1].content

    # 3. Output Guardrails (Secret leakage prevention, voice formatting, hallucination check)
    out_guard_res = guardrails_manager.validate_output(raw_reply)
    safe_reply = out_guard_res.sanitized_text

    # Store in query cache if safe
    if out_guard_res.is_safe and len(messages) <= 2:
        query_cache.set(sanitized_transcript, safe_reply, user_id=user.id)

    log_stage("Orchestrator -> User", output=safe_reply)
    return safe_reply


@app.post("/api/chat")
async def chat(
    message: str = Form(...),
    session_id: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Authenticated text turn: returns text reply and synthesized speech audio."""
    reply = await _run_agent_turn(session_id, message, user=user, db=db)
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


@app.post("/api/voice")
async def voice(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Authenticated voice turn: returns transcribed text + spoken reply."""
    suffix = Path(audio.filename or "command.webm").suffix or ".webm"
    tmp_path = str(Path(tempfile.gettempdir()) / f"{uuid.uuid4()}{suffix}")
    audio_bytes = await audio.read()
    with open(tmp_path, "wb") as f:
        f.write(audio_bytes)

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

    if not transcript:
        return JSONResponse(
            {
                "transcript": "",
                "reply": "I couldn't hear or transcribe any voice input. Please check your mic and try again.",
                "audio_base64": None,
            }
        )

    reply = await _run_agent_turn(session_id, transcript, user=user, db=db)

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

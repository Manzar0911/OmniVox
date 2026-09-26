# OmniVox 🎙️
### Autonomous Voice-Controlled Multi-Agent Executive Assistant
> **Enterprise-Ready Multi-User Voice AI with Google OAuth 2.0, Notion Integration, Aiven PostgreSQL, and LangSmith Observability**

[![Python Version](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-1.4+-1C3C3C.svg?logo=langchain&logoColor=white)](https://www.langchain.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Aiven%20Cloud-336791.svg?logo=postgresql&logoColor=white)](https://aiven.io)
[![LangSmith](https://img.shields.io/badge/Observability-LangSmith-orange.svg?logo=langchain&logoColor=white)](https://smith.langchain.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 🌟 Overview

**OmniVox** is an autonomous, voice-controlled AI executive assistant designed to handle real-world personal and corporate workflows. Built with a modular multi-agent architecture, OmniVox allows authenticated users to seamlessly execute actions across their **Gmail** inboxes, **Notion** workspaces, and the **Web** using natural spoken language or interactive text chat.

Whether deployed 100% locally with open-source models (**Ollama / Qwen 2.5 7B**) or connected to enterprise cloud backends (**AWS Bedrock / OpenAI / Aiven PostgreSQL**), OmniVox provides low-latency voice interactions, strict privacy controls, multi-user isolation, and deep execution observability with **LangSmith**.

---

## 📸 Application Showcase & Screenshots

### 1. Landing & Authentication Gate
Secure multi-user authentication supporting instant account registration and JWT login, gated with `bcrypt` password hashing and PostgreSQL storage.

![OmniVox Landing & Authentication](docs/screenshots/01_landing_auth.png)

---

### 2. Autonomous Voice AI & Interactive Chat Console
Real-time conversational executive console with integrated status badges for connected services, quick-action suggestion chips, audio waveform recording, and neural speech synthesis.

![OmniVox Voice & Chat Console](docs/screenshots/02_voice_chat_console.png)

---

### 3. Google OAuth 2.0 Gmail Integration (Zero Password Sharing)
Official Google OAuth 2.0 consent flow allowing users to securely link their personal Gmail inbox with single-click authentication.

![OmniVox Google OAuth Gmail Integration](docs/screenshots/03_gmail_oauth_modal.png)

---

### 4. Notion Workspace Integration (Live API Validation)
Connect Notion workspaces securely via internal integration secrets, with real-time `/v1/users/me` token verification before saving.

![OmniVox Notion Integration Modal](docs/screenshots/04_notion_integration_modal.png)

---

### 5. LangSmith Observability & Multi-Agent Tracing
Hierarchical execution traces mapping user turns, orchestrator routing decisions, specialist sub-agents, tool executions, and latency/token usage.

![OmniVox LangSmith Tracing](docs/screenshots/05_langsmith_tracing.png)

---

## 🏛️ System Architecture

OmniVox utilizes a **Hierarchical Multi-Agent Architecture** where a central **Orchestrator** coordinates specialized sub-agents dynamically scoped to each user's authenticated credentials.

```
                                  +-----------------------+
                                  | Browser UI / Voice Mic|
                                  +-----------+-----------+
                                              | (WebM Audio / Form Data)
                                              v
                                  +-----------------------+
                                  | Speech-to-Text Engine |
                                  | (Faster-Whisper/STT)  |
                                  +-----------+-----------+
                                              | (Transcript)
                                              v
                              +-------------------------------+
                              |    OmniVox Orchestrator       |
                              |  (Qwen 2.5 / Bedrock / OpenAI)|
                              +---------------+---------------+
                                              |
                   +--------------------------+--------------------------+
                   |                          |                          |
                   v                          v                          v
        +--------------------+     +--------------------+     +--------------------+
        |   notion_expert    |     |    email_expert    |     |     researcher     |
        | (Notion Specialist)|     | (Gmail Specialist) |     | (Research Agent)   |
        +---------+----------+     +---------+----------+     +---------+----------+
                  |                          |                          |
                  | (Notion REST API v1)     | (Google OAuth REST API)  | (Qwen Reasoning)
                  v                          v                          v
        +--------------------+     +--------------------+     +--------------------+
        |  Notion Workspace  |     |   User Gmail API   |     | Knowledge Engine   |
        +--------------------+     +--------------------+     +--------------------+
```

### 🧠 Specialist Agents

1. **`Orchestrator`**:
   - Evaluates user intent from voice transcripts or text.
   - Deconstructs complex multi-step requests into sub-agent workflows (e.g., *"Research AI Agent safety guidelines and create a Notion summary page for my team"*).
   - Enforces voice-optimized output formatting (clean conversational tone, structured sections, zero markdown asterisks).

2. **`email_expert` (Gmail Specialist)**:
   - Queries user inboxes via Google OAuth 2.0 and Gmail REST API.
   - Searches emails by keyword, sender, or subject.
   - Drafts replies and sends emails with strict confirmation safeguards.

3. **`notion_expert` (Notion Specialist)**:
   - Interacts with Notion API v1 using the user's verified integration token.
   - Searches databases and pages across the user's workspace.
   - Reads page blocks and creates structured documents on demand.

4. **`researcher` (Knowledge Specialist)**:
   - Synthesizes in-depth technical or executive summaries on any topic.
   - Formats findings cleanly into *Topic*, *Key Findings*, and *Conclusion* blocks ready for speech synthesis or Notion page storage.

---

## 🔒 Security, Database & Multi-Tenancy

OmniVox is architected for secure multi-user environments:

- **Database Backend**: Powered by **PostgreSQL (Aiven Cloud)** using SQLAlchemy 2.0 with asynchronous `asyncpg` connection pooling and automatic table creation. Falls back gracefully to SQLite for local development.
- **Authentication & Authorization**:
  - Secure passwords hashed with `bcrypt`.
  - Stateless JSON Web Tokens (`JWT` with `HS256`).
  - Mandatory auth gating across all voice and chat execution endpoints.
- **Google OAuth 2.0 (Zero Password Sharing)**:
  - Official OAuth 2.0 authorization code flow with automatic refresh token management (`offline` access type).
  - No user passwords or app passwords required.
- **Active Credential Verification**:
  - Validates Notion tokens against `https://api.notion.com/v1/users/me` before persisting.
  - Verifies Google OAuth access tokens against `https://www.googleapis.com/oauth2/v2/userinfo`.

---

## 📊 LangSmith Observability & Tracing

OmniVox is integrated with **LangSmith** for full-stack LLM and agent observability:

- **Hierarchical Traces**: Sub-agents and dynamic tool calls are connected under parent run trees via `RunnableConfig` propagation.
- **Rich Metadata & Tags**: Every run logs `user_id`, `user_email`, `session_id`, and `conversation_id` alongside tags (`voice_assistant`, `production`, `omnivox`).
- **Real-Time Latency & Cost Tracking**: Monitor token consumption, prompt inputs, tool schemas, and completion times in your LangSmith dashboard.

---

## 📁 Project Structure

```
langchain-voice-agent/
├── omnivox/
│   ├── __init__.py
│   ├── agent.py                 # Standalone orchestrator builder
│   ├── user_agent.py            # User-scoped dynamic orchestrator & sub-agents
│   ├── auth.py                  # JWT authentication, password hashing, user dependencies
│   ├── config.py                # Environment configuration (LLM, DB, OAuth, LangSmith)
│   ├── logging_utils.py         # Formatted CLI pipeline stage logging
│   ├── mcp_client.py            # Model Context Protocol (MCP) client
│   ├── speech_to_text.py        # Voice recognition & audio transcription
│   ├── text_to_speech.py        # Neural text-to-speech voice synthesizer
│   ├── agents/
│   │   ├── email_expert.py      # Gmail specialist sub-agent definition
│   │   ├── notion_expert.py     # Notion specialist sub-agent definition
│   │   └── researcher.py        # Research specialist sub-agent definition
│   ├── db/
│   │   ├── __init__.py          # Database models export
│   │   ├── models.py            # SQLAlchemy 2.0 declarative models (User, Integration, Chat)
│   │   └── session.py           # Async engine & session factory (PostgreSQL / SQLite)
│   └── tools/
│       ├── gmail_dynamic.py     # Per-user Google OAuth 2.0 & Gmail REST API tools
│       ├── notion_dynamic.py    # Per-user Notion API v1 tools & active token validator
│       └── research_tool.py     # Deep research & structured summarization tool
├── webapp/
│   ├── server.py                # FastAPI application server (Auth, OAuth, Chat, Voice)
│   └── static/
│       └── index.html           # Production glassmorphic responsive web interface
├── docs/
│   └── screenshots/             # UI and architecture screenshots
├── .env.example                 # Environment variables configuration template
├── requirements.txt             # Python dependencies
├── FEATURES_AND_ROADMAP.md      # Comprehensive feature catalog & development roadmap
└── README.md                    # Project documentation
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python 3.11+**, **3.12+**, or **3.13+**
- **Node.js 18+** & `npm` (if using MCP servers)
- **Ollama** ([ollama.com](https://ollama.com)) *(Optional for 100% free local inference)*

### 2. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/Manzar0911/OmniVox.git
cd OmniVox

# Create and activate virtual environment
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Linux / macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and configure your credentials:
```bash
cp .env.example .env
```

Edit `.env`:
```env
# ==========================================
# 1. LLM Provider Options
# ==========================================
# Option A: AWS Bedrock (Recommended for Production)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=ap-south-1
BEDROCK_MODEL_ID=global.amazon.nova-2-lite-v1:0

# Option B: OpenAI
# OPENAI_API_KEY=sk-proj-...
# CHAT_MODEL=gpt-4o-mini

# Option C: 100% Free Local Ollama (Zero Cost)
# LLM_PROVIDER=ollama
# OLLAMA_MODEL=qwen2.5:7b
# OLLAMA_BASE_URL=http://localhost:11434

# ==========================================
# 2. Database Connection (PostgreSQL / Aiven)
# ==========================================
DATABASE_URL=postgresql+asyncpg://avnadmin:password@pg-service.aivencloud.com:27142/defaultdb?ssl=require
SECRET_KEY=your-secure-64-character-jwt-secret-key-here

# ==========================================
# 3. Google OAuth 2.0 (for Gmail Integration)
# ==========================================
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/integrations/gmail/callback

# ==========================================
# 4. LangSmith Observability
# ==========================================
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=Omnivox
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

### 5. Launch the OmniVox Server
```bash
uvicorn webapp.server:app --reload --port 8000
```

Open **`http://localhost:8000`** in your browser:
1. Register an account or log in.
2. Click **Integrations** in the top navigation to connect your **Gmail (via Google OAuth)** and **Notion** workspaces.
3. Hold the microphone button or type a command to interact with your executive assistant!

---

## 📡 API Reference

### Authentication Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Register a new user account with email & password |
| `POST` | `/api/auth/login` | Authenticate user and receive a JWT Bearer access token |
| `GET` | `/api/auth/me` | Fetch profile details of the authenticated user |

### Integrations Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/integrations` | List status of all connected integrations (Gmail, Notion) |
| `GET` | `/api/integrations/gmail/auth-url` | Generate Google OAuth 2.0 consent URL for Gmail access |
| `GET` | `/api/integrations/gmail/callback` | OAuth 2.0 exchange handler (exchanges code for tokens) |
| `POST` | `/api/integrations/notion` | Actively verify and connect a Notion integration token |
| `DELETE` | `/api/integrations/{provider}` | Disconnect and purge an integration |

### Voice & Chat Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat` | Send a text prompt; returns text response and base64 synthesized audio |
| `POST` | `/api/voice` | Upload WebM spoken audio; transcribes, routes through agents, and returns synthesized audio |

---

## 🗺️ Roadmap & Features

For complete details on implemented features, planned integrations (Slack, Google Calendar, GitHub, Linear), and enterprise deployment architectures, please review [**FEATURES_AND_ROADMAP.md**](FEATURES_AND_ROADMAP.md).

---

## 🛡️ License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

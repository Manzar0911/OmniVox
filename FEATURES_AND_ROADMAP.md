# OmniVox — Feature Catalog & Architecture Roadmap 🚀

> **Comprehensive guide to potential features, architectural expansions, and development milestones for OmniVox: The Autonomous Voice-Controlled Multi-Agent Executive Assistant.**

---

## 📑 Table of Contents
1. [Current Architecture Baseline](#1-current-architecture-baseline)
2. [Feature Breakdown by Category](#2-feature-breakdown-by-category)
   - [2.1 Agent Ecosystem & MCP Tool Integrations](#21-agent-ecosystem--mcp-tool-integrations)
   - [2.2 Voice Pipeline & Real-Time Audio Engine](#22-voice-pipeline--real-time-audio-engine)
   - [2.3 Memory, Personalization & Knowledge Graphs](#23-memory-personalization--knowledge-graphs)
   - [2.4 Proactive & Autonomous Workflows](#24-proactive--autonomous-workflows)
   - [2.5 Safety, Governance & Human-in-the-Loop (HITL)](#25-safety-governance--human-in-the-loop-hitl)
   - [2.6 UI / UX & Frontend Experience](#26-ui--ux--frontend-experience)
   - [2.7 Developer Experience & Observability](#27-developer-experience--observability)
3. [Phased Implementation Roadmap](#3-phased-implementation-roadmap)
4. [Technical Feasibility & Technology Stack Matrix](#4-technical-feasibility--technology-stack-matrix)

---

## 1. Current Architecture Baseline

OmniVox currently operates with the following core modules:
- **Orchestration**: LangChain `create_agent` with hierarchical delegation to sub-agents.
- **LLM Brain**: Local Qwen 2.5 7B (via Ollama) with fallback support for AWS Bedrock and OpenAI.
- **MCP Integrations**:
  - `email_expert`: Gmail MCP (`@gongrzhe/server-gmail-autoauth-mcp`)
  - `notion_expert`: Notion MCP (`mcp-remote` / `mcp.notion.com`)
  - `researcher`: Local Qwen 2.5 research & synthesis tool
- **Voice In**: `SpeechRecognition` (Google Speech API wrapper + ffmpeg conversion).
- **Voice Out**: `edge-tts` (Microsoft Neural TTS) with `pyttsx3` offline fallback.
- **Serving & Web**: FastAPI backend + Vanilla JS/CSS dark-mode web console.

---

## 2. Feature Breakdown by Category

### 2.1 Agent Ecosystem & MCP Tool Integrations

Expand the specialist network by adding dedicated MCP servers and tools to handle daily executive operations:

| Feature | Description | Target Tools / Protocols | Complexity |
| :--- | :--- | :--- | :--- |
| **Google Calendar / Outlook Specialist (`calendar_expert`)** | Schedule, query, modify meetings, resolve time-slot conflicts, and handle RSVP invites via voice commands. | Google Calendar MCP / Microsoft Graph MCP | Medium |
| **Slack & Discord Specialist (`chat_expert`)** | Check unread channel summaries, search team discussions, and send formatted messages or voice transcripts. | Slack MCP Server / Discord API | Low-Medium |
| **GitHub / GitLab Specialist (`devops_expert`)** | Review open pull requests, check CI/CD pipeline statuses, triage issues, and trigger releases. | GitHub MCP Server | Medium |
| **Local File & Document Search (`files_expert`)** | Query and extract insights from local PDFs, Word documents, CSVs, and notes using local embeddings. | Local Filesystem MCP / ChromaDB | Medium |
| **Real-Time Live Web Search** | Upgrade the `researcher` agent from static internal LLM generation to live DuckDuckGo/Tavily/Playwright real-time web scraping and fact-checking. | `duckduckgo-search` / `tavily-python` | Low |
| **WhatsApp / Telegram Specialist (`messenger_expert`)** | Send instant text/voice alerts or reminders to personal/team messaging channels. | WhatsApp Business API / Telegram Bot API | Medium |
| **Finance & Market Data Tool (`finance_expert`)** | Query stock prices, crypto markets, currency exchange rates, and financial reports. | Yahoo Finance / AlphaVantage MCP | Low |

---

### 2.2 Voice Pipeline & Real-Time Audio Engine

Upgrade the voice layer for lower latency, higher accuracy, and 100% offline autonomy:

* **100% Offline Local Speech-to-Text (`faster-whisper` / `whisper.cpp`)**
  * *Goal*: Eliminate reliance on external speech recognition endpoints.
  * *Implementation*: Run quantized Whisper models (`base.en`, `small.en`, or `distil-whisper`) locally via CUDA/CPU with millisecond response times.
* **Voice Activity Detection (VAD with Silero VAD)**
  * *Goal*: Natural voice capture without having to manually click "Stop Recording".
  * *Implementation*: Detect speech pauses and automatically finalize the audio buffer once speech stops.
* **Wake Word Engine ("Hey OmniVox" / "Jarvis")**
  * *Goal*: True hands-free activation.
  * *Implementation*: Implement **OpenWakeWord** or **Porcupine** to run a lightweight listener on browser/desktop.
* **Full-Duplex Streaming & Interruption (Barge-In)**
  * *Goal*: Sub-second latency and natural conversational flow.
  * *Implementation*: Stream live audio over WebSockets with chunked TTS streaming. Allow user speech to immediately interrupt and cancel outgoing audio playback.
* **Offline Neural TTS Models (Kokoro-82M / Piper)**
  * *Goal*: Studio-quality neural voice output completely offline.
  * *Implementation*: Integrate Kokoro-82M / Piper ONNX for instant local voice generation.

---

### 2.3 Memory, Personalization & Knowledge Graphs

Give OmniVox long-term context, recall, and contextual awareness:

* **Persistent Long-Term Memory (RAG + Vector DB)**
  * Store past conversations, user preferences, frequent contacts, project context, and decisions across restarts using SQLite and ChromaDB/FAISS.
* **Dynamic Persona & Tone Switching**
  * Configurable assistant personas:
    * *Executive Brief*: Ultra-short, bulleted, high-signal responses.
    * *Technical Advisor*: Deep architectural insights and code snippets.
    * *Casual Conversationalist*: Relaxed, conversational tone.
* **Custom Knowledge Graph (Entity Linking)**
  * Track relationships between projects, clients, dates, and Notion database items so the agent understands references like *"the project we discussed yesterday with Alex"*.

---

### 2.4 Proactive & Autonomous Workflows

Shift OmniVox from purely reactive voice commands to proactive assistance:

* **Executive Morning Briefing Routine**
  * Spoken morning digest combining:
    1. Unread urgent/VIP emails
    2. Today's meeting schedule & conflict warnings
    3. Pending Notion tasks and deadlines
    4. Local weather & industry news headlines
* **VIP Email & Message Monitor (Background Cron)**
  * Background worker (via APScheduler) that periodically checks the inbox for high-priority senders or keywords and triggers a voice/push notification.
* **Meeting Preparation Assistant**
  * Automatically pulls Notion notes, past email threads, and attendee LinkedIn/bios 15 minutes before any scheduled calendar meeting.
* **Voice-Triggered Multi-Step Chains**
  * Example: *"Research quantum computing breakthroughs, draft an email summary to Sarah, and save the full report in Notion under Tech Trends."*

---

### 2.5 Safety, Governance & Human-in-the-Loop (HITL)

Protect against unintended real-world side effects:

* **Interactive Action Confirmation (HITL Modal)**
  * For destructive or external actions (e.g., sending an email, creating/deleting Notion pages, canceling meetings), prompt the user with a preview card:
    * `[Confirm & Execute]`
    * `[Edit Draft]`
    * `[Cancel]`
* **Multi-User Role-Based Access Control (RBAC)**
  * JWT-based authentication supporting individual user sessions, private credentials, and permission scopes.
* **Sanitization & Prompt Injection Guardrails**
  * Input/output validation layer to prevent prompt injection attacks from malicious emails or web research content.

---

### 2.6 UI / UX & Frontend Experience

Upgrade the web interface in `webapp/static/index.html`:

* **Live Audio Visualizer & Waveform Animation**
  * Canvas-based reactive audio visualizer displaying real-time speech amplitude during recording and playback.
* **Agent Reasoning & Execution Stepper**
  * Visual timeline showing the active pipeline step in real time:
    $$\text{User Voice} \longrightarrow \text{STT} \longrightarrow \text{Orchestrator} \longrightarrow \text{Email Expert} \longrightarrow \text{TTS} \longrightarrow \text{Audio Out}$$
* **Rich Interactive Cards**
  * **Email Cards**: Sender avatar, subject, snippet, with one-click "Reply" or "Archive".
  * **Notion Cards**: Interactive preview with direct link to the created page.
  * **Research Cards**: Expandable bullet points with source badges.
* **Progressive Web App (PWA) & Mobile Optimization**
  * Installable web app for iOS and Android with background mic access and push notification support.
* **Theme Customizer & Audio Controls**
  * Dark/light glassmorphic themes, TTS speed slider (0.8x - 1.5x), voice selection dropdown, and microphone input device selector.

---

### 2.7 Developer Experience & Observability

* **LangSmith / OpenTelemetry Integration**: Comprehensive tracing of multi-agent latency, tool execution time, and LLM token usage.
* **CLI Client (`omnivox-cli`)**: Terminal-based voice/text interactive CLI for headless servers.
* **Webhook Event Ingestion**: Allow external services (GitHub webhooks, Zapier, Make) to trigger spoken alerts in OmniVox.

---

## 3. Phased Implementation Roadmap

```
+-------------------------------------------------------------------------+
| Phase 1: Immediate Enhancements (Quick Wins)                            |
| - Live Web Search (Tavily / DuckDuckGo in researcher)                   |
| - Local Offline STT (faster-whisper integration)                        |
| - Human-in-the-Loop Action Confirmation UI                              |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| Phase 2: Core Capability Expansion                                      |
| - Google Calendar / Outlook MCP Specialist                              |
| - Persistent Long-Term Memory (SQLite + Vector Store)                   |
| - Executive Morning Briefing multi-agent workflow                       |
| - Silero VAD (Hands-free silence detection)                             |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| Phase 3: Advanced Voice & Autonomy                                      |
| - Duplex WebSocket Streaming Audio & Interruption (Barge-in)            |
| - Wake Word Engine ("Hey OmniVox")                                      |
| - Proactive Background Inbox/Meeting Monitors (Cron)                    |
| - Slack / Discord / GitHub MCP Specialists                              |
| - Mobile PWA & WebGL Audio Visualizer                                   |
+-------------------------------------------------------------------------+
```

---

## 4. Technical Feasibility & Technology Stack Matrix

| Category | Recommended Technology / Library | License / Cost |
| :--- | :--- | :--- |
| **LLM Inference** | Ollama (Qwen 2.5 7B / 3B, Llama 3.1) | MIT / Free & Open Source |
| **STT Engine** | `faster-whisper` / `whisper.cpp` | MIT / Free & Open Source |
| **Voice Activity Detection** | `silero-vad` / `webrtcvad` | MIT / Free & Open Source |
| **TTS Synthesis** | `edge-tts` / `kokoro-onnx` / `piper-tts` | Free & Open Source |
| **Vector Database & Memory** | `chromadb` / `faiss-cpu` / `sqlite3` | Apache 2.0 / Free |
| **Tool Protocol** | `modelcontextprotocol` / `langchain-mcp-adapters` | MIT / Free |
| **Backend Framework** | `fastapi` + `uvicorn` + `websockets` | MIT / BSD / Free |
| **Frontend** | Vanilla JS / Web Audio API / Canvas / PWA | Free |

---

*Document created for OmniVox repository. To implement any feature, reference this document alongside the codebase.*

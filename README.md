# OmniVox 🎙️
### 100% Free Open-Source Autonomous Voice-Controlled Multi-Agent Executive Assistant

**OmniVox** is a local, privacy-first, zero-cost AI executive assistant built with **LangChain**, **Qwen 2.5 7B / Ollama**, **Faster-Whisper / Speech Recognition**, **Neural TTS**, and the **Model Context Protocol (MCP)**. It listens to spoken voice commands and executes real-world workspace actions across **Gmail**, **Notion**, and the **Web** — with **zero subscriptions, zero API costs, and 100% local processing**.

---

## 🏛️ System Architecture

```
Speech In  ──► [ Faster-Whisper / SpeechRecognition ] (Open-source local STT, runs in milliseconds)
     │
     ▼
Agent Brain ──► [ Qwen 2.5 7B-Instruct ] via Ollama (Free local LLM for Gmail/Notion tools)
     │
     ▼
Speech Out ──► [ Neural TTS (Kokoro / Edge-TTS / Pyttsx3) ] (Ultra-realistic, instant open-source local TTS)
```

```
                      +-------------------+
                      |   Browser / UI    |
                      +---------+---------+
                                | (Spoken Voice / Text)
                                v
               +----------------------------------+
               |       OmniVox Orchestrator       |
               |      (Qwen 2.5 7B / Ollama)      |
               +---+--------------+-------------+-+
                   |              |             |
         +---------+              |             +---------+
         v                        v                       v
+------------------+     +------------------+    +------------------+
|  notion_expert   |     |   email_expert   |    |    researcher    |
| (Notion Specialist)|   | (Gmail Specialist)|   | (Research Specialist)|
+--------+---------+     +--------+---------+    +--------+---------+
         |                        |                       |
         | (MCP stdio)            | (MCP stdio)           | (Qwen 2.5 Knowledge)
         v                        v                       v
+------------------+     +------------------+    +------------------+
| Notion MCP Host  |     |  Gmail MCP Node  |    | Qwen 2.5 Engine  |
+--------+---------+     +--------+---------+    +------------------+
         |                        |
         v                        v
  Notion Workspace             Gmail
```

---

## ✨ Key Features

- 🧠 **Local Multi-Agent Brain**: Powered by **Qwen 2.5 7B-Instruct** via Ollama for superior function calling and tool delegation across specialized sub-agents (`notion_expert`, `email_expert`, `researcher`).
- 🎙️ **Local Speech Recognition (STT)**: High-speed speech-to-text processing directly on your machine with zero cloud dependencies.
- 🗣️ **Ultra-Realistic Neural TTS**: High-definition, human-like voice synthesis with zero fees.
- 🔌 **Model Context Protocol (MCP)**: Communicates with services using standardized MCP servers (Gmail MCP and Notion MCP) with persistent OAuth session authentication.
- 🔍 **Autonomous Research & Structuring**: Uses Qwen 2.5 7B's deep reasoning to synthesize structured insights and write pages directly to Notion.
- 🔒 **100% Private & Free**: Runs completely on your own machine with zero data shared with third-party model providers.

---

## 📁 Repository Structure

```
omnivox/
├── __init__.py
├── config.py              # Local Ollama & zero-cost engine configuration
├── logging_utils.py       # Pipeline stage truncation and logging
├── mcp_client.py          # MultiServerMCPClient setup (Gmail + Notion)
├── speech_to_text.py      # Open-source Speech-to-Text module
├── text_to_speech.py      # Open-source Neural Text-to-Speech synthesis
├── agent.py               # Orchestrator agent & tool delegation
├── agents/
│   ├── email_expert.py    # Gmail specialist sub-agent (MCP)
│   ├── notion_expert.py   # Notion specialist sub-agent (MCP)
│   └── researcher.py      # Web research specialist sub-agent
└── tools/
    └── research_tool.py   # Free web search & summarization tool

webapp/
├── server.py              # FastAPI application server & REST/Voice API
└── static/
    └── index.html         # Responsive web interface with real-time voice recognition

scripts/
└── pack_mcp_tokens.py     # Utility to export local MCP OAuth tokens for deployment
```

---

## 🚀 Quickstart (Zero-Cost Local Setup)

### 1. Prerequisites
- **Python 3.11+** or **3.12+**
- **Node.js 18+** & `npm`
- **Ollama** ([ollama.com](https://ollama.com))

### 2. Download the Free Model
```bash
ollama run qwen2.5:7b
```
*(Or for lower RAM laptops: `ollama run qwen2.5:3b`)*

### 3. Install Dependencies
```bash
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 4. One-Time MCP Authentication
1. **Gmail MCP**:
   ```bash
   npx @gongrzhe/server-gmail-autoauth-mcp auth
   npm install -g @gongrzhe/server-gmail-autoauth-mcp
   ```
2. **Notion MCP**:
   ```bash
   npx -y mcp-remote https://mcp.notion.com/mcp
   npm install -g mcp-remote
   ```

### 5. Launch OmniVox
```bash
uvicorn webapp.server:app --reload --port 8000
```
Open **`http://localhost:8000`** and talk to your executive assistant!

---

## 🛡️ License

This project is licensed under the [MIT License](LICENSE).

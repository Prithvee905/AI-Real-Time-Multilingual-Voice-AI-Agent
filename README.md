# 🏥 Smart Voice Agent

## Clinical Appointment Booking System

A production-grade **Real-Time Voice AI Agent** that communicates with patients to manage clinical appointments through natural voice conversations. Supports **English**, **Hindi**, and **Tamil** with contextual memory and sub-450ms latency target.

---

## 🎯 Features

### Core Capabilities
- 🎤 **Voice Conversations** — Speak naturally and get voice responses
- 📅 **Appointment Booking** — Book, reschedule, and cancel appointments
- 🌐 **Multilingual Support** — English, Hindi (हिंदी), Tamil (தமிழ்)
- 🧠 **Contextual Memory** — Remembers conversation context and patient history
- 📢 **Outbound Campaigns** — Proactive reminders and follow-ups
- ⚡ **Low Latency** — Targets < 450ms end-to-end response time
- 📊 **Latency Monitoring** — Real-time measurement and logging

### Appointment Management
- ✅ Book new appointments with doctor selection
- 🔄 Reschedule existing appointments
- ❌ Cancel appointments
- 🔍 Check doctor availability
- ⚠️ Conflict detection and alternative suggestions
- 👨‍⚕️ Doctor search by specialty or name

---

## 🏗️ Architecture Explanation

```
User Speech
     ↓ (WebSocket)
┌──────────────┐
│  STT Service │  ← OpenAI Whisper API (~120ms)
│  (Whisper)   │
└──────┬───────┘
       ↓
┌──────────────┐
│  Language    │  ← langdetect (~10ms)
│  Detection   │
└──────┬───────┘
       ↓
┌──────────────┐     ┌─────────────────┐
│  AI Agent    │────→│ Tool            │
│  (GPT-4o-    │     │ Orchestration   │
│   mini)      │←────│ (8 tools)       │
└──────┬───────┘     └────────┬────────┘
       │                      ↓
       │             ┌─────────────────┐
       │             │ Appointment DB  │
       │             │ (SQLite)        │
       │             └─────────────────┘
       ↓
┌──────────────┐     ┌─────────────────┐
│  TTS Service │     │ Memory System   │
│  (Edge TTS)  │     │ Redis + JSON    │
└──────┬───────┘     └─────────────────┘
       ↓ (WebSocket)
Audio Response → User
```

The system employs a real-time, low-latency conversational pipeline leveraging Websockets for bidirectional, continuous audio integration instead of polling.
Audio requests are converted into text through **OpenAI Whisper STT**, passed into **Language Detection**, and interpreted by a central **AI Reasoning Agent (GPT-4o-mini)**. The agent orchestrates a suite of **8 distinct tools** linked to an underlying SQLite appointments database, accessing local memory layers (Session and Persistent) synchronously. Finally, **Edge TTS** rapidly converts responses back to speech and returns the audio packets back to the continuous websocket stream.

---

## 🚀 Setup Instructions

### Prerequisites
- Python 3.11+
- OpenAI API key
- Redis (optional — falls back to in-memory)
- Docker & Docker Compose (for containerized deployment)

### Option 1: Local Development

1. **Clone and navigate:**
   ```bash
   cd voice-ai-agent
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

5. **Run the server:**
   ```bash
   python main.py
   ```
   Or:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

6. **Open the UI:**
   Navigate to `http://localhost:8000`

### Option 2: Docker Deployment

1. **Set your API key:**
   ```bash
   export OPENAI_API_KEY=sk-your-key-here
   ```

2. **Build and run:**
   ```bash
   docker-compose up --build
   ```

3. **Access:**
   - UI: `http://localhost:8000`
   - API: `http://localhost:8000/api/doctors`

---

## ⚡ Latency Breakdown

The system targets **< 450ms** end-to-end latency from speech end to first audio response.

| Stage | Target | Method |
|-------|--------|--------|
| Speech-to-Text (Whisper) | ~120ms | OpenAI Whisper API |
| Language Detection | ~10ms | Lightweight langdetect |
| AI Reasoning (LLM) | ~200ms | GPT-4o-mini with function calling |
| Tool Execution | ~20ms | Local SQLite queries |
| Text-to-Speech (Edge TTS) | ~100ms | Edge TTS neural synthesis |
| **Total** | **< 450ms** | **Pipeline optimized** |

Every request generates a real-time visual latency report embedded in the frontend UI, as well as console logs for deep tracking.

---

## 🧠 Memory Design

### Session Memory (Short-term)
- **Storage:** Redis (with local fallback if unavailable)
- **TTL:** 30 minutes
- **Stores:** Conversation history, pending intents, user language states, and collected slot entities.
- **Purpose:** Maintains multi-turn conversation coherence and handles partial intent collection (e.g. asking for Time when only Date is provided).

### Persistent Memory (Long-term)
- **Storage:** JSON flat-file store mapped by patient metadata.
- **Stores:** Patient identifiers, name mappings, lifetime language preferences, interaction counts, preferred hospital hubs, and previous appointment behaviors.
- **Purpose:** Personalizes cross-session interactions to make the system behave proactively based on user preferences.

---

## ⚖️ Trade-offs

| Decision | Rationale |
|----------|-----------|
| GPT-4o-mini over GPT-4 | Radically faster and deeply optimized for tool-calling/latency requirements over deep semantic nuance. |
| Edge TTS over OpenAI TTS | Higher rate limits, completely free-tier native, faster time-to-first-byte (TTFB), multi-regional neural voices natively supported. |
| SQLite over PostgreSQL | Zero setup friction for immediate assignment testing. Simple flat-file deployment logic. |
| JSON persistent memory | Portable, human-readable structure, removes database complexity during standard portfolio/assignment evaluation. |
| WebSocket over traditional polling | Single persistent duplex connection directly minimizes latency overhead associated with HTTP handshakes when pushing multi-chunked conversation structures. |

---

## ⚠️ Known Limitations

1. **Whisper Latency Sensitivity** — STT API latency heavily correlates with audio sample quality and client network upload latency, not just OpenAI inference speeds.
2. **Missing Token Streaming** — To keep the tool orchestration logic completely hermetic and predictable within strict bounds, LLM token streaming was eschewed in favor of bulk JSON response generation.
3. **Database Write Concurrency limitations** — Because SQLite utilizes write locks at file scope rather than row scope, extreme simulated traffic loads across WebSockets >50 QPS could yield timeouts during synchronous appointment conflict verification checks.
4. **Agent Hallucinations** — Though extremely rare given the strict function calling guardrails, GPT-4o-mini may dynamically assume day mappings to `next week` dates if user utterances are ambiguous on bounding constraints.
5. **No Built-in Authentication Layer** — Auth is bypassed directly to allow API execution testing unhindered by JWT or OAuth handshakes.

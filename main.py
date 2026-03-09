"""
Main FastAPI Application.
Real-Time Multilingual Voice AI Agent for Clinical Appointment Booking.
"""
import uuid
import time
import json
import base64
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from loguru import logger
from contextlib import asynccontextmanager

from config import HOST, PORT, DEBUG, OPENAI_API_KEY
from backend.database import init_database
from backend.latency import LatencyTracker
from backend.routes.api_routes import router as api_router
from services.speech_to_text.stt_service import transcribe_audio
from services.text_to_speech.tts_service import synthesize_speech
from services.language_detection.lang_detect import detect_language
from agent.reasoning.agent_engine import process_message

# ─── Configure Logging ────────────────────────────────────────
logger.add(
    "logs/voice_agent_{time}.log",
    rotation="10 MB",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


# ─── App Lifecycle ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("🚀 Starting Voice AI Agent...")
    await init_database()
    logger.info("✅ Database initialized")
    logger.info(f"🔑 OpenAI API Key: {'configured' if OPENAI_API_KEY else 'NOT SET'}")
    yield
    logger.info("🛑 Shutting down Voice AI Agent...")


# ─── Create App ───────────────────────────────────────────────
app = FastAPI(
    title="Voice AI Agent - Clinical Appointment System",
    description="Real-Time Multilingual Voice AI Agent for Clinical Appointment Booking",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

# Include API routes
app.include_router(api_router)


# ─── Health Check ─────────────────────────────────────────────
@app.get("/")
async def root(request: Request):
    """Serve the main frontend application."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "running",
        "version": "1.0.0",
        "timestamp": time.time(),
        "openai_configured": bool(OPENAI_API_KEY)
    }


# ─── WebSocket Voice Pipeline ────────────────────────────────
@app.websocket("/ws/voice/{session_id}")
async def voice_pipeline(websocket: WebSocket, session_id: str):
    """
    Real-time voice conversation WebSocket endpoint.

    Protocol:
    - Client sends: {"type": "audio", "data": "<base64 audio>", "format": "webm", "patient_id": "P001", "patient_name": "John"}
    - Client sends: {"type": "text", "text": "book appointment", "patient_id": "P001", "patient_name": "John"}
    - Server responds: {"type": "response", "text": "...", "audio": "<base64 mp3>", "latency": {...}}
    """
    await websocket.accept()
    logger.info(f"🔌 WebSocket connected: session={session_id}")

    try:
        while True:
            # Receive message
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)

            # Initialize latency tracker
            request_id = str(uuid.uuid4())[:8]
            tracker = LatencyTracker(request_id)
            tracker.start_pipeline()

            msg_type = data.get("type", "text")
            patient_id = data.get("patient_id", "PATIENT_DEFAULT")
            patient_name = data.get("patient_name", "Patient")
            language = data.get("language", "")

            transcribed_text = ""
            detected_language = language or "en"

            if msg_type == "audio":
                # ─── Stage 1: Speech-to-Text ──────────────
                tracker.start_stage("speech_to_text")
                audio_bytes = base64.b64decode(data["data"])
                audio_format = data.get("format", "webm")

                stt_result = await transcribe_audio(audio_bytes, language=language or None, format=audio_format)
                tracker.end_stage("speech_to_text")

                if not stt_result["success"]:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Could not understand audio. Please try again.",
                        "request_id": request_id
                    })
                    continue

                transcribed_text = stt_result["text"]
                detected_language = stt_result.get("language", "en")

            elif msg_type == "text":
                # Direct text input
                transcribed_text = data.get("text", "")
                if not transcribed_text:
                    continue

                # ─── Language Detection ───────────────────
                tracker.start_stage("language_detection")
                lang_result = detect_language(transcribed_text)
                tracker.end_stage("language_detection")
                detected_language = language or lang_result["language"]

            # Send transcription back to client
            await websocket.send_json({
                "type": "transcription",
                "text": transcribed_text,
                "language": detected_language,
                "request_id": request_id
            })

            # ─── Stage 2: AI Agent Processing ────────────
            tracker.start_stage("agent_reasoning")
            agent_result = await process_message(
                text=transcribed_text,
                session_id=session_id,
                patient_id=patient_id,
                patient_name=patient_name,
                language=detected_language
            )
            tracker.end_stage("agent_reasoning")

            response_text = agent_result["response"]

            # ─── Stage 3: Text-to-Speech ─────────────────
            tracker.start_stage("text_to_speech")
            tts_result = await synthesize_speech(response_text, detected_language)
            tracker.end_stage("text_to_speech")

            # End pipeline
            tracker.end_pipeline()
            tracker.log_report()

            # Build response
            response = {
                "type": "response",
                "text": response_text,
                "language": detected_language,
                "request_id": request_id,
                "latency": tracker.get_report(),
                "tool_calls": agent_result.get("tool_calls_made", 0)
            }

            # Include audio if TTS succeeded
            if tts_result["success"] and tts_result["audio"]:
                response["audio"] = base64.b64encode(tts_result["audio"]).decode("utf-8")
                response["audio_format"] = tts_result["format"]

            await websocket.send_json(response)

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected: session={session_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket error: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": "An error occurred. Please reconnect.",
                "error": str(e)
            })
        except Exception:
            pass


# ─── Text-only endpoint for testing ──────────────────────────
@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """Simple text-based chat endpoint for testing without audio."""
    data = await request.json()
    text = data.get("text", "")
    patient_id = data.get("patient_id", "PATIENT_DEFAULT")
    patient_name = data.get("patient_name", "Patient")
    session_id = data.get("session_id", str(uuid.uuid4()))
    language = data.get("language", "")

    if not text:
        return {"error": "No text provided"}

    # Detect language if not specified
    if not language:
        lang_result = detect_language(text)
        language = lang_result["language"]

    # Process through agent
    tracker = LatencyTracker(str(uuid.uuid4())[:8])
    tracker.start_pipeline()
    tracker.start_stage("agent_reasoning")

    result = await process_message(
        text=text,
        session_id=session_id,
        patient_id=patient_id,
        patient_name=patient_name,
        language=language
    )

    tracker.end_stage("agent_reasoning")
    tracker.end_pipeline()
    tracker.log_report()

    return {
        "response": result["response"],
        "language": language,
        "session_id": session_id,
        "latency": tracker.get_report()
    }


# ─── Run Server ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info"
    )

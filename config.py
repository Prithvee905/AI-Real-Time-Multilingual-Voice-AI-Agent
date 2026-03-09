"""
Configuration module for the Voice AI Agent.
Loads environment variables and provides app-wide settings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ─── Base Paths ───────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ─── Server ───────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# ─── OpenAI ───────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ─── Redis ────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_AVAILABLE = False  # Will be set at runtime

# ─── Database ─────────────────────────────────────────────────
DATABASE_PATH = str(DATA_DIR / "appointments.db")

# ─── Latency ──────────────────────────────────────────────────
LOG_LATENCY = os.getenv("LOG_LATENCY", "true").lower() == "true"
TARGET_LATENCY_MS = 450

# ─── TTS ──────────────────────────────────────────────────────
TTS_ENGINE = os.getenv("TTS_ENGINE", "edge-tts")

# ─── Voice Mapping (Edge TTS) ────────────────────────────────
VOICE_MAP = {
    "en": "en-US-JennyNeural",
    "hi": "hi-IN-SwaraNeural",
    "ta": "ta-IN-PallaviNeural",
}

# ─── Supported Languages ─────────────────────────────────────
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
}

# ─── Agent Settings ──────────────────────────────────────────
MAX_CONVERSATION_TURNS = 20
SESSION_TTL_SECONDS = 1800  # 30 minutes
PERSISTENT_MEMORY_FILE = str(DATA_DIR / "patient_memory.json")

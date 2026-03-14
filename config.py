"""
config.py
---------
Centralized configuration for the AI RC Car Python controller.
All settings in one place — MQTT, AI, assistant identity, commands.
"""

import os

# ============================================================
# MQTT CONFIGURATION
# (must match the ESP32 firmware exactly)
# ============================================================
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "python_ai_car_001"

# Topics — Python publishes to these (ESP32 subscribes):
TOPIC_COMMAND = "aicar/command"    # forward, backward, left, right, stop, etc.
TOPIC_MODE    = "aicar/mode"       # manual, auto, park

# Topics — ESP32 publishes to these (Python subscribes):
TOPIC_SENSORS  = "aicar/sensors"   # JSON: {front, back, left, right, mode, speed}
TOPIC_STATUS   = "aicar/status"    # JSON: {status, time}

# ============================================================
# AI CONFIGURATION (OpenRouter)
# ============================================================
OPENROUTER_API_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    "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",
)
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-3.5-turbo"  # or "google/gemini-2.0-flash-001"

# ============================================================
# ASSISTANT IDENTITY
# ============================================================
ASSISTANT_DISPLAY_NAME = "HB"
ASSISTANT_WAKE_WORDS = ("hb", "hament", "core")

# Car personality settings
CAR_NAME = "HB"
CAR_PERSONALITY_TRAITS = {
    "style": "friendly, witty, and enthusiastic",
    "enthusiasm": 0.8,
    "humor": 0.6,
    "verbosity": 0.5,
}
MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "car_memory.json")

SYSTEM_PROMPT = (
    f"You are {ASSISTANT_DISPLAY_NAME}, an AI assistant with a {CAR_PERSONALITY_TRAITS['style']} personality, "
    "controlling an RC car. You speak with enthusiasm and character. "
    "The car has commands: forward, backward, left, right, stop, "
    "speed_full, speed_slow. "
    "Modes: manual, auto, park. "
    "When the user asks to move the car, respond with ACTION: <command> "
    "on its own line, then explain what you're doing. "
    "When asked about sensors, use the live data provided. "
    "If the user tells you their name, acknowledge it warmly. "
    "Keep responses short, friendly, and full of personality."
)

# ============================================================
# CAR COMMAND KEYWORDS
# These are routed directly to MQTT instead of AI.
# ============================================================
CAR_COMMANDS = frozenset({
    "forward", "backward", "back", "left", "right", "stop",
    "auto", "auto park", "auto-park", "park",
    "forward left", "forward right",
    "backward left", "backward right",
    "speed full", "speed slow",
})

# ============================================================
# KEYBOARD SHORTCUTS (single-key direct commands, bypass AI)
# ============================================================
KEYBOARD_SHORTCUTS = {
    "w": "forward",
    "s": "backward",
    "a": "left",
    "d": "right",
    "x": "stop",
    "f": "speed_full",
    "g": "speed_slow",
    "1": "mode_manual",
    "2": "mode_auto",
    "3": "mode_park",
}

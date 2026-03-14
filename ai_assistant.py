"""
ai_assistant.py
---------------
Unified AI assistant module.
Sends user questions to OpenRouter (GPT) and extracts car commands from responses.
Includes TTS output and conversation history management.
"""

from typing import Any, Optional

from config import (  # type: ignore[import]
    OPENROUTER_API_KEY, OPENROUTER_API_URL, OPENROUTER_MODEL,
    SYSTEM_PROMPT,
)

try:
    import requests  # type: ignore[import]
except ImportError:
    requests = None

try:
    import pyttsx3  # type: ignore[import]
except ImportError:
    pyttsx3 = None


# ============================================================
# TEXT-TO-SPEECH
# ============================================================
import threading as _tts_threading

_tts_engine: Optional[Any] = None
_tts_lock = _tts_threading.Lock()


def _get_tts() -> Any:
    """Lazy-init pyttsx3 TTS engine with personality voice settings."""
    global _tts_engine
    if pyttsx3 is None:
        raise ImportError("pyttsx3 is required for TTS. Install: pip install pyttsx3")
    if _tts_engine is None:
        _tts_engine = pyttsx3.init()
        try:
            _tts_engine.setProperty('rate', 175)     # slightly faster for energetic feel
            _tts_engine.setProperty('volume', 0.9)
        except Exception:
            pass
    return _tts_engine


def speak(text: str, block: bool = True) -> None:
    """Speak text aloud. Thread-safe via lock. Silently fails if TTS unavailable."""
    global _tts_engine
    if not text or not text.strip():
        return
    # Use lock to prevent concurrent access — pyttsx3 is NOT thread-safe
    if not _tts_lock.acquire(timeout=5):
        print("[TTS] Skipped (engine busy)")
        return
    try:
        engine = _get_tts()
        engine.say(text.strip())
        engine.runAndWait()
    except RuntimeError as e:
        if "run loop" in str(e).lower():
            # Engine is stuck — destroy and recreate it next time
            print("[TTS] Resetting stuck engine...")
            try:
                _tts_engine.stop()  # type: ignore[union-attr]
            except Exception:
                pass
            _tts_engine = None
        else:
            print(f"[TTS] Error: {e}")
    except Exception as e:
        print(f"[TTS] Error: {e}")
    finally:
        _tts_lock.release()


def tts_available() -> bool:
    """Check if TTS is available."""
    return pyttsx3 is not None


def speak_with_personality(event: str, block: bool = False) -> None:
    """Speak a personality-driven reaction for a car event."""
    try:
        from personality import get_personality  # type: ignore[import]
        reaction = get_personality().react(event)
        if reaction:
            speak(reaction, block=block)
    except Exception:
        pass


# ============================================================
# CONVERSATION HISTORY
# ============================================================
_conversation: list[dict[str, str]] = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

MAX_HISTORY = 20  # keep last N messages + system prompt


def _trim_history() -> None:
    """Keep conversation history from growing too large."""
    global _conversation
    if len(_conversation) > MAX_HISTORY + 1:
        _conversation = [_conversation[0]] + _conversation[-(MAX_HISTORY):]


# ============================================================
# ASK AI
# ============================================================
def ask_ai(
    question: str,
    sensor_data: Optional[dict] = None,
    car_online: bool = False,
) -> Optional[str]:
    """
    Send question to OpenRouter and return the assistant's reply.
    Optionally includes live sensor context.
    Returns None on error.
    """
    if requests is None:
        print("[AI] 'requests' library required. Install: pip install requests")
        return None

    # Inject personality context
    try:
        from personality import get_personality  # type: ignore[import]
        p = get_personality()
        personality_ctx = p.get_personality_context()
        p.log_interaction(question)
        # Check if user shared their name
        lower_q = question.lower()
        for phrase in ("my name is ", "i'm ", "i am ", "call me "):
            if phrase in lower_q:
                idx = lower_q.index(phrase) + len(phrase)
                name_guess = question[idx:].strip().split()[0].strip(".,!?")  # type: ignore[index]
                if name_guess:
                    p.remember("user_name", name_guess.title())
    except Exception:
        personality_ctx = ""

    # Build user message with optional sensor context
    user_content = ""
    if personality_ctx:
        user_content += f"[PERSONALITY] {personality_ctx}\n\n"
    if sensor_data:
        user_content += (
            f"[LIVE CAR DATA]\n"
            f"Front: {sensor_data.get('front', '?')}cm | "
            f"Back: {sensor_data.get('back', '?')}cm\n"
            f"Left: {sensor_data.get('left', '?')}cm | "
            f"Right: {sensor_data.get('right', '?')}cm\n"
            f"Mode: {sensor_data.get('mode', '?')} | "
            f"Speed: {sensor_data.get('speed', '?')}/255\n"
            f"Car Online: {car_online}\n"
            f"[END LIVE DATA]\n\n"
        )
    user_content += question

    _conversation.append({"role": "user", "content": user_content})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/iot-car-controller",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": _conversation,
        "max_tokens": 300,
        "temperature": 0.7,
    }

    try:
        r = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()
        choices = data.get("choices") or []
        if not choices:
            return None
        reply = choices[0].get("message", {}).get("content", "").strip()
        if not reply:
            return None

        _conversation.append({"role": "assistant", "content": reply})
        _trim_history()
        return reply

    except Exception as e:
        print(f"[AI] Error: {e}")
        return None


def extract_action(reply: str) -> Optional[str]:
    """
    Extract an ACTION: <command> from the AI response.
    Returns the command string (lowercased) or None if no action found.
    """
    for line in reply.split("\n"):
        stripped = line.strip()
        if stripped.upper().startswith("ACTION:"):
            return stripped.split(":", 1)[1].strip().lower()
    return None


def get_clean_reply(reply: str) -> str:
    """Remove ACTION: lines from the reply for display."""
    lines = [
        line for line in reply.split("\n")
        if not line.strip().upper().startswith("ACTION:")
    ]
    return "\n".join(lines).strip()

"""
voice_control.py
----------------
Voice recognition, wake-word detection, and typed command loops.
Routes car commands to MQTT and general questions to the AI assistant.
"""

import time
from typing import Optional

from config import ASSISTANT_WAKE_WORDS, CAR_COMMANDS, KEYBOARD_SHORTCUTS  # type: ignore[import]
from mqtt_client import CarMqttClient  # type: ignore[import]
from ai_assistant import ask_ai, speak, tts_available, extract_action, get_clean_reply  # type: ignore[import]
from dashboard import log_voice, log_ai, log_warn, log_success, log_error  # type: ignore[import]

try:
    import speech_recognition as sr  # type: ignore[import]
except ImportError:
    sr = None


# ============================================================
# TEXT HELPERS
# ============================================================
def _normalize(text: str) -> str:
    """Collapse whitespace and normalize input."""
    return " ".join(text.strip().lower().replace("_", " ").split())


def _is_wake_word(text: str) -> bool:
    return text.strip().lower() in ASSISTANT_WAKE_WORDS


def _strip_wake_word(text: str) -> str:
    """Remove leading wake word and return the rest."""
    t = text.strip().lower()
    for name in ASSISTANT_WAKE_WORDS:
        if t == name:
            return ""
        if t.startswith(name) and len(t) > len(name) and t[len(name)] in " \t,":  # type: ignore[index]
            return t[len(name):].strip()
    return t


def _is_car_command(text: str) -> bool:
    """Check if text contains a car command keyword (fuzzy match)."""
    t = _normalize(text)
    # Exact match first
    if t in CAR_COMMANDS:
        return True
    # Fuzzy: check if any command keyword is in the text
    command_keywords = [
        "forward", "backward", "back", "left", "right", "stop",
        "speed full", "speed slow", "full speed", "slow speed",
        "auto", "park", "manual",
    ]
    for kw in command_keywords:
        if kw in t:
            return True
    # Common speech variations
    fuzzy_map = {
        "go": "forward", "move": "forward", "ahead": "forward",
        "reverse": "backward", "retreat": "backward",
        "halt": "stop", "brake": "stop", "freeze": "stop",
        "fast": "speed_full", "slow": "speed_slow",
        "turn left": "left", "turn right": "right",
        "go left": "left", "go right": "right",
    }
    for phrase in fuzzy_map:
        if phrase in t:
            return True
    return False


def _extract_car_command(text: str) -> Optional[str]:
    """Extract the actual car command from fuzzy text."""
    t = _normalize(text)

    # Exact match first
    cmd_map = {
        "forward": "forward", "backward": "backward", "back": "backward",
        "left": "left", "right": "right", "stop": "stop",
        "speed full": "speed_full", "speed slow": "speed_slow",
        "full speed": "speed_full", "slow speed": "speed_slow",
    }
    if t in cmd_map:
        return cmd_map[t]

    # Combined directions
    has_forward = "forward" in t or "ahead" in t
    has_backward = "backward" in t or "back" in t or "reverse" in t
    has_left = "left" in t
    has_right = "right" in t

    if has_forward and has_left:
        return "forward_left"
    if has_forward and has_right:
        return "forward_right"
    if has_backward and has_left:
        return "backward_left"
    if has_backward and has_right:
        return "backward_right"

    # Single direction keywords anywhere in text
    if "forward" in t or "ahead" in t or t in ("go", "move"):
        return "forward"
    if "backward" in t or "reverse" in t or "retreat" in t:
        return "backward"
    if has_left:
        return "left"
    if has_right:
        return "right"
    if "stop" in t or "halt" in t or "brake" in t or "freeze" in t:
        return "stop"
    if "fast" in t or "full speed" in t or "speed full" in t:
        return "speed_full"
    if "slow" in t or "slow speed" in t or "speed slow" in t:
        return "speed_slow"
    if "auto" in t and "park" in t:
        return "mode_park"
    if "auto" in t:
        return "mode_auto"
    if "park" in t:
        return "mode_park"
    if "manual" in t:
        return "mode_manual"

    return None


# ============================================================
# COMMAND EXECUTION
# ============================================================
def _execute_command(text: str, car: CarMqttClient, voice_mode: bool = False) -> bool:
    """
    Execute a car command via MQTT using fuzzy matching.
    Returns True to keep running, False to quit.
    """
    t = _normalize(text)

    if t in ("quit", "exit", "stop program"):
        return False

    cmd = _extract_car_command(t)
    if cmd is None:
        log_warn(f"Unknown command: {t}")
        return True

    # Handle mode changes
    if cmd.startswith("mode_"):
        mode = cmd.replace("mode_", "")
        car.send_mode(mode)
        if voice_mode:
            speak(f"{mode.title()} mode.", block=False)
        return True

    # Handle combined directions
    if cmd == "forward_left":
        car.send_command("forward")
        car.send_command("left")
        if voice_mode:
            speak("Forward left.", block=False)
        return True
    if cmd == "forward_right":
        car.send_command("forward")
        car.send_command("right")
        if voice_mode:
            speak("Forward right.", block=False)
        return True
    if cmd == "backward_left":
        car.send_command("backward")
        car.send_command("left")
        if voice_mode:
            speak("Backward left.", block=False)
        return True
    if cmd == "backward_right":
        car.send_command("backward")
        car.send_command("right")
        if voice_mode:
            speak("Backward right.", block=False)
        return True

    # Single command
    car.send_command(cmd)
    if voice_mode:
        speak(f"{cmd.replace('_', ' ').title()}.", block=False)
    return True


# ============================================================
# VOICE COMMAND LOOP
# ============================================================
def run_voice_loop(car: CarMqttClient, mic_index: Optional[int] = None) -> None:
    """
    Continuously listen for voice commands.
    Say wake word → command/question.
    """
    if sr is None:
        raise ImportError(
            "Voice control requires SpeechRecognition + pyaudio.\n"
            "Install: pip install SpeechRecognition pyaudio"
        )

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.6

    # List available mics
    _list_mics()

    mic = sr.Microphone(device_index=mic_index) if mic_index is not None else sr.Microphone()

    # Calibrate
    log_voice("Calibrating microphone... stay quiet for 2 seconds.")
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=2.0)
        recognizer.energy_threshold = max(100, int(recognizer.energy_threshold * 0.7))
    log_success(f"Mic ready. Energy threshold: {recognizer.energy_threshold}")

    use_ai = tts_available()
    log_voice("Voice mode active. Say the wake word, then your command or question.")
    log_voice("Say 'quit' to exit voice mode.")
    speak("Voice mode active. Say the wake word, then your command.", block=True)

    while True:
        try:
            log_voice("Listening...")
            with mic as source:
                audio = recognizer.listen(source, timeout=25, phrase_time_limit=20)

            text = recognizer.recognize_google(audio, language="en-US").strip().lower()
            if not text:
                continue

            log_voice(f"Heard: {text[:80]}")

            # Wake word only → prompt for follow-up
            if _is_wake_word(text):
                speak("Yes? Say your command or question.", block=True)
                time.sleep(0.5)
                text = _listen_followup(recognizer, mic)
                if not text:
                    continue

            stripped = _strip_wake_word(text)
            if not stripped:
                continue

            if stripped in ("quit", "exit"):
                log_voice("Exiting voice mode.")
                break

            if _is_car_command(stripped):
                _execute_command(stripped, car, voice_mode=True)
            elif use_ai:
                log_voice("Thinking...")
                answer = ask_ai(stripped, sensor_data=car.sensor_data, car_online=car.car_online)
                if answer:
                    # Check if AI wants to execute a command
                    action = extract_action(answer)
                    if action:
                        car.send_command(action)
                    clean = get_clean_reply(answer)
                    log_ai(clean)
                    speak(clean, block=True)
                else:
                    log_warn("No response from AI.")
            else:
                log_warn("Not a car command. Install pyttsx3 for AI answers.")

        except sr.UnknownValueError:
            pass  # silence — try again
        except sr.WaitTimeoutError:
            pass  # no speech — loop
        except sr.RequestError as e:
            log_error(f"Speech service error: {e}")
        except KeyboardInterrupt:
            log_voice("Interrupted.")
            break
        except Exception as e:
            log_error(f"Voice error: {e}")


def _listen_followup(recognizer, mic, attempts: int = 2) -> Optional[str]:
    """Listen for a follow-up after wake word."""
    for attempt in range(attempts):
        try:
            with mic as source:
                audio = recognizer.listen(source, timeout=15, phrase_time_limit=20)
            return recognizer.recognize_google(audio, language="en-US").strip().lower()
        except (sr.UnknownValueError, sr.WaitTimeoutError):  # type: ignore[union-attr]
            if attempt == 0:
                speak("Try again.", block=True)
                time.sleep(0.3)
    return None


def _list_mics() -> None:
    """Print available microphone devices."""
    try:
        import pyaudio  # type: ignore[import]
        p = pyaudio.PyAudio()
        log_voice("Available microphones:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                print(f"    [{i}] {info.get('name', 'Unknown')}")
        p.terminate()
    except Exception:
        pass


# ============================================================
# TYPED COMMAND LOOP
# ============================================================
def run_typed_loop(car: CarMqttClient) -> None:
    """
    Interactive typed command loop.
    Supports keyboard shortcuts, car commands, and AI questions.
    """
    use_ai = tts_available()
    print(
        "\n[TYPED] Type a command, shortcut key, or question. Type 'help' for controls.\n"
        "[TYPED] Type 'quit' to exit.\n"
    )

    while True:
        try:
            raw = input(f"\n  You > ").strip()
            if not raw:
                continue

            lower = raw.lower()

            # Quit
            if lower in ("quit", "exit", "q"):
                print("[TYPED] Goodbye.")
                break

            # Keyboard shortcuts (single key)
            if lower in KEYBOARD_SHORTCUTS:
                action = KEYBOARD_SHORTCUTS[lower]
                if action.startswith("mode_"):
                    car.send_mode(action.replace("mode_", ""))
                else:
                    car.send_command(action)
                continue

            # Special commands
            if lower == "help":
                from dashboard import print_controls  # type: ignore[import]
                print_controls()
                continue
            if lower == "dash":
                from dashboard import print_dashboard  # type: ignore[import]
                print_dashboard(car.sensor_data, car.car_status)
                continue
            if lower == "voice":
                run_voice_loop(car)
                continue

            # Wake word handling
            if _is_wake_word(lower):
                print("  Listening... type your command or question.")
                raw = input("  You > ").strip()
                if not raw:
                    continue
                lower = raw.lower()

            stripped = _strip_wake_word(lower) or lower
            if not stripped or stripped in ("quit", "exit"):
                break

            # Car command?
            if _is_car_command(stripped):
                _execute_command(stripped, car)
            elif use_ai:
                log_ai("Thinking...")
                answer = ask_ai(stripped, sensor_data=car.sensor_data, car_online=car.car_online)
                if answer:
                    action = extract_action(answer)
                    if action:
                        car.send_command(action)
                    clean = get_clean_reply(answer)
                    log_ai(clean)
                    speak(clean, block=True)
                else:
                    log_warn("No response from AI.")
            else:
                log_warn("Not a car command. Install requests + pyttsx3 for AI.")

        except KeyboardInterrupt:
            print("\n[TYPED] Goodbye.")
            break

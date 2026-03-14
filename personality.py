"""
personality.py
--------------
Car personality engine with persistent memory.
The car remembers past sessions, user preferences, and has moods/reactions.
Data persisted across sessions in a JSON file.
"""

import json
import os
import random
from datetime import datetime
from typing import Any, Optional


# ============================================================
# DEFAULT PERSONALITY CONFIG
# ============================================================
DEFAULT_CAR_NAME = "HB"
DEFAULT_TRAITS = {
    "style": "friendly and witty",
    "enthusiasm": 0.8,     # 0.0 = monotone, 1.0 = super hyped
    "humor": 0.6,          # 0.0 = serious, 1.0 = jokey
    "verbosity": 0.5,      # 0.0 = terse, 1.0 = chatty
}

MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "car_memory.json")


# ============================================================
# REACTION TEMPLATES
# ============================================================
REACTIONS = {
    "forward": [
        "Full speed ahead! 🚀",
        "Let's go! Moving forward.",
        "Onward and upward!",
        "Zooming forward!",
        "Here we go!",
    ],
    "backward": [
        "Backing it up! 🔙",
        "Reversing now.",
        "Going in reverse, watch out!",
        "Beep beep, backing up!",
    ],
    "left": [
        "Turning left! ◄",
        "Hanging a left!",
        "Steering left now.",
        "Lefty loosey!",
    ],
    "right": [
        "Turning right! ►",
        "Going right!",
        "Steering right now.",
        "Right turn coming up!",
    ],
    "stop": [
        "Stopping! ■",
        "Brakes on!",
        "Halting now.",
        "Full stop!",
        "Whoa there! Stopped.",
    ],
    "speed_full": [
        "Maximum power! ⚡",
        "Full speed engaged!",
        "Turbocharged!",
        "Let's fly!",
    ],
    "speed_slow": [
        "Slowing down. 🐢",
        "Easy does it.",
        "Taking it slow and steady.",
        "Cruise mode activated.",
    ],
    "obstacle": [
        "Whoa! Obstacle detected! Careful!",
        "Something's in the way! Stopping!",
        "Watch out! Obstacle ahead!",
        "Danger zone! Obstacle detected!",
    ],
    "parked": [
        "Parked perfectly! Like a boss. 😎",
        "Parking complete! Nailed it!",
        "Parked and chill.",
        "That's what I call a smooth park!",
    ],
    "stuck": [
        "Uh oh, I'm stuck! Help me out?",
        "Seems like I'm boxed in...",
        "All sides blocked! Need assistance.",
    ],
    "mode_manual": [
        "Manual mode — you're in control!",
        "Switching to manual. You drive!",
        "Manual mode active. Your call, boss!",
    ],
    "mode_auto": [
        "Auto mode — I'll handle the driving!",
        "Going autonomous! Sit back and relax.",
        "Auto pilot engaged!",
    ],
    "mode_park": [
        "Parking mode — finding a spot...",
        "Auto-park activated! Let me handle this.",
        "Finding the perfect spot...",
    ],
    "drowsy_warning": [
        "Hey! Stay awake! I'm stopping for safety!",
        "Wake up! You seem drowsy — stopping the car!",
        "Drowsiness detected! Emergency stop activated!",
        "Eyes open, please! Stopping for safety!",
    ],
    "drowsy_cleared": [
        "You're back! Ready to roll again.",
        "Alert confirmed. Let's continue!",
        "Good to see you awake! Resuming.",
    ],
}

GREETINGS_FIRST = [
    "Hey there! I'm {name}. Nice to meet you! Ready to roll? 🚗",
    "Welcome! I'm {name}, your AI car buddy. Let's hit the road!",
    "Hello, new friend! {name} here. Let's make some magic! ✨",
]

GREETINGS_RETURNING = [
    "Welcome back! Session #{count}. I missed you! 🎉",
    "Hey again! Session #{count}. Ready for another adventure?",
    "Back for more? That's session #{count}! Let's go! 🚀",
    "Good to see you again! This is our {count}th ride together.",
]

GREETINGS_TIME = {
    "morning": "Good morning! ☀️ ",
    "afternoon": "Good afternoon! 😎 ",
    "evening": "Good evening! 🌙 ",
    "night": "Night owl, huh? 🦉 ",
}


# ============================================================
# CAR PERSONALITY CLASS
# ============================================================
class CarPersonality:
    """Persistent personality engine for the AI RC Car."""

    def __init__(self, name: str = DEFAULT_CAR_NAME, traits: Optional[dict] = None,
                 memory_file: str = MEMORY_FILE):
        self.name = name
        self.traits = traits or DEFAULT_TRAITS.copy()
        self.memory_file = memory_file
        self._memory: dict[str, Any] = {}
        self._interaction_count = 0
        self._session_start = datetime.now()

        self._load_memory()
        self._start_session()

    # ---- Persistence ----
    def _load_memory(self) -> None:
        """Load memory from JSON file."""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self._memory = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._memory = {}

    def _save_memory(self) -> None:
        """Save memory to JSON file."""
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self._memory, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"[PERSONALITY] Save error: {e}")

    # ---- Memory API ----
    def remember(self, key: str, value: Any) -> None:
        """Store a key-value pair in persistent memory."""
        self._memory[key] = value
        self._save_memory()

    def recall(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from persistent memory."""
        return self._memory.get(key, default)

    def get_all_memory(self) -> dict:
        """Return all memory as a dict (for AI context)."""
        return dict(self._memory)

    # ---- Session tracking ----
    def _start_session(self) -> None:
        """Log a new session start."""
        sessions = self._memory.get("session_count", 0) + 1
        self._memory["session_count"] = sessions
        self._memory["last_session"] = datetime.now().isoformat()

        history = self._memory.get("session_history", [])
        history.append({
            "session": sessions,
            "start": datetime.now().isoformat(),
        })
        # Keep last 20 session records
        self._memory["session_history"] = history[-20:]
        self._save_memory()

    @property
    def session_count(self) -> int:
        return self._memory.get("session_count", 1)

    # ---- Mood System ----
    def get_mood(self) -> str:
        """Determine current mood based on interactions and session duration."""
        mins = (datetime.now() - self._session_start).seconds / 60.0

        if self._interaction_count > 30:
            return "energetic"
        elif self._interaction_count > 15:
            return "happy"
        elif mins > 30:
            return "tired"
        elif mins > 15:
            return "relaxed"
        else:
            return "neutral"

    def get_mood_emoji(self) -> str:
        emojis = {
            "energetic": "⚡", "happy": "😊", "relaxed": "😌",
            "tired": "😴", "neutral": "🤖",
        }
        return emojis.get(self.get_mood(), "🤖")

    # ---- Greetings ----
    def get_greeting(self) -> str:
        """Generate a contextual greeting."""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            time_key = "morning"
        elif 12 <= hour < 17:
            time_key = "afternoon"
        elif 17 <= hour < 21:
            time_key = "evening"
        else:
            time_key = "night"

        time_greeting = GREETINGS_TIME[time_key]

        if self.session_count <= 1:
            base = random.choice(GREETINGS_FIRST).format(name=self.name)
        else:
            base = random.choice(GREETINGS_RETURNING).format(
                name=self.name, count=self.session_count
            )

        return f"{time_greeting}{base}"

    # ---- Reactions ----
    def react(self, event: str) -> str:
        """Get a personality-driven reaction for an event."""
        self._interaction_count += 1

        templates = REACTIONS.get(event, [])
        if not templates:
            return ""

        reaction = random.choice(templates)

        # Add mood flair
        mood = self.get_mood()
        if mood == "energetic" and random.random() < 0.4:
            reaction += " Let's GOOO! 🔥"
        elif mood == "tired" and random.random() < 0.3:
            reaction += " *yawn* ...but I'm still here for you!"

        return reaction

    def log_interaction(self, text: str) -> None:
        """Track an interaction for mood/stats."""
        self._interaction_count += 1
        total = self._memory.get("total_interactions", 0) + 1
        self._memory["total_interactions"] = total
        self._save_memory()

    def get_personality_context(self) -> str:
        """Return a string with personality context for the AI prompt."""
        mood = self.get_mood()
        sessions = self.session_count
        interactions = self._memory.get("total_interactions", 0)
        user_name = self.recall("user_name", "the user")

        return (
            f"Your name is {self.name}. "
            f"Your personality is {self.traits['style']}. "
            f"Current mood: {mood}. "
            f"This is session #{sessions} with {user_name}. "
            f"Total interactions across all sessions: {interactions}. "
            f"Respond in a way that matches your mood and personality. "
            f"If the user tells you their name, remember it for next time."
        )


# ============================================================
# SINGLETON INSTANCE
# ============================================================
_personality: Optional[CarPersonality] = None


def get_personality() -> CarPersonality:
    """Get or create the global CarPersonality singleton."""
    global _personality
    if _personality is None:
        _personality = CarPersonality()
    return _personality

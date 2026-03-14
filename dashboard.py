"""
dashboard.py
-------------
Colorama-powered terminal dashboard for the AI RC Car.
Displays live sensor bars, car status, mode, and speed info.
Also provides color-coded logging helpers used across the application.
"""

import os
from datetime import datetime

try:
    from colorama import init, Fore, Style  # type: ignore[import]
    init(autoreset=True)
except ImportError:
    # Fallback: no colors
    class _Stub:
        def __getattr__(self, _):
            return ""
    Fore = _Stub()
    Style = _Stub()


# ============================================================
# SCREEN HELPERS
# ============================================================
def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_banner() -> None:
    print(Fore.CYAN + Style.BRIGHT + """
╔═══════════════════════════════════════════════════════════╗
║          🚗  AI RC CAR — PYTHON CONTROLLER                ║
║              Voice · AI · MQTT                            ║
╚═══════════════════════════════════════════════════════════╝""")


# ============================================================
# LOGGING HELPERS
# ============================================================
def _log(msg: str, color: str = "", prefix: str = "ℹ") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.CYAN}[{ts}]{Style.RESET_ALL} {color}{prefix}  {msg}{Style.RESET_ALL}")


def log_info(msg: str)    -> None: _log(msg, Fore.WHITE,   "ℹ")
def log_success(msg: str) -> None: _log(msg, Fore.GREEN,   "✅")
def log_error(msg: str)   -> None: _log(msg, Fore.RED,     "❌")
def log_warn(msg: str)    -> None: _log(msg, Fore.YELLOW,  "⚠️ ")
def log_ai(msg: str)      -> None: _log(msg, Fore.MAGENTA, "🤖")
def log_car(msg: str)     -> None: _log(msg, Fore.CYAN,    "🚗")
def log_voice(msg: str)   -> None: _log(msg, Fore.BLUE,    "🎤")


# ============================================================
# SENSOR BAR
# ============================================================
def _sensor_bar(label: str, value: float, max_val: float = 200) -> None:
    """Draw a visual bar for one sensor distance."""
    clamped = min(value, max_val)
    bar_len = int((clamped / max_val) * 20)
    bar = "█" * bar_len + "░" * (20 - bar_len)
    dist_str = f"{value:.1f}cm" if value < 999 else " ---  "

    if value < 15:
        color = Fore.RED
    elif value < 35:
        color = Fore.YELLOW
    else:
        color = Fore.GREEN

    print(f"  {label:<6} {color}|{bar}| {dist_str}{Style.RESET_ALL}")


# ============================================================
# FULL DASHBOARD
# ============================================================
def print_dashboard(sensor_data: dict, car_status: str = "") -> None:
    """Print the live sensor dashboard block."""
    mode = sensor_data.get("mode", "manual").upper()
    speed = sensor_data.get("speed", 0)

    if mode == "MANUAL":
        mc = Fore.CYAN
    elif mode == "AUTO":
        mc = Fore.YELLOW
    else:
        mc = Fore.MAGENTA

    print(Fore.WHITE + Style.BRIGHT + "\n  ┌─────────── LIVE SENSORS ───────────┐")
    _sensor_bar("FRONT", sensor_data.get("front", 999))
    _sensor_bar("BACK",  sensor_data.get("back", 999))
    _sensor_bar("LEFT",  sensor_data.get("left", 999))
    _sensor_bar("RIGHT", sensor_data.get("right", 999))
    print(Fore.WHITE + "  ├────────────────────────────────────┤")
    print(f"  │  Mode : {mc}{mode:<10}{Style.RESET_ALL}  Speed: {Fore.CYAN}{speed}/255{Style.RESET_ALL}  │")
    if car_status:
        print(f"  │  Status: {Fore.YELLOW}{car_status[:28]:<28}{Style.RESET_ALL}│")  # type: ignore[index]
    print(Fore.WHITE + "  └────────────────────────────────────┘")


# ============================================================
# HELP / CONTROLS
# ============================================================
def print_controls() -> None:
    print(Fore.CYAN + Style.BRIGHT + """
  ┌─────────────────────────────────────────────────────────┐
  │                    CONTROLS                             │
  ├────────────┬────────────────────────────────────────────┤
  │  W         │  Move Forward                              │
  │  S         │  Move Backward                             │
  │  A         │  Turn Left                                 │
  │  D         │  Turn Right                                │
  │  X         │  STOP                                      │
  │  F         │  Full Speed                                │
  │  G         │  Slow Speed                                │
  ├────────────┼────────────────────────────────────────────┤
  │  1         │  Manual Mode                               │
  │  2         │  Auto Mode (obstacle avoidance)            │
  │  3         │  Auto Park Mode                            │
  ├────────────┼────────────────────────────────────────────┤
  │  voice     │  Start Voice Control                       │
  │  dash      │  Show Sensor Dashboard                     │
  │  help      │  Show This Menu                            │
  │  quit      │  Quit                                      │
  ├────────────┼────────────────────────────────────────────┤
  │  Anything  │  Send to AI Assistant                      │
  │  else      │  e.g. "park near the wall"                 │
  └────────────┴────────────────────────────────────────────┘
""")

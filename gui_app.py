"""
gui_app.py
----------
Premium desktop GUI for the AI RC Car controller.
Built with CustomTkinter — deep space dark theme, animated sensor gauges,
glassmorphism panels, gradient accents, control pad, AI chat, and status bar.

Designed for national-level hackathon presentation.
"""

import threading
import math
import time as _time
from typing import Optional

import customtkinter as ctk  # type: ignore[import]

from config import KEYBOARD_SHORTCUTS  # type: ignore[import]
from mqtt_client import CarMqttClient  # type: ignore[import]
from ai_assistant import ask_ai, extract_action, get_clean_reply, speak, tts_available, speak_with_personality  # type: ignore[import]


# ============================================================
# THEME — Deep Space / Cyberpunk
# ============================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Primary palette
COLOR_BG_DEEP    = "#0a0e1a"      # deep space black
COLOR_BG_CARD    = "#111827"      # card background
COLOR_BG_CARD2   = "#1a1f35"      # slightly lighter card
COLOR_BG_INPUT   = "#0d1117"      # input fields
COLOR_BORDER     = "#1e293b"      # subtle borders

# Accent colors
COLOR_CYAN       = "#06b6d4"      # primary accent
COLOR_CYAN_GLOW  = "#22d3ee"      # hover glow
COLOR_CYAN_DIM   = "#0e4f5c"      # muted cyan
COLOR_PURPLE     = "#8b5cf6"      # secondary accent
COLOR_PURPLE_DIM = "#4c2889"      # muted purple
COLOR_BLUE       = "#3b82f6"      # info
COLOR_GREEN      = "#10b981"      # success / safe
COLOR_GREEN_GLOW = "#34d399"      # bright green
COLOR_YELLOW     = "#f59e0b"      # warning
COLOR_ORANGE     = "#f97316"      # caution
COLOR_RED        = "#ef4444"      # danger
COLOR_RED_GLOW   = "#f87171"      # bright red
COLOR_PINK       = "#ec4899"      # stop button

# Text
COLOR_TEXT        = "#e2e8f0"     # primary text
COLOR_TEXT_DIM    = "#94a3b8"     # secondary text
COLOR_TEXT_MUTED  = "#64748b"     # muted/hint text


def _dist_color(value: float) -> str:
    """Return gradient color based on distance threshold."""
    if value < 15:
        return COLOR_RED
    elif value < 25:
        return COLOR_ORANGE
    elif value < 40:
        return COLOR_YELLOW
    else:
        return COLOR_GREEN


def _dist_glow(value: float) -> str:
    """Return glow color for danger states."""
    if value < 15:
        return COLOR_RED_GLOW
    elif value < 25:
        return COLOR_ORANGE
    else:
        return COLOR_GREEN_GLOW


# ============================================================
# MAIN APPLICATION
# ============================================================
class CarControlApp(ctk.CTk):
    """AI RC Car — Premium Controller GUI."""

    def __init__(self) -> None:
        super().__init__()

        self.title("AI RC Car — Neural Controller")
        self.geometry("1060x780")
        self.minsize(960, 700)
        self.configure(fg_color=COLOR_BG_DEEP)

        # Animation state
        self._pulse_phase = 0.0
        self._sensor_anim = {"front": 0.0, "back": 0.0, "left": 0.0, "right": 0.0}

        # Voice feedback state
        self._voice_muted = False
        self._last_sensor_warn = 0.0  # cooldown for sensor warnings

        # Drowsiness detection state
        self._drowsiness_detector = None
        self._drowsiness_active = False

        # --- MQTT Client ---
        self.car = CarMqttClient(
            on_sensors=self._on_sensors,
            on_status=self._on_status,
        )

        # --- Build UI ---
        self._build_header()
        self._build_main_area()
        self._build_chat_panel()
        self._build_status_bar()

        # --- Keyboard bindings (WASD + Arrow keys) ---
        self.bind("<KeyPress-w>", lambda e: self._key_cmd(e, "forward"))
        self.bind("<KeyPress-a>", lambda e: self._key_cmd(e, "left"))
        self.bind("<KeyPress-s>", lambda e: self._key_cmd(e, "backward"))
        self.bind("<KeyPress-d>", lambda e: self._key_cmd(e, "right"))
        self.bind("<KeyPress-x>", lambda e: self._key_cmd(e, "stop"))
        self.bind("<KeyPress-f>", lambda e: self._key_cmd(e, "speed_full"))
        self.bind("<KeyPress-g>", lambda e: self._key_cmd(e, "speed_slow"))

        self.bind("<Up>",    lambda e: self._key_cmd(e, "forward"))
        self.bind("<Down>",  lambda e: self._key_cmd(e, "backward"))
        self.bind("<Left>",  lambda e: self._key_cmd(e, "left"))
        self.bind("<Right>", lambda e: self._key_cmd(e, "right"))
        self.bind("<space>", lambda e: self._key_cmd(e, "stop"))

        # --- Connect MQTT on startup ---
        self._connect_mqtt()

        # --- Periodic sensor UI refresh + animations ---
        self._schedule_sensor_refresh()
        self._animate_pulse()

        # --- Personality greeting ---
        self._show_personality_greeting()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ================================================================
    # HEADER — Gradient-style top bar
    # ================================================================
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=COLOR_BG_CARD, corner_radius=0, height=64,
                              border_width=0)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        # Left: Logo + title
        logo_frame = ctk.CTkFrame(header, fg_color="transparent")
        logo_frame.pack(side="left", padx=20)

        # Glowing dot indicator
        self.header_dot = ctk.CTkLabel(
            logo_frame, text="●", font=ctk.CTkFont(size=14),
            text_color=COLOR_YELLOW,
        )
        self.header_dot.pack(side="left", padx=(0, 8))

        title = ctk.CTkLabel(
            logo_frame, text="AI RC CAR",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_CYAN,
        )
        title.pack(side="left")

        subtitle = ctk.CTkLabel(
            logo_frame, text="  NEURAL CONTROLLER",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_TEXT_DIM,
        )
        subtitle.pack(side="left", padx=(4, 0), pady=(4, 0))

        # Right: Mode selector
        mode_frame = ctk.CTkFrame(header, fg_color="transparent")
        mode_frame.pack(side="right", padx=20)

        mode_label = ctk.CTkLabel(
            mode_frame, text="MODE",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
        )
        mode_label.pack(side="left", padx=(0, 10))

        self.mode_var = ctk.StringVar(value="Manual")
        mode_menu = ctk.CTkOptionMenu(
            mode_frame, variable=self.mode_var,
            values=["Manual", "Auto", "Park"],
            command=self._on_mode_change,
            width=130, height=36,
            corner_radius=10,
            fg_color=COLOR_BG_CARD2,
            button_color=COLOR_CYAN_DIM,
            button_hover_color=COLOR_CYAN,
            dropdown_fg_color=COLOR_BG_CARD,
            dropdown_hover_color=COLOR_CYAN_DIM,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        mode_menu.pack(side="right")

        # Bottom border glow
        glow_line = ctk.CTkFrame(self, fg_color=COLOR_CYAN_DIM, height=2, corner_radius=0)
        glow_line.pack(fill="x")

    # ================================================================
    # MAIN AREA — Sensors left, Controls right
    # ================================================================
    def _build_main_area(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=False, padx=16, pady=(12, 6))

        # --- Left: Sensor Panel ---
        self._build_sensor_panel(main)

        # --- Right: Control Panel ---
        self._build_control_panel(main)

    def _build_sensor_panel(self, parent) -> None:
        """Glassmorphism sensor panel with animated gauges."""
        sensor_frame = ctk.CTkFrame(
            parent, fg_color=COLOR_BG_CARD, corner_radius=16,
            border_width=1, border_color=COLOR_BORDER,
        )
        sensor_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Title bar
        title_bar = ctk.CTkFrame(sensor_frame, fg_color="transparent")
        title_bar.pack(fill="x", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            title_bar, text="◈  LIVE SENSORS",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_CYAN,
        ).pack(side="left")

        self.sensor_status_dot = ctk.CTkLabel(
            title_bar, text="● ACTIVE",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLOR_GREEN,
        )
        self.sensor_status_dot.pack(side="right")

        # Separator
        ctk.CTkFrame(sensor_frame, fg_color=COLOR_BORDER, height=1).pack(
            fill="x", padx=16, pady=(8, 12)
        )

        # Sensor bars
        self.sensor_bars: dict[str, tuple[ctk.CTkProgressBar, ctk.CTkLabel, ctk.CTkLabel]] = {}
        sensor_icons = {"Front": "▲", "Back": "▼", "Left": "◄", "Right": "►"}

        for name in ("Front", "Back", "Left", "Right"):
            row = ctk.CTkFrame(sensor_frame, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=5)

            # Icon + label
            icon_lbl = ctk.CTkLabel(
                row, text=sensor_icons[name], width=22,
                font=ctk.CTkFont(size=14), text_color=COLOR_CYAN,
            )
            icon_lbl.pack(side="left")

            name_lbl = ctk.CTkLabel(
                row, text=f" {name}", width=55, anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLOR_TEXT,
            )
            name_lbl.pack(side="left")

            # Progress bar with custom styling
            bar = ctk.CTkProgressBar(
                row, height=20, corner_radius=10, width=200,
                progress_color=COLOR_GREEN, fg_color=COLOR_BG_CARD2,
                border_width=0,
            )
            bar.pack(side="left", padx=(8, 10))
            bar.set(1.0)

            # Value label
            val = ctk.CTkLabel(
                row, text="---", width=70, anchor="e",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=COLOR_GREEN,
            )
            val.pack(side="right")

            self.sensor_bars[name.lower()] = (bar, val, icon_lbl)

        # Info section
        info_sep = ctk.CTkFrame(sensor_frame, fg_color=COLOR_BORDER, height=1)
        info_sep.pack(fill="x", padx=16, pady=(14, 10))

        info_frame = ctk.CTkFrame(sensor_frame, fg_color=COLOR_BG_CARD2,
                                  corner_radius=10)
        info_frame.pack(fill="x", padx=16, pady=(0, 16))

        info_inner = ctk.CTkFrame(info_frame, fg_color="transparent")
        info_inner.pack(padx=14, pady=10)

        self.lbl_mode = ctk.CTkLabel(
            info_inner, text="⚙  Mode: MANUAL",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT,
        )
        self.lbl_mode.pack(anchor="w", pady=1)

        self.lbl_speed = ctk.CTkLabel(
            info_inner, text="⚡  Speed: 200 / 255",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_CYAN,
        )
        self.lbl_speed.pack(anchor="w", pady=1)

    def _build_control_panel(self, parent) -> None:
        """Premium control panel with gradient-style buttons."""
        ctrl_frame = ctk.CTkFrame(
            parent, fg_color=COLOR_BG_CARD, corner_radius=16,
            border_width=1, border_color=COLOR_BORDER,
        )
        ctrl_frame.pack(side="right", fill="both", expand=True, padx=(8, 0))

        # Title
        title_bar = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        title_bar.pack(fill="x", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            title_bar, text="◈  CONTROLS",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_PURPLE,
        ).pack(side="left")

        ctk.CTkLabel(
            title_bar, text="WASD / ↑←↓→",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
        ).pack(side="right")

        ctk.CTkFrame(ctrl_frame, fg_color=COLOR_BORDER, height=1).pack(
            fill="x", padx=16, pady=(8, 14)
        )

        # D-pad — premium style
        dpad = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        dpad.pack(pady=(0, 8))

        btn_w, btn_h = 72, 54
        btn_radius = 12

        # Row 1: Forward
        r1 = ctk.CTkFrame(dpad, fg_color="transparent")
        r1.pack()
        self._make_dpad_btn(r1, "▲", "forward", btn_w, btn_h, btn_radius,
                            COLOR_CYAN_DIM, COLOR_CYAN).pack(pady=2)

        # Row 2: Left, Stop, Right
        r2 = ctk.CTkFrame(dpad, fg_color="transparent")
        r2.pack()
        self._make_dpad_btn(r2, "◄", "left", btn_w, btn_h, btn_radius,
                            COLOR_CYAN_DIM, COLOR_CYAN).pack(side="left", padx=3)
        # Stop button (special — red/pink)
        stop_btn = ctk.CTkButton(
            r2, text="■", command=lambda: self._cmd("stop"),
            width=btn_w, height=btn_h, corner_radius=btn_radius,
            font=ctk.CTkFont(size=20, weight="bold"),
            fg_color="#7f1d1d", hover_color=COLOR_RED,
            border_width=2, border_color=COLOR_RED,
        )
        stop_btn.pack(side="left", padx=3)
        self._make_dpad_btn(r2, "►", "right", btn_w, btn_h, btn_radius,
                            COLOR_CYAN_DIM, COLOR_CYAN).pack(side="left", padx=3)

        # Row 3: Backward
        r3 = ctk.CTkFrame(dpad, fg_color="transparent")
        r3.pack()
        self._make_dpad_btn(r3, "▼", "backward", btn_w, btn_h, btn_radius,
                            COLOR_CYAN_DIM, COLOR_CYAN).pack(pady=2)

        # Speed buttons
        speed_sep = ctk.CTkFrame(ctrl_frame, fg_color=COLOR_BORDER, height=1)
        speed_sep.pack(fill="x", padx=24, pady=(10, 10))

        speed_row = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        speed_row.pack(pady=(0, 6))

        ctk.CTkButton(
            speed_row, text="⚡ FULL SPEED",
            command=lambda: self._cmd("speed_full"),
            width=120, height=38, corner_radius=10,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#064e3b", hover_color="#059669",
            border_width=1, border_color=COLOR_GREEN,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            speed_row, text="🐢 SLOW",
            command=lambda: self._cmd("speed_slow"),
            width=120, height=38, corner_radius=10,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#78350f", hover_color="#d97706",
            border_width=1, border_color=COLOR_YELLOW,
        ).pack(side="left", padx=4)

        # Feature button
        feat_row = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        feat_row.pack(pady=(4, 16))

        ctk.CTkButton(
            feat_row, text="🎤 VOICE CONTROL",
            command=self._start_voice,
            width=252, height=38, corner_radius=10,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_PURPLE_DIM, hover_color=COLOR_PURPLE,
            border_width=1, border_color=COLOR_PURPLE,
        ).pack()

        # Voice mute toggle
        mute_row = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        mute_row.pack(pady=(4, 16))

        self._mute_btn = ctk.CTkButton(
            mute_row, text="🔊 VOICE ON",
            command=self._toggle_voice_mute,
            width=252, height=34, corner_radius=10,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLOR_BG_CARD2, hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER,
        )
        self._mute_btn.pack()

        # Drowsiness detection toggle
        drowsy_row = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        drowsy_row.pack(pady=(4, 16))

        self._drowsy_btn = ctk.CTkButton(
            drowsy_row, text="😴 DROWSINESS OFF",
            command=self._toggle_drowsiness,
            width=252, height=38, corner_radius=10,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_BG_CARD2, hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER,
        )
        self._drowsy_btn.pack()

    def _make_dpad_btn(self, parent, text, cmd, w, h, r, fg, hover):
        """Create a styled D-pad button."""
        return ctk.CTkButton(
            parent, text=text, command=lambda: self._cmd(cmd),
            width=w, height=h, corner_radius=r,
            font=ctk.CTkFont(size=20, weight="bold"),
            fg_color=fg, hover_color=hover,
            border_width=1, border_color=COLOR_CYAN,
        )

    # ================================================================
    # CHAT / LOG PANEL
    # ================================================================
    def _build_chat_panel(self) -> None:
        chat_frame = ctk.CTkFrame(
            self, fg_color=COLOR_BG_CARD, corner_radius=16,
            border_width=1, border_color=COLOR_BORDER,
        )
        chat_frame.pack(fill="both", expand=True, padx=16, pady=6)

        # Title
        title_bar = ctk.CTkFrame(chat_frame, fg_color="transparent")
        title_bar.pack(fill="x", padx=20, pady=(12, 0))

        ctk.CTkLabel(
            title_bar, text="◈  AI CHAT & LOG",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_BLUE,
        ).pack(side="left")

        self.chat_count_label = ctk.CTkLabel(
            title_bar, text="0 messages",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
        )
        self.chat_count_label.pack(side="right")

        ctk.CTkFrame(chat_frame, fg_color=COLOR_BORDER, height=1).pack(
            fill="x", padx=16, pady=(8, 6)
        )

        # Chat log with custom styling
        self.chat_log = ctk.CTkTextbox(
            chat_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=COLOR_BG_INPUT, text_color=COLOR_TEXT,
            corner_radius=10, wrap="word",
            border_width=1, border_color=COLOR_BORDER,
        )
        self.chat_log.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        self.chat_log.configure(state="disabled")
        self._msg_count = 0

        # Input row
        input_row = ctk.CTkFrame(chat_frame, fg_color="transparent")
        input_row.pack(fill="x", padx=14, pady=(0, 14))

        self.chat_input = ctk.CTkEntry(
            input_row,
            placeholder_text="Type a command or ask the AI assistant...",
            font=ctk.CTkFont(size=13), height=42, corner_radius=12,
            fg_color=COLOR_BG_INPUT, text_color=COLOR_TEXT,
            border_width=1, border_color=COLOR_BORDER,
        )
        self.chat_input.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.chat_input.bind("<Return>", lambda e: self._on_send())

        send_btn = ctk.CTkButton(
            input_row, text="SEND ›", width=90, height=42, corner_radius=12,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_CYAN_DIM, hover_color=COLOR_CYAN,
            border_width=1, border_color=COLOR_CYAN,
            command=self._on_send,
        )
        send_btn.pack(side="right")

    # ================================================================
    # STATUS BAR — Premium bottom bar
    # ================================================================
    def _build_status_bar(self) -> None:
        bar = ctk.CTkFrame(
            self, fg_color=COLOR_BG_CARD, corner_radius=0, height=36,
            border_width=0,
        )
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        # Top border glow
        ctk.CTkFrame(self, fg_color=COLOR_BORDER, height=1, corner_radius=0).pack(
            fill="x", side="bottom"
        )

        self.lbl_mqtt_status = ctk.CTkLabel(
            bar, text="  ● MQTT: Connecting...",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_YELLOW,
        )
        self.lbl_mqtt_status.pack(side="left", padx=12)

        self.lbl_car_status = ctk.CTkLabel(
            bar, text="● Car: Offline",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
        )
        self.lbl_car_status.pack(side="left", padx=16)

        keys_hint = ctk.CTkLabel(
            bar,
            text="W/A/S/D or ↑←↓→ = Move  │  X/Space = Stop  │  F = Fast  │  G = Slow",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_MUTED,
        )
        keys_hint.pack(side="right", padx=12)

        # Drowsiness EAR indicator
        self.lbl_drowsy_status = ctk.CTkLabel(
            bar, text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
        )
        self.lbl_drowsy_status.pack(side="right", padx=8)

    # ================================================================
    # ANIMATIONS
    # ================================================================
    def _animate_pulse(self) -> None:
        """Pulse animation for status indicators."""
        self._pulse_phase += 0.15
        if self._pulse_phase > 2 * math.pi:
            self._pulse_phase -= 2 * math.pi

        # Pulse the header dot based on connection
        pulse_val = (math.sin(self._pulse_phase) + 1) / 2  # 0..1

        if self.car.connected and self.car.car_online:
            # Smooth green pulse
            self.header_dot.configure(
                text_color=COLOR_GREEN if pulse_val > 0.3 else COLOR_GREEN_GLOW
            )
        elif self.car.connected:
            self.header_dot.configure(
                text_color=COLOR_CYAN if pulse_val > 0.3 else COLOR_CYAN_GLOW
            )
        else:
            self.header_dot.configure(
                text_color=COLOR_YELLOW if pulse_val > 0.5 else COLOR_ORANGE
            )

        self.after(80, self._animate_pulse)

    # ================================================================
    # MQTT CONNECTION
    # ================================================================
    def _connect_mqtt(self) -> None:
        def _do_connect():
            try:
                self.car.connect()
                import time
                for _ in range(10):
                    if self.car.connected:
                        break
                    time.sleep(0.5)
                self.after(0, self._update_mqtt_status)
            except Exception as e:
                self.after(0, lambda: self._log(f"❌ MQTT error: {e}"))

        threading.Thread(target=_do_connect, daemon=True).start()

    def _update_mqtt_status(self) -> None:
        if self.car.connected:
            self.lbl_mqtt_status.configure(
                text="  ● MQTT: Connected", text_color=COLOR_GREEN
            )
            self._log("✅ MQTT connected to broker.hivemq.com")
        elif self.car._reconnect_active:
            self.lbl_mqtt_status.configure(
                text="  ● MQTT: Reconnecting...", text_color=COLOR_YELLOW
            )
            self._log("🔄 MQTT reconnecting...")
        else:
            self.lbl_mqtt_status.configure(
                text="  ● MQTT: Disconnected", text_color=COLOR_RED
            )

    # ================================================================
    # SENSOR UPDATE (periodic)
    # ================================================================
    def _schedule_sensor_refresh(self) -> None:
        self._refresh_sensors()
        self._poll_mqtt_status()
        self.after(300, self._schedule_sensor_refresh)

    def _poll_mqtt_status(self) -> None:
        """Keep the status bar in sync with the actual MQTT connection state."""
        if self.car.connected:
            current = self.lbl_mqtt_status.cget("text_color")
            if current != COLOR_GREEN:
                self.lbl_mqtt_status.configure(
                    text="  ● MQTT: Connected", text_color=COLOR_GREEN
                )
                self._log("✅ MQTT reconnected!")
        elif self.car._reconnect_active:
            self.lbl_mqtt_status.configure(
                text="  ● MQTT: Reconnecting...", text_color=COLOR_YELLOW
            )
        else:
            current = self.lbl_mqtt_status.cget("text_color")
            if current != COLOR_RED:
                self.lbl_mqtt_status.configure(
                    text="  ● MQTT: Disconnected", text_color=COLOR_RED
                )

    def _refresh_sensors(self) -> None:
        data = self.car.sensor_data

        for key in ("front", "back", "left", "right"):
            val = data.get(key, 999)
            if key in self.sensor_bars:
                bar, lbl, icon_lbl = self.sensor_bars[key]

                # Smooth animated progress
                target = max(0.02, min(1.0, val / 200.0))
                bar.set(target)

                color = _dist_color(val)
                bar.configure(progress_color=color)
                lbl.configure(
                    text=f"{val:.0f} cm" if val < 999 else "---",
                    text_color=color,
                )

                # Icon color changes with danger
                icon_lbl.configure(text_color=color if val < 35 else COLOR_CYAN)

        mode = data.get("mode", "manual").upper()
        speed = data.get("speed", 0)

        # Mode with color coding
        mode_colors = {"MANUAL": COLOR_CYAN, "AUTO": COLOR_YELLOW, "PARK": COLOR_PURPLE}
        mc = mode_colors.get(mode, COLOR_TEXT)
        self.lbl_mode.configure(text=f"⚙  Mode: {mode}", text_color=mc)
        self.lbl_speed.configure(text=f"⚡  Speed: {speed} / 255")

        # Car online status
        if self.car.car_online:
            self.lbl_car_status.configure(
                text="● Car: Online", text_color=COLOR_GREEN
            )
            self.sensor_status_dot.configure(
                text="● ACTIVE", text_color=COLOR_GREEN
            )
        else:
            self.lbl_car_status.configure(
                text="● Car: Offline", text_color=COLOR_TEXT_MUTED
            )
            self.sensor_status_dot.configure(
                text="● WAITING", text_color=COLOR_TEXT_MUTED
            )

        # Sync mode dropdown
        mode_map = {"MANUAL": "Manual", "AUTO": "Auto", "PARK": "Park"}
        if mode in mode_map and self.mode_var.get() != mode_map[mode]:
            self.mode_var.set(mode_map[mode])

    # ================================================================
    # MQTT CALLBACKS
    # ================================================================
    def _on_sensors(self, data: dict) -> None:
        pass  # Handled by periodic refresh

    def _on_status(self, data: dict) -> None:
        status = data.get("status", "")
        self.after(0, lambda: self._log(f"🚗 {status}"))
        lower = status.lower()
        if any(word in lower for word in ("obstacle", "blocked", "stuck", "danger", "safety")):
            threading.Thread(
                target=lambda: speak("Warning, obstacle detected.", block=False),
                daemon=True,
            ).start()
        elif any(word in lower for word in ("parked", "complete")):
            threading.Thread(
                target=lambda: speak_with_personality("parked", block=False),
                daemon=True,
            ).start()

    # ================================================================
    # COMMAND SENDING
    # ================================================================
    def _key_cmd(self, event, command: str) -> Optional[str]:
        """Handle keyboard command — skip if chat input is focused."""
        if event.widget == self.chat_input._entry:
            return None
        self._cmd(command)
        return "break"

    def _cmd(self, command: str) -> None:
        """Send a command to the car via MQTT with voice feedback."""
        self.car.send_command(command)
        self._log(f"→ {command}")
        # Voice feedback
        if not self._voice_muted:
            threading.Thread(
                target=lambda: speak_with_personality(command, block=False),
                daemon=True,
            ).start()

    def _on_mode_change(self, mode_str: str) -> None:
        mode = mode_str.lower()
        self.car.send_mode(mode)
        self._log(f"→ Mode: {mode.upper()}")
        # Voice feedback for mode change
        if not self._voice_muted:
            threading.Thread(
                target=lambda: speak_with_personality(f"mode_{mode}", block=False),
                daemon=True,
            ).start()

    # ================================================================
    # CHAT INPUT
    # ================================================================
    def _on_send(self) -> None:
        text = self.chat_input.get().strip()
        if not text:
            return
        self.chat_input.delete(0, "end")
        self._log(f"You: {text}")

        # Check if it's a car command shortcut
        lower = text.lower()
        if lower in KEYBOARD_SHORTCUTS:
            action = KEYBOARD_SHORTCUTS[lower]
            if action.startswith("mode_"):
                self.car.send_mode(action.replace("mode_", ""))
            else:
                self.car.send_command(action)
            return

        # Check car commands
        car_cmds = {
            "forward", "backward", "back", "left", "right", "stop",
            "speed full", "speed slow",
        }
        if lower in car_cmds:
            cmd = lower.replace(" ", "_")
            if cmd == "back":
                cmd = "backward"
            self.car.send_command(cmd)
            return

        # Mode changes
        if lower in ("auto", "auto park", "park", "manual"):
            mode = "park" if "park" in lower else ("auto" if lower == "auto" else "manual")
            self.car.send_mode(mode)
            return

        # Send to AI in background
        self._log("🤖 Thinking...")
        threading.Thread(target=self._ask_ai_bg, args=(text,), daemon=True).start()

    def _ask_ai_bg(self, question: str) -> None:
        """Ask AI in background thread, update UI on completion."""
        answer = ask_ai(question, sensor_data=self.car.sensor_data, car_online=self.car.car_online)
        if answer:
            action = extract_action(answer)
            if action:
                self.car.send_command(action)
                self.after(0, lambda: self._log(f"→ AI action: {action}"))
            clean = get_clean_reply(answer)
            self.after(0, lambda: self._log(f"🤖 {clean}"))
            if tts_available():
                speak(clean, block=True)
        else:
            self.after(0, lambda: self._log("🤖 No response from AI."))

    # ================================================================
    # FEATURES
    # ================================================================
    def _start_voice(self) -> None:
        self._log("🎤 Starting voice mode...")

        def _voice_thread():
            try:
                from voice_control import run_voice_loop  # type: ignore[import]
                run_voice_loop(self.car)
            except ImportError as e:
                self.after(0, lambda: self._log(f"❌ Voice not available: {e}"))
            except Exception as e:
                self.after(0, lambda: self._log(f"❌ Voice error: {e}"))
            finally:
                self.after(0, lambda: self._log("🎤 Voice mode ended."))

        threading.Thread(target=_voice_thread, daemon=True).start()

    def _toggle_voice_mute(self) -> None:
        """Toggle voice feedback on/off."""
        self._voice_muted = not self._voice_muted
        if self._voice_muted:
            self._mute_btn.configure(text="🔇 VOICE OFF", fg_color="#7f1d1d",
                                     border_color=COLOR_RED)
            self._log("🔇 Voice feedback muted.")
        else:
            self._mute_btn.configure(text="🔊 VOICE ON", fg_color=COLOR_BG_CARD2,
                                     border_color=COLOR_BORDER)
            self._log("🔊 Voice feedback enabled.")

    def _show_personality_greeting(self) -> None:
        """Show personality greeting in chat log on startup."""
        try:
            from personality import get_personality  # type: ignore[import]
            p = get_personality()
            greeting = p.get_greeting()
            self._log(f"🤖 {greeting}")
            mood = p.get_mood()
            self._log(f"🤖 Mood: {mood} {p.get_mood_emoji()}")
            if not self._voice_muted:
                threading.Thread(
                    target=lambda: speak(greeting, block=False),
                    daemon=True,
                ).start()
        except Exception as e:
            self._log(f"🤖 Hello! Ready to roll.")

    def _toggle_drowsiness(self) -> None:
        """Toggle drowsiness detection on/off."""
        if not self._drowsiness_active:
            try:
                from drowsiness import DrowsinessDetector  # type: ignore[import]
                self._drowsiness_detector = DrowsinessDetector()
                self._drowsiness_detector.start(  # type: ignore[union-attr]
                    on_drowsy=self._on_drowsy,
                    on_alert=self._on_drowsy_alert,
                    on_yawn=self._on_yawn,
                    on_error=self._on_drowsy_error,
                )
                self._drowsiness_active = True
                self._drowsy_btn.configure(
                    text="😴 DROWSINESS ON", fg_color="#064e3b",
                    border_color=COLOR_GREEN,
                )
                self._log("😴 Drowsiness detection started. Camera active.")
                self._update_drowsiness_ui()
            except ImportError as e:
                self._log(f"❌ Drowsiness not available: {e}")
            except Exception as e:
                self._log(f"❌ Drowsiness error: {e}")
        else:
            if self._drowsiness_detector:
                self._drowsiness_detector.stop()  # type: ignore[union-attr]
                self._drowsiness_detector = None
            self._drowsiness_active = False
            self._drowsy_btn.configure(
                text="😴 DROWSINESS OFF", fg_color=COLOR_BG_CARD2,
                border_color=COLOR_BORDER,
            )
            self.lbl_drowsy_status.configure(text="")
            self._log("😴 Drowsiness detection stopped.")

    def _on_drowsy(self) -> None:
        """Called when drowsiness is confirmed — auto-stop the car + LOUD ALARM!"""
        self.after(0, lambda: self._log("🚨🚨🚨 DROWSINESS DETECTED! Auto-stopping car!"))
        self.after(0, lambda: self.car.send_command("stop"))
        # Visual alert — flash the header red
        self.after(0, lambda: self.header_dot.configure(text_color=COLOR_RED_GLOW))
        # Flash the drowsy button red
        self.after(0, lambda: self._drowsy_btn.configure(
            text="🚨 DROWSY! WAKE UP!", fg_color="#dc2626",
            border_color="#ef4444",
        ))
        # Start flashing effect
        self.after(0, self._flash_drowsy_alert)

        # CONTINUOUS ALARM — plays repeatedly until driver alert
        def _alarm():
            while getattr(self, '_drowsiness_active', False) and \
                  getattr(self, '_drowsiness_detector', None) and \
                  getattr(self._drowsiness_detector, 'is_drowsy', False):
                try:
                    speak("Wake up bro", block=True)
                    import time
                    time.sleep(1)
                except Exception:
                    break
        threading.Thread(target=_alarm, daemon=True).start()

    def _flash_drowsy_alert(self) -> None:
        """Flash the UI red to wake the user up."""
        if not hasattr(self, '_flash_count'):
            self._flash_count = 0
        self._flash_count += 1

        if self._flash_count > 10:  # flash 10 times (~5 seconds)
            self._flash_count = 0
            return

        # Toggle between red and dark
        if self._flash_count % 2 == 0:
            self._drowsy_btn.configure(fg_color="#dc2626")
            self.header_dot.configure(text_color=COLOR_RED_GLOW)
        else:
            self._drowsy_btn.configure(fg_color="#7f1d1d")
            self.header_dot.configure(text_color=COLOR_RED)

        self.after(500, self._flash_drowsy_alert)

    def _on_drowsy_alert(self) -> None:
        """Called when driver is back to alert."""
        self.after(0, lambda: self._log("✅ Driver alert confirmed. Safe to continue."))
        # Reset button appearance
        self.after(0, lambda: self._drowsy_btn.configure(
            text="😴 DROWSINESS ON", fg_color="#064e3b",
            border_color=COLOR_GREEN,
        ))
        self._flash_count = 0
        # Quick confirmation beep
        def _beep():
            try:
                import winsound
                winsound.Beep(600, 200)  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                speak("You're back! Stay alert.", block=True)
            except Exception:
                pass
        threading.Thread(target=_beep, daemon=True).start()

    def _on_yawn(self) -> None:
        """Called when yawning detected — gentle warning."""
        self.after(0, lambda: self._log("🥱 Yawning detected! Consider taking a break."))
        # Single short beep for yawn
        def _yawn_beep():
            try:
                import winsound
                winsound.Beep(800, 300)  # type: ignore[attr-defined]
            except Exception:
                pass
        threading.Thread(target=_yawn_beep, daemon=True).start()

    def _on_drowsy_error(self, msg: str) -> None:
        """Called when drowsiness detection encounters an error."""
        self.after(0, lambda: self._log(f"❌ Drowsiness error: {msg}"))
        # Reset the toggle state
        self._drowsiness_active = False
        self.after(0, lambda: self._drowsy_btn.configure(
            text="😴 DROWSINESS OFF", fg_color=COLOR_BG_CARD2,
            border_color=COLOR_BORDER,
        ))
        self.after(0, lambda: self.lbl_drowsy_status.configure(text=""))

    def _update_drowsiness_ui(self) -> None:
        """Update drowsiness status in the status bar."""
        if not self._drowsiness_active or not self._drowsiness_detector:
            return
        d = self._drowsiness_detector
        ear = d.current_ear  # type: ignore[union-attr]
        if d.is_drowsy:  # type: ignore[union-attr]
            self.lbl_drowsy_status.configure(
                text=f"😴 EAR: {ear:.2f} │ DROWSY!",
                text_color=COLOR_RED,
            )
        elif ear > 0:
            self.lbl_drowsy_status.configure(
                text=f"👁 EAR: {ear:.2f} │ Alert",
                text_color=COLOR_GREEN,
            )
        else:
            self.lbl_drowsy_status.configure(
                text="👁 No face", text_color=COLOR_TEXT_MUTED,
            )
        self.after(300, self._update_drowsiness_ui)

    # ================================================================
    # LOG HELPER
    # ================================================================
    def _log(self, message: str) -> None:
        """Append a styled message to the chat log."""
        self.chat_log.configure(state="normal")

        # Add timestamp prefix
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.chat_log.insert("end", f"[{ts}] {message}\n")
        self.chat_log.see("end")
        self.chat_log.configure(state="disabled")

        self._msg_count += 1
        self.chat_count_label.configure(text=f"{self._msg_count} messages")

    # ================================================================
    # CLEANUP
    # ================================================================
    def _on_close(self) -> None:
        try:
            self.car.send_command("stop")
        except Exception:
            pass
        try:
            self.car.disconnect()
        except Exception:
            pass
        self.destroy()


# ============================================================
# ENTRY POINT
# ============================================================
def launch_gui() -> None:
    """Launch the GUI application."""
    app = CarControlApp()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()

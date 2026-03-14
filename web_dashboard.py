"""
web_dashboard.py
----------------
Flask + SocketIO web dashboard for the AI RC Car.
Mobile-friendly responsive UI with real-time sensor updates.
Control the car from any device on the same network!
"""

import json
import threading
import time
import os
from typing import Optional

try:
    from flask import Flask, render_template, request, jsonify  # type: ignore[import]
    from flask_socketio import SocketIO, emit  # type: ignore[import]
except ImportError:
    Flask = None
    SocketIO = None

from mqtt_client import CarMqttClient  # type: ignore[import]
from ai_assistant import ask_ai, extract_action, get_clean_reply  # type: ignore[import]


# ============================================================
# FLASK APP SETUP
# ============================================================
app = None
socketio = None
_car: Optional[CarMqttClient] = None


def create_app(car: CarMqttClient):
    """Create and configure the Flask app."""
    global app, socketio, _car
    _car = car

    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)  # type: ignore[misc]
    app.config["SECRET_KEY"] = "aicar-secret-2024"
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")  # type: ignore[misc]

    # ---- Routes ----
    @app.route("/")
    def index():
        return render_template("dashboard.html")

    @app.route("/api/sensors")
    def api_sensors():
        return jsonify(_car.sensor_data if _car else {})

    @app.route("/api/command", methods=["POST"])
    def api_command():
        data = request.get_json() or {}
        cmd = data.get("command", "").strip().lower()
        if cmd and _car:
            _car.send_command(cmd)
            return jsonify({"ok": True, "command": cmd})
        return jsonify({"ok": False, "error": "No command"}), 400

    @app.route("/api/mode", methods=["POST"])
    def api_mode():
        data = request.get_json() or {}
        mode = data.get("mode", "").strip().lower()
        if mode in ("manual", "auto", "park") and _car:
            _car.send_mode(mode)
            return jsonify({"ok": True, "mode": mode})
        return jsonify({"ok": False, "error": "Invalid mode"}), 400

    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        data = request.get_json() or {}
        question = data.get("message", "").strip()
        if not question:
            return jsonify({"ok": False, "error": "No message"}), 400
        answer = ask_ai(question,
                        sensor_data=_car.sensor_data if _car else None,
                        car_online=_car.car_online if _car else False)
        if answer:
            action = extract_action(answer)
            if action and _car:
                _car.send_command(action)
            clean = get_clean_reply(answer)
            return jsonify({"ok": True, "reply": clean, "action": action})
        return jsonify({"ok": False, "error": "AI unavailable"}), 500

    # ---- WebSocket events ----
    @socketio.on("connect")
    def on_connect():
        print("[WEB] Client connected")
        if _car:
            emit("sensors", _car.sensor_data)

    @socketio.on("command")
    def on_command(data):
        cmd = data.get("command", "").strip().lower()
        if cmd and _car:
            _car.send_command(cmd)
            emit("command_ack", {"command": cmd})

    @socketio.on("mode")
    def on_mode(data):
        mode = data.get("mode", "").strip().lower()
        if mode in ("manual", "auto", "park") and _car:
            _car.send_mode(mode)
            emit("mode_ack", {"mode": mode})

    @socketio.on("chat")
    def on_chat(data):
        question = data.get("message", "").strip()
        if not question:
            return
        answer = ask_ai(question,
                        sensor_data=_car.sensor_data if _car else None,
                        car_online=_car.car_online if _car else False)
        if answer:
            action = extract_action(answer)
            if action and _car:
                _car.send_command(action)
            clean = get_clean_reply(answer)
            emit("chat_reply", {"reply": clean, "action": action})
        else:
            emit("chat_reply", {"reply": "Sorry, AI is unavailable right now.", "action": None})

    return app, socketio


# ============================================================
# BACKGROUND SENSOR BROADCAST
# ============================================================
def _sensor_broadcast_loop():
    """Broadcast sensor data to all connected WebSocket clients."""
    while True:
        time.sleep(0.3)
        if socketio and _car:
            data = dict(_car.sensor_data)
            data["car_online"] = _car.car_online
            data["mqtt_connected"] = _car.connected
            socketio.emit("sensors", data)


# ============================================================
# START WEB DASHBOARD
# ============================================================
def start_web_dashboard(car: CarMqttClient, host: str = "0.0.0.0", port: int = 5000):
    """Start the web dashboard server."""
    if Flask is None or SocketIO is None:
        print("[WEB] Flask/SocketIO not installed!")
        print("[WEB] Install: pip install flask flask-socketio")
        return

    create_app(car)

    # Start sensor broadcast thread
    broadcast = threading.Thread(target=_sensor_broadcast_loop, daemon=True)
    broadcast.start()

    print(f"\n{'='*50}")
    print(f"  🌐 Web Dashboard starting on http://{host}:{port}")
    print(f"  📱 Open on your phone to control the car!")
    print(f"{'='*50}\n")

    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)  # type: ignore[union-attr]

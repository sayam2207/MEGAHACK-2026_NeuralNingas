"""
mqtt_client.py
--------------
MQTT communication layer for the AI RC Car.
Handles connection, publishing commands/modes, and receiving
sensor data and status updates from ESP32.

Compatible with paho-mqtt v2.x (CallbackAPIVersion.VERSION2).
"""

import json
import threading
import time
from typing import Any, Callable, Optional

import paho.mqtt.client as mqtt  # type: ignore[import]
from paho.mqtt.enums import CallbackAPIVersion  # type: ignore[import]

from config import (  # type: ignore[import]
    MQTT_BROKER, MQTT_PORT, MQTT_CLIENT_ID,
    TOPIC_COMMAND, TOPIC_MODE,
    TOPIC_SENSORS, TOPIC_STATUS,
)


class CarMqttClient:
    """Thread-safe MQTT client for the AI RC Car."""

    def __init__(
        self,
        on_sensors: Optional[Callable[[dict], None]] = None,
        on_status: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.on_sensors = on_sensors
        self.on_status = on_status

        # paho-mqtt v2 requires CallbackAPIVersion
        self._client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=MQTT_CLIENT_ID,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self._lock = threading.Lock()
        self._connected = False
        self._reconnect_active = False  # guard for reconnect thread

        # Latest sensor snapshot (updated from MQTT)
        self.sensor_data: dict[str, Any] = {
            "front": 999, "back": 999, "left": 999, "right": 999,
            "mode": "manual", "speed": 200,
        }
        self.car_status: str = "Waiting for car..."
        self.car_online: bool = False

    # ----------------------------------------------------------------
    # MQTT callbacks (paho v2 signature: 5 params)
    # ----------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self._connected = True
            self._reconnect_active = False
            client.subscribe(TOPIC_SENSORS)
            client.subscribe(TOPIC_STATUS)
            print("[MQTT] Connected and subscribed.")
        else:
            print(f"[MQTT] Connection failed (reason_code={reason_code})")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self._connected = False
        print(f"[MQTT] Disconnected (reason_code={reason_code}).")
        # Auto-reconnect in background
        self._start_reconnect()

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        raw = msg.payload.decode("utf-8", errors="ignore").strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"raw": raw}

        if topic == TOPIC_SENSORS:
            self.sensor_data = data
            self.car_online = True
            if self.on_sensors:
                try:
                    self.on_sensors(data)  # type: ignore[misc]
                except Exception as e:
                    print(f"[MQTT] Sensor callback error: {e}")

        elif topic == TOPIC_STATUS:
            status = data.get("status", raw)
            self.car_status = str(status) if status is not None else raw
            if self.on_status:
                try:
                    self.on_status(data)  # type: ignore[misc]
                except Exception as e:
                    print(f"[MQTT] Status callback error: {e}")

    # ----------------------------------------------------------------
    # Auto-reconnect with exponential backoff
    # ----------------------------------------------------------------
    def _start_reconnect(self) -> None:
        """Spawn a background thread to reconnect if not already running."""
        if self._reconnect_active:
            return
        self._reconnect_active = True
        threading.Thread(target=self._reconnect_loop, daemon=True).start()

    def _reconnect_loop(self) -> None:
        """Try to reconnect with exponential backoff (2s → 4s → 8s → ... max 30s)."""
        delay = 2
        while not self._connected and self._reconnect_active:
            print(f"[MQTT] Reconnecting in {delay}s...")
            time.sleep(delay)
            try:
                self._client.reconnect()
                print("[MQTT] Reconnect attempt sent.")
                # Wait a bit for the on_connect callback
                time.sleep(2)
                if self._connected:
                    print("[MQTT] Reconnected successfully!")
                    return
            except Exception as e:
                print(f"[MQTT] Reconnect failed: {e}")
            delay = min(delay * 2, 30)
        self._reconnect_active = False

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------
    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self, keepalive: int = 60) -> None:
        """Connect to broker and start background network loop."""
        with self._lock:
            if self._connected:
                return
            print(f"[MQTT] Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
            self._client.connect(MQTT_BROKER, MQTT_PORT, keepalive=keepalive)
            self._client.loop_start()

    def disconnect(self) -> None:
        """Gracefully disconnect."""
        with self._lock:
            self._reconnect_active = False  # stop auto-reconnect
            try:
                self._client.loop_stop()
            except Exception:
                pass
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._connected = False

    def send_command(self, command: str) -> None:
        """Publish a movement/action command to the car."""
        cmd = command.strip().lower()
        if not cmd:
            return
        self._ensure_connected()
        self._client.publish(TOPIC_COMMAND, cmd, qos=0)
        print(f"[MQTT] → command: {cmd}")

    def send_mode(self, mode: str) -> None:
        """Publish a mode change (manual, auto, park)."""
        m = mode.strip().lower()
        if m not in ("manual", "auto", "park"):
            print(f"[MQTT] Invalid mode: {m}")
            return
        self._ensure_connected()
        self._client.publish(TOPIC_MODE, m, qos=0)
        print(f"[MQTT] → mode: {m}")

    def _ensure_connected(self) -> None:
        if not self._connected:
            try:
                self.connect()
            except Exception as e:
                print(f"[MQTT] Connection failed: {e}")

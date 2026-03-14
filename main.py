"""
main.py
-------
Entry point for the AI RC Car Python Controller.

Orchestrates:
  - MQTT connection to ESP32
  - Voice command mode
  - Typed command mode (with AI, shortcuts, dashboard)
"""

import sys
import threading
import time

from config import KEYBOARD_SHORTCUTS  # type: ignore[import]
from mqtt_client import CarMqttClient  # type: ignore[import]
from ai_assistant import speak, tts_available  # type: ignore[import]
from voice_control import run_voice_loop, run_typed_loop  # type: ignore[import]
from dashboard import (  # type: ignore[import]
    clear_screen, print_banner, print_controls, print_dashboard,
    log_info, log_success, log_error, log_warn, log_car,
)


# ============================================================
# MQTT CALLBACKS
# ============================================================
def on_status(data: dict) -> None:
    """Handle status messages from the car."""
    status = data.get("status", "")
    log_car(f"Status: {status}")

    # Speak important events
    if "obstacle" in status.lower() or "blocked" in status.lower():
        speak("Warning, obstacle detected.", block=False)
    elif "parked" in status.lower() or "complete" in status.lower():
        speak("Parking complete.", block=False)
    elif "stuck" in status.lower():
        speak("Car is stuck.", block=False)


def on_sensors(data: dict) -> None:
    """Handle sensor updates (silent — just stored in mqtt_client)."""
    pass  # Data auto-stored in car.sensor_data


# ============================================================
# DASHBOARD BACKGROUND THREAD
# ============================================================
def dashboard_thread(car: CarMqttClient, interval: float = 5.0) -> None:
    """Periodically print sensor dashboard (background)."""
    while True:
        time.sleep(interval)
        if car.car_online:
            print_dashboard(car.sensor_data, car.car_status)


# ============================================================
# MAIN
# ============================================================
def main() -> None:
    clear_screen()
    print_banner()
    print()

    # --- MQTT Setup ---
    log_info("Initializing MQTT connection...")
    car = CarMqttClient(
        on_sensors=on_sensors,
        on_status=on_status,
    )

    try:
        car.connect()
    except Exception as e:
        log_error(f"MQTT connection failed: {e}")
        log_warn("Continuing in offline mode — commands won't reach the car.")

    # Wait briefly for connection
    for _ in range(10):
        if car.connected:
            break
        time.sleep(0.5)

    if car.connected:
        log_success("MQTT connected!")
    else:
        log_warn("MQTT not connected. Continuing anyway...")

    # --- Start dashboard background thread ---
    dash = threading.Thread(target=dashboard_thread, args=(car,), daemon=True)
    dash.start()

    # --- Mode Selection ---
    print_controls()
    print(
        "  Choose your control method:\n"
        "    [1] Typed commands (keyboard + AI)\n"
        "    [2] Voice commands (microphone + AI)\n"
    )

    while True:
        choice = input("  Enter 1 or 2: ").strip()
        if choice == "1":
            log_info("Starting typed command mode...\n")
            try:
                run_typed_loop(car)
            except KeyboardInterrupt:
                pass
            break
        elif choice == "2":
            log_info("Starting voice command mode...\n")
            try:
                run_voice_loop(car)
            except ImportError as e:
                log_error(f"Voice mode not available: {e}")
                log_warn("Falling back to typed mode.\n")
                run_typed_loop(car)
            except KeyboardInterrupt:
                pass
            break
        else:
            print("  Please enter 1 or 2.")

    # --- Cleanup ---
    log_info("Shutting down...")
    car.send_command("stop")
    time.sleep(0.3)
    car.disconnect()
    log_success("Goodbye!")


if __name__ == "__main__":
    if "--gui" in sys.argv:
        from gui_app import launch_gui  # type: ignore[import]
        launch_gui()
    elif "--web" in sys.argv:
        # Start web dashboard with MQTT
        from mqtt_client import CarMqttClient  # type: ignore[import]
        from web_dashboard import start_web_dashboard  # type: ignore[import]
        import time as _t

        car = CarMqttClient(
            on_sensors=on_sensors,
            on_status=on_status,
        )
        try:
            car.connect()
        except Exception as e:
            log_error(f"MQTT connection failed: {e}")
        for _ in range(10):
            if car.connected:
                break
            _t.sleep(0.5)
        if car.connected:
            log_success("MQTT connected!")
        else:
            log_warn("MQTT not connected. Web dashboard will start anyway.")
        start_web_dashboard(car)
    else:
        main()

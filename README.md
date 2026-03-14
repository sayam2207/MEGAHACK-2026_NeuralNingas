# 🚗 AI RC Car — IoT Project

An AI-powered RC car controlled via **voice commands**, **typed commands**, **web dashboard**, **Blynk IoT app**, or **autonomous modes**, using an **ESP32** microcontroller and a **Python AI brain** connected over **MQTT**.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Voice Control** | Speak commands: "Forward", "Stop", "Auto Park" |
| **Voice Feedback** 🆕 | Car talks back with personality-driven responses |
| **Car Personality** 🆕 | Persistent memory, mood system, contextual greetings |
| **AI Assistant** | Ask any question — powered by OpenRouter (GPT-3.5/4) |
| **Auto Mode** | Autonomous obstacle avoidance using 4 ultrasonic sensors |
| **Auto Parking** | Detect parallel parking gap + park automatically |
| **Premium GUI** | Cyberpunk-themed desktop controller with animated sensors |
| **Web Dashboard** 🆕 | Control from phone! Real-time sensors + AI chat via browser |
| **Blynk IoT** 🆕 | Mobile app control with joystick, gauges, and terminal |
| **Drowsiness Detection** 🆕 | Laptop camera monitors eyes — auto-stops car if drowsy |
| **Safety System** | Auto-stop on obstacle detection in all modes |

---

## 🔧 Hardware

### Components
- ESP32 DevKit V1 (30-pin)
- L298N Motor Driver (dual H-bridge)
- 4x HC-SR04 Ultrasonic Sensors
- Buck Converter (power regulation)
- DC Motors (2x drive + steering, or 4WD)

### Wiring

| Component | ESP32 GPIO | Notes |
|-----------|-----------|-------|
| **L298N Motor Driver** | | |
| IN1 (Motor A dir) | GPIO 27 | |
| IN2 (Motor A dir) | GPIO 26 | |
| IN3 (Motor B dir) | GPIO 25 | |
| IN4 (Motor B dir) | GPIO 33 | |
| ENA (Motor A PWM) | GPIO 14 | Speed control |
| ENB (Motor B PWM) | GPIO 12 | Speed control |
| **Ultrasonic Sensors** | | |
| Front TRIG / ECHO | GPIO 13 / 15 | |
| Back TRIG / ECHO | GPIO 2 / 4 | |
| Left TRIG / ECHO | GPIO 32 / 35 | GPIO 35 = input-only |
| Right TRIG / ECHO | GPIO 22 / 23 | |

---

## 📦 Project Structure

```
IoT Project/
├── esp32/
│   └── main.ino          # ESP32 firmware (Arduino + Blynk)
├── config.py             # Centralized configuration
├── mqtt_client.py        # MQTT communication layer
├── ai_assistant.py       # AI/GPT integration + TTS
├── voice_control.py      # Voice + typed command loops
├── personality.py        # Car personality + persistent memory
├── drowsiness.py         # Drowsiness detection (camera)
├── dashboard.py          # Terminal UI + logging
├── gui_app.py            # Premium desktop GUI
├── web_dashboard.py      # Flask web dashboard server
├── templates/
│   └── dashboard.html    # Web dashboard HTML
├── static/
│   ├── style.css         # Web dashboard CSS
│   └── app.js            # Web dashboard JavaScript
├── main.py               # Entry point
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

---

## 🚀 Setup

### 1. ESP32 Firmware

1. Install [Arduino IDE](https://www.arduino.cc/en/software)
2. Add ESP32 Board Package:
   - **File → Preferences → Additional Board URLs:**
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
   - **Tools → Boards Manager → search "esp32" → Install**
3. Install Arduino libraries:
   - `PubSubClient` (by Nick O'Leary)
   - `ArduinoJson` (by Benoit Blanchon)
   - `Blynk` (by Blynk Inc.) — **only if using Blynk IoT**
4. Open `esp32/main.ino`
5. Update `WIFI_SSID` and `WIFI_PASSWORD`
6. **Board settings:** ESP32 Dev Module, 921600 upload speed, 240MHz CPU
7. Upload to ESP32

### 2. Python Controller

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### PyAudio on Windows
If `pyaudio` fails to install:
```bash
pip install pipwin
pipwin install pyaudio
```

### 3. API Key (for AI chat)
Set the `OPENROUTER_API_KEY` environment variable:
```bash
set OPENROUTER_API_KEY=your-key-here
```
Or edit `config.py` directly.

### 4. Blynk IoT Setup (Optional)

1. Go to [https://blynk.cloud](https://blynk.cloud) → create account
2. **Create a Template** named "AI RC Car" with ESP32 + WiFi
3. **Add Datastreams** (Virtual Pins):

   | Pin | Name | Type | Range | Widget |
   |-----|------|------|-------|--------|
   | V0 | Movement | Integer | 0–4 | Joystick / Buttons |
   | V1 | Mode | Integer | 1–3 | Segmented Switch |
   | V2 | Speed | Integer | 0–255 | Slider |
   | V3 | Front Dist | Double | 0–400 | Gauge |
   | V4 | Back Dist | Double | 0–400 | Gauge |
   | V5 | Left Dist | Double | 0–400 | Gauge |
   | V6 | Right Dist | Double | 0–400 | Gauge |
   | V7 | E-Stop | Integer | 0–1 | Button |
   | V8 | Status | String | — | Terminal |

4. **Create a Device** from the template
5. Copy `BLYNK_TEMPLATE_ID`, `BLYNK_TEMPLATE_NAME`, and `BLYNK_AUTH_TOKEN`
6. Uncomment and paste into `esp32/main.ino` (lines 46–48)
7. Re-upload firmware

---

## 🎮 Usage

### GUI Mode (Recommended)
```bash
python main.py --gui
```

### Web Dashboard (Control from Phone!)
```bash
python main.py --web
```
Then open `http://<your-pc-ip>:5000` on your phone browser.

### Terminal Mode
```bash
python main.py
```

Choose **typed** or **voice** mode, then:

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| W | Forward |
| S | Backward |
| A | Left |
| D | Right |
| X | Stop |
| F | Full Speed |
| G | Slow Speed |
| 1 | Manual Mode |
| 2 | Auto Mode |
| 3 | Park Mode |

### Special Commands
| Command | Action |
|---------|--------|
| `voice` | Switch to voice control |
| `dash` | Show sensor dashboard |
| `help` | Show controls |
| `quit` | Exit |
| *anything else* | Send to AI assistant |

---

## 🆕 New Features Guide

### 🔊 Voice Feedback
The car talks back when you press buttons or issue commands! Each action gets a personality-driven spoken response. Toggle voice on/off with the **🔊 VOICE ON** button in the GUI.

### 🧠 Car Personality & Memory
The car remembers you across sessions! It tracks session count, greets you by time of day, and has moods (neutral → happy → energetic → tired). Data is stored in `car_memory.json`. Tell the AI your name and it'll remember you.

### 😴 Drowsiness Detection
Click **😴 DROWSINESS** in the GUI to start camera-based eye monitoring. Uses MediaPipe FaceMesh to compute Eye Aspect Ratio (EAR). If your eyes close for too long → car auto-stops + voice alert! Also detects yawning.

### 📱 Blynk IoT App
After setup (see above), open the Blynk app on your phone. Use the joystick to drive, slider for speed, and gauges show live sensor data. V7 button = emergency stop.

---

## 📡 MQTT Topics

| Direction | Topic | Payload |
|-----------|-------|---------|
| Python → ESP32 | `aicar/command` | `forward`, `backward`, `left`, `right`, `stop`, `speed_full`, `speed_slow` |
| Python → ESP32 | `aicar/mode` | `manual`, `auto`, `park` |
| ESP32 → Python | `aicar/sensors` | `{front, back, left, right, mode, speed}` |
| ESP32 → Python | `aicar/status` | `{status, time}` |

---

## 🅿️ Auto-Parking Algorithm

1. **Say "Auto Park"** or press `3`
2. Car enters `PARK_SCAN` — drives forward slowly
3. Right ultrasonic sensor detects a gap (40–120 cm)
4. Gap size estimated from duration × speed
5. Car pulls forward to align (`PARK_FOUND`)
6. Differential reverse-right into spot (`PARK_REVERSE_IN`)
7. Fine-adjustment using all 4 sensors (`PARK_ADJUST`)
8. Car stops and announces **"Parked!"** (`PARK_DONE`)

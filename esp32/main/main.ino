/*
  ============================================================
  AI RC CAR — ESP32 Firmware
  ============================================================
  Hardware:
    - ESP32 DevKit V1 (30-pin)
    - L298N Motor Driver (dual H-bridge)
    - 4x HC-SR04 Ultrasonic Sensors (Front, Back, Left, Right)
    - Buck Converter (power regulation)

  Features:
    - Manual Mode   — MQTT commands from Python AI brain
    - Auto Mode     — autonomous obstacle avoidance (4 sensors)
    - Park Mode     — detect gap on right side + parallel park
    - Heartbeat     — periodic alive signal to Python
    - Emergency Stop — works in ALL modes

  MQTT Broker: broker.hivemq.com:1883 (free, public)
  ============================================================

  PIN LAYOUT (30-pin ESP32 DevKit V1):
  -----------------------------------------------------------
  L298N Motor Driver:
    IN1  -> GPIO 27   (Motor A direction 1)
    IN2  -> GPIO 26   (Motor A direction 2)
    IN3  -> GPIO 25   (Motor B direction 1)
    IN4  -> GPIO 33   (Motor B direction 2)
    ENA  -> GPIO 14   (Motor A speed — PWM)
    ENB  -> GPIO 12   (Motor B speed — PWM)

  Ultrasonic Sensors (HC-SR04):
    FRONT: TRIG -> GPIO 13, ECHO -> GPIO 15
    BACK:  TRIG -> GPIO 2,  ECHO -> GPIO 4
    LEFT:  TRIG -> GPIO 32, ECHO -> GPIO 35  (input-only)
    RIGHT: TRIG -> GPIO 22, ECHO -> GPIO 23
  -----------------------------------------------------------
*/

// ============================================================
// LIBRARIES
// ============================================================
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>



// ============================================================
// CONFIGURATION — CHANGE THESE FOR YOUR NETWORK
// ============================================================
const char* WIFI_SSID      = "NEO 10R";
const char* WIFI_PASSWORD  = "sayam2207";

const char* MQTT_BROKER    = "broker.hivemq.com";
const int   MQTT_PORT      = 1883;
const char* MQTT_CLIENT_ID = "esp32_ai_car_001";  // must be unique per device

// MQTT Topics — Python publishes, ESP32 subscribes:
const char* TOPIC_COMMAND  = "aicar/command";   // movement commands
const char* TOPIC_MODE     = "aicar/mode";      // manual / auto / park

// MQTT Topics — ESP32 publishes, Python subscribes:
const char* TOPIC_SENSORS  = "aicar/sensors";   // ultrasonic JSON
const char* TOPIC_STATUS   = "aicar/status";    // status messages

// ============================================================
// MOTOR DRIVER PINS (L298N)
// ============================================================
#define MOTOR_A_IN1  27
#define MOTOR_A_IN2  26
#define MOTOR_B_IN3  25
#define MOTOR_B_IN4  33
#define MOTOR_A_ENA  14   // PWM — Motor A speed
#define MOTOR_B_ENB  12   // PWM — Motor B speed

// PWM configuration
#define PWM_CHANNEL_A   0
#define PWM_CHANNEL_B   1
#define PWM_FREQ        1000
#define PWM_RESOLUTION  8   // 8-bit → 0–255

// Speed presets
#define SPEED_FULL  200
#define SPEED_SLOW  100
#define SPEED_STOP  0

// ============================================================
// ULTRASONIC SENSOR PINS
// ============================================================
#define US_FRONT_TRIG  13
#define US_FRONT_ECHO  15
#define US_BACK_TRIG   2
#define US_BACK_ECHO   4
#define US_LEFT_TRIG   32
#define US_LEFT_ECHO   35   // GPIO 35 is input-only — perfect for ECHO
#define US_RIGHT_TRIG  22
#define US_RIGHT_ECHO  23

// Distance thresholds (cm)
#define DIST_DANGER    15    // emergency stop
#define DIST_SLOW      35    // reduce speed
#define DIST_PARK_MIN  40    // minimum gap for parking
#define DIST_PARK_MAX  120   // ignore very large openings

// ============================================================
// GLOBAL STATE
// ============================================================
WiFiClient   espClient;
PubSubClient mqttClient(espClient);

// --- Modes ---
enum CarMode { MODE_MANUAL, MODE_AUTO, MODE_PARK };
CarMode currentMode = MODE_MANUAL;

// --- Auto-parking state machine ---
enum ParkState {
  PARK_SCAN,         // driving forward, scanning right side for gap
  PARK_FOUND,        // gap found, aligning alongside front car
  PARK_REVERSE_IN,   // reversing into spot with differential steering
  PARK_ADJUST,       // fine-tuning position with all 4 sensors
  PARK_DONE          // parked successfully
};
ParkState parkState = PARK_SCAN;

// --- Sensor readings ---
float distFront = 999, distBack = 999, distLeft = 999, distRight = 999;

// --- Timing (all non-blocking via millis()) ---
unsigned long lastSensorPublish = 0;
unsigned long lastHeartbeat     = 0;

const unsigned long SENSOR_INTERVAL    = 200;    // ms
const unsigned long HEARTBEAT_INTERVAL = 5000;   // 5 s

// --- Auto-mode non-blocking timing ---
unsigned long autoActionStart = 0;
enum AutoStep { AUTO_DRIVE, AUTO_DECIDE, AUTO_TURN, AUTO_REVERSE };
AutoStep autoStep = AUTO_DRIVE;

// --- Park non-blocking timing ---
unsigned long parkTimer    = 0;
float  parkGapStart        = 0;
bool   parkMeasuringGap    = false;
int    parkReversePhase    = 0;

// --- Speed ---
int currentSpeed = SPEED_FULL;

// --- Last known movement direction (for safety checks) ---
enum MoveDir { DIR_NONE, DIR_FORWARD, DIR_BACKWARD, DIR_LEFT, DIR_RIGHT };
MoveDir lastDirection = DIR_NONE;

// ============================================================
// FORWARD DECLARATIONS
// ============================================================
void setupMotors();
void setupUltrasonics();
void connectWiFi();
void setupMQTT();
void reconnectMQTT();
void mqttCallback(char* topic, byte* payload, unsigned int length);
void readAllSensors();
void publishSensorData();
void publishStatus(const char* msg);
void moveForward(int speed);
void moveBackward(int speed);
void turnLeft(int speed);
void turnRight(int speed);
void stopCar();
void runAutoMode();
void runAutoParking();
void manualModeSafetyCheck();
float readUltrasonic(int trigPin, int echoPin);

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  Serial.println("\n\n========================================");
  Serial.println("   AI RC CAR — ESP32 Firmware v2.0");
  Serial.println("========================================");

  setupMotors();
  setupUltrasonics();
  connectWiFi();
  setupMQTT();

  Serial.println("[BOOT] All systems ready.");
  publishStatus("Car online. All systems ready.");


}

// ============================================================
// MAIN LOOP — fully non-blocking
// ============================================================
void loop() {
  // 1) MQTT keep-alive
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();

  // 2) Read sensors every loop iteration (they're fast)
  readAllSensors();

  // 3) Publish sensor data periodically
  unsigned long now = millis();
  if (now - lastSensorPublish >= SENSOR_INTERVAL) {
    publishSensorData();
    lastSensorPublish = now;
  }

  // 4) Heartbeat
  if (now - lastHeartbeat >= HEARTBEAT_INTERVAL) {
    mqttClient.publish(TOPIC_STATUS, "{\"heartbeat\":true}");
    lastHeartbeat = now;
  }

  // 5) Run mode-specific logic
  switch (currentMode) {
    case MODE_AUTO:   runAutoMode();           break;
    case MODE_PARK:   runAutoParking();         break;
    case MODE_MANUAL: manualModeSafetyCheck();  break;
  }



  delay(20);  // small yield to prevent watchdog reset
}

// ============================================================
// MOTOR SETUP
// ============================================================
void setupMotors() {
  pinMode(MOTOR_A_IN1, OUTPUT);
  pinMode(MOTOR_A_IN2, OUTPUT);
  pinMode(MOTOR_B_IN3, OUTPUT);
  pinMode(MOTOR_B_IN4, OUTPUT);

  // ESP32 Arduino Core v3.x PWM API
  ledcAttach(MOTOR_A_ENA, PWM_FREQ, PWM_RESOLUTION);
  ledcAttach(MOTOR_B_ENB, PWM_FREQ, PWM_RESOLUTION);

  stopCar();
  Serial.println("[MOTOR] L298N initialized.");
}

// ============================================================
// MOTOR CONTROL
// ============================================================
void moveForward(int speed) {
  digitalWrite(MOTOR_A_IN1, HIGH); digitalWrite(MOTOR_A_IN2, LOW);
  digitalWrite(MOTOR_B_IN3, LOW); digitalWrite(MOTOR_B_IN4, HIGH); // Inverted B
  ledcWrite(MOTOR_A_ENA, speed);
  ledcWrite(MOTOR_B_ENB, speed);
  lastDirection = DIR_FORWARD;
}

void moveBackward(int speed) {
  digitalWrite(MOTOR_A_IN1, LOW); digitalWrite(MOTOR_A_IN2, HIGH);
  digitalWrite(MOTOR_B_IN3, HIGH); digitalWrite(MOTOR_B_IN4, LOW); // Inverted B
  ledcWrite(MOTOR_A_ENA, speed);
  ledcWrite(MOTOR_B_ENB, speed);
  lastDirection = DIR_BACKWARD;
}

void turnLeft(int speed) {
  // Left motor backward, Right motor forward → pivot left
  digitalWrite(MOTOR_A_IN1, LOW);  digitalWrite(MOTOR_A_IN2, HIGH);
  digitalWrite(MOTOR_B_IN3, LOW); digitalWrite(MOTOR_B_IN4, HIGH); // Inverted B
  ledcWrite(MOTOR_A_ENA, speed);
  ledcWrite(MOTOR_B_ENB, speed);
  lastDirection = DIR_LEFT;
}

void turnRight(int speed) {
  // Left motor forward, Right motor backward → pivot right
  digitalWrite(MOTOR_A_IN1, HIGH); digitalWrite(MOTOR_A_IN2, LOW);
  digitalWrite(MOTOR_B_IN3, HIGH);  digitalWrite(MOTOR_B_IN4, LOW); // Inverted B
  ledcWrite(MOTOR_A_ENA, speed);
  ledcWrite(MOTOR_B_ENB, speed);
  lastDirection = DIR_RIGHT;
}

void stopCar() {
  digitalWrite(MOTOR_A_IN1, LOW); digitalWrite(MOTOR_A_IN2, LOW);
  digitalWrite(MOTOR_B_IN3, LOW); digitalWrite(MOTOR_B_IN4, LOW);
  ledcWrite(MOTOR_A_ENA, 0);
  ledcWrite(MOTOR_B_ENB, 0);
  lastDirection = DIR_NONE;
}

// Differential reverse-right for parking (left motor faster)
void reverseRight(int baseSpeed) {
  digitalWrite(MOTOR_A_IN1, LOW); digitalWrite(MOTOR_A_IN2, HIGH);
  digitalWrite(MOTOR_B_IN3, HIGH); digitalWrite(MOTOR_B_IN4, LOW); // Inverted B
  ledcWrite(MOTOR_A_ENA, min(255, baseSpeed + 30));  // left faster
  ledcWrite(MOTOR_B_ENB, max(0,   baseSpeed - 30));  // right slower
  lastDirection = DIR_BACKWARD;
}

// ============================================================
// ULTRASONIC SENSORS
// ============================================================
void setupUltrasonics() {
  pinMode(US_FRONT_TRIG, OUTPUT); pinMode(US_FRONT_ECHO, INPUT);
  pinMode(US_BACK_TRIG,  OUTPUT); pinMode(US_BACK_ECHO,  INPUT);
  pinMode(US_LEFT_TRIG,  OUTPUT); pinMode(US_LEFT_ECHO,  INPUT);
  pinMode(US_RIGHT_TRIG, OUTPUT); pinMode(US_RIGHT_ECHO, INPUT);
  Serial.println("[SENSOR] 4x HC-SR04 initialized.");
}

float readUltrasonic(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 30000);  // 30 ms timeout
  if (duration == 0) return 999.0;  // no echo → very far / error
  return (duration * 0.0343) / 2.0;
}

void readAllSensors() {
  distFront = readUltrasonic(US_FRONT_TRIG, US_FRONT_ECHO);
  distBack  = readUltrasonic(US_BACK_TRIG,  US_BACK_ECHO);
  distLeft  = readUltrasonic(US_LEFT_TRIG,  US_LEFT_ECHO);
  distRight = readUltrasonic(US_RIGHT_TRIG, US_RIGHT_ECHO);
}

// ============================================================
// WIFI
// ============================================================
void connectWiFi() {
  Serial.printf("[WIFI] Connecting to %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\n[WIFI] Connected — IP: %s\n", WiFi.localIP().toString().c_str());
}

// ============================================================
// MQTT
// ============================================================
void setupMQTT() {
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  reconnectMQTT();
}

void reconnectMQTT() {
  int attempts = 0;
  while (!mqttClient.connected() && attempts < 5) {
    Serial.print("[MQTT] Connecting... ");
    if (mqttClient.connect(MQTT_CLIENT_ID)) {
      Serial.println("OK");
      mqttClient.subscribe(TOPIC_COMMAND);
      mqttClient.subscribe(TOPIC_MODE);
      publishStatus("MQTT connected.");
    } else {
      Serial.printf("FAIL (rc=%d), retry in 3s\n", mqttClient.state());
      delay(3000);
    }
    attempts++;
  }
}

// ============================================================
// MQTT CALLBACK — receive commands from Python AI
// ============================================================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  char msg[length + 1];
  memcpy(msg, payload, length);
  msg[length] = '\0';

  Serial.printf("[MQTT] %s → %s\n", topic, msg);

  // --- MODE changes ---
  if (strcmp(topic, TOPIC_MODE) == 0) {
    if (strcmp(msg, "manual") == 0) {
      currentMode = MODE_MANUAL;
      autoStep = AUTO_DRIVE;
      stopCar();
      publishStatus("Mode: MANUAL");
    } else if (strcmp(msg, "auto") == 0) {
      currentMode = MODE_AUTO;
      autoStep = AUTO_DRIVE;
      publishStatus("Mode: AUTO (obstacle avoidance)");
    } else if (strcmp(msg, "park") == 0) {
      currentMode = MODE_PARK;
      parkState = PARK_SCAN;
      parkMeasuringGap = false;
      parkReversePhase = 0;
      publishStatus("Mode: PARKING");
    }
    return;
  }

  // --- COMMANDS ---
  if (strcmp(topic, TOPIC_COMMAND) == 0) {

    // Emergency stop works in ALL modes
    if (strcmp(msg, "stop") == 0) {
      stopCar();
      if (currentMode != MODE_MANUAL) {
        currentMode = MODE_MANUAL;
        publishStatus("EMERGENCY STOP — switched to manual.");
      }
      return;
    }

    // Speed commands work in ALL modes
    if (strcmp(msg, "speed_full") == 0) {
      currentSpeed = SPEED_FULL;
      // Immediately update motors if car is moving
      if (lastDirection != DIR_NONE) {
        ledcWrite(MOTOR_A_ENA, currentSpeed);
        ledcWrite(MOTOR_B_ENB, currentSpeed);
      }
      publishStatus("Speed → FULL (200)");
      return;
    }
    if (strcmp(msg, "speed_slow") == 0) {
      currentSpeed = SPEED_SLOW;
      // Immediately update motors if car is moving
      if (lastDirection != DIR_NONE) {
        ledcWrite(MOTOR_A_ENA, currentSpeed);
        ledcWrite(MOTOR_B_ENB, currentSpeed);
      }
      publishStatus("Speed → SLOW (100)");
      return;
    }

    // Other commands only in manual mode
    if (currentMode != MODE_MANUAL) {
      publishStatus("Command ignored — not in manual mode. Send 'stop' to override.");
      return;
    }

    if (strcmp(msg, "forward") == 0) {
      if (distFront > DIST_DANGER) {
        moveForward(currentSpeed);
      } else {
        publishStatus("BLOCKED: obstacle ahead!");
      }
    } else if (strcmp(msg, "backward") == 0) {
      if (distBack > DIST_DANGER) {
        moveBackward(currentSpeed);
      } else {
        publishStatus("BLOCKED: obstacle behind!");
      }
    } else if (strcmp(msg, "left") == 0) {
      turnLeft(currentSpeed);
    } else if (strcmp(msg, "right") == 0) {
      turnRight(currentSpeed);
    } else {
      Serial.printf("[MQTT] Unknown command: %s\n", msg);
    }
  }
}

// ============================================================
// MANUAL MODE — active safety (stop if obstacle appears)
// ============================================================
void manualModeSafetyCheck() {
  if (lastDirection == DIR_FORWARD && distFront <= DIST_DANGER) {
    stopCar();
    publishStatus("SAFETY: front obstacle — auto-stopped!");
  }
  if (lastDirection == DIR_BACKWARD && distBack <= DIST_DANGER) {
    stopCar();
    publishStatus("SAFETY: rear obstacle — auto-stopped!");
  }
}

// ============================================================
// AUTO MODE — non-blocking obstacle avoidance
// ============================================================
void runAutoMode() {
  unsigned long now = millis();
  int spd = currentSpeed;

  switch (autoStep) {

    case AUTO_DRIVE:
      if (distFront > DIST_SLOW) {
        moveForward(spd);
      } else if (distFront > DIST_DANGER) {
        moveForward(SPEED_SLOW);
      } else {
        stopCar();
        // Give sensors half a second to stabilize after sudden stop
        autoActionStart = now;
        autoStep = AUTO_DECIDE;
      }
      break;

    case AUTO_DECIDE:
      // Pause 400 ms then pick a direction based on side sensors
      if (now - autoActionStart >= 400) {
        if (distLeft > distRight && distLeft > DIST_SLOW) {
          turnLeft(spd);
          publishStatus("AUTO: Turning Left");
          autoStep = AUTO_TURN;
          autoActionStart = now;
        } else if (distRight > distLeft && distRight > DIST_SLOW) {
          turnRight(spd);
          publishStatus("AUTO: Turning Right");
          autoStep = AUTO_TURN;
          autoActionStart = now;
        } else {
          // Both sides blocked or dangerous -> Reverse
          moveBackward(spd);
          publishStatus("AUTO: Blocked sides, reversing...");
          autoStep = AUTO_REVERSE;
          autoActionStart = now;
        }
      }
      break;

    case AUTO_TURN:
      if (now - autoActionStart >= 500) {  // Turn for 500ms
        stopCar();
        autoStep = AUTO_DRIVE;
      }
      break;

    case AUTO_REVERSE:
      if (now - autoActionStart >= 600) {  // Reverse for 600ms
        stopCar();
        // After reversing, pick the side with MORE space to pivot towards
        if (distLeft > distRight) { 
          turnLeft(spd); 
          publishStatus("AUTO: Pivot Left");
        } else { 
          turnRight(spd); 
          publishStatus("AUTO: Pivot Right");
        }
        autoStep = AUTO_TURN;
        autoActionStart = now;
      }
      break;
  }
}

// ============================================================
// AUTO PARKING — non-blocking state machine
// ============================================================
void runAutoParking() {
  unsigned long now = millis();

  switch (parkState) {

    // --- SCAN: drive forward slowly, watch right sensor for gap ---
    case PARK_SCAN:
      if (distFront < DIST_DANGER) {
        stopCar();
        publishStatus("PARK: front blocked — waiting...");
        return;
      }
      moveForward(SPEED_SLOW);

      // Detect gap start
      if (!parkMeasuringGap && distRight > DIST_PARK_MIN && distRight < DIST_PARK_MAX) {
        parkMeasuringGap = true;
        parkGapStart = distRight;
        parkTimer = now;
        Serial.println("[PARK] Gap start detected on right.");
      }

      // Measure gap duration
      if (parkMeasuringGap) {
        unsigned long gapDuration = now - parkTimer;
        if (distRight < DIST_PARK_MIN / 2 || gapDuration > 3000) {
          parkMeasuringGap = false;
          float estMeters = gapDuration * 0.0003;
          Serial.printf("[PARK] Gap ended — %lums, ~%.2fm\n", gapDuration, estMeters);

          if (estMeters > 0.3 && gapDuration < 5000) {
            stopCar();
            publishStatus("PARK: spot found — starting maneuver.");
            parkTimer = now;
            parkState = PARK_FOUND;
          }
        }
      }
      break;

    // --- FOUND: pull forward past the spot to align ---
    case PARK_FOUND:
      moveForward(SPEED_SLOW);
      if (now - parkTimer >= 600) {
        stopCar();
        parkTimer = now;
        parkReversePhase = 0;
        parkState = PARK_REVERSE_IN;
        publishStatus("PARK: aligned — reversing in...");
      }
      break;

    // --- REVERSE IN: phase 0 = curve back-right, phase 1 = straight back ---
    case PARK_REVERSE_IN:
      if (distBack < DIST_DANGER) {
        stopCar();
        publishStatus("PARK: rear obstacle — aborting reverse!");
        parkTimer = now;
        parkState = PARK_ADJUST;
        return;
      }

      if (parkReversePhase == 0) {
        reverseRight(SPEED_SLOW);
        if (now - parkTimer >= 1200) {
          parkReversePhase = 1;
          parkTimer = now;
        }
      } else {
        moveBackward(SPEED_SLOW);
        if (now - parkTimer >= 800 || distBack < DIST_DANGER) {
          stopCar();
          parkTimer = now;
          parkState = PARK_ADJUST;
          publishStatus("PARK: adjusting position...");
        }
      }
      break;

    // --- ADJUST: fine-tune with all 4 sensors ---
    case PARK_ADJUST:
      if (now - parkTimer < 300) return;  // brief pause after reverse

      // Front/back centering
      if (distFront < distBack && distFront > DIST_DANGER) {
        moveBackward(SPEED_SLOW);
      } else if (distBack < distFront && distBack > DIST_DANGER) {
        moveForward(SPEED_SLOW);
      } else {
        stopCar();
      }

      // Side clearance
      if (distLeft < 10 && distRight >= 10) {
        turnRight(SPEED_SLOW);
      } else if (distRight < 10 && distLeft >= 10) {
        turnLeft(SPEED_SLOW);
      }

      // Done adjusting after 500 ms
      if (now - parkTimer >= 800) {
        stopCar();
        parkState = PARK_DONE;
      }
      break;

    // --- DONE ---
    case PARK_DONE:
      stopCar();
      publishStatus("PARK COMPLETE — car is parked!");
      Serial.println("[PARK] === DONE ===");
      publishSensorData();
      currentMode = MODE_MANUAL;
      break;
  }
}

// ============================================================
// MQTT PUBLISHING
// ============================================================
void publishSensorData() {
  StaticJsonDocument<256> doc;
  doc["front"]   = distFront;
  doc["back"]    = distBack;
  doc["left"]    = distLeft;
  doc["right"]   = distRight;
  doc["mode"]    = (currentMode == MODE_MANUAL) ? "manual" :
                   (currentMode == MODE_AUTO)   ? "auto"   : "park";
  doc["speed"]   = currentSpeed;

  char buf[256];
  serializeJson(doc, buf);
  mqttClient.publish(TOPIC_SENSORS, buf);


}

void publishStatus(const char* msg) {
  Serial.printf("[STATUS] %s\n", msg);
  StaticJsonDocument<256> doc;
  doc["status"] = msg;
  doc["time"]   = millis();
  char buf[256];
  serializeJson(doc, buf);
  mqttClient.publish(TOPIC_STATUS, buf);
}



/*
  ============================================================
  QUICK REFERENCE
  ============================================================

  Python → ESP32:
    aicar/command  →  forward | backward | left | right | stop |
                      speed_full | speed_slow
    aicar/mode     →  manual | auto | park

  ESP32 → Python:
    aicar/sensors  →  {front, back, left, right, mode, speed}
    aicar/status   →  {status, time}

  Arduino IDE Libraries:
    1. PubSubClient  — Nick O'Leary
    2. ArduinoJson   — Benoit Blanchon
    3. ESP32 Board Package

  Board Settings:
    Board:            ESP32 Dev Module
    Upload Speed:     921600
    CPU Frequency:    240 MHz
    Flash Size:       4 MB
    Partition Scheme: Default 4 MB with spiffs
  ============================================================
*/

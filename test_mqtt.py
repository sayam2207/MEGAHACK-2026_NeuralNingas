import paho.mqtt.client as mqtt
import time
import sys
from datetime import datetime

def on_connect(client, userdata, flags, rc):
    client.subscribe("aicar/command")

def on_message(client, userdata, msg):
    with open("mqtt_cmd_log.txt", "a") as f:
        ts = datetime.now().strftime("%H:%M:%S")
        f.write(f"[{ts}] {msg.payload.decode()}\n")

with open("mqtt_cmd_log.txt", "w") as f:
    f.write("")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect("broker.hivemq.com", 1883, 60)
client.loop_start()

time.sleep(15)
client.loop_stop()
sys.exit(0)

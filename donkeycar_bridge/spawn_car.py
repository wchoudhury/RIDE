import requests
import json

url = "http://localhost:9091"

spawn_msg = {
    "msg_type": "car_config",
    "body": {
        "car_name": "car1",
        "body_style": "donkey",
        "body_rgb": [255, 0, 0],
        "camera_fov": 75,
        "camera_angle_offset": 0,
        "drive_train_type": "DD",
        "racer_name": "Wafee",
        "max_speed": 5.0,
        "scale": 1.0
    }
}

try:
    response = requests.post(url, data=json.dumps(spawn_msg))
    print("✅ Car spawn request sent (probably worked if no crash in sim)")
except requests.exceptions.ConnectionError as e:
    print(f"⚠️ Spawn likely worked but got non-HTTP response: {e}")

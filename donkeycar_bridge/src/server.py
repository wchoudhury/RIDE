from flask import Flask, request, jsonify
import time

app = Flask(__name__)

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/api/drive", methods=["POST"])
def drive():
    data = request.get_json()
    steering = data.get("steering", 0.0)
    throttle = data.get("throttle", 0.0)
    print(f"Received: Steering={steering}, Throttle={throttle}")
    # TODO: GPIO/PWM motor control here
    return jsonify({"received": True})

@app.route("/api/telemetry", methods=["GET"])
def telemetry():
    return jsonify({
        "steering": 0.1,
        "throttle": 0.2,
        "timestamp": time.time()
    })

@app.route("/api/camera", methods=["GET"])
def camera():
    # Simulate camera response (base64 encoded image)
    dummy_image_b64 = ""  # leave blank or load from a sample image
    return jsonify({
        "image": dummy_image_b64
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8887)

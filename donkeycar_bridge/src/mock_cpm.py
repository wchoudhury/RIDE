import random

def init(name: str):
    print(f"[Mock CPM] Initialized with name: {name}")

class LogLevel:
    Info = "INFO"
    Warn = "WARN"
    Error = "ERROR"
    Debug = "DEBUG"

class Logging:
    @staticmethod
    def Instance():
        return Logging()

    def set_id(self, log_id):
        print(f"[Mock CPM] Log ID set to: {log_id}")

    def set_min_level(self, level):
        print(f"[Mock CPM] Log level set to: {level}")

    def write(self, level, message):
        print(f"[Mock CPM][{level}] {message}")

class ParameterReceiver:
    def __init__(self, vehicle_id=None):
        self.vehicle_id = vehicle_id
        self.last_cmd = {"throttle": 0.2, "steering": 0.0}

    def get_latest_command(self):
        self.last_cmd["steering"] = random.uniform(-1.0, 1.0)
        self.last_cmd["throttle"] = random.uniform(0.2, 0.5)
        print(f"[Mock CPM] Sending command: {self.last_cmd}")
        return self.last_cmd

    def send_state(self, state):
        print(f"[Mock CPM] Received state: {state}")

    def get_parameter_double(self, name):
        print(f"[Mock CPM] get_parameter_double({name}) → 1.0")
        return 1.0

    def get_parameter_int(self, name):
        print(f"[Mock CPM] get_parameter_int({name}) → 1")
        return 1

    def get_parameter_bool(self, name):
        print(f"[Mock CPM] get_parameter_bool({name}) → False")
        return False

class AsyncReader:
    def __init__(self, topic_name, callback=None):
        print(f"[Mock CPM] AsyncReader created for topic: {topic_name}")
        self.topic = topic_name
        self.callback = callback

class Writer:
    def __init__(self, topic_name):
        print(f"[Mock CPM] Writer created for topic: {topic_name}")
        self.topic = topic_name

    def write(self, message):
        print(f"[Mock CPM] Writing to topic {self.topic}: {message}")

class VehicleState:
    def __init__(self):
        self.vehicle_id = 0
        self.time_stamp = 0
        self.steering = 0.0
        self.velocity = 0.0

        class Pose:
            def __init__(self):
                self.x = 0.0
                self.y = 0.0
                self.yaw = 0.0

        self.pose = Pose()


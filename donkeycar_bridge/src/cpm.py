"""
Minimal CPM Python bindings for Donkeycar Bridge.
This replaces the missing compiled CPM Python bindings.
"""

import time
import threading
from typing import Dict, Any

def init(name: str):
    """Initialize CPM system with given name"""
    print(f"[CPM] Initialized with name: {name}")

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
        print(f"[CPM] Log ID set to: {log_id}")
    
    def set_min_level(self, level):
        print(f"[CPM] Log level set to: {level}")
    
    def write(self, level, message):
        print(f"[CPM][{level}] {message}")

class VehicleState:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.speed = 0.0

class ParameterReceiver:
    def __init__(self, vehicle_id=None):
        self.vehicle_id = vehicle_id
        self._running = False
        self._command_thread = None
        self._latest_command = {"throttle": 0.0, "steering": 0.0}
        
    def start(self):
        """Start the parameter receiver"""
        self._running = True
        self._command_thread = threading.Thread(target=self._command_loop)
        self._command_thread.start()
        print(f"[CPM] ParameterReceiver started for vehicle {self.vehicle_id}")
    
    def stop(self):
        """Stop the parameter receiver"""
        self._running = False
        if self._command_thread:
            self._command_thread.join()
        print(f"[CPM] ParameterReceiver stopped for vehicle {self.vehicle_id}")
    
    def _command_loop(self):
        """Background thread for receiving commands"""
        while self._running:
            # In real CPM, this would receive DDS messages
            # For now, generate test commands
            time.sleep(0.1)
    
    def get_latest_command(self):
        """Get the latest command from CPM system"""
        # This would normally come from DDS messages
        return self._latest_command
    
    def send_state(self, state: Dict[str, Any]):
        """Send vehicle state back to CPM system"""
        print(f"[CPM] Vehicle {self.vehicle_id} state: x={state.get('x', 0):.2f}, y={state.get('y', 0):.2f}, yaw={state.get('yaw', 0):.2f}")
    
    def get_parameter_double(self, name: str) -> float:
        """Get a double parameter from CPM"""
        defaults = {
            "vehicle_max_speed": 2.0,
            "steering_gain": 1.0,
            "throttle_gain": 1.0
        }
        value = defaults.get(name, 1.0)
        print(f"[CPM] get_parameter_double({name}) → {value}")
        return value
    
    def get_parameter_int(self, name: str) -> int:
        """Get an integer parameter from CPM"""
        defaults = {
            "vehicle_id": self.vehicle_id or 1,
            "update_rate": 50
        }
        value = defaults.get(name, 1)
        print(f"[CPM] get_parameter_int({name}) → {value}")
        return value
    
    def get_parameter_bool(self, name: str) -> bool:
        """Get a boolean parameter from CPM"""
        defaults = {
            "enable_logging": True,
            "simulation_mode": True
        }
        value = defaults.get(name, False)
        print(f"[CPM] get_parameter_bool({name}) → {value}")
        return value

class Timer:
    def __init__(self, period_ms: int):
        self.period_ms = period_ms
        self._callbacks = []
        self._running = False
        self._thread = None
    
    def start(self, callback):
        """Start timer with callback"""
        self._callbacks.append(callback)
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._timer_loop)
            self._thread.start()
    
    def stop(self):
        """Stop the timer"""
        self._running = False
        if self._thread:
            self._thread.join()
    
    def _timer_loop(self):
        """Timer loop"""
        while self._running:
            for callback in self._callbacks:
                try:
                    callback()
                except Exception as e:
                    print(f"[CPM] Timer callback error: {e}")
            time.sleep(self.period_ms / 1000.0)

# Vehicle command types
class VehicleCommand:
    def __init__(self):
        self.steering = 0.0
        self.throttle = 0.0
        self.timestamp = time.time()

print("[CPM] CPM Python bindings loaded successfully")
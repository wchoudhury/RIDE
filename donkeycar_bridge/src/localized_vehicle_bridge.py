"""
Localized Vehicle Bridge - integrates AprilTag localization with vehicle control.
This combines camera-based positioning with Donkeycar control for the RIDE project.
"""

import time
import threading
import numpy as np
from typing import Dict, Optional
from camera_localizer import CameraLocalizer
from network_controller import DonkeycarNetworkController

import cpm

class LocalizedVehicleBridge:
    """Bridge that provides localized control of Donkeycar vehicles"""
    
    def __init__(self, vehicle_id: int, car_config: Dict):
        """
        Initialize localized vehicle bridge.
        
        Args:
            vehicle_id: CPM vehicle ID
            car_config: Configuration for car connection (ip, port, etc.)
        """
        self.vehicle_id = vehicle_id
        self.car_config = car_config
        
        # Initialize CPM communication
        cpm.init(f"localized_vehicle_{vehicle_id}")
        self.logger = cpm.Logging.Instance()
        self.logger.set_id(f"localized_vehicle_{vehicle_id}")
        self.logger.set_min_level(cpm.LogLevel.Info)
        
        # Set up parameter receiver for commands
        self.parameter_receiver = cpm.ParameterReceiver(vehicle_id)
        
        # Initialize network controller for car communication
        self.network_controller = DonkeycarNetworkController(car_config)
        
        # Initialize camera localizer
        self.camera_localizer = CameraLocalizer()
        self.camera_localizer.set_position_callback(self._on_position_update)
        
        # Vehicle state
        self.current_position = {'x': 0.0, 'y': 0.0, 'yaw': 0.0, 'confidence': 0.0}
        self.last_command = {'steering': 0.0, 'throttle': 0.0}
        self.state_lock = threading.Lock()
        
        # Control loop
        self.running = False
        self.control_thread = None
        self.control_rate = 20  # Hz
        
        # Statistics
        self.stats = {
            'commands_sent': 0,
            'position_updates': 0,
            'start_time': time.time()
        }
        
        print(f"[LocalizedBridge] Initialized for vehicle {vehicle_id}")
    
    def start(self) -> bool:
        """Start the localized vehicle bridge"""
        try:
            # Start network connection to car
            if not self.network_controller.connect():
                print("[LocalizedBridge] Failed to connect to vehicle")
                return False
            
            # Start camera localization
            if not self.camera_localizer.start_camera():
                print("[LocalizedBridge] Failed to start camera")
                return False
            
            if not self.camera_localizer.start_processing():
                print("[LocalizedBridge] Failed to start localization")
                return False
            
            # Start CPM parameter receiver
            self.parameter_receiver.start()
            
            # Start control loop
            self.running = True
            self.control_thread = threading.Thread(target=self._control_loop)
            self.control_thread.daemon = True
            self.control_thread.start()
            
            print(f"[LocalizedBridge] Vehicle {self.vehicle_id} bridge started successfully")
            return True
            
        except Exception as e:
            print(f"[LocalizedBridge] Start error: {e}")
            return False
    
    def stop(self):
        """Stop the localized vehicle bridge"""
        print(f"[LocalizedBridge] Stopping vehicle {self.vehicle_id} bridge...")
        
        # Stop control loop
        self.running = False
        if self.control_thread:
            self.control_thread.join(timeout=2.0)
        
        # Stop components
        self.camera_localizer.stop_processing()
        self.parameter_receiver.stop()
        self.network_controller.disconnect()
        
        # Print statistics
        self._print_statistics()
        
        print(f"[LocalizedBridge] Vehicle {self.vehicle_id} bridge stopped")
    
    def _control_loop(self):
        """Main control loop"""
        control_interval = 1.0 / self.control_rate
        last_control_time = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Run control at target rate
                if current_time - last_control_time >= control_interval:
                    self._update_control()
                    last_control_time = current_time
                
                # Send vehicle state to CPM
                self._send_vehicle_state()
                
                # Small delay
                time.sleep(0.01)
                
            except Exception as e:
                print(f"[LocalizedBridge] Control loop error: {e}")
                time.sleep(0.1)
    
    def _update_control(self):
        """Update vehicle control based on CPM commands"""
        try:
            # Get latest command from CPM
            command = self.parameter_receiver.get_latest_command()
            
            if command:
                with self.state_lock:
                    self.last_command = command.copy()
                
                # Send command to vehicle
                success = self.network_controller.send_control(
                    command['steering'], 
                    command['throttle']
                )
                
                if success:
                    self.stats['commands_sent'] += 1
                else:
                    self.logger.write(cpm.LogLevel.Warn, "Failed to send command to vehicle")
            
        except Exception as e:
            print(f"[LocalizedBridge] Control update error: {e}")
    
    def _send_vehicle_state(self):
        """Send current vehicle state to CPM system"""
        try:
            with self.state_lock:
                state = {
                    'vehicle_id': self.vehicle_id,
                    'x': self.current_position['x'],
                    'y': self.current_position['y'],
                    'yaw': self.current_position['yaw'],
                    'speed': 0.0,  # Could calculate from throttle
                    'steering': self.last_command['steering'],
                    'throttle': self.last_command['throttle'],
                    'confidence': self.current_position['confidence'],
                    'timestamp': time.time()
                }
            
            # Send to CPM parameter system
            self.parameter_receiver.send_state(state)
            
        except Exception as e:
            print(f"[LocalizedBridge] State send error: {e}")
    
    def _on_position_update(self, localization_result: Dict):
        """Callback for position updates from camera localizer"""
        try:
            position = localization_result['position']
            
            with self.state_lock:
                self.current_position = position.copy()
            
            self.stats['position_updates'] += 1
            
            # Log significant position changes
            if position['confidence'] > 0.5:
                self.logger.write(
                    cpm.LogLevel.Info,
                    f"Vehicle {self.vehicle_id} position: "
                    f"x={position['x']:.2f}, y={position['y']:.2f}, "
                    f"yaw={np.degrees(position['yaw']):.1f}°"
                )
            
        except Exception as e:
            print(f"[LocalizedBridge] Position update error: {e}")
    
    def get_current_state(self) -> Dict:
        """Get current vehicle state"""
        with self.state_lock:
            return {
                'position': self.current_position.copy(),
                'command': self.last_command.copy(),
                'vehicle_id': self.vehicle_id,
                'timestamp': time.time()
            }
    
    def get_camera_frame(self):
        """Get current camera frame with visualization"""
        return self.camera_localizer.get_visualization_frame()
    
    def set_tag_map(self, tag_map: Dict[int, tuple]):
        """Update AprilTag position map"""
        self.camera_localizer.update_tag_map(tag_map)
        print(f"[LocalizedBridge] Updated tag map with {len(tag_map)} tags")
    
    def capture_debug_frame(self, filename: str = None):
        """Capture frame for debugging"""
        if filename is None:
            filename = f"debug_frame_vehicle_{self.vehicle_id}_{int(time.time())}.jpg"
        
        return self.camera_localizer.capture_frame_to_file(filename)
    
    def _print_statistics(self):
        """Print bridge statistics"""
        runtime = time.time() - self.stats['start_time']
        
        print(f"\n[LocalizedBridge] Vehicle {self.vehicle_id} Statistics:")
        print(f"  Runtime: {runtime:.1f} seconds")
        print(f"  Commands sent: {self.stats['commands_sent']}")
        print(f"  Position updates: {self.stats['position_updates']}")
        print(f"  Command rate: {self.stats['commands_sent']/runtime:.1f} Hz")
        print(f"  Position rate: {self.stats['position_updates']/runtime:.1f} Hz")

def create_localized_bridge(vehicle_id: int, car_ip: str, car_port: int = 8887) -> LocalizedVehicleBridge:
    """
    Convenience function to create a localized vehicle bridge.
    
    Args:
        vehicle_id: CPM vehicle ID
        car_ip: IP address of physical car
        car_port: Port of car web interface
        
    Returns:
        Configured LocalizedVehicleBridge
    """
    car_config = {
        'ip': car_ip,
        'port': car_port,
        'protocol': 'http',
        'timeout': 5.0
    }
    
    return LocalizedVehicleBridge(vehicle_id, car_config)

def test_localized_bridge():
    """Test function for localized bridge"""
    # Test with mock car configuration
    car_config = {
        'ip': 'localhost',
        'port': 8887,
        'protocol': 'http',
        'timeout': 5.0
    }
    
    bridge = LocalizedVehicleBridge(1, car_config)
    
    print("Testing LocalizedVehicleBridge...")
    print("Note: This test requires a physical camera and car to be fully functional")
    
    # Print current state
    state = bridge.get_current_state()
    print(f"Initial state: {state}")

if __name__ == "__main__":
    test_localized_bridge()
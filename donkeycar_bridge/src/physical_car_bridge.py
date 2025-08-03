"""
Physical Car Bridge for Donkeycar integration with CPM Lab.
This module provides a bridge between the CPM Lab and physical donkeycars over the network.
"""

import os
import sys
import time
import threading
import json
import numpy as np

# Import CPM Python bindings
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import cpm


# Import network controller
from network_controller import DonkeycarNetworkController
from visualizer import DonkeycarVisualizer

class PhysicalCarBridge:
    """Bridge that connects CPM Lab to physical Donkeycar vehicles over the network"""
    
    def __init__(self, vehicle_id, config=None):
        self.vehicle_id = vehicle_id
        self.config = config
        self.is_running = False
        
        # Initialize CPM components
        try:
            cpm.Logging.Instance().set_id("donkeycar_bridge_" + str(vehicle_id))
        except:
            cpm.init("donkeycar_bridge_" + str(vehicle_id))
            cpm.Logging.Instance().set_id("donkeycar_bridge_" + str(vehicle_id))
        
        # Create network controller for communicating with physical car
        self.network_controller = DonkeycarNetworkController(vehicle_id, config)
        
        # Create visualizer for displaying car data in CPM Lab Control Center
        self.visualizer = DonkeycarVisualizer(vehicle_id)
        
        # Set up DDS communication with CPM Lab
        self.command_reader = cpm.AsyncReader("vehicle_command_" + str(vehicle_id), 
                                          self._on_vehicle_command)
        self.state_writer = cpm.Writer("vehicle_state_" + str(vehicle_id))
        self.hlc_ready_reader = cpm.AsyncReader("hlc_ready", self._on_hlc_ready)
        
        # Initialize state variables
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_yaw = 0.0
        self.current_speed = 0.0
        self.current_steering = 0.0
        self.current_throttle = 0.0
        self.last_state_update_time = 0
        
        # Process command frequency
        self.command_frequency = 20  # Hz
        self.state_update_frequency = 10  # Hz
        
        # Threading
        self.bridge_thread = None
        self.running = False
        
        cpm.Logging.Instance().write(cpm.LogLevel.Info, 
                                   f"Physical car bridge initialized for vehicle {vehicle_id}")
    
    def start(self):
        """Start the bridge loop to communicate with the physical car"""
        if self.is_running:
            return True
        
        # Start network controller's telemetry collection
        self.network_controller.start_telemetry_collection()
        
        # Start bridge thread
        self.running = True
        self.bridge_thread = threading.Thread(target=self._bridge_loop)
        self.bridge_thread.daemon = True
        self.bridge_thread.start()
        
        self.is_running = True
        cpm.Logging.Instance().write(cpm.LogLevel.Info, 
                                   f"Physical car bridge started for vehicle {self.vehicle_id}")
        return True
    
    def stop(self):
        """Stop the bridge loop"""
        self.running = False
        
        if self.bridge_thread:
            self.bridge_thread.join(timeout=2.0)
        
        # Stop network controller's telemetry collection
        self.network_controller.stop_telemetry_collection()
        
        self.is_running = False
        cpm.Logging.Instance().write(cpm.LogLevel.Info, 
                                   f"Physical car bridge stopped for vehicle {self.vehicle_id}")
    
    def _on_vehicle_command(self, command):
        """Handle incoming vehicle commands from CPM Lab"""
        try:
            # Extract command data
            if command.command.index == cpm.VehicleCommandIndex.DIRECT:
                steering = command.command.steering_target
                velocity = command.command.velocity_target
                
                # Scale values for donkeycar (donkeycar uses -1 to 1 for both steering and throttle)
                max_steering = self.config.get('MAX_STEERING_ANGLE', 30.0)
                max_speed = self.config.get('MAX_SPEED', 1.0)
                
                # Convert to donkeycar scale
                steering_scaled = steering / max_steering
                throttle_scaled = velocity / max_speed
                
                # Clamp values to valid range
                steering_scaled = max(-1.0, min(1.0, steering_scaled))
                throttle_scaled = max(-1.0, min(1.0, throttle_scaled))
                
                # Send command to physical car via network controller
                self.network_controller.send_command(steering_scaled, throttle_scaled)
                
                # Store current command values
                self.current_steering = steering
                self.current_throttle = velocity
                
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error, 
                                      f"Error handling vehicle command: {str(e)}")
    
    def _on_hlc_ready(self, ready_msg):
        """Handle HLC ready messages"""
        # When high-level controller is ready, we can start sending vehicle state
        if ready_msg.vehicle_id == self.vehicle_id and ready_msg.ready:
            # Already handled by bridge loop
            pass
    
    def _bridge_loop(self):
        """Main loop that synchronizes physical car data with CPM Lab"""
        last_state_time = time.time()
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check if network controller is connected to physical car
                if not self.network_controller.is_connected():
                    # Try to reconnect every few seconds
                    time.sleep(2.0)
                    continue
                
                # Update vehicle state at defined frequency
                if current_time - last_state_time >= 1.0 / self.state_update_frequency:
                    last_state_time = current_time
                    self._update_vehicle_state()
                
                # Get latest camera frame for visualization
                camera_frame = self.network_controller.get_latest_camera_frame()
                if camera_frame is not None:
                    self.visualizer.visualize_camera_image(camera_frame)
                
                # Visualize vehicle steering and throttle
                steering, throttle = self.network_controller.get_latest_steering_throttle()
                self.visualizer.visualize_steering_throttle(
                    steering, 
                    throttle,
                    max_steering=self.config.get('MAX_STEERING_ANGLE', 30.0) / 180 * 3.14159,
                    max_throttle=self.config.get('MAX_SPEED', 1.0)
                )
                
                # Sleep to maintain loop frequency
                time.sleep(0.01)  # 100Hz max loop rate
                
            except Exception as e:
                cpm.Logging.Instance().write(cpm.LogLevel.Error, 
                                          f"Error in bridge loop: {str(e)}")
                time.sleep(1.0)
    
    def _update_vehicle_state(self):
        """Update the vehicle state in CPM Lab based on physical car telemetry"""
        try:
            # For a real implementation, you would get position and orientation
            # from the physical car's telemetry (e.g., GPS, IMU)
            # Here we're using a simple model to estimate position based on steering and throttle
            
            # Get latest steering and throttle values from the network controller
            steering, throttle = self.network_controller.get_latest_steering_throttle()
            
            # Convert to physical values
            max_steering = self.config.get('MAX_STEERING_ANGLE', 30.0)
            max_speed = self.config.get('MAX_SPEED', 1.0)
            
            # Convert from donkeycar scale (-1 to 1) to physical values
            physical_steering = steering * max_steering * (3.14159 / 180.0)  # radians
            physical_speed = throttle * max_speed  # m/s
            
            # Update position estimate (very simplified model)
            dt = time.time() - self.last_state_update_time
            if self.last_state_update_time > 0 and dt > 0:
                # Simple bicycle model for position update
                self.current_yaw += physical_steering * dt * physical_speed * 0.5  # Very simplified steering model
                self.current_x += physical_speed * dt * np.cos(self.current_yaw)
                self.current_y += physical_speed * dt * np.sin(self.current_yaw)
                self.current_speed = physical_speed
            
            self.last_state_update_time = time.time()
            
            # Create vehicle state message
            state = cpm.VehicleState()
            state.vehicle_id = self.vehicle_id
            state.time_stamp = cpm.get_time_ns()
            
            # Set position and orientation
            state.pose.x = self.current_x
            state.pose.y = self.current_y
            state.pose.yaw = self.current_yaw
            
            # Set velocity
            state.twist.v_long = self.current_speed
            state.twist.v_tran = 0.0
            state.twist.omega = physical_steering * physical_speed * 0.5  # Simplified angular velocity
            
            # Send state update to CPM Lab
            self.state_writer.write(state)
            
            # Visualize the vehicle position
            self.visualizer.visualize_vehicle(
                self.current_x, 
                self.current_y, 
                self.current_yaw,
                duration=0.2
            )
            
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error, 
                                      f"Error updating vehicle state: {str(e)}")
    
    def is_connected(self):
        """Check if bridge is connected to physical car"""
        return self.network_controller.is_connected()
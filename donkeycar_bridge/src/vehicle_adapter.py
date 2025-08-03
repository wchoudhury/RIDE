"""
Vehicle Adapter for Donkeycar integration with CPM Lab.
This module provides an adapter that makes a Donkeycar appear as a CPM Lab vehicle.
"""

import os
import sys
import time
import threading
import numpy as np

# Import CPM Python bindings
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import cpm


class DonkeycarVehicleAdapter:
    """Adapter that makes a Donkeycar appear as a CPM Lab vehicle"""
    
    def __init__(self, vehicle_id, config=None):
        self.vehicle_id = vehicle_id
        self.vehicle_ready = False
        
        # Initialize CPM components
        cpm.init("donkeycar_adapter_" + str(vehicle_id))
        cpm.Logging.Instance().set_id("donkeycar_adapter_" + str(vehicle_id))
        
        # Set up DDS communication
        self.command_writer = cpm.Writer("vehicle_command_" + str(vehicle_id))
        self.state_reader = cpm.AsyncReader("vehicle_state_" + str(vehicle_id), 
                                         self._on_vehicle_state)
        self.hlc_ready_writer = cpm.Writer("hlc_ready")
        
        # Load configuration
        if config:
            self.config = config
        else:
            # Use parameter system to get configuration
            self.parameter_receiver = cpm.ParameterReceiver()
            self.config = self._load_config_from_parameters()
        
        # Initialize vehicle state
        self.current_state = None
        self.last_command_time = 0
        
    def _load_config_from_parameters(self):
        """Load configuration from CPM parameter system"""
        config = {}
        
        # Vehicle parameters
        config['MAX_VELOCITY'] = self.parameter_receiver.get_parameter_double(
            "donkeycar/" + str(self.vehicle_id) + "/max_velocity")
        config['STEERING_SCALE'] = self.parameter_receiver.get_parameter_double(
            "donkeycar/" + str(self.vehicle_id) + "/steering_scale")
        
        # Control parameters
        config['CONTROL_FREQUENCY'] = self.parameter_receiver.get_parameter_int(
            "donkeycar/control_frequency")
        
        # Set default values if parameters not found
        if config['MAX_VELOCITY'] == 0.0:
            config['MAX_VELOCITY'] = 1.5  # m/s
        if config['STEERING_SCALE'] == 0.0:
            config['STEERING_SCALE'] = 0.5  # radians
        if config['CONTROL_FREQUENCY'] == 0:
            config['CONTROL_FREQUENCY'] = 20  # Hz
        
        return config
    
    def _on_vehicle_state(self, state):
        """Handle incoming vehicle state updates from the Donkeycar"""
        self.current_state = state
        
    def send_command(self, steering, velocity):
        """Send a control command to the Donkeycar
        
        Args:
            steering: Steering angle in radians
            velocity: Velocity in m/s
        
        Returns:
            bool: True if command was sent successfully
        """
        try:
            # Create command message
            command = cpm.VehicleCommandDirect()
            command.vehicle_id = self.vehicle_id
            command.time_stamp = cpm.get_time_ns()
            
            # Set control values
            command.steering_target = float(steering)
            command.velocity_target = float(velocity)
            
            # Send command
            msg = cpm.VehicleCommand()
            msg.command = command
            self.command_writer.write(msg)
            
            self.last_command_time = time.time()
            
            return True
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error, 
                                      f"Error sending command: {str(e)}")
            return False
    
    def announce_ready(self):
        """Announce that this vehicle's HLC is ready"""
        try:
            ready_msg = cpm.HLCReady()
            ready_msg.vehicle_id = self.vehicle_id
            ready_msg.ready = True
            ready_msg.time_stamp = cpm.get_time_ns()
            
            self.hlc_ready_writer.write(ready_msg)
            self.vehicle_ready = True
            
            cpm.Logging.Instance().write(cpm.LogLevel.Info, 
                                      f"Vehicle {self.vehicle_id} announced as ready")
            
            return True
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error, 
                                      f"Error announcing ready state: {str(e)}")
            return False
    
    def get_current_state(self):
        """Get the current vehicle state"""
        return self.current_state
    
    def is_ready(self):
        """Check if the vehicle is ready"""
        return self.vehicle_ready
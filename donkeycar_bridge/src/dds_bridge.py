"""
DDS Bridge for Donkeycar to CPM Lab communication.
This module acts as a bridge between Donkeycar and CPM Lab's DDS communication system.
"""

import os
import sys
import time
import threading
import numpy as np

# Import CPM Python bindings
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import cpm
from visualizer import DonkeycarVisualizer

# Import Donkeycar if available
try:
    import donkeycar as dk
    from donkeycar.vehicle import Vehicle
    from donkeycar.parts.actuator import PCA9685, PWMSteering, PWMThrottle
    DONKEYCAR_AVAILABLE = True
except ImportError:
    print("Warning: Donkeycar library not found. Running in simulation mode.")
    DONKEYCAR_AVAILABLE = False

class DonkeycarDDSBridge:
    """Bridge between Donkeycar API and CPM Lab DDS communication"""
    
    def __init__(self, vehicle_id, config=None):
        # Initialize CPM components
        cpm.init("donkeycar_bridge_" + str(vehicle_id))
        cpm.Logging.Instance().set_id("donkeycar_bridge_" + str(vehicle_id))
        
        self.vehicle_id = vehicle_id
        self.running = False
        
        # Initialize DDS readers and writers
        self.vehicle_command_reader = cpm.AsyncReader("vehicle_command_" + str(vehicle_id), 
                                                    self._on_vehicle_command)
        self.vehicle_state_writer = cpm.Writer("vehicle_state_" + str(vehicle_id))
        
        # Initialize visualizer
        self.visualizer = DonkeycarVisualizer(vehicle_id)
        
        # Initialize configuration
        if config:
            self.config = config
        else:
            # Use parameter system to get configuration
            self.parameter_receiver = cpm.ParameterReceiver()
            self.config = self._load_config_from_parameters()
        
        # Initialize Donkeycar vehicle if available
        if DONKEYCAR_AVAILABLE:
            self.dk_vehicle = Vehicle()
            self._setup_donkeycar()
        else:
            self.dk_vehicle = None
            cpm.Logging.Instance().write(cpm.LogLevel.Warn, 
                "Donkeycar not available, running in simulation mode")
        
        # Initialize vehicle state
        self.steering = 0.0
        self.throttle = 0.0
        self.last_update_time = 0
        
        # Initialize vehicle pose (simulated)
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.heading = 0.0
        self.path_history = []  # Store path history for visualization
        
        # Flag to indicate if we have camera
        self.has_camera = False
        
        # Latest camera image
        self.latest_camera_image = None
        
        # Start state update thread
        self.update_thread = threading.Thread(target=self._state_update_loop)
        self.update_thread.daemon = True
        
        # Start visualization thread
        self.vis_thread = threading.Thread(target=self._visualization_loop)
        self.vis_thread.daemon = True
    
    def _load_config_from_parameters(self):
        """Load configuration from CPM parameter system"""
        config = {}
        
        # Vehicle parameters
        config['MAX_VELOCITY'] = self.parameter_receiver.get_parameter_double(
            "donkeycar/" + str(self.vehicle_id) + "/max_velocity")
        config['STEERING_SCALE'] = self.parameter_receiver.get_parameter_double(
            "donkeycar/" + str(self.vehicle_id) + "/steering_scale")
        
        # Donkeycar specific parameters
        config['STEERING_CHANNEL'] = self.parameter_receiver.get_parameter_int(
            "donkeycar/" + str(self.vehicle_id) + "/steering_channel")
        config['THROTTLE_CHANNEL'] = self.parameter_receiver.get_parameter_int(
            "donkeycar/" + str(self.vehicle_id) + "/throttle_channel")
        config['STEERING_LEFT_PWM'] = self.parameter_receiver.get_parameter_int(
            "donkeycar/" + str(self.vehicle_id) + "/steering_left_pwm")
        config['STEERING_RIGHT_PWM'] = self.parameter_receiver.get_parameter_int(
            "donkeycar/" + str(self.vehicle_id) + "/steering_right_pwm")
        config['THROTTLE_FORWARD_PWM'] = self.parameter_receiver.get_parameter_int(
            "donkeycar/" + str(self.vehicle_id) + "/throttle_forward_pwm")
        config['THROTTLE_STOPPED_PWM'] = self.parameter_receiver.get_parameter_int(
            "donkeycar/" + str(self.vehicle_id) + "/throttle_stopped_pwm")
        config['THROTTLE_REVERSE_PWM'] = self.parameter_receiver.get_parameter_int(
            "donkeycar/" + str(self.vehicle_id) + "/throttle_reverse_pwm")
        
        # Control parameters
        config['DRIVE_LOOP_HZ'] = self.parameter_receiver.get_parameter_int(
            "donkeycar/control_frequency")
        
        # Visualization parameters
        config['USE_CAMERA'] = self.parameter_receiver.get_parameter_bool(
            "donkeycar/use_camera")
        
        # Set default values if parameters not found
        if config['MAX_VELOCITY'] == 0.0:
            config['MAX_VELOCITY'] = 1.5  # m/s
        if config['STEERING_SCALE'] == 0.0:
            config['STEERING_SCALE'] = 0.5  # radians
        if config['DRIVE_LOOP_HZ'] == 0:
            config['DRIVE_LOOP_HZ'] = 20  # Hz
        
        return config
        
    def _setup_donkeycar(self):
        """Set up the donkeycar vehicle with necessary parts"""
        if not DONKEYCAR_AVAILABLE:
            return
            
        try:
            # Set up actuators based on config
            steering_controller = PCA9685(self.config['STEERING_CHANNEL'], 
                                        address=0x40, 
                                        busnum=1)
            steering = PWMSteering(controller=steering_controller,
                                left_pulse=self.config['STEERING_LEFT_PWM'],
                                right_pulse=self.config['STEERING_RIGHT_PWM'])
            
            throttle_controller = PCA9685(self.config['THROTTLE_CHANNEL'], 
                                        address=0x40, 
                                        busnum=1)
            throttle = PWMThrottle(controller=throttle_controller,
                                max_pulse=self.config['THROTTLE_FORWARD_PWM'],
                                zero_pulse=self.config['THROTTLE_STOPPED_PWM'],
                                min_pulse=self.config['THROTTLE_REVERSE_PWM'])
            
            # Add parts to vehicle
            self.dk_vehicle.add(steering, inputs=['steering'], threaded=False)
            self.dk_vehicle.add(throttle, inputs=['throttle'], threaded=False)
            
            # Add camera if configured and available
            if self.config.get('USE_CAMERA', True):
                try:
                    from donkeycar.parts.camera import PiCamera
                    cam = PiCamera(resolution=(160, 120))
                    
                    # Add our own camera handler to get images for visualization
                    def cam_handler(img):
                        self.latest_camera_image = img
                        return img
                        
                    self.dk_vehicle.add(cam, outputs=['cam/image_array'], threaded=True)
                    self.dk_vehicle.add(cam_handler, inputs=['cam/image_array'], outputs=['cam/image_processed'], threaded=False)
                    
                    self.has_camera = True
                    cpm.Logging.Instance().write(cpm.LogLevel.Info, 
                                              "Camera initialized for visualization")
                except ImportError:
                    self.has_camera = False
                    cpm.Logging.Instance().write(cpm.LogLevel.Info, 
                                              "Camera not available, running without camera visualization.")
            else:
                self.has_camera = False
                
            cpm.Logging.Instance().write(cpm.LogLevel.Info, 
                                      "Donkeycar setup complete")
                                      
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error, 
                                      f"Error setting up Donkeycar: {str(e)}")
    
    def _on_vehicle_command(self, command):
        """Handle incoming vehicle commands from CPM"""
        try:
            # Extract steering and throttle from command
            # Translate CPM command format to Donkeycar control values (-1 to 1)
            if hasattr(command, 'command'):
                steering = command.command.steering_target / self.config['STEERING_SCALE']
                throttle = command.command.velocity_target / self.config['MAX_VELOCITY']
            else:
                # For mock implementation
                steering = 0.0
                throttle = 0.0
                cpm.Logging.Instance().write(cpm.LogLevel.Debug, 
                                         "Received mock command")
            
            # Clamp values to Donkeycar range
            steering = max(-1.0, min(1.0, steering))
            throttle = max(-1.0, min(1.0, throttle))
            
            # Store the values
            self.steering = steering
            self.throttle = throttle
            
            # Update the Donkeycar parts if available
            if DONKEYCAR_AVAILABLE and self.dk_vehicle:
                self.dk_vehicle.update_parts('steering', steering)
                self.dk_vehicle.update_parts('throttle', throttle)
                
            # Update simulated vehicle state for visualization
            self._update_simulated_position(steering, throttle)
            
            # Log the command
            cpm.Logging.Instance().write(cpm.LogLevel.Info, 
                                      f"Received command: steering={steering}, throttle={throttle}")
            
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error, 
                                      f"Error processing vehicle command: {str(e)}")
    
    def _update_simulated_position(self, steering, throttle):
        """Update simulated position based on steering and throttle
        
        This is only used when we don't have real position data from the vehicle.
        """
        current_time = time.time()
        dt = current_time - self.last_update_time
        if dt <= 0:
            return
            
        # Only update if enough time has passed
        if dt < 1.0 / self.config['DRIVE_LOOP_HZ']:
            return
            
        # Convert to physical values
        physical_steering = steering * self.config['STEERING_SCALE']
        physical_velocity = throttle * self.config['MAX_VELOCITY']
        
        # Update position using simple bicycle model
        # Assuming wheelbase of 0.25m
        wheelbase = 0.25
        
        # Update heading based on steering and velocity
        self.heading += (physical_velocity * np.tan(physical_steering) / wheelbase) * dt
        
        # Normalize heading to [-pi, pi]
        while self.heading > np.pi:
            self.heading -= 2 * np.pi
        while self.heading < -np.pi:
            self.heading += 2 * np.pi
            
        # Update position
        self.pos_x += physical_velocity * np.cos(self.heading) * dt
        self.pos_y += physical_velocity * np.sin(self.heading) * dt
        
        # Store position in path history for visualization
        self.path_history.append((self.pos_x, self.pos_y))
        
        # Limit path history length
        max_path_points = 100
        if len(self.path_history) > max_path_points:
            self.path_history = self.path_history[-max_path_points:]
            
        self.last_update_time = current_time
    
    def _state_update_loop(self):
        while self.running:
            try:
                self._publish_vehicle_state()
                # Sleep shorter to check running flag more often
                for _ in range(10):
                    if not self.running:
                        break
                    time.sleep(0.1)  # total 1 second in 0.1s increments
            except Exception as e:
                cpm.Logging.Instance().write(cpm.LogLevel.Error, f"Error in state update loop: {str(e)}")
                time.sleep(1.0)
    
    def _visualization_loop(self):
        """Background thread to handle visualization updates"""
        while self.running:
            try:
                # Visualize vehicle position and path
                if self.path_history:
                    x_points = [p[0] for p in self.path_history]
                    y_points = [p[1] for p in self.path_history]
                    
                    # Visualize the path
                    self.visualizer.visualize_path(x_points, y_points)
                    
                    # Visualize the vehicle
                    self.visualizer.visualize_vehicle(self.pos_x, self.pos_y, self.heading)
                
                # Visualize steering and throttle
                actual_steering = self.steering * self.config['STEERING_SCALE']
                actual_throttle = self.throttle * self.config['MAX_VELOCITY']
                self.visualizer.visualize_steering_throttle(
                    actual_steering, 
                    actual_throttle,
                    max_steering=self.config['STEERING_SCALE'],
                    max_throttle=self.config['MAX_VELOCITY']
                )
                
                # Visualize camera image if available
                if self.has_camera and self.latest_camera_image is not None:
                    self.visualizer.visualize_camera_image(self.latest_camera_image)
                
                # Sleep to control visualization rate
                time.sleep(0.05)  # 20 Hz max for visualization
                
            except Exception as e:
                cpm.Logging.Instance().write(cpm.LogLevel.Error, 
                                          f"Error in visualization loop: {str(e)}")
                time.sleep(1.0)  # Sleep longer on error
    
    def _publish_vehicle_state(self):
        """Publish the current vehicle state back to CPM"""
        try:
            # Create a vehicle state message
            state = cpm.VehicleState()
            state.vehicle_id = self.vehicle_id
            state.time_stamp = cpm.get_time_ns()
            
            # Set current control values
            state.steering = self.steering * self.config['STEERING_SCALE']
            state.velocity = self.throttle * self.config['MAX_VELOCITY']
            
            # Set position and orientation - for now using simulated values
            # In the future, this would come from actual sensors
            state.pose.x = self.pos_x
            state.pose.y = self.pos_y
            state.pose.yaw = self.heading
            
            # Publish state
            self.vehicle_state_writer.write(state)
            
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error, 
                                      f"Error publishing vehicle state: {str(e)}")
    
    def start(self):
        """Start the bridge"""
        if self.running:
            return
            
        self.running = True
        
        # Start the state update thread
        self.update_thread.start()
        
        # Start the visualization thread
        self.vis_thread.start()
        
        # Start the Donkeycar vehicle if available
        if DONKEYCAR_AVAILABLE and self.dk_vehicle:
            self.dk_vehicle.start(rate_hz=self.config['DRIVE_LOOP_HZ'], 
                              max_loop_count=None, 
                              verbose=False)
        
        # Initialize simulation time
        self.last_update_time = time.time()
        
        cpm.Logging.Instance().write(cpm.LogLevel.Info, 
                                  f"Donkeycar Bridge for vehicle {self.vehicle_id} started")
    
    def stop(self):
        """Stop the bridge"""
        self.running = False

        # Stop the Donkeycar vehicle if available
        if DONKEYCAR_AVAILABLE and self.dk_vehicle:
            self.dk_vehicle.stop()
            self.dk_vehicle.profiler.report()

        # Wait for the threads to finish
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=2.0)

        if self.vis_thread.is_alive():
            self.vis_thread.join(timeout=2.0)

        cpm.Logging.Instance().write(cpm.LogLevel.Info,
            f"Donkeycar Bridge for vehicle {self.vehicle_id} stopped")



def main():
    """Main function to run the Donkeycar DDS Bridge"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Donkeycar DDS Bridge')
    parser.add_argument('vehicle_id', type=int, help='Vehicle ID')
    args = parser.parse_args()
    
    # Create and start the bridge
    bridge = DonkeycarDDSBridge(args.vehicle_id)
    
    try:
        bridge.start()
        
        # Keep the program running until Ctrl+C
        while True:
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        # Stop the bridge on Ctrl+C
        bridge.stop()


if __name__ == "__main__":
    main()
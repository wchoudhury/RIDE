"""
Example high-level controller for Donkeycar integration with CPM Lab.
This example makes a Donkeycar follow a figure-eight trajectory.
"""

import os
import sys
import time
import threading
import math
import signal
import argparse
import numpy as np

# Add the parent directory to the path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(parent_dir, "src"))

# Import our vehicle adapter
from vehicle_adapter import DonkeycarVehicleAdapter
import cpm


class DonkeycarFigureEightController:
    """Example high-level controller that makes a Donkeycar drive in a figure-eight pattern"""
    
    def __init__(self, vehicle_id, size=1.0, speed=0.5):
        # Initialize CPM components
        cpm.init("donkeycar_figure8_" + str(vehicle_id))
        cpm.Logging.Instance().set_id("donkeycar_figure8_" + str(vehicle_id))
        
        self.vehicle_id = vehicle_id
        self.size = size  # Size of the figure-eight
        self.speed = speed
        self.running = False
        
        # Create vehicle adapter
        self.vehicle = DonkeycarVehicleAdapter(vehicle_id)
        
        # Set up timer for control updates
        self.timer = None
        self.control_period = 1.0 / 20.0  # 20 Hz control rate
        
        # Initialize trajectory parameters
        self.start_time = 0
        self.period = 10.0  # Time to complete one cycle in seconds
        
        # Track current position (simulation only)
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.yaw = 0.0
        self.last_update = 0
        
    def _calculate_trajectory_point(self, t):
        """Calculate the desired position, velocity, and steering at time t
        
        Args:
            t: Time in seconds
            
        Returns:
            tuple: (x, y, v_x, v_y, heading)
        """
        # Normalize time to the period
        t_norm = (t % self.period) / self.period
        
        # Calculate figure-eight coordinates using parametric equations
        # https://en.wikipedia.org/wiki/Lissajous_curve
        x = self.size * math.sin(2 * math.pi * t_norm)
        y = self.size * math.sin(4 * math.pi * t_norm) / 2
        
        # Calculate derivatives (velocity components)
        v_x = self.size * 2 * math.pi / self.period * math.cos(2 * math.pi * t_norm)
        v_y = self.size * 4 * math.pi / self.period * math.cos(4 * math.pi * t_norm) / 2
        
        # Calculate heading angle from velocity components
        heading = math.atan2(v_y, v_x)
        
        return (x, y, v_x, v_y, heading)
    
    def _control_update(self):
        """Update the vehicle control commands based on the figure-eight trajectory"""
        if not self.running:
            return
            
        # Calculate elapsed time
        elapsed_time = time.time() - self.start_time
        
        # Get the desired trajectory point
        x, y, v_x, v_y, desired_heading = self._calculate_trajectory_point(elapsed_time)
        
        # Calculate velocity magnitude
        velocity = min(math.sqrt(v_x**2 + v_y**2), self.speed)
        
        # Calculate desired steering angle
        # In a real system, this would use vehicle state and a control law
        # For simulation, we'll use a simple approach
        
        # For simulation, update our position based on previous commands
        dt = time.time() - self.last_update
        self.last_update = time.time()
        
        if dt > 0:
            # Simple vehicle model for simulation
            self.pos_x += velocity * math.cos(self.yaw) * dt
            self.pos_y += velocity * math.sin(self.yaw) * dt
        
        # Calculate the heading error
        heading_error = self._normalize_angle(desired_heading - self.yaw)
        
        # Simple proportional control for steering
        steering = 0.5 * heading_error  # P controller with gain 0.5
        
        # Clamp steering to reasonable limits
        steering = max(-0.5, min(0.5, steering))
        
        # Update yaw for simulation based on steering angle and velocity
        # This is a very simplified model
        if dt > 0:
            # Assuming wheelbase of 0.25m
            self.yaw += velocity * math.tan(steering) / 0.25 * dt
            self.yaw = self._normalize_angle(self.yaw)
        
        # Send command to vehicle
        self.vehicle.send_command(steering, velocity)
        
        # Log current simulation state
        if elapsed_time % 1.0 < self.control_period:  # Log once per second
            cpm.Logging.Instance().write(cpm.LogLevel.Info,
                f"Sim position: ({self.pos_x:.2f}, {self.pos_y:.2f}), heading: {self.yaw:.2f}, " +
                f"target: ({x:.2f}, {y:.2f}), heading: {desired_heading:.2f}")
        
        # Schedule next update
        self.timer = threading.Timer(self.control_period, self._control_update)
        self.timer.daemon = True
        self.timer.start()
    
    def _normalize_angle(self, angle):
        """Normalize an angle to [-pi, pi]"""
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle
        
    def start(self):
        """Start the controller"""
        if self.running:
            return
            
        # Announce that the HLC is ready
        self.vehicle.announce_ready()
        
        cpm.Logging.Instance().write(cpm.LogLevel.Info, 
                                   f"Starting figure-eight controller for vehicle {self.vehicle_id}")
        
        self.running = True
        self.start_time = time.time()
        self.last_update = self.start_time
        
        # Start the control loop
        self._control_update()
        
    def stop(self):
        """Stop the controller"""
        self.running = False
        
        # Cancel the timer if it exists
        if self.timer:
            self.timer.cancel()
        
        # Send zero command to stop the vehicle
        self.vehicle.send_command(0.0, 0.0)
        
        cpm.Logging.Instance().write(cpm.LogLevel.Info, 
                                   f"Stopped figure-eight controller for vehicle {self.vehicle_id}")

def main():
    """Main function to run the figure-eight controller"""
    parser = argparse.ArgumentParser(description='Donkeycar Figure-Eight Controller')
    parser.add_argument('vehicle_id', type=int, help='Vehicle ID')
    parser.add_argument('--size', type=float, default=1.0, help='Size of the figure-eight in meters')
    parser.add_argument('--speed', type=float, default=0.5, help='Maximum vehicle speed in m/s')
    
    args = parser.parse_args()
    
    controller = DonkeycarFigureEightController(args.vehicle_id, args.size, args.speed)
    
    # Set up signal handling for clean shutdown
    def signal_handler(sig, frame):
        controller.stop()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the controller
    controller.start()
    
    # Keep the program running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        controller.stop()
        sys.exit(0)

if __name__ == "__main__":
    main()
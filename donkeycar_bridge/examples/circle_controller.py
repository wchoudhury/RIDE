"""
Example high-level controller for Donkeycar integration with CPM Lab.
This example makes a Donkeycar drive in a circle.
"""

import os
import sys
import time
import threading
import math
import signal
import argparse

# Add the parent directory to the path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(parent_dir, "src"))

# Import our vehicle adapter
from vehicle_adapter import DonkeycarVehicleAdapter
import cpm


class DonkeycarCircleController:
    """Example high-level controller that makes a Donkeycar drive in a circle"""
    
    def __init__(self, vehicle_id, radius=1.0, speed=0.5):
        # Initialize CPM components
        cpm.init("donkeycar_circle_" + str(vehicle_id))
        cpm.Logging.Instance().set_id("donkeycar_circle_" + str(vehicle_id))
        
        self.vehicle_id = vehicle_id
        self.radius = radius
        self.speed = speed
        self.running = False
        
        # Create vehicle adapter
        self.vehicle = DonkeycarVehicleAdapter(vehicle_id)
        
        # Set up timer for control updates
        self.timer = None
        self.control_period = 1.0 / 20.0  # 20 Hz control rate
        
        # Initialize trajectory parameters
        self.start_time = 0
        
    def _control_update(self):
        """Update the vehicle control commands based on the circular trajectory"""
        if not self.running:
            return
            
        # Calculate elapsed time
        elapsed_time = time.time() - self.start_time
        
        # Calculate steering angle for circular motion
        # For a circle, we need constant steering
        # The tighter the radius, the more steering we need
        steering = 0.8 * (1.0 / self.radius)  # Simplified steering model
        
        # Clamp steering to reasonable limits
        steering = max(-0.5, min(0.5, steering))
        
        # Send command to vehicle
        self.vehicle.send_command(steering, self.speed)
        
        # Log current state
        state = self.vehicle.get_current_state()
        if state:
            cpm.Logging.Instance().write(cpm.LogLevel.Debug, 
                                       f"Vehicle state: velocity={state.velocity}, steering={state.steering}")
        
        # Schedule next update
        self.timer = threading.Timer(self.control_period, self._control_update)
        self.timer.daemon = True
        self.timer.start()
        
    def start(self):
        """Start the controller"""
        if self.running:
            return
            
        # Announce that the HLC is ready
        self.vehicle.announce_ready()
        
        cpm.Logging.Instance().write(cpm.LogLevel.Info, 
                                   f"Starting circle controller for vehicle {self.vehicle_id}")
        
        self.running = True
        self.start_time = time.time()
        
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
                                   f"Stopped circle controller for vehicle {self.vehicle_id}")

def main():
    """Main function to run the circle controller"""
    parser = argparse.ArgumentParser(description='Donkeycar Circle Controller')
    parser.add_argument('vehicle_id', type=int, help='Vehicle ID')
    parser.add_argument('--radius', type=float, default=1.0, help='Circle radius in meters')
    parser.add_argument('--speed', type=float, default=0.5, help='Vehicle speed in m/s')
    
    args = parser.parse_args()
    
    controller = DonkeycarCircleController(args.vehicle_id, args.radius, args.speed)
    
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
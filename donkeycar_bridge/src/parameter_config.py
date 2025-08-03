"""
Parameter configuration for Donkeycar integration with CPM Lab.
This module sets up parameter configurations for Donkeycar vehicles in the CPM Lab system.
"""

import os
import sys
import argparse
import donkeycar as dk

# Import CPM Python bindings
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import cpm


def create_donkeycar_parameters(vehicle_ids):
    """Create parameter configurations for Donkeycar vehicles
    
    Args:
        vehicle_ids: List of vehicle IDs to configure
    """
    # Initialize CPM
    cpm.init("donkeycar_parameter_setup")
    cpm.Logging.Instance().set_id("donkeycar_parameter_setup")
    
    try:
        # Create parameter server
        parameter_server = cpm.ParameterServer()
        
        # General Donkeycar parameters
        parameter_server.set_parameter_int("donkeycar/control_frequency", 20)
        parameter_server.set_parameter_bool("donkeycar/use_camera", True)
        parameter_server.set_parameter_string("donkeycar/camera_type", "picamera")
        
        # Configure each vehicle
        for vehicle_id in vehicle_ids:
            # Vehicle physical properties
            parameter_server.set_parameter_double(f"donkeycar/{vehicle_id}/max_velocity", 1.5)  # m/s
            parameter_server.set_parameter_double(f"donkeycar/{vehicle_id}/max_acceleration", 1.0)  # m/s^2
            parameter_server.set_parameter_double(f"donkeycar/{vehicle_id}/max_steering_angle", 0.5)  # radians
            parameter_server.set_parameter_double(f"donkeycar/{vehicle_id}/wheelbase", 0.25)  # meters
            parameter_server.set_parameter_double(f"donkeycar/{vehicle_id}/steering_scale", 0.5)  # radians
            
            # Donkeycar-specific parameters
            parameter_server.set_parameter_int(f"donkeycar/{vehicle_id}/steering_channel", 1)
            parameter_server.set_parameter_int(f"donkeycar/{vehicle_id}/throttle_channel", 0)
            parameter_server.set_parameter_int(f"donkeycar/{vehicle_id}/steering_left_pwm", 460)
            parameter_server.set_parameter_int(f"donkeycar/{vehicle_id}/steering_right_pwm", 290)
            parameter_server.set_parameter_int(f"donkeycar/{vehicle_id}/throttle_forward_pwm", 500)
            parameter_server.set_parameter_int(f"donkeycar/{vehicle_id}/throttle_stopped_pwm", 370)
            parameter_server.set_parameter_int(f"donkeycar/{vehicle_id}/throttle_reverse_pwm", 220)
            
        cpm.Logging.Instance().write(cpm.LogLevel.Info,
                                   f"Created parameters for {len(vehicle_ids)} Donkeycar vehicles")
                                   
    except Exception as e:
        cpm.Logging.Instance().write(cpm.LogLevel.Error,
                                   f"Error setting up parameters: {str(e)}")

def load_car_config(car_path):
    """Load configuration from a Donkeycar config file
    
    Args:
        car_path: Path to the car directory
        
    Returns:
        dict: Configuration dictionary
    """
    try: # TODO FIX DK Config parsing
        # sys.path.append(car_path)
        # import myconfig path (car_path/myconfig.py)
        myconfig_path = os.path.join(car_path, 'myconfig.py')
        myconfig = dk.load_config(myconfig=myconfig_path)
        
        # Extract configuration values
        config = {}
        
        # Steering settings
        config['STEERING_CHANNEL'] = getattr(myconfig, 'STEERING_CHANNEL', 1)
        config['STEERING_LEFT_PWM'] = getattr(myconfig, 'STEERING_LEFT_PWM', 460)
        config['STEERING_RIGHT_PWM'] = getattr(myconfig, 'STEERING_RIGHT_PWM', 290)
        
        # Throttle settings
        config['THROTTLE_CHANNEL'] = getattr(myconfig, 'THROTTLE_CHANNEL', 0)
        config['THROTTLE_FORWARD_PWM'] = getattr(myconfig, 'THROTTLE_FORWARD_PWM', 500)
        config['THROTTLE_STOPPED_PWM'] = getattr(myconfig, 'THROTTLE_STOPPED_PWM', 370)
        config['THROTTLE_REVERSE_PWM'] = getattr(myconfig, 'THROTTLE_REVERSE_PWM', 220)
        
        # Other settings
        config['MAX_VELOCITY'] = getattr(myconfig, 'MAX_VELOCITY', 1.5)
        config['STEERING_SCALE'] = getattr(myconfig, 'STEERING_SCALE', 0.5)
        
        return config
        
    except ImportError:
        print(f"Could not import myconfig from {car_path}")
        return None

def main():
    """Main function to set up parameters"""
    parser = argparse.ArgumentParser(description='Donkeycar parameter setup for CPM Lab')
    parser.add_argument('vehicle_ids', type=int, nargs='+', help='Vehicle IDs to configure')
    parser.add_argument('--car-path', type=str, help='Path to Donkeycar directory to load settings from')
    
    args = parser.parse_args()
    
    # If car path is provided, load configuration and create custom parameters
    if args.car_path:
        config = load_car_config(args.car_path)
        if config:
            cpm.init("donkeycar_parameter_setup")
            parameter_server = cpm.ParameterServer()
            
            for vehicle_id in args.vehicle_ids:
                for key, value in config.items():
                    if isinstance(value, float):
                        parameter_server.set_parameter_double(f"donkeycar/{vehicle_id}/{key.lower()}", value)
                    elif isinstance(value, int):
                        parameter_server.set_parameter_int(f"donkeycar/{vehicle_id}/{key.lower()}", value)
                    elif isinstance(value, bool):
                        parameter_server.set_parameter_bool(f"donkeycar/{vehicle_id}/{key.lower()}", value)
                    elif isinstance(value, str):
                        parameter_server.set_parameter_string(f"donkeycar/{vehicle_id}/{key.lower()}", value)
            
            print(f"Created parameters from car config for {len(args.vehicle_ids)} Donkeycar vehicles")
    else:
        # Otherwise create default parameters
        create_donkeycar_parameters(args.vehicle_ids)

if __name__ == "__main__":
    main()
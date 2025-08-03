#!/usr/bin/env python3
"""
Launch script for connecting to physical donkeycars over the network.
This allows the donkeycar bridge to communicate with real cars.
"""

import os
import sys
import time
import argparse
import importlib.util
from pathlib import Path

# Add src directory to path for module imports
current_dir = Path(__file__).parent.absolute()
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

def load_config_module(config_path):
    """Load a configuration from a Python file path"""
    try:
        spec = importlib.util.spec_from_file_location("config", config_path)
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        return config
    except Exception as e:
        print(f"Error loading configuration file: {str(e)}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Connect to physical donkeycar over the network')
    
    parser.add_argument('--vehicle-id', type=int, default=1,
                        help='Vehicle ID for the donkeycar')
    
    parser.add_argument('--config', type=str, default=None,
                        help='Path to configuration file')
    
    parser.add_argument('--car-name', type=str, default=None,
                        help='Name of the physical car to connect to (must be defined in config)')
    
    parser.add_argument('--ip', type=str, default=None,
                        help='IP address of the physical car')
    
    parser.add_argument('--port', type=int, default=None,
                        help='Port number for the physical car')
    
    parser.add_argument('--protocol', type=str, choices=['http', 'mqtt'], default=None,
                        help='Communication protocol (http or mqtt)')
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = args.config
    if not config_path:
        config_path = os.path.join(current_dir, 'simulation', 'config.py')
    
    print(f"Loading configuration from {config_path}...")
    config_module = load_config_module(config_path)
    
    if not config_module:
        print("Failed to load configuration. Exiting...")
        return 1
    
    # Override configuration with command line arguments
    if args.protocol:
        config_module.PROTOCOL = args.protocol
    
    # Enable network mode
    config_module.NETWORK_ENABLED = True
    config_module.SIMULATION_MODE = False
    
    # Handle car selection or direct IP/port
    car_name = args.car_name
    if car_name and car_name in config_module.PHYSICAL_CARS:
        car_config = config_module.PHYSICAL_CARS[car_name]
        ip_address = car_config['ip']
        port = car_config['port']
        print(f"Using pre-configured car '{car_name}' at {ip_address}:{port}")
    else:
        # Use command line IP/port or defaults
        ip_address = args.ip or "localhost" 
        port = args.port or config_module.DEFAULT_PORT
        print(f"Connecting to car at {ip_address}:{port}")
    
    # Update the config with the car details
    config_module.PHYSICAL_CARS[f"car{args.vehicle_id}"] = {
        "ip": ip_address,
        "port": port
    }
    
    # Import here to avoid module import issues
    from src.physical_car_bridge import PhysicalCarBridge
    import sys
    sys.path.append('src')
    import cpm

    
    print(f"Initializing physical car bridge for vehicle {args.vehicle_id}...")
    config_dict = {
        'VEHICLE_ID': args.vehicle_id,
        'MAX_SPEED': config_module.MAX_SPEED,
        'MAX_STEERING_ANGLE': config_module.MAX_STEERING_ANGLE,
        'PROTOCOL': config_module.PROTOCOL,
        'CAR_IP': ip_address,
        'CAR_PORT': port
    }
    
    # Add MQTT settings if needed
    if config_module.PROTOCOL.lower() == 'mqtt':
        config_dict['MQTT_BROKER'] = config_module.MQTT_BROKER
        config_dict['MQTT_PORT'] = config_module.MQTT_PORT
        config_dict['MQTT_TOPIC_PREFIX'] = config_module.MQTT_TOPIC_PREFIX
    
    # Create and start the bridge
    try:
        bridge = PhysicalCarBridge(args.vehicle_id, config_dict)
        bridge.start()
        
        print(f"Physical car bridge started for vehicle {args.vehicle_id}.")
        print("Press Ctrl+C to stop...")
        
        # Announce vehicle as ready
        state = cpm.VehicleState()
        state.vehicle_id = args.vehicle_id
        state.time_stamp = cpm.get_time_ns()
        bridge.state_writer.write(state)
        
        # Keep program alive until Ctrl+C
        try:
            while True:
                time.sleep(1)
                if bridge.is_connected():
                    sys.stdout.write(".")
                    sys.stdout.flush()
                else:
                    sys.stdout.write("x")
                    sys.stdout.flush()
        except KeyboardInterrupt:
            print("\nStopping bridge...")
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        if 'bridge' in locals():
            bridge.stop()
    
    print("Bridge stopped.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
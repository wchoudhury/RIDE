
import sys
import os
import time

#add paths
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../MessagesTest'))

from donkeycar_bridge.src.dds_interface_wrapper import DDSInterface
from messages_test import VehicleCommandDirect


def on_command(msg):
    
    print(f"Received command:")
    print(f"  Vehicle ID: {msg.vehicle_id}")
    print(f"  Throttle: {msg.motor_throttle}")
    print(f"  Steering: {msg.steering_servo}")
    print()
    
    #need Send to donkeycar actuators
    


def main():
    print("Starting DDS subscriber")
    dds = DDSInterface(domain_id=0)
    dds.subscribe("vehicle_command", on_command)
    
    print("Waiting for commands")

    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping")
        dds.close()


if __name__ == "__main__":
    main()

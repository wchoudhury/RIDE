
import time
import sys
import os

#add paths
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../MessagesTest'))

from donkeycar_bridge.src.dds_interface_wrapper import DDSInterface
from messages_test import Header, Pose2D, VehicleState


def main():
    print("Starting DDS publisher")
    dds = DDSInterface(domain_id=0)
    
    print("Publishing vehicle state every 0.05s (20 Hz)")
    
    try:
        while True:
            header = Header.now()
            
            #replace these values with real sensors later
            state = VehicleState(
                vehicle_id=1,
                header=header,
                pose=Pose2D(x=0.1, y=0.2, yaw=0.3),
                IPS_update_age_nanoseconds=1_000_000,
                odometer_distance=5.0,
                imu_acceleration_forward=0.1,
                imu_acceleration_left=0.0,
                imu_acceleration_up=9.81,
                imu_yaw=0.3,
                imu_yaw_rate=0.01,
                speed=0.5,
                battery_voltage=11.8,
                motor_current=0.2,
                motor_throttle=0.1,
                steering_servo=0.05,
                is_real=True,
            )
            
            dds.publish("vehicle_state", state)
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\nStopping...")
        dds.close()


if __name__ == "__main__":
    main()

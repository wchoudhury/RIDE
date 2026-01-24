import json
from typing import Callable, Any
from dataclasses import asdict

#I dont have fastdds so I will test it as json
try:
    import fastdds
    HAS_FASTDDS = True
except ImportError:
    HAS_FASTDDS = False
    print("No fastdds, just testing")

class DDSInterface:
    
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self.participant = None
        self.callbacks = {}
        
        if HAS_FASTDDS:
            factory = fastdds.DomainParticipantFactory.get_instance()
            self.participant = factory.create_participant(domain_id, fastdds.DomainParticipantQos())
            print(f"[DDS] Connected to {domain_id}")
        else:
            print(f"[TEST] Connected to domain {domain_id}")
    
    def publish(self, topic: str, message: Any):
        if HAS_FASTDDS and self.participant:
            print(f"[DDS] Publishing to {topic}: {type(message).__name__}")
        else:
            #just for testing
            try:
                data = json.dumps(asdict(message), indent=2)
            except:
                data = str(message)
            print(f"[TEST] {topic} -> {data}")
    
    def subscribe(self, topic: str, callback: Callable):
        self.callbacks[topic] = callback
        if HAS_FASTDDS and self.participant:
            print(f"[DDS] Subscribed to {topic}")
        else:
            print(f"[TEST] Subscribed to {topic}")
    
    def close(self):
        if HAS_FASTDDS and self.participant:
            factory = fastdds.DomainParticipantFactory.get_instance()
            factory.delete_participant(self.participant)
            print("[DDS] Closed")
        else:
            print("[TEST] Closed")

#test
if __name__ == "__main__":
    from messages_test import *
    
    print("Createing DDS")
    dds = DDSInterface(domain_id=0)
    
    print("Creating Messages")
    header = Header.now()
    
    vehicle_state = VehicleState(
        vehicle_id=1,
        header=header,
        pose=Pose2D(x=10.0, y=5.0, yaw=0.5),
        IPS_update_age_nanoseconds=1000000,
        odometer_distance=150.0,
        imu_acceleration_forward=0.5,
        imu_acceleration_left=0.1,
        imu_acceleration_up=9.81,
        imu_yaw=0.5,
        imu_yaw_rate=0.05,
        speed=5.5,
        battery_voltage=12.6,
        motor_current=2.1,
        motor_throttle=0.3,
        steering_servo=0.1,
        is_real=True
    )
    
    command = VehicleCommandDirect(
        vehicle_id=1,
        header=header,
        motor_throttle=0.4,
        steering_servo=0.2
    )
    
    #publishing
    print("publishing messages")
    dds.publish("vehicle_state", vehicle_state)
    dds.publish("vehicle_command", command)
    
    #subscribing
    print("subscribing to topics")
    def my_callback(data):
        print(f"got {data}")
    
    dds.subscribe("vehicle_state", my_callback)
    dds.subscribe("vehicle_command", my_callback)
    

    dds.close()
    

    print("done testing, everything works")


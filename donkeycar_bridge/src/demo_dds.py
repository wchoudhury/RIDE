
import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '../../MessagesTest'))
from messages_test import Header, Pose2D, VehicleState, VehicleCommandDirect

print("\n--- DDS Message Demo ---\n")

#create vehicleState message
print("Creating VehicleState message...")
print("-" * 40)

state = VehicleState(
    vehicle_id=1,
    header=Header.now(),
    pose=Pose2D(x=5.0, y=3.2, yaw=0.785),
    IPS_update_age_nanoseconds=500_000,
    odometer_distance=142.5,
    imu_acceleration_forward=0.8,
    imu_acceleration_left=0.1,
    imu_acceleration_up=9.81,
    imu_yaw=0.785,
    imu_yaw_rate=0.05,
    speed=2.3,
    battery_voltage=11.8,
    motor_current=1.5,
    motor_throttle=0.4,
    steering_servo=0.15,
    is_real=True,
)

print(f"Vehicle ID: {state.vehicle_id}")
print(f"Position: ({state.pose.x}, {state.pose.y})")
print(f"Speed: {state.speed} m/s")
print(f"Battery: {state.battery_voltage}V")
print(f"Throttle: {state.motor_throttle}, Steering: {state.steering_servo}")
print()

#create a command message
print("Creating VehicleCommandDirect message...")
print("-" * 40)

command = VehicleCommandDirect(
    vehicle_id=1,
    header=Header.now(),
    motor_throttle=0.6,
    steering_servo=-0.3
)

print(f"Vehicle ID: {command.vehicle_id}")
print(f"Throttle: {command.motor_throttle} (forward)")
print(f"Steering: {command.steering_servo} (left)")
print()

#testing publishing
print("Testing DDS publishing...")
print("-" * 40)

sys.path.append(os.path.dirname(__file__))
from donkeycar_bridge.src.dds_interface_wrapper import DDSInterface

dds = DDSInterface(domain_id=0)

print("Publishing 5 messages...")
for i in range(5):
    state.speed = 2.0 + (i * 0.5)
    state.pose.x += 0.5
    state.odometer_distance += 0.5
    
    print(f"#{i+1}: speed={state.speed} m/s, x={state.pose.x} m")
    dds.publish("vehicle_state", state)
    time.sleep(0.5)

print()

#testing command reception
print("Testing command reception...")
print("-" * 40)

def on_command_received(cmd):
    print(f"Got command for vehicle {cmd.vehicle_id}")
    print(f"  Throttle: {cmd.motor_throttle}, Steering: {cmd.steering_servo}")
    
    if cmd.motor_throttle > 0:
        print(f"  -> Forward at {cmd.motor_throttle*100}%")
    elif cmd.motor_throttle < 0:
        print(f"  -> Backward at {abs(cmd.motor_throttle)*100}%")
    else:
        print(f"  -> Stopped")

dds.subscribe("vehicle_command", on_command_received)

print("Simulating 3 commands...\n")

commands = [
    VehicleCommandDirect(1, Header.now(), 0.5, 0.0),
    VehicleCommandDirect(1, Header.now(), 0.3, 0.4),
    VehicleCommandDirect(1, Header.now(), 0.0, 0.0),
]

for cmd in commands:
    on_command_received(cmd)
    time.sleep(0.8)

print()

#simple car simulation
print("Car simulation (5 seconds)...")
print("-" * 40)

import math

x, y, yaw = 0.0, 0.0, 0.0
speed = 1.5
steering = 0.3
dt = 0.2

for i in range(25):
    x += speed * math.cos(yaw) * dt
    y += speed * math.sin(yaw) * dt
    yaw += steering * speed * dt
    
    battery = 12.0 - (i * 0.01)
    
    print(f"t={i*dt:.1f}s | pos=({x:5.2f}, {y:5.2f}) | yaw={math.degrees(yaw):5.1f}° | battery={battery:.2f}V")
    
    time.sleep(dt)

print("\nDone.")


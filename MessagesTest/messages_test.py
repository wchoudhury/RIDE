from dataclasses import dataclass, field
from typing import List
import time



@dataclass
class Header:
    create_stamp: int  # nanoseconds since epoch
    valid_after_stamp: int  # nanoseconds since epoch

    @staticmethod
    def now() -> "Header":
        ns = time.time_ns()
        return Header(create_stamp=ns, valid_after_stamp=ns)

@dataclass
class Pose2D:
    x: float  # meters
    y: float  # meters
    yaw: float  # radians

#car to cpm

@dataclass
class VehicleState:
    vehicle_id: int  # octet (0–255)
    header: Header
    pose: Pose2D
    IPS_update_age_nanoseconds: int  # unsigned long long
    odometer_distance: float  # m
    imu_acceleration_forward: float  # m/s²
    imu_acceleration_left: float  # m/s²
    imu_acceleration_up: float  # m/s²
    imu_yaw: float  # rad [0, 2π)
    imu_yaw_rate: float  # rad/s
    speed: float  # m/s
    battery_voltage: float  # V
    motor_current: float  # A
    motor_throttle: float  # [-1, 1]
    steering_servo: float  # [-1, 1]
    is_real: bool  

    def __post_init__(self):
        if not (0 <= self.vehicle_id <= 255):
            raise ValueError("vehicle_id must be 0..255")
        if not (-1.0 <= self.motor_throttle <= 1.0):
            raise ValueError("motor_throttle must be in [-1, 1]")
        if not (-1.0 <= self.steering_servo <= 1.0):
            raise ValueError("steering_servo must be in [-1, 1]")

# cpm to car

@dataclass
class VehicleCommandDirect:
    vehicle_id: int
    header: Header
    motor_throttle: float  # [-1, 1]
    steering_servo: float  # [-1, 1]

    def __post_init__(self):
        if not (0 <= self.vehicle_id <= 255):
            raise ValueError("vehicle_id must be 0..255")
        if not (-1.0 <= self.motor_throttle <= 1.0):
            raise ValueError("motor_throttle must be in [-1, 1]")
        if not (-1.0 <= self.steering_servo <= 1.0):
            raise ValueError("steering_servo must be in [-1, 1]")



@dataclass
class TimeStamp:
    nanoseconds: int  # ns since epoch

@dataclass
class TrajectoryPoint:
    t: TimeStamp  # (ns
    px: float  # m
    py: float  # m
    vx: float  # m/s
    vy: float  # m/s

@dataclass
class VehicleCommandTrajectory:
    vehicle_id: int
    header: Header
    trajectory_points: List[TrajectoryPoint] 

@dataclass
class IPS:
    vehicle_id: int
    pose: Pose2D

@dataclass
class HLCStartup:
    hlc_id: int
    status: str  # booting, ready, error

@dataclass
class VehicleStateList:
    states: List[VehicleState] = field(default_factory=list)

@dataclass
class ReadyStatus:
    hlc_id: int
    status: str  # ready

@dataclass
class SystemTrigger:
    command: str  # start or stop

@dataclass
class CommonroadDDSGoalState:
    planning_problem_id: int
    goal_state: dict   

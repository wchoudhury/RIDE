from dataclasses import dataclass, field
from typing import List, Optional
import time


@dataclass
class Header:
    create_stamp: int  # nanoseconds
    valid_after_stamp: int  # nanoseconds

    @staticmethod
    def now() -> "Header":
        """Helper to create header with current time."""
        ns = int(time.time() * 1e9)
        return Header(create_stamp=ns, valid_after_stamp=ns)


@dataclass
class Pose2D:
    x: float  # meters
    y: float  # meters
    yaw: float  # radians


@dataclass
class VehicleState:
    vehicle_id: int  # octet (0–255)
    header: Header
    pose: Pose2D
    IPS_update_age_nanoseconds: int  # unsigned long long
    odometer_distance: float  # meters
    imu_acceleration_forward: float  # m/s²
    imu_acceleration_left: float  # m/s²
    imu_acceleration_up: float  # m/s²
    imu_yaw: float  # rad (unfiltered)
    imu_yaw_rate: float  # rad/s
    speed: float  # m/s
    battery_voltage: float  # V
    motor_current: float  # A
    motor_throttle: float  # [-1, 1]
    steering_servo: float  # [-1, 1]
    is_real: bool  # True = physical, False = simulator


@dataclass
class VehicleCommandDirect:
    vehicle_id: int
    header: Header
    motor_throttle: float  # [-1, 1]
    steering_servo: float  # [-1, 1]


@dataclass
class TrajectoryPoint:
    ti: int  # absolute time (ns)
    px: float  # position x (m)
    py: float  # position y (m)
    vx: float  # velocity x (m/s)
    vy: float  # velocity y (m/s)


@dataclass
class VehicleCommandTrajectory:
    vehicle_id: int
    header: Header
    trajectory: List[TrajectoryPoint]


@dataclass
class IPS:
    vehicle_id: int
    pose: Pose2D


@dataclass
class HLCStartup:
    hlc_id: int
    status: str  # "booting", "ready", "error"


@dataclass
class VehicleStateList:
    states: List[VehicleState] = field(default_factory=list)


@dataclass
class ReadyStatus:
    hlc_id: int
    status: str  # "ready", etc.


@dataclass
class SystemTrigger:
    command: str  # "start" or "stop"


@dataclass
class CommonroadDDSGoalState:
    planning_problem_id: int
    goal_state: dict  # flexible: could hold pose, velocity, etc.
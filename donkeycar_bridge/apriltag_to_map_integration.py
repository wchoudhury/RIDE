#!/usr/bin/env python3
"""
AprilTag to Map Integration Script
This script connects the AprilTag localization pipeline to the CPM Lab map visualization.

Pipeline: AprilTag Detection → Position Calculation → DDS Publishing → Map Visualization

Usage:
    python apriltag_to_map_integration.py --vehicle-id 1 --camera-id 0
    python apriltag_to_map_integration.py --vehicle-id 1 --camera-ip 192.168.1.100
"""

import argparse
import time
import threading
import signal
import sys
from typing import Dict, Optional

# Import our components
from src.apriltag_localizer import AprilTagLocalizer
from src.map_visualization_subscriber import MapVisualizationSubscriber
import cpm

class AprilTagMapIntegration:
    """Integrates AprilTag localization with CPM Lab map visualization"""
    
    def __init__(self, vehicle_id: int, camera_config: Dict):
        """
        Initialize the AprilTag to Map integration.
        
        Args:
            vehicle_id: CPM Lab vehicle ID
            camera_config: Camera configuration (id, ip, etc.)
        """
        self.vehicle_id = vehicle_id
        self.camera_config = camera_config
        self.running = False
        
        # Initialize CPM communication (only once per process)
        try:
            cpm.init(f"apriltag_map_integration_{vehicle_id}")
        except:
            pass  # Already initialized
        
        self.logger = cpm.Logging.Instance()
        self.logger.set_id(f"apriltag_integration_{vehicle_id}")
        self.logger.set_min_level(cpm.LogLevel.Info)
        
        # Components
        self.apriltag_localizer = None
        self.map_subscriber = None
        self.vehicle_state_publisher = None
        
        # State
        self.current_position = {'x': 0.0, 'y': 0.0, 'yaw': 0.0, 'confidence': 0.0}
        self.position_lock = threading.Lock()
        
        # Processing thread
        self.processing_thread = None
        self.processing_rate = 20  # Hz
        
        # Statistics  
        self.stats = {
            'frames_processed': 0,
            'detections_made': 0,
            'positions_published': 0,
            'start_time': time.time()
        }
        
        print(f"[Integration] Initialized for vehicle {vehicle_id}")
    
    def start(self) -> bool:
        """Start the AprilTag to Map integration"""
        try:
            # Initialize AprilTag localizer
            print("[Integration] Starting AprilTag localizer...")
            self.apriltag_localizer = self._setup_apriltag_localizer()
            
            # Initialize map visualization subscriber  
            print("[Integration] Starting map visualization...")
            self.map_subscriber = MapVisualizationSubscriber(self.vehicle_id)
            if not self.map_subscriber.start():
                print("[Integration] Failed to start map subscriber")
                return False
            
            # Initialize DDS publisher for vehicle state
            print("[Integration] Setting up DDS publisher...")
            self.vehicle_state_publisher = cpm.Writer(f"vehicle_state_{self.vehicle_id}")
            
            # Start processing loop
            self.running = True
            self.processing_thread = threading.Thread(target=self._processing_loop)
            self.processing_thread.daemon = True
            self.processing_thread.start()
            
            print(f"[Integration] Successfully started AprilTag→Map integration for vehicle {self.vehicle_id}")
            return True
            
        except Exception as e:
            print(f"[Integration] Failed to start: {e}")
            return False
    
    def stop(self):
        """Stop the integration"""
        print(f"[Integration] Stopping AprilTag→Map integration for vehicle {self.vehicle_id}...")
        
        # Stop processing
        self.running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=2.0)
        
        # Stop components
        if self.map_subscriber:
            self.map_subscriber.stop()
        
        # Print statistics
        self._print_stats()
        
        print(f"[Integration] Stopped integration for vehicle {self.vehicle_id}")
    
    def _setup_apriltag_localizer(self) -> AprilTagLocalizer:
        """Set up the AprilTag localizer with proper configuration"""
        
        # Camera calibration parameters for Basler acA2040-90uc (2048x2048)
        # These are estimated values - MUST BE CALIBRATED FOR YOUR SETUP
        camera_params = {
            'fx': 1800.0,  # Focal length X - estimated for 1" sensor at 2048px
            'fy': 1800.0,  # Focal length Y - estimated for 1" sensor at 2048px
            'cx': 1024.0,  # Principal point X - center of 2048px width
            'cy': 1024.0,  # Principal point Y - center of 2048px height
            'k1': 0.0,     # Radial distortion - NEEDS CALIBRATION
            'k2': 0.0,     # Radial distortion - NEEDS CALIBRATION
            'p1': 0.0,     # Tangential distortion - NEEDS CALIBRATION
            'p2': 0.0      # Tangential distortion - NEEDS CALIBRATION
        }
        
        # AprilTag world coordinates (example 2x2m square track)
        # IMPORTANT: Update these coordinates to match your physical tag positions
        tag_map = {
            0: (0.0, 0.0, 0.0),     # Origin - bottom left
            1: (2.0, 0.0, 0.0),     # Bottom right
            2: (2.0, 2.0, 0.0),     # Top right  
            3: (0.0, 2.0, 0.0),     # Top left
            4: (1.0, 1.0, 0.0),     # Center (optional)
        }
        
        localizer = AprilTagLocalizer(camera_params, tag_map)
        
        print(f"[Integration] AprilTag localizer configured with {len(tag_map)} tags")
        print("[Integration] ⚠️  IMPORTANT: Update camera_params and tag_map for your setup!")
        
        return localizer
    
    def _processing_loop(self):
        """Main processing loop for AprilTag detection and publishing"""
        import cv2
        
        # Initialize camera
        camera = self._setup_camera()
        if camera is None:
            print("[Integration] Failed to initialize camera")
            return
        
        processing_interval = 1.0 / self.processing_rate
        last_processing_time = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Process at target rate
                if current_time - last_processing_time >= processing_interval:
                    self._process_frame(camera)
                    last_processing_time = current_time
                
                # Small delay to prevent CPU overload
                time.sleep(0.01)
                
            except Exception as e:
                self.logger.write(cpm.LogLevel.Error, f"Processing loop error: {e}")
                time.sleep(0.1)
        
        # Cleanup Basler camera
        if camera:
            camera.disconnect()
    
    def _setup_camera(self):
        """Set up Basler camera using proper Pylon SDK interface"""
        from src.basler_camera_interface import create_camera_interface
        
        try:
            if 'id' in self.camera_config:
                # Local Basler camera using Pylon SDK
                camera_id = self.camera_config['id']
                print(f"[Integration] Connecting to Basler camera {camera_id} using Pylon SDK")
                
                # Create Basler camera interface
                camera = create_camera_interface(camera_id, prefer_basler=True)
                
                # Connect to camera
                if not camera.connect():
                    print("[Integration] ERROR: Failed to connect to Basler camera")
                    print("[Integration] Check:")
                    print("  1. Camera is connected via USB 3.0")
                    print("  2. Pylon SDK is installed (pip install pypylon)")
                    print("  3. Camera is not used by another application")
                    return None
                
                # Start image acquisition
                if not camera.start_grabbing():
                    print("[Integration] ERROR: Failed to start camera acquisition")
                    camera.disconnect()
                    return None
                
                # Test frame grab
                test_frame = camera.grab_frame(timeout_ms=5000)
                if test_frame is None:
                    print("[Integration] ERROR: Failed to grab test frame")
                    camera.disconnect()
                    return None
                
                # Verify frame specifications
                if test_frame.shape != (2048, 2048, 3):
                    print(f"[Integration] ERROR: Wrong frame shape: {test_frame.shape}")
                    print("[Integration] Expected: (2048, 2048, 3) for acA2040-90uc")
                    camera.disconnect()
                    return None
                
                # Print camera info
                info = camera.get_camera_info()
                print(f"[Integration] Camera connected: {info.get('model', 'Unknown')} "
                      f"(Serial: {info.get('serial', 'Unknown')})")
                print(f"[Integration] Resolution: {info.get('width', 0)}x{info.get('height', 0)} "
                      f"@ {info.get('fps', 0)}fps")
                
                return camera
                
            elif 'ip' in self.camera_config:
                print("[Integration] ERROR: Network cameras not supported for Basler integration")
                print("[Integration] Basler cameras must be directly connected via USB 3.0")
                return None
                
            else:
                print("[Integration] ERROR: No valid camera configuration found")
                print("[Integration] Specify camera with --camera-id parameter")
                return None
            
        except Exception as e:
            print(f"[Integration] Camera setup error: {e}")
            return None
    
    def _process_frame(self, camera):
        """Process a single camera frame"""
        try:
            # Capture frame from Basler camera
            frame = camera.grab_frame(timeout_ms=100)  # 100ms timeout for high frame rate
            if frame is None:
                return
            
            self.stats['frames_processed'] += 1
            
            # Process with AprilTag localizer
            result = self.apriltag_localizer.process_frame(frame)
            
            # Update statistics
            if result['num_tags'] > 0:
                self.stats['detections_made'] += 1
            
            # Update position
            position = result['position']
            with self.position_lock:
                self.current_position = position.copy()
            
            # Publish to DDS if we have a good position
            if position['confidence'] > 0.3:
                self._publish_vehicle_state(position)
                self.stats['positions_published'] += 1
            
            # Optional: Display processed frame for debugging
            if self.camera_config.get('show_debug', False):
                debug_frame = self.apriltag_localizer.draw_detections(frame, result)
                cv2.imshow(f"AprilTag Detection - Vehicle {self.vehicle_id}", debug_frame)
                cv2.waitKey(1)
                
        except Exception as e:
            self.logger.write(cpm.LogLevel.Error, f"Frame processing error: {e}")
    
    def _publish_vehicle_state(self, position: Dict):
        """Publish vehicle state to DDS for map visualization"""
        try:
            # Create VehicleState message
            vehicle_state = cpm.VehicleState()
            vehicle_state.vehicle_id = self.vehicle_id
            
            # Set header
            vehicle_state.header.create_stamp = cpm.get_time_ns()
            vehicle_state.header.valid_after_stamp = cpm.get_time_ns()
            
            # Set pose from AprilTag localization
            vehicle_state.pose.x = position['x']
            vehicle_state.pose.y = position['y']
            vehicle_state.pose.yaw = position['yaw']
            
            # Set IPS update age (0 since this is fresh AprilTag data)
            vehicle_state.IPS_update_age_nanoseconds = 0
            
            # Set as real vehicle (not simulation)
            vehicle_state.is_real = True
            
            # Other fields (if available)
            vehicle_state.speed = 0.0  # Could be calculated from position history
            vehicle_state.motor_throttle = 0.0
            vehicle_state.steering_servo = 0.0
            vehicle_state.battery_voltage = 0.0
            vehicle_state.motor_current = 0.0
            
            # Publish the message
            self.vehicle_state_publisher.write(vehicle_state)
            
        except Exception as e:
            self.logger.write(cpm.LogLevel.Error, f"Error publishing vehicle state: {e}")
    
    def get_current_position(self) -> Dict:
        """Get current vehicle position"""
        with self.position_lock:
            return self.current_position.copy()
    
    def _print_stats(self):
        """Print integration statistics"""
        runtime = time.time() - self.stats['start_time']
        
        print(f"\n[Integration] Vehicle {self.vehicle_id} Statistics:")
        print(f"  Runtime: {runtime:.1f} seconds")
        print(f"  Frames processed: {self.stats['frames_processed']}")
        print(f"  AprilTag detections: {self.stats['detections_made']}")
        print(f"  Positions published: {self.stats['positions_published']}")
        
        if runtime > 0:
            print(f"  Processing rate: {self.stats['frames_processed']/runtime:.1f} FPS")
            print(f"  Detection rate: {self.stats['detections_made']/runtime:.1f} Hz")
            print(f"  Publishing rate: {self.stats['positions_published']/runtime:.1f} Hz")
        
        if self.stats['frames_processed'] > 0:
            detection_ratio = self.stats['detections_made'] / self.stats['frames_processed']
            print(f"  Detection success: {detection_ratio*100:.1f}%")


def main():
    """Main function to run AprilTag to Map integration"""
    parser = argparse.ArgumentParser(description='AprilTag to Map Integration')
    parser.add_argument('--vehicle-id', type=int, default=1, 
                       help='CPM Lab vehicle ID (default: 1)')
    parser.add_argument('--camera-id', type=int, 
                       help='Local camera ID (e.g., 0 for /dev/video0)')
    parser.add_argument('--camera-ip', type=str,
                       help='Network camera IP address')
    parser.add_argument('--show-debug', action='store_true',
                       help='Show debug visualization window')
    
    args = parser.parse_args()
    
    # Configure camera
    camera_config = {'show_debug': args.show_debug}
    
    if args.camera_id is not None:
        camera_config['id'] = args.camera_id
    elif args.camera_ip:
        camera_config['ip'] = args.camera_ip
    else:
        print("ERROR: Must specify either --camera-id or --camera-ip")
        sys.exit(1)
    
    # Create and start integration
    integration = AprilTagMapIntegration(args.vehicle_id, camera_config)
    
    # Set up signal handlers for clean shutdown
    def signal_handler(sig, frame):
        print("\n[Integration] Received shutdown signal...")
        integration.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start integration
    print(f"[Integration] Starting AprilTag→Map integration for vehicle {args.vehicle_id}")
    print(f"[Integration] Camera config: {camera_config}")
    print("[Integration] Press Ctrl+C to stop")
    
    if integration.start():
        try:
            # Keep running until stopped
            while integration.running:
                time.sleep(1)
                
                # Print status occasionally
                position = integration.get_current_position()
                if position['confidence'] > 0.5:
                    print(f"[Integration] Vehicle {args.vehicle_id} position: "
                          f"x={position['x']:.2f}m, y={position['y']:.2f}m, "
                          f"confidence={position['confidence']:.2f}")
                
        except KeyboardInterrupt:
            print("\n[Integration] Interrupted by user")
        
        integration.stop()
    else:
        print("[Integration] Failed to start integration")
        sys.exit(1)


if __name__ == "__main__":
    main()
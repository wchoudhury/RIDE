"""
Camera-based localization integration for Donkeycar Bridge.
Handles camera feed processing and AprilTag localization.
"""

import cv2
import numpy as np
import threading
import time
from typing import Dict, Optional, Callable
from apriltag_localizer import AprilTagLocalizer

class CameraLocalizer:
    def __init__(self, camera_params: Optional[Dict] = None, tag_map: Optional[Dict] = None):
        """
        Initialize camera-based localizer.
        
        Args:
            camera_params: Camera calibration parameters
            tag_map: AprilTag positions in world coordinates
        """
        self.apriltag_localizer = AprilTagLocalizer(camera_params, tag_map)
        
        # Camera capture
        self.camera = None
        self.camera_index = 0  # Default camera
        
        # Processing control
        self.is_running = False
        self.processing_thread = None
        self.frame_lock = threading.Lock()
        
        # Current camera frame
        self.current_frame = None
        self.frame_timestamp = 0
        
        # Position callback
        self.position_callback = None
        
        # Processing rate
        self.target_fps = 30
        self.processing_interval = 1.0 / self.target_fps
        
        print("[CameraLocalizer] Initialized")
    
    def set_position_callback(self, callback: Callable[[Dict], None]):
        """Set callback function for position updates"""
        self.position_callback = callback
    
    def start_camera(self, camera_index: int = 0) -> bool:
        """
        Start camera capture.
        
        Args:
            camera_index: Camera device index
            
        Returns:
            True if camera started successfully
        """
        try:
            self.camera = cv2.VideoCapture(camera_index)
            self.camera_index = camera_index
            
            if not self.camera.isOpened():
                print(f"[CameraLocalizer] Failed to open camera {camera_index}")
                return False
            
            # Set camera properties for better performance
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            
            print(f"[CameraLocalizer] Camera {camera_index} started successfully")
            return True
            
        except Exception as e:
            print(f"[CameraLocalizer] Camera start error: {e}")
            return False
    
    def start_processing(self) -> bool:
        """Start the localization processing thread"""
        if self.is_running:
            print("[CameraLocalizer] Processing already running")
            return True
        
        if self.camera is None:
            print("[CameraLocalizer] Camera not initialized")
            return False
        
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
        print("[CameraLocalizer] Processing started")
        return True
    
    def stop_processing(self):
        """Stop the localization processing"""
        self.is_running = False
        
        if self.processing_thread:
            self.processing_thread.join(timeout=2.0)
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        print("[CameraLocalizer] Processing stopped")
    
    def _processing_loop(self):
        """Main processing loop for camera frames"""
        last_process_time = 0
        
        while self.is_running:
            try:
                current_time = time.time()
                
                # Capture frame
                ret, frame = self.camera.read()
                if not ret:
                    print("[CameraLocalizer] Failed to capture frame")
                    time.sleep(0.1)
                    continue
                
                # Update current frame
                with self.frame_lock:
                    self.current_frame = frame.copy()
                    self.frame_timestamp = current_time
                
                # Process frame at target rate
                if current_time - last_process_time >= self.processing_interval:
                    self._process_current_frame(frame)
                    last_process_time = current_time
                
                # Small delay to prevent CPU overload
                time.sleep(0.01)
                
            except Exception as e:
                print(f"[CameraLocalizer] Processing error: {e}")
                time.sleep(0.1)
    
    def _process_current_frame(self, frame: np.ndarray):
        """Process a single frame for localization"""
        try:
            # Run AprilTag detection and localization
            result = self.apriltag_localizer.process_frame(frame)
            
            # Add frame info to result
            result['frame_timestamp'] = self.frame_timestamp
            result['camera_index'] = self.camera_index
            
            # Call position callback if set
            if self.position_callback:
                self.position_callback(result)
            
            # Log detection info
            if result['num_tags'] > 0:
                pos = result['position']
                print(f"[CameraLocalizer] Position: x={pos['x']:.2f}, y={pos['y']:.2f}, "
                      f"yaw={np.degrees(pos['yaw']):.1f}°, conf={pos['confidence']:.2f}, "
                      f"tags={result['num_tags']}")
            
        except Exception as e:
            print(f"[CameraLocalizer] Frame processing error: {e}")
    
    def get_current_position(self) -> Dict:
        """Get the current position estimate"""
        return self.apriltag_localizer.get_position()
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get the current camera frame"""
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None
    
    def get_visualization_frame(self) -> Optional[np.ndarray]:
        """Get camera frame with localization visualization overlay"""
        frame = self.get_current_frame()
        if frame is None:
            return None
        
        try:
            # Process frame for detections
            result = self.apriltag_localizer.process_frame(frame)
            
            # Draw visualization
            vis_frame = self.apriltag_localizer.draw_detections(frame, result)
            
            return vis_frame
            
        except Exception as e:
            print(f"[CameraLocalizer] Visualization error: {e}")
            return frame
    
    def update_tag_map(self, tag_map: Dict[int, tuple]):
        """Update the AprilTag position map"""
        self.apriltag_localizer.set_tag_map(tag_map)
    
    def calibrate_camera(self, calibration_data: Dict):
        """Update camera calibration parameters"""
        self.apriltag_localizer.calibrate_camera(calibration_data)
    
    def capture_frame_to_file(self, filename: str) -> bool:
        """Capture current frame to file for debugging"""
        frame = self.get_current_frame()
        if frame is None:
            return False
        
        try:
            cv2.imwrite(filename, frame)
            print(f"[CameraLocalizer] Frame saved to {filename}")
            return True
        except Exception as e:
            print(f"[CameraLocalizer] Frame save error: {e}")
            return False
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        self.stop_processing()

def test_camera_localizer():
    """Test function for camera localizer"""
    def position_callback(result):
        pos = result['position']
        print(f"Position update: x={pos['x']:.2f}, y={pos['y']:.2f}, "
              f"conf={pos['confidence']:.2f}, tags={result['num_tags']}")
    
    # Create localizer
    localizer = CameraLocalizer()
    localizer.set_position_callback(position_callback)
    
    # Try to start camera (will fail without physical camera)
    if localizer.start_camera(0):
        localizer.start_processing()
        
        try:
            # Run for 10 seconds
            time.sleep(10)
        except KeyboardInterrupt:
            pass
        
        localizer.stop_processing()
    else:
        print("No camera available for testing")
    
if __name__ == "__main__":
    test_camera_localizer()
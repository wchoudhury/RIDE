"""
Basler Camera Interface for RIDE Project
Provides proper communication with Basler acA2040-90uc camera using Pylon SDK.
"""

import numpy as np
import time
from typing import Optional, Dict, Tuple

try:
    from pypylon import pylon
    PYLON_AVAILABLE = True
except ImportError:
    PYLON_AVAILABLE = False
    print("WARNING: pypylon not installed. Install with: pip install pypylon")

class BaslerCameraInterface:
    """Interface for Basler acA2040-90uc camera using Pylon SDK"""
    
    def __init__(self, camera_index: int = 0):
        """
        Initialize Basler camera interface.
        
        Args:
            camera_index: Index of camera to connect to (0 for first camera)
        """
        if not PYLON_AVAILABLE:
            raise ImportError("pypylon not available. Install with: pip install pypylon")
        
        self.camera_index = camera_index
        self.camera = None
        self.converter = pylon.ImageFormatConverter()
        self.is_connected = False
        
        # Configure image format converter to RGB
        self.converter.OutputPixelFormat = pylon.PixelType_RGB8packed
        self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
        
        # Camera specifications for acA2040-90uc
        self.target_specs = {
            'width': 2048,
            'height': 2048,
            'fps': 90,
            'pixel_format': 'RGB8',
            'sensor_format': '1"',
            'model': 'acA2040-90uc'
        }
        
        print(f"[BaslerCamera] Initialized interface for camera index {camera_index}")
    
    def connect(self) -> bool:
        """
        Connect to Basler camera and configure it.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Get camera list
            devices = pylon.TlFactory.GetInstance().EnumerateDevices()
            if len(devices) == 0:
                print("[BaslerCamera] ERROR: No Basler cameras found")
                return False
            
            if self.camera_index >= len(devices):
                print(f"[BaslerCamera] ERROR: Camera index {self.camera_index} not available")
                print(f"[BaslerCamera] Available cameras: {len(devices)}")
                return False
            
            # Get device info
            device_info = devices[self.camera_index]
            camera_model = device_info.GetModelName()
            camera_serial = device_info.GetSerialNumber()
            
            print(f"[BaslerCamera] Connecting to: {camera_model} (Serial: {camera_serial})")
            
            # Verify this is the expected camera model
            if "acA2040-90uc" not in camera_model:
                print(f"[BaslerCamera] WARNING: Expected acA2040-90uc, got {camera_model}")
                print("[BaslerCamera] Proceeding anyway, but specs may not match")
            
            # Create camera instance
            self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(device_info))
            
            # Open camera connection
            self.camera.Open()
            
            # Configure camera settings for acA2040-90uc
            self._configure_camera()
            
            # Verify configuration
            if not self._verify_configuration():
                print("[BaslerCamera] ERROR: Camera configuration verification failed")
                self.disconnect()
                return False
            
            self.is_connected = True
            print(f"[BaslerCamera] Successfully connected and configured {camera_model}")
            return True
            
        except Exception as e:
            print(f"[BaslerCamera] Connection error: {e}")
            return False
    
    def _configure_camera(self):
        """Configure camera settings for optimal AprilTag detection"""
        try:
            print("[BaslerCamera] Configuring camera settings...")
            
            # Set pixel format to RGB8 for color images
            self.camera.PixelFormat.SetValue("RGB8")
            
            # Set resolution to full 2048x2048
            self.camera.Width.SetValue(2048)
            self.camera.Height.SetValue(2048)
            
            # Set frame rate
            self.camera.AcquisitionFrameRateEnable.SetValue(True)
            self.camera.AcquisitionFrameRate.SetValue(90.0)
            
            # Set exposure settings for good AprilTag detection
            self.camera.ExposureMode.SetValue("Timed")
            self.camera.ExposureAuto.SetValue("Off")
            self.camera.ExposureTime.SetValue(5000.0)  # 5ms exposure
            
            # Set gain settings
            self.camera.GainAuto.SetValue("Off")
            self.camera.Gain.SetValue(0.0)  # Minimum gain for low noise
            
            # Optimize for indoor lighting and high contrast
            self.camera.LightSourcePreset.SetValue("Daylight5000K")
            
            # Enable timestamp for synchronization
            self.camera.TimestampLatch.SetValue("Software")
            
            print("[BaslerCamera] Camera configuration complete")
            
        except Exception as e:
            print(f"[BaslerCamera] Configuration error: {e}")
            raise
    
    def _verify_configuration(self) -> bool:
        """Verify camera was configured correctly"""
        try:
            # Check resolution
            width = self.camera.Width.GetValue()
            height = self.camera.Height.GetValue()
            if width != 2048 or height != 2048:
                print(f"[BaslerCamera] ERROR: Resolution mismatch. Got {width}x{height}, expected 2048x2048")
                return False
            
            # Check pixel format
            pixel_format = self.camera.PixelFormat.GetValue()
            if pixel_format != "RGB8":
                print(f"[BaslerCamera] ERROR: Pixel format mismatch. Got {pixel_format}, expected RGB8")
                return False
            
            # Check frame rate
            fps = self.camera.AcquisitionFrameRate.GetValue()
            if abs(fps - 90.0) > 1.0:
                print(f"[BaslerCamera] WARNING: Frame rate mismatch. Got {fps}, expected 90")
            
            print(f"[BaslerCamera] Configuration verified: {width}x{height} @ {fps}fps, {pixel_format}")
            return True
            
        except Exception as e:
            print(f"[BaslerCamera] Verification error: {e}")
            return False
    
    def start_grabbing(self) -> bool:
        """Start continuous image acquisition"""
        try:
            if not self.is_connected:
                print("[BaslerCamera] ERROR: Camera not connected")
                return False
            
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            print("[BaslerCamera] Started image acquisition")
            return True
            
        except Exception as e:
            print(f"[BaslerCamera] Start grabbing error: {e}")
            return False
    
    def grab_frame(self, timeout_ms: int = 5000) -> Optional[np.ndarray]:
        """
        Grab a single frame from the camera.
        
        Args:
            timeout_ms: Timeout in milliseconds
            
        Returns:
            RGB image as numpy array, or None if failed
        """
        try:
            if not self.camera.IsGrabbing():
                print("[BaslerCamera] ERROR: Camera not grabbing")
                return None
            
            # Retrieve image
            grab_result = self.camera.RetrieveResult(timeout_ms, pylon.TimeoutHandling_ThrowException)
            
            if grab_result.GrabSucceeded():
                # Convert to RGB format
                image = self.converter.Convert(grab_result)
                img_array = image.GetArray()
                
                # Release grab result
                grab_result.Release()
                
                return img_array
            else:
                print(f"[BaslerCamera] Grab failed: {grab_result.ErrorCode} - {grab_result.ErrorDescription}")
                grab_result.Release()
                return None
                
        except Exception as e:
            print(f"[BaslerCamera] Frame grab error: {e}")
            return None
    
    def stop_grabbing(self):
        """Stop image acquisition"""
        try:
            if self.camera and self.camera.IsGrabbing():
                self.camera.StopGrabbing()
                print("[BaslerCamera] Stopped image acquisition")
        except Exception as e:
            print(f"[BaslerCamera] Stop grabbing error: {e}")
    
    def disconnect(self):
        """Disconnect from camera"""
        try:
            self.stop_grabbing()
            
            if self.camera and self.camera.IsOpen():
                self.camera.Close()
                print("[BaslerCamera] Disconnected from camera")
            
            self.is_connected = False
            
        except Exception as e:
            print(f"[BaslerCamera] Disconnect error: {e}")
    
    def get_camera_info(self) -> Dict:
        """Get camera information and current settings"""
        if not self.is_connected:
            return {"error": "Camera not connected"}
        
        try:
            info = {
                "model": self.camera.DeviceModelName.GetValue(),
                "serial": self.camera.DeviceSerialNumber.GetValue(),
                "firmware": self.camera.DeviceFirmwareVersion.GetValue(),
                "width": self.camera.Width.GetValue(),
                "height": self.camera.Height.GetValue(), 
                "pixel_format": self.camera.PixelFormat.GetValue(),
                "fps": self.camera.AcquisitionFrameRate.GetValue(),
                "exposure_time": self.camera.ExposureTime.GetValue(),
                "gain": self.camera.Gain.GetValue(),
                "temperature": self.camera.DeviceTemperature.GetValue()
            }
            return info
            
        except Exception as e:
            return {"error": f"Failed to get camera info: {e}"}
    
    def __del__(self):
        """Cleanup on destruction"""
        self.disconnect()


# OpenCV fallback for testing (when Basler not available)
class OpenCVCameraFallback:
    """Fallback camera interface using OpenCV for testing"""
    
    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.camera = None
        self.is_connected = False
        print(f"[OpenCVFallback] WARNING: Using OpenCV fallback for camera {camera_index}")
        print("[OpenCVFallback] This may not work properly with Basler cameras")
    
    def connect(self) -> bool:
        import cv2
        self.camera = cv2.VideoCapture(self.camera_index)
        if not self.camera.isOpened():
            return False
        
        # Force exact settings - no fallback
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 2048)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 2048)
        self.camera.set(cv2.CAP_PROP_FPS, 90)
        
        self.is_connected = True
        return True
    
    def start_grabbing(self) -> bool:
        return self.is_connected
    
    def grab_frame(self, timeout_ms: int = 5000) -> Optional[np.ndarray]:
        if not self.is_connected:
            return None
        
        ret, frame = self.camera.read()
        return frame if ret else None
    
    def stop_grabbing(self):
        pass
    
    def disconnect(self):
        if self.camera:
            self.camera.release()
        self.is_connected = False
    
    def get_camera_info(self) -> Dict:
        return {"model": "OpenCV Fallback", "warning": "Not using Pylon SDK"}


def create_camera_interface(camera_index: int = 0, prefer_basler: bool = True) -> 'BaslerCameraInterface':
    """
    Factory function to create appropriate camera interface.
    
    Args:
        camera_index: Camera index to connect to
        prefer_basler: Whether to prefer Basler Pylon SDK over OpenCV
        
    Returns:
        Camera interface instance
    """
    if prefer_basler and PYLON_AVAILABLE:
        return BaslerCameraInterface(camera_index)
    else:
        if prefer_basler:
            print("[CameraFactory] WARNING: Pylon SDK not available, using OpenCV fallback")
        return OpenCVCameraFallback(camera_index)


def test_basler_camera():
    """Test function for Basler camera interface"""
    print("=== Testing Basler Camera Interface ===")
    
    # Create camera interface
    camera = create_camera_interface(0, prefer_basler=True)
    
    try:
        # Connect to camera
        if not camera.connect():
            print("Failed to connect to camera")
            return
        
        # Print camera info
        info = camera.get_camera_info()
        print(f"Camera Info: {info}")
        
        # Start grabbing
        if not camera.start_grabbing():
            print("Failed to start grabbing")
            return
        
        # Grab a few test frames
        print("Grabbing test frames...")
        for i in range(5):
            frame = camera.grab_frame()
            if frame is not None:
                print(f"Frame {i+1}: {frame.shape}, dtype={frame.dtype}")
            else:
                print(f"Frame {i+1}: Failed")
            
            time.sleep(0.1)
        
        print("Test completed successfully")
        
    finally:
        camera.disconnect()


if __name__ == "__main__":
    test_basler_camera()
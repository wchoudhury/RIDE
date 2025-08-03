"""
AprilTag-based localization system for Donkeycar Bridge.
Detects AprilTags from camera feed and calculates vehicle position.
"""

import cv2
import numpy as np
import apriltag
import math
from typing import Dict, List, Tuple, Optional

class AprilTagLocalizer:
    def __init__(self, camera_params: Optional[Dict] = None, tag_map: Optional[Dict] = None):
        """
        Initialize AprilTag localizer.
        
        Args:
            camera_params: Camera calibration parameters (fx, fy, cx, cy, k1, k2, p1, p2)
            tag_map: Dictionary mapping tag IDs to world coordinates {tag_id: (x, y, z)}
        """
        # Initialize AprilTag detector with default options
        options = apriltag.DetectorOptions(families="tag36h11")
        self.detector = apriltag.Detector(options)
        
        # Camera parameters (default values - should be calibrated)
        self.camera_params = camera_params or {
            'fx': 500.0,  # Focal length X
            'fy': 500.0,  # Focal length Y  
            'cx': 320.0,  # Principal point X
            'cy': 240.0,  # Principal point Y
            'k1': 0.0,    # Radial distortion
            'k2': 0.0,    # Radial distortion
            'p1': 0.0,    # Tangential distortion
            'p2': 0.0     # Tangential distortion
        }
        
        # AprilTag to world coordinate mapping
        self.tag_map = tag_map or self._create_default_tag_map()
        
        # Tag size in meters (physical size of printed tags)
        self.tag_size = 0.1  # 10cm tags
        
        # Vehicle position estimate
        self.current_position = {'x': 0.0, 'y': 0.0, 'yaw': 0.0, 'confidence': 0.0}
        
        print(f"[AprilTag] Localizer initialized with {len(self.tag_map)} known tags")
    
    def _create_default_tag_map(self) -> Dict[int, Tuple[float, float, float]]:
        """Create a default tag map for testing"""
        # Example: tags arranged in a grid around a track
        tag_map = {
            0: (0.0, 0.0, 0.0),     # Origin tag
            1: (2.0, 0.0, 0.0),     # 2m along X-axis
            2: (2.0, 2.0, 0.0),     # Corner tag
            3: (0.0, 2.0, 0.0),     # Complete the square
            4: (1.0, 1.0, 0.0),     # Center tag
            5: (4.0, 0.0, 0.0),     # Extended track
            6: (4.0, 2.0, 0.0),     # Extended corner
        }
        return tag_map
    
    def process_frame(self, image: np.ndarray) -> Dict:
        """
        Process camera frame and detect AprilTags for localization.
        
        Args:
            image: Camera frame as numpy array
            
        Returns:
            Dictionary with position estimate and detection info
        """
        # Convert to grayscale for AprilTag detection
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Detect AprilTags
        detections = self.detector.detect(gray)
        
        result = {
            'position': self.current_position.copy(),
            'detections': [],
            'num_tags': len(detections),
            'timestamp': cv2.getTickCount() / cv2.getTickFrequency()
        }
        
        if not detections:
            # No tags detected - return last known position with low confidence
            result['position']['confidence'] = max(0.0, self.current_position['confidence'] - 0.1)
            return result
        
        # Process each detection
        valid_positions = []
        
        for detection in detections:
            tag_id = detection.tag_id
            
            if tag_id not in self.tag_map:
                print(f"[AprilTag] Unknown tag ID: {tag_id}")
                continue
            
            # Get tag position in world coordinates
            tag_world_pos = self.tag_map[tag_id]
            
            # Calculate vehicle position from tag detection
            vehicle_pos = self._calculate_position_from_tag(detection, tag_world_pos)
            
            if vehicle_pos:
                valid_positions.append(vehicle_pos)
                
                # Store detection info for visualization
                result['detections'].append({
                    'tag_id': tag_id,
                    'corners': detection.corners.tolist(),
                    'center': detection.center.tolist(),
                    'estimated_position': vehicle_pos
                })
        
        # Update position estimate
        if valid_positions:
            self.current_position = self._fuse_position_estimates(valid_positions)
            result['position'] = self.current_position.copy()
        else:
            # Decay confidence if no valid detections
            self.current_position['confidence'] = max(0.0, self.current_position['confidence'] - 0.2)
            result['position'] = self.current_position.copy()
        
        return result
    
    def _calculate_position_from_tag(self, detection, tag_world_pos: Tuple[float, float, float]) -> Optional[Dict]:
        """
        Calculate vehicle position from a single tag detection.
        
        Args:
            detection: AprilTag detection object
            tag_world_pos: Tag position in world coordinates (x, y, z)
            
        Returns:
            Estimated vehicle position or None if calculation fails
        """
        try:
            # Camera intrinsic matrix
            camera_matrix = np.array([
                [self.camera_params['fx'], 0, self.camera_params['cx']],
                [0, self.camera_params['fy'], self.camera_params['cy']],
                [0, 0, 1]
            ])
            
            # Distortion coefficients
            dist_coeffs = np.array([
                self.camera_params['k1'], self.camera_params['k2'],
                self.camera_params['p1'], self.camera_params['p2']
            ])
            
            # 3D tag corners in tag coordinate system
            tag_3d_points = np.array([
                [-self.tag_size/2, -self.tag_size/2, 0],
                [ self.tag_size/2, -self.tag_size/2, 0],
                [ self.tag_size/2,  self.tag_size/2, 0],
                [-self.tag_size/2,  self.tag_size/2, 0]
            ], dtype=np.float32)
            
            # 2D tag corners in image
            image_points = detection.corners.astype(np.float32)
            
            # Solve PnP to get tag pose relative to camera
            success, rvec, tvec = cv2.solvePnP(
                tag_3d_points, image_points, camera_matrix, dist_coeffs
            )
            
            if not success:
                return None
            
            # Convert rotation vector to rotation matrix
            R_tag_cam, _ = cv2.Rodrigues(rvec)
            
            # Camera pose relative to tag
            R_cam_tag = R_tag_cam.T
            t_cam_tag = -R_cam_tag @ tvec.flatten()
            
            # Transform to world coordinates
            tag_x, tag_y, tag_z = tag_world_pos
            
            # For simplicity, assume tags are vertical and camera is horizontal
            # This is a simplified transformation - would need full 3D transformation for complex setups
            
            # Extract yaw angle from camera-tag relative orientation
            yaw = math.atan2(R_cam_tag[0, 1], R_cam_tag[0, 0])
            
            # Calculate vehicle position in world coordinates
            # Assuming camera is at the center of the vehicle
            vehicle_x = tag_x - t_cam_tag[0]
            vehicle_y = tag_y - t_cam_tag[2]  # Z-axis points forward from tag
            
            return {
                'x': vehicle_x,
                'y': vehicle_y,
                'yaw': yaw,
                'confidence': 0.8,  # High confidence for successful detection
                'source_tag': detection.tag_id,
                'distance_to_tag': np.linalg.norm(t_cam_tag)
            }
            
        except Exception as e:
            print(f"[AprilTag] Position calculation error: {e}")
            return None
    
    def _fuse_position_estimates(self, positions: List[Dict]) -> Dict:
        """
        Fuse multiple position estimates from different tags.
        
        Args:
            positions: List of position estimates
            
        Returns:
            Fused position estimate
        """
        if len(positions) == 1:
            return positions[0]
        
        # Weight estimates by confidence and inverse distance
        total_weight = 0.0
        weighted_x = 0.0
        weighted_y = 0.0
        weighted_yaw_x = 0.0  # For circular mean of angles
        weighted_yaw_y = 0.0
        
        for pos in positions:
            # Weight by confidence and inverse distance to tag
            weight = pos['confidence'] / (1.0 + pos['distance_to_tag'])
            
            weighted_x += weight * pos['x']
            weighted_y += weight * pos['y']
            weighted_yaw_x += weight * math.cos(pos['yaw'])
            weighted_yaw_y += weight * math.sin(pos['yaw'])
            total_weight += weight
        
        if total_weight == 0:
            return positions[0]  # Fallback
        
        # Calculate weighted average
        fused_x = weighted_x / total_weight
        fused_y = weighted_y / total_weight
        fused_yaw = math.atan2(weighted_yaw_y / total_weight, weighted_yaw_x / total_weight)
        
        # Confidence based on number of detections and agreement
        confidence = min(0.9, 0.5 + 0.1 * len(positions))
        
        return {
            'x': fused_x,
            'y': fused_y,
            'yaw': fused_yaw,
            'confidence': confidence,
            'num_sources': len(positions)
        }
    
    def get_position(self) -> Dict:
        """Get current position estimate"""
        return self.current_position.copy()
    
    def set_tag_map(self, tag_map: Dict[int, Tuple[float, float, float]]):
        """Update the tag map"""
        self.tag_map = tag_map
        print(f"[AprilTag] Updated tag map with {len(tag_map)} tags")
    
    def calibrate_camera(self, calibration_data: Dict):
        """Update camera calibration parameters"""
        self.camera_params.update(calibration_data)
        print("[AprilTag] Camera calibration updated")
    
    def draw_detections(self, image: np.ndarray, detections_info: Dict) -> np.ndarray:
        """
        Draw AprilTag detections and position info on image.
        
        Args:
            image: Input image
            detections_info: Detection results from process_frame()
            
        Returns:
            Image with overlaid detection visualization
        """
        output = image.copy()
        
        # Draw tag detections
        for detection in detections_info['detections']:
            corners = np.array(detection['corners'], dtype=np.int32)
            
            # Draw tag outline
            cv2.polylines(output, [corners], True, (0, 255, 0), 2)
            
            # Draw tag ID
            center = tuple(map(int, detection['center']))
            cv2.putText(output, f"ID: {detection['tag_id']}", 
                       (center[0] - 20, center[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw position info
        pos = detections_info['position']
        info_text = [
            f"X: {pos['x']:.2f}m",
            f"Y: {pos['y']:.2f}m", 
            f"Yaw: {math.degrees(pos['yaw']):.1f}°",
            f"Conf: {pos['confidence']:.2f}",
            f"Tags: {detections_info['num_tags']}"
        ]
        
        for i, text in enumerate(info_text):
            cv2.putText(output, text, (10, 30 + i * 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return output

def test_apriltag_localizer():
    """Test function for AprilTag localizer"""
    # Create test localizer
    localizer = AprilTagLocalizer()
    
    # Create a test image (you would normally get this from camera)
    test_image = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Process frame
    result = localizer.process_frame(test_image)
    
    print("AprilTag Localizer Test:")
    print(f"Position: {result['position']}")
    print(f"Detections: {result['num_tags']}")
    
if __name__ == "__main__":
    test_apriltag_localizer()
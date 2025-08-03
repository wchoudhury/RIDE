"""
Map Visualization Subscriber for AprilTag Localization
This component subscribes to AprilTag position data and sends vehicle visualization
commands to the CPM Lab Control Center map display.
"""

import time
import threading
import math
from typing import Dict, Optional
import cpm

class MapVisualizationSubscriber:
    """Subscribes to AprilTag localization data and updates map visualization"""
    
    def __init__(self, vehicle_id: int):
        """
        Initialize map visualization subscriber.
        
        Args:
            vehicle_id: ID of the vehicle to visualize
        """
        self.vehicle_id = vehicle_id
        self.running = False
        
        # Initialize CPM communication
        try:
            cpm.init(f"map_viz_{vehicle_id}")
            self.logger = cpm.Logging.Instance()
            self.logger.set_id(f"map_viz_{vehicle_id}")
            self.logger.set_min_level(cpm.LogLevel.Info)
        except:
            self.logger = cpm.Logging.Instance()
            self.logger.set_id(f"map_viz_{vehicle_id}")
        
        # DDS subscribers and publishers
        self.vehicle_state_reader = None
        self.visualization_writer = None
        
        # Current vehicle state
        self.current_position = {'x': 0.0, 'y': 0.0, 'yaw': 0.0, 'confidence': 0.0}
        self.last_update_time = 0
        self.position_lock = threading.Lock()
        
        # Visualization parameters
        self.vehicle_color = (0, 150, 255)  # Blue
        self.path_color = (255, 100, 0)     # Orange
        self.low_confidence_color = (150, 150, 150)  # Gray
        self.vehicle_size = 0.25  # meters
        
        # Path history for trail visualization
        self.path_history = []
        self.max_path_points = 50
        
        # Rate limiting
        self.last_viz_update = 0
        self.viz_update_interval = 0.1  # 10 Hz max
        
        print(f"[MapViz] Initialized subscriber for vehicle {vehicle_id}")
    
    def start(self) -> bool:
        """Start the map visualization subscriber"""
        try:
            # Create DDS reader for vehicle state (AprilTag positions)
            # Use RIDE project topic naming convention
            vehicle_state_topic = f"vehicle_state_{self.vehicle_id}"
            self.vehicle_state_reader = cpm.AsyncReader(
                vehicle_state_topic, 
                self._on_vehicle_state_received
            )
            
            # Create DDS writer for visualization commands
            # Use RIDE project visualization topic
            self.visualization_writer = cpm.Writer("visualization_commands")
            
            self.running = True
            
            print(f"[MapViz] Started visualization subscriber for vehicle {self.vehicle_id}")
            print(f"[MapViz] Listening on topic: {vehicle_state_topic}")
            
            return True
            
        except Exception as e:
            print(f"[MapViz] Failed to start: {e}")
            return False
    
    def stop(self):
        """Stop the map visualization subscriber"""
        self.running = False
        
        # Clear visualizations
        self._clear_vehicle_visualization()
        
        print(f"[MapViz] Stopped visualization subscriber for vehicle {self.vehicle_id}")
    
    def _on_vehicle_state_received(self, vehicle_states):
        """
        Callback for receiving vehicle state messages from AprilTag localization.
        
        Args:
            vehicle_states: List of VehicleState DDS messages
        """
        if not self.running:
            return
            
        try:
            for state in vehicle_states:
                # Filter for our vehicle ID
                if hasattr(state, 'vehicle_id') and state.vehicle_id == self.vehicle_id:
                    self._process_vehicle_state(state)
                    
        except Exception as e:
            self.logger.write(cpm.LogLevel.Error, f"Error processing vehicle states: {e}")
    
    def _process_vehicle_state(self, state):
        """
        Process a single vehicle state message and update visualization.
        
        Args:
            state: VehicleState DDS message
        """
        try:
            # Extract position data
            if hasattr(state, 'pose'):
                x = state.pose.x
                y = state.pose.y
                yaw = state.pose.yaw
                
                # Calculate confidence based on IPS update age
                confidence = 1.0
                if hasattr(state, 'IPS_update_age_nanoseconds'):
                    age_seconds = state.IPS_update_age_nanoseconds / 1e9
                    # Confidence decays with age, 0 confidence after 2 seconds
                    confidence = max(0.0, 1.0 - (age_seconds / 2.0))
                
                # Update current position
                with self.position_lock:
                    self.current_position = {
                        'x': float(x),
                        'y': float(y), 
                        'yaw': float(yaw),
                        'confidence': confidence
                    }
                    self.last_update_time = time.time()
                
                # Update path history
                self._update_path_history(x, y)
                
                # Update map visualization
                self._update_map_visualization()
                
                # Log position updates (throttled)
                if confidence > 0.5:
                    current_time = time.time()
                    if current_time - self.last_viz_update > 1.0:  # Log every second
                        self.logger.write(
                            cpm.LogLevel.Info,
                            f"Vehicle {self.vehicle_id} position: x={x:.2f}m, y={y:.2f}m, "
                            f"yaw={math.degrees(yaw):.1f}°, conf={confidence:.2f}"
                        )
                        self.last_viz_update = current_time
                
        except Exception as e:
            self.logger.write(cpm.LogLevel.Error, f"Error processing vehicle state: {e}")
    
    def _update_path_history(self, x: float, y: float):
        """Update the vehicle's path history for trail visualization"""
        self.path_history.append((x, y))
        
        # Limit path history length
        if len(self.path_history) > self.max_path_points:
            self.path_history.pop(0)
    
    def _update_map_visualization(self):
        """Update the vehicle visualization on the map"""
        # Rate limit visualization updates
        current_time = time.time()
        if current_time - self.last_viz_update < self.viz_update_interval:
            return
        
        try:
            with self.position_lock:
                position = self.current_position.copy()
            
            # Choose colors based on confidence
            if position['confidence'] > 0.7:
                vehicle_color = self.vehicle_color
                path_color = self.path_color
            elif position['confidence'] > 0.3:
                vehicle_color = (200, 200, 0)  # Yellow for medium confidence
                path_color = (200, 150, 0)
            else:
                vehicle_color = self.low_confidence_color
                path_color = self.low_confidence_color
            
            # Draw vehicle path trail
            self._draw_vehicle_path(path_color)
            
            # Draw vehicle icon
            self._draw_vehicle_icon(
                position['x'], 
                position['y'], 
                position['yaw'],
                vehicle_color,
                position['confidence']
            )
            
            # Draw confidence indicator
            self._draw_confidence_indicator(
                position['x'],
                position['y'], 
                position['confidence']
            )
            
        except Exception as e:
            self.logger.write(cpm.LogLevel.Error, f"Error updating visualization: {e}")
    
    def _draw_vehicle_icon(self, x: float, y: float, yaw: float, color: tuple, confidence: float):
        """Draw the vehicle icon on the map"""
        try:
            # Create vehicle shape (rectangle with direction arrow)
            length = self.vehicle_size
            width = self.vehicle_size * 0.6
            
            # Calculate vehicle corners
            cos_yaw = math.cos(yaw)
            sin_yaw = math.sin(yaw)
            
            corners = [
                (x + length/2 * cos_yaw - width/2 * sin_yaw, 
                 y + length/2 * sin_yaw + width/2 * cos_yaw),
                (x + length/2 * cos_yaw + width/2 * sin_yaw, 
                 y + length/2 * sin_yaw - width/2 * cos_yaw),
                (x - length/2 * cos_yaw + width/2 * sin_yaw, 
                 y - length/2 * sin_yaw - width/2 * cos_yaw),
                (x - length/2 * cos_yaw - width/2 * sin_yaw, 
                 y - length/2 * sin_yaw + width/2 * cos_yaw)
            ]
            
            # Create visualization message for vehicle body
            vehicle_viz = cpm.Visualization()
            # Use hash of string for ID (CPM requires numeric ID)
            vehicle_viz.id = hash(f"apriltag_vehicle_{self.vehicle_id}") & 0xFFFFFFFFFFFFFFFF
            vehicle_viz.type = cpm.VisualizationType.Polygon
            vehicle_viz.time_to_live = int((time.time() + 1.0) * 1e9)  # 1 second TTL in nanoseconds
            
            # Add corner points using CPM Point2D structure
            for corner_x, corner_y in corners:
                point = cpm.Point2D()
                point.x = float(corner_x)
                point.y = float(corner_y)
                vehicle_viz.points.append(point)
            
            # Set color using CPM Color structure
            vehicle_viz.color.r = int(color[0])
            vehicle_viz.color.g = int(color[1]) 
            vehicle_viz.color.b = int(color[2])
            vehicle_viz.color.a = int(255 * confidence)  # Alpha based on confidence
            vehicle_viz.size = 2.0  # Line width in pixels
            
            # Send vehicle visualization
            self.visualization_writer.write(vehicle_viz)
            
            # Draw direction arrow
            arrow_length = length * 0.8
            arrow_tip_x = x + arrow_length * cos_yaw
            arrow_tip_y = y + arrow_length * sin_yaw
            
            arrow_viz = cpm.Visualization()
            arrow_viz.id = hash(f"apriltag_vehicle_arrow_{self.vehicle_id}") & 0xFFFFFFFFFFFFFFFF
            arrow_viz.type = cpm.VisualizationType.LineStrips
            arrow_viz.time_to_live = int((time.time() + 1.0) * 1e9)
            
            # Arrow line
            center_point = cpm.Point2D()
            center_point.x = x
            center_point.y = y
            arrow_viz.points.append(center_point)
            
            tip_point = cpm.Point2D()
            tip_point.x = arrow_tip_x
            tip_point.y = arrow_tip_y  
            arrow_viz.points.append(tip_point)
            
            # Arrow color (brighter)
            arrow_viz.color.r = min(255, color[0] + 50)
            arrow_viz.color.g = min(255, color[1] + 50)
            arrow_viz.color.b = min(255, color[2] + 50)
            arrow_viz.color.a = int(255 * confidence)
            arrow_viz.size = 3.0
            
            # Send arrow visualization
            self.visualization_writer.write(arrow_viz)
            
        except Exception as e:
            self.logger.write(cpm.LogLevel.Error, f"Error drawing vehicle icon: {e}")
    
    def _draw_vehicle_path(self, color: tuple):
        """Draw the vehicle's path trail"""
        if len(self.path_history) < 2:
            return
            
        try:
            path_viz = cpm.Visualization()
            path_viz.id = f"apriltag_vehicle_path_{self.vehicle_id}".encode()
            path_viz.type = cpm.VisualizationType.LineStrips
            path_viz.time_to_live = int((time.time() + 2.0) * 1e9)  # 2 second TTL
            
            # Add path points
            for x, y in self.path_history:
                point = cpm.Point2D()
                point.x = x
                point.y = y
                path_viz.points.append(point)
            
            # Set path style
            path_viz.color.r = color[0]
            path_viz.color.g = color[1]
            path_viz.color.b = color[2] 
            path_viz.color.a = 180  # Semi-transparent
            path_viz.size = 1.5
            
            # Send path visualization
            self.visualization_writer.write(path_viz)
            
        except Exception as e:
            self.logger.write(cpm.LogLevel.Error, f"Error drawing vehicle path: {e}")
    
    def _draw_confidence_indicator(self, x: float, y: float, confidence: float):
        """Draw confidence indicator around vehicle"""
        try:
            # Draw confidence circle around vehicle
            confidence_viz = cpm.Visualization()
            confidence_viz.id = f"apriltag_confidence_{self.vehicle_id}".encode()
            confidence_viz.type = cpm.VisualizationType.FilledCircle
            confidence_viz.time_to_live = int((time.time() + 1.0) * 1e9)
            
            # Circle center
            center_point = cpm.Point2D()
            center_point.x = x
            center_point.y = y
            confidence_viz.points.append(center_point)
            
            # Circle size based on confidence (smaller = more confident)
            confidence_viz.size = (1.0 - confidence) * 0.3 + 0.1
            
            # Color: Green for high confidence, Red for low confidence
            confidence_viz.color.r = int(255 * (1.0 - confidence))
            confidence_viz.color.g = int(255 * confidence)
            confidence_viz.color.b = 0
            confidence_viz.color.a = 100  # Semi-transparent
            
            # Send confidence visualization
            self.visualization_writer.write(confidence_viz)
            
        except Exception as e:
            self.logger.write(cpm.LogLevel.Error, f"Error drawing confidence indicator: {e}")
    
    def _clear_vehicle_visualization(self):
        """Clear all vehicle visualizations from the map"""
        try:
            # Send empty visualizations with zero TTL to clear them
            for viz_id in [f"apriltag_vehicle_{self.vehicle_id}", 
                          f"apriltag_vehicle_arrow_{self.vehicle_id}",
                          f"apriltag_vehicle_path_{self.vehicle_id}",
                          f"apriltag_confidence_{self.vehicle_id}"]:
                
                clear_viz = cpm.Visualization()
                clear_viz.id = viz_id.encode()
                clear_viz.type = cpm.VisualizationType.Polygon
                clear_viz.time_to_live = 0  # Immediate expiry
                
                self.visualization_writer.write(clear_viz)
                
        except Exception as e:
            self.logger.write(cpm.LogLevel.Error, f"Error clearing visualizations: {e}")
    
    def get_current_position(self) -> Dict:
        """Get current vehicle position"""
        with self.position_lock:
            return self.current_position.copy()
    
    def is_position_valid(self, max_age_seconds: float = 2.0) -> bool:
        """Check if current position is valid and recent"""
        current_time = time.time()
        age = current_time - self.last_update_time
        
        with self.position_lock:
            confidence = self.current_position['confidence']
        
        return age < max_age_seconds and confidence > 0.3


def create_map_subscriber(vehicle_id: int) -> MapVisualizationSubscriber:
    """
    Convenience function to create a map visualization subscriber.
    
    Args:
        vehicle_id: ID of vehicle to visualize
        
    Returns:
        Configured MapVisualizationSubscriber
    """
    return MapVisualizationSubscriber(vehicle_id)


def test_map_visualization():
    """Test function for map visualization subscriber"""
    print("Testing MapVisualizationSubscriber...")
    
    # Create subscriber for vehicle 1
    subscriber = MapVisualizationSubscriber(1)
    
    # Start subscriber
    if subscriber.start():
        print("Map visualization subscriber started successfully")
        print("Waiting for AprilTag position data...")
        
        try:
            # Keep running for test
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("Test interrupted by user")
        
        finally:
            subscriber.stop()
    else:
        print("Failed to start map visualization subscriber")


if __name__ == "__main__":
    test_map_visualization()
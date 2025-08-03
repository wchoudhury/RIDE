"""
Visualization module for Donkeycar integration with CPM Lab.
This module provides visualization capabilities for Donkeycar data in the CPM Lab Control Center.
"""

import os
import sys
import time
import threading
import numpy as np
import base64
import json
from io import BytesIO
from PIL import Image

# Import CPM Python bindings
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import cpm


class DonkeycarVisualizer:
    """Visualizer that sends Donkeycar data to the CPM Lab Control Center"""
    
    def __init__(self, vehicle_id):
        self.vehicle_id = vehicle_id
        
        # Initialize CPM components if not already initialized
        try:
            cpm.Logging.Instance().set_id("donkeycar_vis_" + str(vehicle_id))
            # Set logging level to reduce verbosity - only log warnings and errors
            cpm.Logging.Instance().set_min_level(cpm.LogLevel.Warn)
        except:
            cpm.init("donkeycar_vis_" + str(vehicle_id))
            cpm.Logging.Instance().set_id("donkeycar_vis_" + str(vehicle_id))
            cpm.Logging.Instance().set_min_level(cpm.LogLevel.Warn)
        
        # Create writers for visualization data
        self.visual_writer = cpm.Writer("visualization_commands")
        self.camera_writer = cpm.Writer("donkeycar_camera_" + str(vehicle_id))
        
        # For throttling visualization updates
        self.last_vis_update = 0
        self.vis_update_interval = 0.05  # 20 Hz max for visualization
        
        # For throttling camera updates
        self.last_camera_update = 0
        self.camera_update_interval = 0.1  # 10 Hz max for camera feed
        
        # Tracking to avoid duplicate log messages
        self.last_steering = None
        self.last_throttle = None
        
        cpm.Logging.Instance().write(cpm.LogLevel.Info, 
                                   f"Donkeycar visualizer initialized for vehicle {vehicle_id}")
    
    def visualize_path(self, x_points, y_points, color=(255, 0, 0), line_width=2, 
                      layer="donkeycar", duration=0.5, z_value=0.05):
        """Visualize a path in the Lab Control Center
        
        Args:
            x_points: List of x coordinates
            y_points: List of y coordinates
            color: RGB tuple for line color
            line_width: Width of the line in pixels
            layer: Layer name for the visualization
            duration: How long the path should be visible (seconds)
            z_value: Height of the visualization
        """
        # Rate limit visualization updates
        current_time = time.time()
        if current_time - self.last_vis_update < self.vis_update_interval:
            return
        self.last_vis_update = current_time
        
        try:
            # Create visualization command object
            vis_command = {
                "command": "draw_polyline",
                "layer": f"donkeycar_{self.vehicle_id}_{layer}",
                "object_id": f"donkeycar_{self.vehicle_id}_path",
                "points": [],
                "color": color,
                "line_width": line_width,
                "duration": duration,
                "z_value": z_value
            }
            
            # Add points to the path
            for x, y in zip(x_points, y_points):
                vis_command["points"].append({"x": float(x), "y": float(y), "z": float(z_value)})
            
            # Convert to JSON and send
            vis_json = json.dumps(vis_command)
            self.visual_writer.write(vis_json)
            
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error, 
                                      f"Error visualizing path: {str(e)}")
    
    def visualize_vehicle(self, x, y, heading, color=(0, 0, 255), 
                         layer="donkeycar", duration=0.5, z_value=0.1):
        """Visualize the vehicle position and heading in the Lab Control Center
        
        Args:
            x: X coordinate of the vehicle
            y: Y coordinate of the vehicle
            heading: Heading angle in radians
            color: RGB tuple for vehicle color
            layer: Layer name for the visualization
            duration: How long the vehicle should be visible (seconds)
            z_value: Height of the visualization
        """
        # Rate limit visualization updates
        current_time = time.time()
        if current_time - self.last_vis_update < self.vis_update_interval:
            return
        self.last_vis_update = current_time
        
        try:
            # Create vehicle visualization
            # We'll draw a simple car shape as a polygon
            length = 0.3  # Length of car in meters
            width = 0.15  # Width of car in meters
            
            # Calculate corners of the car rectangle
            cos_h = np.cos(heading)
            sin_h = np.sin(heading)
            
            # Front right, front left, rear left, rear right
            corners = [
                (x + length/2 * cos_h - width/2 * sin_h, y + length/2 * sin_h + width/2 * cos_h),
                (x + length/2 * cos_h + width/2 * sin_h, y + length/2 * sin_h - width/2 * cos_h),
                (x - length/2 * cos_h + width/2 * sin_h, y - length/2 * sin_h - width/2 * cos_h),
                (x - length/2 * cos_h - width/2 * sin_h, y - length/2 * sin_h + width/2 * cos_h)
            ]
            
            # Create polygon command
            vis_command = {
                "command": "draw_polygon",
                "layer": f"donkeycar_{self.vehicle_id}_{layer}",
                "object_id": f"donkeycar_{self.vehicle_id}_vehicle",
                "points": [],
                "color": color,
                "fill": True,
                "duration": duration,
                "z_value": z_value
            }
            
            # Add corners to the polygon
            for corner_x, corner_y in corners:
                vis_command["points"].append({"x": float(corner_x), "y": float(corner_y), "z": float(z_value)})
            
            # Add an arrow to show heading
            arrow_points = [
                (x + length/2 * cos_h, y + length/2 * sin_h),  # Front center
                (x + length * cos_h, y + length * sin_h)  # Arrow tip
            ]
            
            arrow_command = {
                "command": "draw_polyline",
                "layer": f"donkeycar_{self.vehicle_id}_{layer}",
                "object_id": f"donkeycar_{self.vehicle_id}_heading",
                "points": [],
                "color": (255, 255, 0),  # Yellow arrow
                "line_width": 2,
                "duration": duration,
                "z_value": z_value + 0.01  # Slightly above the vehicle
            }
            
            # Add points to the arrow
            for arrow_x, arrow_y in arrow_points:
                arrow_command["points"].append({"x": float(arrow_x), "y": float(arrow_y), "z": float(z_value + 0.01)})
            
            # Send both commands
            self.visual_writer.write(json.dumps(vis_command))
            self.visual_writer.write(json.dumps(arrow_command))
            
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error, 
                                      f"Error visualizing vehicle: {str(e)}")
    
    def visualize_camera_image(self, image_array):
        """Send camera image to Lab Control Center for visualization
        
        Args:
            image_array: NumPy array with image data (RGB format)
        """
        # Rate limit camera updates
        current_time = time.time()
        if current_time - self.last_camera_update < self.camera_update_interval:
            return
        self.last_camera_update = current_time
        
        try:
            # Check if image is valid
            if image_array is None or image_array.size == 0:
                return
                
            # Convert numpy array to PIL Image
            image = Image.fromarray(image_array)
            
            # Resize image if needed (to reduce bandwidth)
            max_dim = 320
            if image.width > max_dim or image.height > max_dim:
                if image.width > image.height:
                    new_width = max_dim
                    new_height = int(image.height * max_dim / image.width)
                else:
                    new_height = max_dim
                    new_width = int(image.width * max_dim / image.height)
                image = image.resize((new_width, new_height), Image.LANCZOS)
            
            # Convert to JPEG and encode as base64
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=80)
            img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Create camera data message
            camera_data = {
                "vehicle_id": self.vehicle_id,
                "timestamp": cpm.get_time_ns(),
                "image_data": img_str,
                "format": "jpeg",
                "width": image.width,
                "height": image.height
            }
            
            # Send camera data
            self.camera_writer.write(json.dumps(camera_data))
            
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error, 
                                      f"Error sending camera image: {str(e)}")
    
    def visualize_steering_throttle(self, steering, throttle, max_steering=0.5, max_throttle=1.0,
                                   color_steering=(0, 255, 0), color_throttle=(255, 128, 0),
                                   layer="donkeycar_controls", duration=0.5):
        """Visualize steering and throttle values as gauges
        
        Args:
            steering: Current steering value (-1 to 1)
            throttle: Current throttle value (-1 to 1)
            max_steering: Maximum steering value in radians
            max_throttle: Maximum throttle value in m/s
            color_steering: RGB color for steering gauge
            color_throttle: RGB color for throttle gauge
            layer: Layer name for visualization
            duration: How long the gauges should be visible
        """
        # Rate limit visualization updates
        current_time = time.time()
        if current_time - self.last_vis_update < self.vis_update_interval:
            return
        self.last_vis_update = current_time
        
        try:
            # Normalize steering and throttle to [-1, 1]
            norm_steering = max(-1.0, min(1.0, steering / max_steering if max_steering != 0 else 0))
            norm_throttle = max(-1.0, min(1.0, throttle / max_throttle if max_throttle != 0 else 0))
            
            # Create text commands for displaying values
            steering_text = {
                "command": "draw_text",
                "layer": f"donkeycar_{self.vehicle_id}_{layer}",
                "object_id": f"donkeycar_{self.vehicle_id}_steering_text",
                "text": f"Steering: {steering:.2f} rad",
                "position": {"x": 10, "y": 30},
                "color": color_steering,
                "font_size": 12,
                "duration": duration,
                "screen_coordinates": True
            }
            
            throttle_text = {
                "command": "draw_text",
                "layer": f"donkeycar_{self.vehicle_id}_{layer}",
                "object_id": f"donkeycar_{self.vehicle_id}_throttle_text",
                "text": f"Throttle: {throttle:.2f} m/s",
                "position": {"x": 10, "y": 50},
                "color": color_throttle,
                "font_size": 12,
                "duration": duration,
                "screen_coordinates": True
            }
            
            # Create gauge bars
            steering_gauge = {
                "command": "draw_rect",
                "layer": f"donkeycar_{self.vehicle_id}_{layer}",
                "object_id": f"donkeycar_{self.vehicle_id}_steering_gauge",
                "position": {"x": 150, "y": 30},
                "width": 100 * abs(norm_steering),
                "height": 10,
                "color": color_steering,
                "fill": True,
                "duration": duration,
                "screen_coordinates": True,
                "anchor": "left" if norm_steering >= 0 else "right"
            }
            
            throttle_gauge = {
                "command": "draw_rect",
                "layer": f"donkeycar_{self.vehicle_id}_{layer}",
                "object_id": f"donkeycar_{self.vehicle_id}_throttle_gauge",
                "position": {"x": 150, "y": 50},
                "width": 100 * abs(norm_throttle),
                "height": 10,
                "color": color_throttle,
                "fill": True,
                "duration": duration,
                "screen_coordinates": True,
                "anchor": "left" if norm_throttle >= 0 else "right"
            }
            
            # Send all visualization commands
            self.visual_writer.write(json.dumps(steering_text))
            self.visual_writer.write(json.dumps(throttle_text))
            self.visual_writer.write(json.dumps(steering_gauge))
            self.visual_writer.write(json.dumps(throttle_gauge))
            
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error, 
                                      f"Error visualizing controls: {str(e)}")
"""
Network Controller for Donkeycar integration with CPM Lab.
This module provides network communication capabilities to interact with physical donkeycar vehicles.
"""

import os
import sys
import time
import json
import threading
import requests
import logging
from urllib.parse import urljoin
import base64
import numpy as np
from PIL import Image
from io import BytesIO

# Optional MQTT support
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

# Import CPM Python bindings
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import cpm



class DonkeycarNetworkController:
    """Controller that communicates with physical Donkeycar vehicles over the network"""
    
    def __init__(self, vehicle_id, config=None):
        """Initialize the network controller
        
        Args:
            vehicle_id: The ID of the vehicle to control
            config: Configuration dictionary (if None, will load from parameters)
        """
        self.vehicle_id = vehicle_id
        self.connected = False
        self.car_name = f"car{vehicle_id}"
        self.session = requests.Session()
        
        # Initialize CPM components if not already initialized
        try:
            cpm.Logging.Instance().set_id("donkeycar_network_" + str(vehicle_id))
        except:
            cpm.init("donkeycar_network_" + str(vehicle_id))
            cpm.Logging.Instance().set_id("donkeycar_network_" + str(vehicle_id))
        
        # Initialize state variables
        self.current_steering = 0.0
        self.current_throttle = 0.0
        self.last_command_time = 0
        self.last_telemetry_time = 0
        
        # For storing received camera data
        self.latest_camera_frame = None
        self.latest_telemetry = None
        
        # Load configuration
        if config:
            self.config = config
        else:
            # Use parameter system to get configuration if available
            try:
                self.parameter_receiver = cpm.ParameterReceiver()
                self.config = self._load_config_from_parameters()
            except:
                self.config = self._load_default_config()
        
        # Set up connection to physical car based on protocol
        self.protocol = self.config.get('PROTOCOL', 'http').lower()
        
        if self.protocol == 'mqtt' and MQTT_AVAILABLE:
            self._setup_mqtt_connection()
        elif self.protocol == 'http':
            self._setup_http_connection()
        else:
            cpm.Logging.Instance().write(cpm.LogLevel.Warning,
                                      f"Unsupported protocol: {self.protocol}, defaulting to HTTP")
            self.protocol = 'http'
            self._setup_http_connection()
        
        # Set up telemetry listener thread
        self.telemetry_thread = None
        self.running = False
    
    def _load_config_from_parameters(self):
        """Load configuration from CPM parameter system"""
        config = {}
        
        # Network parameters
        config['PROTOCOL'] = self.parameter_receiver.get_parameter_string(
            "donkeycar/network/protocol")
        
        # Get physical car settings for this vehicle ID
        car_ip = self.parameter_receiver.get_parameter_string(
            f"donkeycar/network/{self.vehicle_id}/ip")
        car_port = self.parameter_receiver.get_parameter_int(
            f"donkeycar/network/{self.vehicle_id}/port")
        car_name = self.parameter_receiver.get_parameter_string(
            f"donkeycar/network/{self.vehicle_id}/name")
        
        if car_ip and car_port:
            config['CAR_IP'] = car_ip
            config['CAR_PORT'] = car_port
        
        if car_name:
            self.car_name = car_name
        
        # MQTT settings if applicable
        if config.get('PROTOCOL', '').lower() == 'mqtt':
            config['MQTT_BROKER'] = self.parameter_receiver.get_parameter_string(
                "donkeycar/network/mqtt_broker")
            config['MQTT_PORT'] = self.parameter_receiver.get_parameter_int(
                "donkeycar/network/mqtt_port")
            config['MQTT_TOPIC_PREFIX'] = self.parameter_receiver.get_parameter_string(
                "donkeycar/network/mqtt_topic_prefix")
        
        # Set default values if parameters not found
        if not config.get('PROTOCOL'):
            config['PROTOCOL'] = 'http'
        if not config.get('CAR_IP'):
            config['CAR_IP'] = 'localhost'
        if not config.get('CAR_PORT'):
            config['CAR_PORT'] = 8887
            
        return config
    
    def _load_default_config(self):
        """Load default configuration when parameter system is not available"""
        return {
            'PROTOCOL': 'http',
            'CAR_IP': 'localhost',
            'CAR_PORT': 8887,
            'MQTT_BROKER': 'localhost',
            'MQTT_PORT': 1883,
            'MQTT_TOPIC_PREFIX': 'donkeycar/'
        }
    
    def _setup_http_connection(self):
        """Set up HTTP connection to the physical car"""
        self.base_url = f"http://{self.config['CAR_IP']}:{self.config['CAR_PORT']}"
        
        try:
            # Test connection
            response = self.session.get(urljoin(self.base_url, '/api/health'), timeout=3)
            if response.status_code == 200:
                self.connected = True
                cpm.Logging.Instance().write(cpm.LogLevel.Info,
                                           f"Connected to physical car at {self.base_url}")
            else:
                cpm.Logging.Instance().write(cpm.LogLevel.Warning,
                                          f"Could not connect to physical car at {self.base_url}: {response.status_code}")
        except requests.exceptions.RequestException as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Warning,
                                      f"Could not connect to physical car at {self.base_url}: {str(e)}")
    
    def _setup_mqtt_connection(self):
        """Set up MQTT connection to the physical car"""
        if not MQTT_AVAILABLE:
            cpm.Logging.Instance().write(cpm.LogLevel.Error,
                                       "MQTT not available. Install paho-mqtt package.")
            return
        
        self.mqtt_client = mqtt.Client(f"donkeycar_bridge_{self.vehicle_id}")
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
        
        try:
            self.mqtt_client.connect(
                self.config.get('MQTT_BROKER', 'localhost'),
                self.config.get('MQTT_PORT', 1883),
                keepalive=60
            )
            self.mqtt_client.loop_start()
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error,
                                       f"Could not connect to MQTT broker: {str(e)}")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback for when MQTT connection is established"""
        if rc == 0:
            self.connected = True
            cpm.Logging.Instance().write(cpm.LogLevel.Info,
                                       f"Connected to MQTT broker")
            
            # Subscribe to telemetry topic
            topic_prefix = self.config.get('MQTT_TOPIC_PREFIX', 'donkeycar/')
            telemetry_topic = f"{topic_prefix}{self.car_name}/telemetry"
            camera_topic = f"{topic_prefix}{self.car_name}/camera"
            
            self.mqtt_client.subscribe(telemetry_topic)
            self.mqtt_client.subscribe(camera_topic)
        else:
            cpm.Logging.Instance().write(cpm.LogLevel.Warning,
                                      f"Failed to connect to MQTT broker, return code: {rc}")
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Callback for when MQTT connection is lost"""
        self.connected = False
        cpm.Logging.Instance().write(cpm.LogLevel.Warning,
                                   f"Disconnected from MQTT broker with code: {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Callback for when an MQTT message is received"""
        try:
            topic = msg.topic
            topic_prefix = self.config.get('MQTT_TOPIC_PREFIX', 'donkeycar/')
            
            # Handle telemetry data
            if topic.endswith('/telemetry'):
                telemetry_data = json.loads(msg.payload.decode('utf-8'))
                self._process_telemetry(telemetry_data)
            
            # Handle camera data
            elif topic.endswith('/camera'):
                camera_data = json.loads(msg.payload.decode('utf-8'))
                self._process_camera_data(camera_data)
                
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error,
                                      f"Error processing MQTT message: {str(e)}")
    
    def send_command(self, steering, throttle):
        """Send control commands to the physical car
        
        Args:
            steering: Steering value (-1.0 to 1.0)
            throttle: Throttle value (-1.0 to 1.0)
            
        Returns:
            bool: True if command was sent successfully
        """
        # Rate limit commands to avoid flooding the network
        current_time = time.time()
        if current_time - self.last_command_time < 0.05:  # 20Hz max
            return True
        
        self.last_command_time = current_time
        self.current_steering = steering
        self.current_throttle = throttle
        
        # Clamp values to valid range
        steering = max(-1.0, min(1.0, steering))
        throttle = max(-1.0, min(1.0, throttle))
        
        if self.protocol == 'mqtt' and MQTT_AVAILABLE:
            return self._send_mqtt_command(steering, throttle)
        else:
            return self._send_http_command(steering, throttle)
    
    def _send_http_command(self, steering, throttle):
        """Send command using HTTP protocol"""
        if not self.connected:
            self._setup_http_connection()
            if not self.connected:
                return False
        
        try:
            command_url = urljoin(self.base_url, '/api/drive')
            data = {
                'steering': float(steering),
                'throttle': float(throttle),
                'drive_mode': 'user',
                'recording': False
            }
            
            response = self.session.post(command_url, json=data, timeout=1)
            if response.status_code == 200:
                return True
            else:
                cpm.Logging.Instance().write(cpm.LogLevel.Warning,
                                         f"HTTP command failed with status {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.connected = False
            cpm.Logging.Instance().write(cpm.LogLevel.Error,
                                      f"Error sending HTTP command: {str(e)}")
            return False
    
    def _send_mqtt_command(self, steering, throttle):
        """Send command using MQTT protocol"""
        if not self.connected or not MQTT_AVAILABLE:
            return False
        
        try:
            topic_prefix = self.config.get('MQTT_TOPIC_PREFIX', 'donkeycar/')
            command_topic = f"{topic_prefix}{self.car_name}/drive"
            
            data = {
                'steering': float(steering),
                'throttle': float(throttle),
                'drive_mode': 'user',
                'recording': False
            }
            
            message = json.dumps(data)
            self.mqtt_client.publish(command_topic, message)
            return True
            
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error,
                                      f"Error sending MQTT command: {str(e)}")
            return False
    
    def start_telemetry_collection(self):
        """Start a background thread to collect telemetry from the car"""
        if self.telemetry_thread and self.telemetry_thread.is_alive():
            return True
            
        self.running = True
        
        if self.protocol == 'mqtt':
            # MQTT already has asynchronous data collection
            return True
        
        # For HTTP, we need a polling thread
        self.telemetry_thread = threading.Thread(
            target=self._telemetry_collection_loop,
            daemon=True
        )
        self.telemetry_thread.start()
        return True
    
    def stop_telemetry_collection(self):
        """Stop the telemetry collection thread"""
        self.running = False
        
        if self.protocol == 'mqtt' and self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
    
    def _telemetry_collection_loop(self):
        """Loop that polls for telemetry data from the car via HTTP"""
        while self.running:
            try:
                # Get telemetry data
                telemetry_url = urljoin(self.base_url, '/api/telemetry')
                response = self.session.get(telemetry_url, timeout=1)
                
                if response.status_code == 200:
                    telemetry_data = response.json()
                    self._process_telemetry(telemetry_data)
                
                # Get camera image
                camera_url = urljoin(self.base_url, '/api/camera')
                response = self.session.get(camera_url, timeout=1)
                
                if response.status_code == 200:
                    camera_data = response.json()
                    self._process_camera_data(camera_data)
                    
            except requests.exceptions.RequestException as e:
                cpm.Logging.Instance().write(cpm.LogLevel.Warning,
                                          f"Error fetching data from car: {str(e)}")
                self.connected = False
                time.sleep(5)  # Wait before attempting to reconnect
                self._setup_http_connection()
            
            # Sleep to maintain appropriate polling rate
            time.sleep(0.1)  # 10Hz polling rate
    
    def _process_telemetry(self, telemetry_data):
        """Process telemetry data received from the car"""
        self.latest_telemetry = telemetry_data
        self.last_telemetry_time = time.time()
        
        # Example of extracting data (depends on the car's telemetry format)
        # You may need to adjust this based on the actual donkeycar telemetry format
        try:
            if 'steering' in telemetry_data:
                self.current_steering = telemetry_data.get('steering', 0.0)
            
            if 'throttle' in telemetry_data:
                self.current_throttle = telemetry_data.get('throttle', 0.0)
            
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error,
                                      f"Error processing telemetry: {str(e)}")
    
    def _process_camera_data(self, camera_data):
        """Process camera data received from the car"""
        try:
            if 'image' in camera_data and camera_data['image']:
                # Decode base64 image
                image_bytes = base64.b64decode(camera_data['image'])
                image = Image.open(BytesIO(image_bytes))
                
                # Convert to numpy array for processing
                self.latest_camera_frame = np.array(image)
                
        except Exception as e:
            cpm.Logging.Instance().write(cpm.LogLevel.Error,
                                      f"Error processing camera data: {str(e)}")
    
    def get_latest_camera_frame(self):
        """Get the latest camera frame from the car
        
        Returns:
            numpy.ndarray: Image data as numpy array or None if not available
        """
        return self.latest_camera_frame
    
    def get_latest_steering_throttle(self):
        """Get the latest steering and throttle values
        
        Returns:
            tuple: (steering, throttle) values
        """
        return (self.current_steering, self.current_throttle)
    
    def is_connected(self):
        """Check if connection to the car is active
        
        Returns:
            bool: True if connected
        """
        return self.connected
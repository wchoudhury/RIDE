# Basler Camera Setup Instructions for RIDE Project

## Hardware Overview
- **Camera**: Basler Ace Classic acA2040-90uc
- **Resolution**: 2048 x 2048 pixels
- **Frame Rate**: 90 fps maximum
- **Connection**: USB 3.0 (5 Gbit/s bandwidth)
- **Lens**: Basler C11-0824-12M f8.5mm

## Software Requirements

### 1. Install Basler Pylon SDK

#### **On Linux/macOS:**
```bash
# Download Pylon SDK from Basler website
# https://www.baslerweb.com/en/downloads/software-downloads/

# For Ubuntu/Debian:
wget https://www.baslerweb.com/fp-1615275559/media/downloads/software/pylon_software/pylon_7.X.X_linux_x86_64_setup.tar.gz

# Extract and install
tar -xzf pylon_7.X.X_linux_x86_64_setup.tar.gz
cd pylon_7.X.X_linux_x86_64
sudo ./setup-usb.sh  # Setup USB permissions
sudo ./install.sh   # Install Pylon SDK
```

#### **Environment Setup:**
```bash
# Add Pylon to PATH (add to ~/.bashrc)
export PYLON_ROOT=/opt/pylon
export PATH=$PATH:$PYLON_ROOT/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$PYLON_ROOT/lib64

# Reload environment
source ~/.bashrc
```

### 2. Install Python Bindings

```bash
# Install pypylon (Pylon Python bindings)
pip install pypylon

# Verify installation
python3 -c "from pypylon import pylon; print('Pylon SDK installed successfully')"
```

### 3. USB Permissions Setup

```bash
# Add user to dialout group for USB camera access
sudo usermod -a -G dialout $USER

# Create udev rule for Basler cameras (if not done by installer)
sudo nano /etc/udev/rules.d/69-basler-cameras.rules

# Add this content:
SUBSYSTEM=="usb", ATTRS{idVendor}=="2676", MODE="0664", GROUP="dialout"

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Logout and login for group changes to take effect
```

## Testing Camera Connection

### 1. Test with Pylon Viewer
```bash
# Launch Pylon Viewer GUI
pylonviewer

# Should detect your acA2040-90uc camera
# Verify 2048x2048 resolution and 90fps capability
```

### 2. Test with Python
```bash
cd /Users/wchoudhury/Desktop/RIDE-project/donkeycar_bridge

# Test Basler camera interface
python3 src/basler_camera_interface.py

# Expected output:
# [BaslerCamera] Connecting to: acA2040-90uc (Serial: XXXXXXXX)
# [BaslerCamera] Configuration verified: 2048x2048 @ 90fps, RGB8
# Frame 1: (2048, 2048, 3), dtype=uint8
```

## Camera Configuration for AprilTag Detection

### Optimal Settings in Code:
- **Resolution**: 2048 x 2048 (full sensor)
- **Frame Rate**: 90 fps
- **Pixel Format**: RGB8 (color)
- **Exposure**: 5ms (fixed, not auto)
- **Gain**: 0 (minimum for low noise)
- **Light Source**: Daylight 5000K

### Physical Setup:
- **Mounting Height**: ~2 meters above AprilTags
- **Lighting**: Even, diffused lighting to avoid shadows
- **Tag Size**: 10cm (0.1m) recommended for 2m height
- **Field of View**: With f8.5mm lens at 2m height ≈ 2.4m x 2.4m coverage

## Troubleshooting

### Camera Not Detected
```bash
# Check USB 3.0 connection
lsusb | grep -i basler

# Should show: Bus XXX Device XXX: ID 2676:XXXX Basler AG

# Check Pylon installation
pylon-config --version

# Test camera enumeration
python3 -c "
from pypylon import pylon
devices = pylon.TlFactory.GetInstance().EnumerateDevices()
print(f'Found {len(devices)} cameras')
for i, dev in enumerate(devices):
    print(f'Camera {i}: {dev.GetModelName()} - {dev.GetSerialNumber()}')
"
```

### Permission Issues
```bash
# Check current user groups
groups $USER

# Should include 'dialout'

# If not, add user and reboot
sudo usermod -a -G dialout $USER
sudo reboot
```

### USB Bandwidth Issues
```bash
# Check USB 3.0 connection speed
dmesg | grep -i usb | tail -10

# Should show "SuperSpeed USB device" for USB 3.0

# If using USB hub, connect camera directly to computer
# High resolution at 90fps requires full USB 3.0 bandwidth
```

### Frame Rate Too Low
- Ensure USB 3.0 connection (not USB 2.0)
- Check USB cable quality (should be USB 3.0 certified)
- Verify no other high-bandwidth USB devices on same controller
- Reduce exposure time if possible

### Image Quality Issues
- **Too Dark**: Increase exposure time (but not above 11ms for 90fps)
- **Too Bright**: Decrease exposure time or add neutral density filter
- **Blurry**: Ensure proper focus and stable mounting
- **Noisy**: Keep gain at minimum (0), improve lighting instead

## AprilTag Detection Optimization

### Camera Settings:
- **High Contrast**: Important for sharp tag edges
- **Sharp Focus**: Critical for tag corner detection
- **Stable Exposure**: Avoid auto-exposure for consistent detection

### Physical Setup:
- **Perpendicular Mounting**: Camera should be directly overhead
- **Even Lighting**: Avoid directional shadows on tags
- **Stable Platform**: Minimize vibration/movement

## Integration with RIDE System

Once camera is working:

1. **Update Configuration**:
   ```bash
   nano config/apriltag_config.yaml
   # Update camera calibration parameters after calibration
   ```

2. **Run Calibration**:
   ```bash
   # Camera calibration script (to be created)
   python3 calibrate_basler_camera.py --camera-id 0
   ```

3. **Test Full Integration**:
   ```bash
   ./launch_apriltag_localization.sh --vehicle-id 1 --camera-id 0 --debug
   ```

## Expected Performance

With proper setup:
- **Frame Rate**: 90 fps sustained
- **AprilTag Detection**: <10ms per frame
- **Position Accuracy**: <2cm with proper calibration
- **Detection Range**: 10cm tags detectable up to 3m distance
- **Multiple Tags**: Can detect 4-6 tags simultaneously in field of view

## Hardware Verification Checklist

- [ ] Camera detected by `lsusb` with ID 2676:XXXX
- [ ] Pylon Viewer can connect and stream video
- [ ] Python test shows 2048x2048 @ 90fps capability
- [ ] USB 3.0 connection confirmed (SuperSpeed)
- [ ] User has dialout group permissions
- [ ] Stable mounting with clear view of AprilTag area
- [ ] Even lighting without shadows or glare
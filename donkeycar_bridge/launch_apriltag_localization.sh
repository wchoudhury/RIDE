#!/bin/bash

# Launch AprilTag Localization System for RIDE Project
# This script starts the complete AprilTag → Map visualization pipeline

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default configuration
VEHICLE_ID=1
CAMERA_ID=0
CAMERA_IP=""
SHOW_DEBUG=false
CONFIG_FILE="config/apriltag_config.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
Launch AprilTag Localization System

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -v, --vehicle-id ID     CPM Lab vehicle ID (default: 1)
    -c, --camera-id ID      Local camera ID (e.g., 0 for /dev/video0)
    -i, --camera-ip IP      Network camera IP address
    -d, --debug             Show debug visualization window
    -f, --config FILE       Configuration file (default: config/apriltag_config.yaml)
    -h, --help              Show this help message

EXAMPLES:
    # Use local camera 0 for vehicle 1
    $0 --vehicle-id 1 --camera-id 0

    # Use network camera for vehicle 2 with debug window
    $0 --vehicle-id 2 --camera-ip 192.168.1.100 --debug

    # Use custom configuration file
    $0 --vehicle-id 1 --camera-id 0 --config my_config.yaml

REQUIREMENTS:
    - CPM Lab system running
    - Lab Control Center started
    - Camera connected and accessible
    - AprilTags positioned in camera view
    - Proper camera calibration in config file

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--vehicle-id)
            VEHICLE_ID="$2"
            shift 2
            ;;
        -c|--camera-id)
            CAMERA_ID="$2"
            shift 2
            ;;
        -i|--camera-ip)
            CAMERA_IP="$2"
            shift 2
            ;;
        -d|--debug)
            SHOW_DEBUG=true
            shift
            ;;
        -f|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Print startup banner
echo "================================================="
echo "  RIDE Project - AprilTag Localization System"
echo "================================================="
echo ""

# Validate inputs
if [[ -z "$CAMERA_ID" && -z "$CAMERA_IP" ]]; then
    print_error "Must specify either --camera-id or --camera-ip"
    show_help
    exit 1
fi

if [[ -n "$CAMERA_ID" && -n "$CAMERA_IP" ]]; then
    print_error "Cannot specify both --camera-id and --camera-ip"
    show_help
    exit 1
fi

# Check if configuration file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    print_error "Configuration file not found: $CONFIG_FILE"
    exit 1
fi

print_info "Configuration:"
print_info "  Vehicle ID: $VEHICLE_ID"
if [[ -n "$CAMERA_ID" ]]; then
    print_info "  Camera ID: $CAMERA_ID"
else
    print_info "  Camera IP: $CAMERA_IP"
fi
print_info "  Debug mode: $SHOW_DEBUG"
print_info "  Config file: $CONFIG_FILE"
echo ""

# Check dependencies
print_info "Checking dependencies..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    print_error "python3 is not installed or not in PATH"
    exit 1
fi

# Check required Python modules
print_info "Checking Python dependencies..."
REQUIRED_MODULES=("cv2:opencv-python" "numpy:numpy" "apriltag:apriltag" "yaml:pyyaml" "pypylon:pypylon")
MISSING_MODULES=()

for module_info in "${REQUIRED_MODULES[@]}"; do
    module_name="${module_info%%:*}"
    pip_name="${module_info##*:}"
    
    if ! python3 -c "import $module_name" &> /dev/null; then
        MISSING_MODULES+=("$pip_name")
        print_error "Required Python module not found: $module_name"
    fi
done

if [ ${#MISSING_MODULES[@]} -gt 0 ]; then
    print_error "Missing Python modules. Install with:"
    print_info "pip install ${MISSING_MODULES[*]}"
    
    # Also check for CPM Lab Python bindings
    if ! python3 -c "import cpm" &> /dev/null; then
        print_error "CPM Lab Python bindings not found"
        print_warning "Make sure CPM Lab is built and PYTHONPATH includes CPM Python bindings"
    fi
    
    exit 1
fi

# Check if camera is accessible (for local cameras)
if [[ -n "$CAMERA_ID" ]]; then
    if [[ ! -e "/dev/video$CAMERA_ID" ]]; then
        print_warning "Camera device /dev/video$CAMERA_ID not found"
        print_warning "Make sure camera is connected and not used by another application"
    fi
fi

print_success "Dependencies check passed"
echo ""

# Check CPM Lab system
print_info "Checking CPM Lab system..."

# This is a placeholder - you would check if CPM Lab processes are running
# For now, we'll just warn the user
print_warning "Make sure CPM Lab system is running:"
print_warning "  1. Start CPM Lab middleware"
print_warning "  2. Start Lab Control Center GUI"
print_warning "  3. Ensure DDS communication is working"
echo ""

# Setup environment
print_info "Setting up environment..."

# Set Python path to include src directory
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"

# Create necessary directories
mkdir -p debug_images
mkdir -p logs

print_success "Environment setup complete"
echo ""

# Build command line arguments
PYTHON_ARGS="--vehicle-id $VEHICLE_ID"

if [[ -n "$CAMERA_ID" ]]; then
    PYTHON_ARGS="$PYTHON_ARGS --camera-id $CAMERA_ID"
else
    PYTHON_ARGS="$PYTHON_ARGS --camera-ip $CAMERA_IP"
fi

if [[ "$SHOW_DEBUG" == "true" ]]; then
    PYTHON_ARGS="$PYTHON_ARGS --show-debug"
fi

# Start the integration
print_info "Starting AprilTag localization system..."
print_info "Command: python3 apriltag_to_map_integration.py $PYTHON_ARGS"
print_info "Press Ctrl+C to stop"
echo ""

# Trap signals for clean shutdown
trap 'print_info "Shutting down..."; exit 0' SIGINT SIGTERM

# Start the Python script
python3 apriltag_to_map_integration.py $PYTHON_ARGS

print_success "AprilTag localization system stopped"
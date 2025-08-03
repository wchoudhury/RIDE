#!/bin/bash

# Simplified launch script for Donkeycar simulator with bridge
# This script skips the Lab Control Center requirement

# Check arguments
if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <vehicle_id> [car_path] [--figure-eight]"
    echo "  vehicle_id: The ID of the vehicle to use"
    echo "  car_path: Path to a Donkeycar directory (optional, uses default config if not provided)"
    echo "  --figure-eight: Use figure-eight controller instead of circle controller"
    exit 1
fi

VEHICLE_ID=$1
CONTROLLER="circle"
CAR_PATH=""

# Parse additional arguments
shift
while [ "$#" -gt 0 ]; do
    case "$1" in
        --figure-eight)
            CONTROLLER="figure-eight"
            ;;
        *)
            # Assume it's a car path if it's not a recognized flag
            if [ -d "$1" ]; then
                CAR_PATH="$1"
            else
                echo "Warning: Unrecognized argument or directory does not exist: $1"
            fi
            ;;
    esac
    shift
done

# Path to the RIDE project
PROJECT_DIR="/Users/wchoudhury/Desktop/RIDE-project"
BRIDGE_DIR="${PROJECT_DIR}/donkeycar_bridge"
LOGS_DIR="${BRIDGE_DIR}/logs"

# Create logs directory if it doesn't exist
mkdir -p "${LOGS_DIR}"

echo "Skipping Lab Control Center requirement for simulation..."

# Set up Donkeycar parameters
echo "Setting up Donkeycar parameters for vehicle ${VEHICLE_ID}..."
if [ -n "$CAR_PATH" ]; then
    python "${BRIDGE_DIR}/src/parameter_config.py" ${VEHICLE_ID} --car-path "${CAR_PATH}"
else
    python "${BRIDGE_DIR}/src/parameter_config.py" ${VEHICLE_ID}
fi

# Start the Donkeycar Bridge with logging to file
echo "Starting Donkeycar Bridge for vehicle ${VEHICLE_ID}..."
python "${BRIDGE_DIR}/src/dds_bridge.py" ${VEHICLE_ID} > "${LOGS_DIR}/bridge_${VEHICLE_ID}.log" 2>&1 &
BRIDGE_PID=$!

# Give the bridge time to initialize
sleep 2

# Start the appropriate controller with logging to file
if [ "$CONTROLLER" = "figure-eight" ]; then
    echo "Starting Figure-Eight Controller for vehicle ${VEHICLE_ID}..."
    python "${BRIDGE_DIR}/examples/figure_eight_controller.py" ${VEHICLE_ID} > "${LOGS_DIR}/controller_${VEHICLE_ID}.log" 2>&1 &
else
    echo "Starting Circle Controller for vehicle ${VEHICLE_ID}..."
    python "${BRIDGE_DIR}/examples/circle_controller.py" ${VEHICLE_ID} > "${LOGS_DIR}/controller_${VEHICLE_ID}.log" 2>&1 &
fi
CONTROLLER_PID=$!

# Set up trap to kill processes on exit
cleanup() {
    echo "Stopping processes..."
    kill $BRIDGE_PID $CONTROLLER_PID 2>/dev/null
    wait $BRIDGE_PID $CONTROLLER_PID 2>/dev/null
    echo "All processes stopped."
}

trap cleanup INT TERM

# Wait for the controller to finish
echo "Donkeycar is now running with bridge. Press Ctrl+C to stop."
wait $CONTROLLER_PID
cleanup
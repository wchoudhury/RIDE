import time
import argparse

import sys
sys.path.append('src')
import cpm
from dds_bridge import DonkeycarDDSBridge

class DonkeyCPMWrapper:
    def __init__(self, vehicle_id):
        self.vehicle_id = vehicle_id
        self.cpm_receiver = cpm.ParameterReceiver(vehicle_id)
        self.car_interface = DonkeycarDDSBridge(vehicle_id)
        self.car_interface.start()

    def step(self):
        control_cmd = self.cpm_receiver.get_latest_command()
        self.car_interface._on_vehicle_command(control_cmd)
        self.cpm_receiver.send_state(self.car_interface._publish_vehicle_state())

    def run(self):
        print(f"🚗 Starting wrapper for vehicle {self.vehicle_id}")
        try:
            while True:
                self.step()
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("🛑 Stopping simulation.")
            self.car_interface.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vehicle-id", type=int, required=True)
    args = parser.parse_args()

    wrapper = DonkeyCPMWrapper(vehicle_id=args.vehicle_id)
    wrapper.run()

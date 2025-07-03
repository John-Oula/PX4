import os
import json
import time
from pymavlink import mavutil


class DroneMissionManager:
    def __init__(self, connection_string):
        self.connection = mavutil.mavlink_connection(connection_string)
        self.connection.wait_heartbeat()
        print("Connected to the drone. Heartbeat received.")

        self.target_system = self.connection.target_system
        self.target_component = self.connection.target_component
        print(f"Target system: {self.target_system}, Target component: {self.target_component}")

    def wait_for_home_position(self):
        print("Waiting for PX4 to set home position...")
        while True:
            msg = self.connection.recv_match(type='HOME_POSITION', blocking=True, timeout=1)
            if msg:
                lat = msg.latitude * 1e-7
                lon = msg.longitude * 1e-7
                alt = msg.altitude * 1e-3
                print(f"PX4 set home position: Lat {lat}, Lon {lon}, Alt {alt}")
                break
            else:
                time.sleep(0.5)

    def upload_mission(self, mission_file_path):
        if not os.path.exists(mission_file_path):
            raise FileNotFoundError(f"Mission file not found: {mission_file_path}")

        print(f"Uploading mission from {mission_file_path}...")
        with open(mission_file_path, 'r') as mission_file:
            mission_data = json.load(mission_file)

        mission_items = mission_data.get("mission", {}).get("items", [])
        if not mission_items:
            raise ValueError("No mission items found in the .plan file.")

        mavlink_mission = []
        for i, item in enumerate(mission_items):
            params = item.get("params", [0] * 7)
            mavlink_item = {
                "param1": float(params[0] or 0),
                "param2": float(params[1] or 0),
                "param3": float(params[2] or 0),
                "param4": float(params[3] or 0),
                "x": float(params[4] or 0),
                "y": float(params[5] or 0),
                "z": float(params[6] or 0),
                "frame": int(item.get("frame", 3)),
                "command": int(item.get("command", 16)),
                "current": 1 if i == 0 else 0,
                "autocontinue": 1,
                "seq": i
            }
            mavlink_mission.append(mavlink_item)

        print(f"Prepared {len(mavlink_mission)} mission items")

        self.connection.mav.mission_clear_all_send(self.target_system, self.target_component)
        ack = self.connection.recv_match(type='MISSION_ACK', blocking=True, timeout=5)

        self.connection.mav.mission_count_send(
            self.target_system, self.target_component, len(mavlink_mission), 0)

        for i in range(len(mavlink_mission)):
            msg = self.connection.recv_match(type=['MISSION_REQUEST', 'MISSION_REQUEST_INT'], blocking=True, timeout=10)
            if not msg:
                print(f"Error: No mission request received for item {i}.")
                return False

            item = mavlink_mission[msg.seq]
            self.connection.mav.mission_item_send(
                self.target_system,
                self.target_component,
                msg.seq,
                item["frame"],
                item["command"],
                item["current"],
                item["autocontinue"],
                item["param1"],
                item["param2"],
                item["param3"],
                item["param4"],
                item["x"],
                item["y"],
                item["z"]
            )

        ack = self.connection.recv_match(type='MISSION_ACK', blocking=True, timeout=10)
        if not ack or ack.type != mavutil.mavlink.MAV_MISSION_ACCEPTED:
            print("Error: Mission not accepted")
            return False

        return True

    def start_mission(self):
        print("Starting mission...")

        self.connection.mav.command_long_send(
            self.target_system,
            self.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0, 1, 0, 0, 0, 0, 0, 0)
        self.connection.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)

        self.connection.mav.command_long_send(
            self.target_system,
            self.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0, 1, 4, 0, 0, 0, 0, 0)
        self.connection.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)

        self.connection.mav.command_long_send(
            self.target_system,
            self.target_component,
            mavutil.mavlink.MAV_CMD_MISSION_START,
            0, 0, 0, 0, 0, 0, 0, 0)

        ack = self.connection.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)
        if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            print("Mission started successfully!")
            return True
        else:
            print("Error: Mission start failed")
            return False


if __name__ == "__main__":
    connection_string = 'udp:127.0.0.1:14550'
    mission_file = 'test.plan'

    drone_manager = DroneMissionManager(connection_string)
    drone_manager.wait_for_home_position()

    if drone_manager.upload_mission(mission_file):
        drone_manager.start_mission()
    else:
        print("Mission upload failed")

import json
import time
import os
from threading import Thread
from pymavlink import mavutil
from collections import defaultdict


class MultiUAVScheduler:
    def __init__(self, distribution_path, mission_dir, px4_port_map):
        with open(distribution_path) as f:
            self.distribution = json.load(f)
        self.mission_dir = mission_dir
        self.px4_port_map = px4_port_map
        self.start_reference = time.monotonic()
        self.mission_results = {}

    def connect_to_drone(self, vehicle_id):
        udp_port = self.px4_port_map[vehicle_id]
        conn_str = f"udp:127.0.0.1:{udp_port}"
        connection = mavutil.mavlink_connection(conn_str)
        try:
            connection.wait_heartbeat(timeout=10)
            print(f"[{vehicle_id}] ✅ Heartbeat received on port {udp_port}")
        except Exception as e:
            print(f"[{vehicle_id}] ❌ Failed to receive heartbeat on port {udp_port}: {e}")
            return None

        print(f"[{vehicle_id}] Waiting for home position...")
        # while True:
        #     msg = connection.recv_match(type='HOME_POSITION', blocking=True, timeout=1)
        #     if msg:
        #         lat = msg.latitude * 1e-7
        #         lon = msg.longitude * 1e-7
        #         alt = msg.altitude * 1e-3
        #         print(f"[{vehicle_id}] Home position set: Lat {lat}, Lon {lon}, Alt {alt}")
        #         break
        #     else:
        #         time.sleep(0.5)
        return connection

    def start_mission(self, connection, vehicle_id):
        print(f"[{vehicle_id}] Arming and starting mission...")
        connection.mav.command_long_send(
            connection.target_system,
            connection.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0, 1, 0, 0, 0, 0, 0, 0)
        connection.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)

        connection.mav.command_long_send(
            connection.target_system,
            connection.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0, 1, 4, 0, 0, 0, 0, 0)
        connection.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)

        connection.mav.command_long_send(
            connection.target_system,
            connection.target_component,
            mavutil.mavlink.MAV_CMD_MISSION_START,
            0, 0, 0, 0, 0, 0, 0, 0)

        ack = connection.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)
        if ack:
            print(f"[{vehicle_id}] Mission start ACK result: {ack.result}")
            if ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                print(f"[{vehicle_id}] Mission started successfully!")
                return True
            else:
                print(f"[{vehicle_id}] Mission start denied. Drone might be disarmed or have no mission.")
        else:
            print(f"[{vehicle_id}] No ACK received for mission start.")
        return False

    def launch_vehicle_missions(self, vehicle_id, missions):
        if vehicle_id not in self.px4_port_map:
            print(f"[{vehicle_id}] No connection mapping found.")
            self.mission_results[vehicle_id] = "❌ No connection mapping"
            return

        connection = self.connect_to_drone(vehicle_id)
        if not connection:
            print(f"[{vehicle_id}] ❌ Connection failed. Skipping mission scheduling.")
            self.mission_results[vehicle_id] = "❌ No heartbeat"
            return

        started_count = 0

        for mission in missions:
            task_id = mission['task_id']
            mission_file = os.path.join(
                self.mission_dir,
                f"mission_T{task_id}_UAV{vehicle_id}.plan"
            )

            print(f"[{vehicle_id}] Sleeping for 10 seconds before starting mission T{task_id}...")
            time.sleep(10)

            print(f"[{vehicle_id}] Attempting mission start for T{task_id}...")

            success = True  # self.upload_mission(connection, vehicle_id, mission_file)

            retry_count = 2
            count_msg = None
            while retry_count > 0:
                connection.mav.mission_request_list_send(
                    connection.target_system,
                    connection.target_component
                )
                msg = connection.recv_match(blocking=True, timeout=5)
                count_msg = connection.recv_match(type='MISSION_COUNT', blocking=True, timeout=5)
                if count_msg:
                    break
                retry_count -= 1
                time.sleep(1.0)

            if count_msg:
                print(f"[{vehicle_id}] Mission buffer has {count_msg.count} items.")
                if count_msg.count == 0:
                    print(f"[{vehicle_id}] ⚠️ No mission items loaded. Skipping mission start.")
                    continue
            else:
                print(f"[{vehicle_id}] ⚠️ Could not verify mission count. Mission start may fail.")

            if success:
                if self.start_mission(connection, vehicle_id):
                    started_count += 1
            else:
                print(f"[{vehicle_id}] Skipping mission start due to failed upload.")

        if started_count > 0:
            self.mission_results[vehicle_id] = f"✅ {started_count} mission(s) started"
        else:
            self.mission_results[vehicle_id] = "⚠️ No missions started"

    def start_all(self):
        vehicle_missions = defaultdict(list)
        for mission in self.distribution['missions']:
            vehicle_missions[mission['vehicle_id']].append(mission)

        threads = []
        for i, (vehicle_id, missions) in enumerate(vehicle_missions.items()):
            thread = Thread(target=self.launch_vehicle_missions, args=(vehicle_id, missions))
            thread.start()
            threads.append(thread)
            time.sleep(1.0)

        for t in threads:
            t.join()

        print("\n==== MISSION RESULTS ====")
        for vid, result in sorted(self.mission_results.items()):
            print(f"UAV {vid}: {result}")


if __name__ == "__main__":
    px4_ports = {
        5: 14540,
        8: 14541,
        11: 14542,
        12: 14543
    }
    scheduler = MultiUAVScheduler(
        '/home/sz6/Desktop/px4-scout/scout/data/distribution.json',
        '/home/sz6/Desktop/px4-scout/scout/missions',
        px4_ports
    )
    scheduler.start_all()

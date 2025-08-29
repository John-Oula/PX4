#!/usr/bin/env python3
"""
BAMS Mission Computer - PX4 SITL Offboard Control
Simple offboard control for PX4 SITL with Gazebo using UDP port 14540
"""

import time
import sys
import os
import signal
import threading
import pymavlink.mavutil as mavutil
from pymavlink import mavutil


class PX4SITLOffboardControl:
    def __init__(self):
        self.running = True
        self.mavlink_connection = None
        self.start_time = time.time()
        self.setpoint_thread = None
        self.current_waypoint = (0.0, 0.0, -5.0, 0.0)  # Default waypoint (x, y, z, yaw)
        self.armed = False
        self.offboard_active = False

        # Set up signal handler
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handle Ctrl+C for clean shutdown"""
        print("\n🛑 Ctrl+C detected - Stopping offboard control...")
        self.running = False

    def connect_mavlink(self):
        """Connect to PX4 SITL via MAVLink UDP"""
        try:
            print("🔌 Connecting to PX4 SITL via UDP port 14540...")

            # Create MAVLink connection to PX4 SITL
            self.mavlink_connection = mavutil.mavlink_connection(
                'udp:0.0.0.0:14540',  # Listen on UDP port 14540
                source_system=255,  # Ground control system ID
                source_component=1
            )

            print("⏳ Waiting for PX4 SITL heartbeat...")
            heartbeat = self.mavlink_connection.wait_heartbeat(timeout=10)

            if heartbeat:
                print(f"✅ MAVLink connected to PX4 SITL (system {heartbeat.get_srcSystem()})")
                return True
            else:
                print("❌ No MAVLink heartbeat received from PX4 SITL")
                return False

        except Exception as e:
            print(f"❌ MAVLink connection failed: {e}")
            return False

    def send_position_setpoint(self, x, y, z, yaw=0.0):
        """Send position setpoint using MAVLink"""
        try:
            if self.mavlink_connection is None:
                return

            # Use system boot time in milliseconds (uint32)
            timestamp_ms = int((time.time() - self.start_time) * 1000) & 0xFFFFFFFF

            # Send SET_POSITION_TARGET_LOCAL_NED message
            self.mavlink_connection.mav.set_position_target_local_ned_send(
                timestamp_ms,  # time_boot_ms (uint32)
                self.mavlink_connection.target_system,  # target_system (uint8)
                self.mavlink_connection.target_component,  # target_component (uint8)
                1,  # coordinate_frame (uint8) LOCAL_NED
                0b110111111000,  # type_mask (uint16) position only
                float(x), float(y), float(z),  # position NED (float)
                0.0, 0.0, 0.0,  # velocity NED (float, ignored)
                0.0, 0.0, 0.0,  # acceleration NED (float, ignored)
                float(yaw), 0.0  # yaw, yaw_rate (float)
            )

        except Exception as e:
            print(f"❌ Error sending position setpoint: {e}")

    def set_flight_mode(self, mode):
        """Set PX4 flight mode"""
        try:
            if self.mavlink_connection is None:
                return False

            # Set flight mode
            self.mavlink_connection.set_mode(mode)
            print(f"✅ Flight mode set to: {mode}")
            return True

        except Exception as e:
            print(f"❌ Error setting flight mode: {e}")
            return False

    def arm_disarm(self, arm=True):
        """Arm or disarm the vehicle"""
        try:
            if self.mavlink_connection is None:
                return False

            if arm:
                self.mavlink_connection.arducopter_arm()
                print("✅ Vehicle armed")
                self.armed = True
            else:
                self.mavlink_connection.arducopter_disarm()
                print("✅ Vehicle disarmed")
                self.armed = False

            return True

        except Exception as e:
            print(f"❌ Error arming/disarming: {e}")
            return False

    def start_offboard(self):
        """Start offboard control"""
        try:
            if self.mavlink_connection is None:
                return False

            # Send initial position setpoint
            x, y, z, yaw = self.current_waypoint
            self.send_position_setpoint(x, y, z, yaw)
            time.sleep(0.1)  # Small delay

            # Send MAV_CMD_DO_SET_MODE to set OFFBOARD mode
            self.mavlink_connection.mav.command_long_send(
                self.mavlink_connection.target_system,
                self.mavlink_connection.target_component,
                176,  # MAV_CMD_DO_SET_MODE
                0,  # confirmation
                1,  # mode (1 = OFFBOARD)
                0,  # custom_mode
                0,  # custom_submode
                0,  # unused
                0,  # unused
                0,  # unused
                0   # param7
            )

            print("✅ Offboard control started")
            self.offboard_active = True
            return True

        except Exception as e:
            print(f"❌ Error starting offboard control: {e}")
            return False

    def stop_offboard(self):
        """Stop offboard control"""
        try:
            if self.mavlink_connection is None:
                return False

            # Send MAV_CMD_DO_SET_MODE to set MANUAL mode
            self.mavlink_connection.mav.command_long_send(
                self.mavlink_connection.target_system,
                self.mavlink_connection.target_component,
                176,  # MAV_CMD_DO_SET_MODE
                0,  # confirmation
                0,  # mode (0 = MANUAL)
                0,  # custom_mode
                0,  # custom_submode
                0,  # unused
                0,  # unused
                0,  # unused
                0   # param7
            )

            print("✅ Offboard control stopped")
            self.offboard_active = False
            return True

        except Exception as e:
            print(f"❌ Error stopping offboard control: {e}")
            return False

    def send_land_command(self):
        """Send MAVLink LAND command for PX4"""
        try:
            if self.mavlink_connection is None:
                return False

            # For PX4, use MAV_CMD_NAV_LAND with proper parameters
            # MAV_CMD_NAV_LAND = 21
            self.mavlink_connection.mav.command_long_send(
                self.mavlink_connection.target_system,
                self.mavlink_connection.target_component,
                21,  # MAV_CMD_NAV_LAND
                0,  # confirmation
                0,  # Minimum target altitude if mode is aborted (0 = not used)
                0,  # Precision land mode (0 = normal landing)
                0,  # Yaw angle in degrees (0 = use current yaw)
                0,  # Latitude (0 = use current position)
                0,  # Longitude (0 = use current position)
                0,  # Altitude (0 = use current altitude)
                0   # param7
            )
            print("✅ MAVLink LAND command sent to PX4")
            return True

        except Exception as e:
            print(f"❌ Error sending LAND command: {e}")
            return False

    def setpoint_loop(self):
        """Background thread to send position setpoints at 100Hz"""
        print("🎯 Starting position setpoint loop at 100Hz...")

        while self.running:
            try:
                if self.offboard_active:
                    # Send position setpoint continuously at 100Hz
                    x, y, z, yaw = self.current_waypoint
                    self.send_position_setpoint(x, y, z, yaw)
                time.sleep(0.01)  # 100Hz

            except Exception as e:
                print(f"❌ Error in setpoint loop: {e}")
                time.sleep(1)

    def run(self):
        """Main execution"""
        try:
            print("=" * 60)
            print("🚀 BAMS MISSION COMPUTER - PX4 SITL OFFBOARD CONTROL")
            print("=" * 60)
            print("🎯 Mission: Simple offboard control for PX4 SITL with Gazebo")
            print("📡 Connection: UDP port 14540")
            print("⚡ Setpoint frequency: 100Hz")
            print("=" * 60)

            # Connect to PX4 SITL via MAVLink
            print("\n🔌 CONNECTING TO PX4 SITL")
            print("-" * 40)
            if not self.connect_mavlink():
                print("❌ Failed to connect to PX4 SITL")
                return

            # Start position setpoint thread
            print("\n🎯 STARTING POSITION SETPOINT THREAD")
            print("-" * 40)
            self.setpoint_thread = threading.Thread(target=self.setpoint_loop, daemon=True)
            self.setpoint_thread.start()
            print("✅ Position setpoint thread started at 100Hz")

            # Mission execution
            print("\n🚀 MISSION EXECUTION")
            print("-" * 40)
            print("⚠️  Press Ctrl+C to stop")
            print("=" * 60)

            # Step 1: Stream setpoints for 2 seconds to establish connection
            print("\n📡 Step 1: Streaming setpoints for 2 seconds...")
            self.current_waypoint = (0.0, 0.0, -5.0, 0.0)
            start_time = time.time()
            while time.time() - start_time < 2 and self.running:
                time.sleep(0.1)

            if not self.running:
                return

            # Step 2: Switch to OFFBOARD mode
            print("\n🎯 Step 2: Switching to OFFBOARD mode...")
            if not self.start_offboard():
                print("❌ Failed to start offboard control")
                return

            # Wait for offboard mode to be active
            time.sleep(2)
            if not self.running:
                return

            # Step 3: Arm the vehicle
            print("\n🔓 Step 3: Arming the vehicle...")
            if not self.arm_disarm(arm=True):
                print("❌ Failed to arm vehicle")
                return

            # Wait for arming to complete
            time.sleep(2)
            if not self.running:
                return

            # Step 4: Mission waypoints
            print("\n🎯 Step 4: Executing mission waypoints...")

            # Waypoint 1: Hover at current position
            print("📍 Waypoint 1: Hover at current position")
            self.current_waypoint = (0.0, 0.0, -5.0, 0.0)
            start_time = time.time()
            while time.time() - start_time < 10 and self.running:
                time.sleep(0.1)

            if not self.running:
                return

            # Waypoint 2: Move forward
            print("📍 Waypoint 2: Move forward 5m")
            self.current_waypoint = (5.0, 0.0, -5.0, 0.0)
            start_time = time.time()
            while time.time() - start_time < 10 and self.running:
                time.sleep(0.1)

            if not self.running:
                return

            # Waypoint 3: Move right
            print("📍 Waypoint 3: Move right 5m")
            self.current_waypoint = (5.0, 5.0, -5.0, 0.0)
            start_time = time.time()
            while time.time() - start_time < 10 and self.running:
                time.sleep(0.1)

            if not self.running:
                return

            # Waypoint 4: Return to start
            print("📍 Waypoint 4: Return to start position")
            self.current_waypoint = (0.0, 0.0, -5.0, 0.0)
            start_time = time.time()
            while time.time() - start_time < 10 and self.running:
                time.sleep(0.1)

            if not self.running:
                return

            # Step 5: Land
            print("\n🛬 Step 5: Landing...")
            self.send_land_command()
            time.sleep(10)

            # Step 6: Mission complete
            print("\n🔒 Step 6: Mission complete")
            print("⚠️  Please disarm the vehicle manually when ready")

            # Mission complete
            print("\n✅ Mission completed!")
            self.running = False

        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            print("\n🛑 Cleanup...")
            self.running = False

            # Stop offboard control
            if self.offboard_active:
                print("🛑 Stopping offboard control...")
                self.stop_offboard()

            # Disarm vehicle
            if self.armed:
                print("🔒 Disarming vehicle...")
                self.arm_disarm(arm=False)

            # Cleanup complete
            print("✅ Cleanup complete")

            # Wait for threads to stop
            if self.setpoint_thread and self.setpoint_thread.is_alive():
                print("⏳ Waiting for setpoint thread to stop...")
                self.setpoint_thread.join(timeout=2)
                print("✅ Setpoint thread stopped")

            # Close MAVLink connection
            if self.mavlink_connection:
                print("🔌 Closing MAVLink connection...")
                self.mavlink_connection.close()
                print("✅ MAVLink connection closed")

            print("✅ Cleanup completed")


if __name__ == "__main__":
    controller = PX4SITLOffboardControl()
    controller.run()

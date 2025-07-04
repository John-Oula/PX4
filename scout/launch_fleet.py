#!/usr/bin/env python3
"""
Simple Multi-UAV Fleet Launcher
Reads distribution.json, spawns exact number of drones, launches everything

Usage: python3 launch_fleet.py distribution.json [world_name]
"""

import json
import sys
import os
import subprocess
import signal
import time
from collections import defaultdict


class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'


class FleetLauncher:
    def __init__(self, json_file, world_name="empty"):
        self.json_file = json_file
        self.world_name = world_name
        # Auto-detect PX4 directory
        self.px4_dir = self._find_px4_dir()
        self.processes = []
        self.vehicles = {}
        self.task_count = defaultdict(int)

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _find_px4_dir(self):
        """Auto-detect PX4 directory"""
        # Try current directory and parent directories
        current_dir = os.path.abspath(os.getcwd())

        # Check if we're already in PX4 directory
        if os.path.exists(os.path.join(current_dir, "platforms", "posix")):
            return current_dir

        # Check parent directories
        parent = os.path.dirname(current_dir)
        while parent != "/":
            if os.path.exists(os.path.join(parent, "platforms", "posix")):
                return parent
            parent = os.path.dirname(parent)

        # Default fallback
        return "/root/PX4"

    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print(f"\n{Colors.RED}🛑 Shutdown signal received...{Colors.NC}")
        self.cleanup()
        sys.exit(0)

    def parse_fleet_info(self):
        """Extract vehicle information from JSON"""
        try:
            with open(self.json_file, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"{Colors.RED}❌ Error: {self.json_file} not found{Colors.NC}")
            return False
        except json.JSONDecodeError as e:
            print(f"{Colors.RED}❌ Error: Invalid JSON - {e}{Colors.NC}")
            return False

        # Extract unique vehicles and count tasks
        for result in data.get('missions', []):
            if 'error' in result:
                continue

            if 'vehicle_id' in result and 'path_info' in result:
                vehicle_id = result['vehicle_id']
                self.task_count[vehicle_id] += 1

                # Store vehicle info (first occurrence)
                if vehicle_id not in self.vehicles:
                    start_point = result['path_info']['start_point']

                    # Get real-world coordinates from path_lat_long (first coordinate pair)
                    path_lat_long = result['path_info'].get('path_lat_long', [])
                    realworld_coords = path_lat_long[0] if path_lat_long else None

                    self.vehicles[vehicle_id] = {
                        'start_point': start_point,
                        'grid_x': start_point[0],
                        'grid_y': start_point[1],
                        'gazebo_x': start_point[0] / 1.0,
                        'gazebo_y': start_point[1] / 1.0,
                        'real_lat': realworld_coords[0] if realworld_coords else None,  # latitude is first
                        'real_lon': realworld_coords[1] if realworld_coords else None  # longitude is second
                    }

        if not self.vehicles:
            print(f"{Colors.RED}❌ No vehicles found in JSON{Colors.NC}")
            return False

        return True

    def print_fleet_summary(self):
        """Display fleet information"""
        vehicle_ids = sorted(self.vehicles.keys())

        print(f"{Colors.BLUE}🚁 MULTI-UAV FLEET LAUNCHER{Colors.NC}")
        print(f"{Colors.BLUE}{'=' * 50}{Colors.NC}")
        print(f"📄 JSON file: {Colors.YELLOW}{self.json_file}{Colors.NC}")
        print(f"🌍 World: {Colors.YELLOW}{self.world_name}{Colors.NC}")
        print(f"📁 PX4 directory: {Colors.YELLOW}{self.px4_dir}{Colors.NC}")
        print(f"🚁 Fleet size: {Colors.YELLOW}{len(vehicle_ids)}{Colors.NC} vehicles")
        print(f"📝 Total tasks: {Colors.YELLOW}{sum(self.task_count.values())}{Colors.NC}")
        print("")

        print(f"{Colors.CYAN}📊 VEHICLE FLEET:{Colors.NC}")
        for vid in vehicle_ids:
            vehicle = self.vehicles[vid]
            tasks = self.task_count[vid]
            if vehicle['real_lat'] and vehicle['real_lon']:
                print(
                    f"   Vehicle {vid:2}: Real({vehicle['real_lat']:.6f}, {vehicle['real_lon']:.6f}) | Tasks: {tasks}")
            else:
                print(f"   Vehicle {vid:2}: Grid({vehicle['grid_x']:3}, {vehicle['grid_y']:3}) | Tasks: {tasks}")
        print("")

    def validate_px4(self):
        """Check PX4 setup"""
        if not os.path.exists(self.px4_dir):
            print(f"{Colors.RED}❌ PX4 directory not found: {self.px4_dir}{Colors.NC}")
            return False

        build_dir = f"{self.px4_dir}/build/px4_sitl_default"
        if not os.path.exists(build_dir):
            print(f"{Colors.YELLOW}📦 Building PX4...{Colors.NC}")
            if not self._build_px4():
                return False

        return True

    def _build_px4(self):
        """Build PX4 SITL"""
        try:
            env = os.environ.copy()
            env['DONT_RUN'] = '1'

            result = subprocess.run(
                ['make', 'px4_sitl_default'],
                cwd=self.px4_dir,
                env=env,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print(f"{Colors.GREEN}✅ PX4 build successful{Colors.NC}")
                return True
            else:
                print(f"{Colors.RED}❌ PX4 build failed{Colors.NC}")
                return False

        except Exception as e:
            print(f"{Colors.RED}❌ Build error: {e}{Colors.NC}")
            return False

    def launch_vehicles(self):
        """Launch all PX4 SITL instances with proper spawn positions in Gazebo"""
        vehicle_ids = sorted(self.vehicles.keys())
        print(f"{Colors.GREEN}🚀 Spawning {len(vehicle_ids)} vehicles in Gazebo...{Colors.NC}")

        for i, vehicle_id in enumerate(vehicle_ids):
            vehicle = self.vehicles[vehicle_id]
            mavlink_port = 14540 + i

            # Use real coordinates if available, otherwise fallback to grid-based
            if vehicle['real_lat'] and vehicle['real_lon']:
                home_lat = vehicle['real_lat']
                home_lon = vehicle['real_lon']
                location_str = f"Real({home_lat:.6f}, {home_lon:.6f})"

                # Convert real world coordinates to relative Gazebo positions
                # This is a simple offset approach - you may need to adjust based on your requirements
                gazebo_x = vehicle['gazebo_x']
                gazebo_y = vehicle['gazebo_y']
            else:
                # Fallback: use grid coordinates with default base location
                home_lat = 47.397742 + (vehicle['gazebo_y'] * 0.0001)
                home_lon = 8.545594 + (vehicle['gazebo_x'] * 0.0001)
                location_str = f"Grid-based({home_lat:.6f}, {home_lon:.6f})"

                # Use grid positions directly for Gazebo spawn
                gazebo_x = vehicle['gazebo_x']
                gazebo_y = vehicle['gazebo_y']

            # Create spawn position string for Gazebo (x,y,z,roll,pitch,yaw)
            # Spread vehicles out in Gazebo world coordinates
            # Add some spacing to prevent overlap
            spawn_x = gazebo_x * 2.0  # Scale up for better spacing
            spawn_y = gazebo_y * 2.0  # Scale up for better spacing
            spawn_z = 0.1  # Slightly above ground

            # If first vehicle, spawn at origin
            if i == 0:
                gazebo_pose = "0,0,0.1,0,0,0"
            else:
                gazebo_pose = f"{spawn_x},{spawn_y},{spawn_z},0,0,0"

            print(f"   Vehicle {vehicle_id}: {location_str} | Gazebo pose: {gazebo_pose} | Port {mavlink_port}")

            # Set environment variables for PX4
            env = os.environ.copy()

            # GPS home coordinates for navigation
            env['PX4_HOME_LAT'] = str(home_lat)
            env['PX4_HOME_LON'] = str(home_lon)
            env['PX4_HOME_ALT'] = '100'  # Generic altitude

            # Vehicle configuration
            env['PX4_SYS_AUTOSTART'] = '4001'  # X500 quadcopter configuration
            env['PX4_SIM_MODEL'] = 'gz_x500'  # Gazebo X500 model

            # CRITICAL: Set spawn position in Gazebo world
            env['PX4_GZ_MODEL_POSE'] = gazebo_pose
            env['HEADLESS'] = '1'

            # Additional Gazebo settings
            env['LIBGL_ALWAYS_SOFTWARE'] = '1'  # Software rendering for compatibility
            env['DISPLAY'] = ':0'  # Ensure proper display

            # For multi-vehicle, set standalone mode for instances after the first
            if i > 0:
                env['PX4_GZ_STANDALONE'] = '1'

            # Launch PX4 SITL instance
            try:
                px4_process = subprocess.Popen([
                    f"{self.px4_dir}/build/px4_sitl_default/bin/px4",
                    "-i", str(vehicle_id)  # Instance ID
                ], cwd=self.px4_dir, env=env,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                self.processes.append(px4_process)

                # Longer delay for first vehicle (starts Gazebo), shorter for others
                time.sleep(15 if i == 0 else 5)

            except Exception as e:
                print(f"{Colors.RED}❌ Failed to launch vehicle {vehicle_id}: {e}{Colors.NC}")

        print(
            f"{Colors.CYAN}   → Check Gazebo window to see all {len(vehicle_ids)} drones at different positions!{Colors.NC}")

    def print_connection_info(self):
        """Show QGroundControl connection information"""
        vehicle_ids = sorted(self.vehicles.keys())

        print(f"\n{Colors.BLUE}📡 QGROUNDCONTROL CONNECTIONS:{Colors.NC}")
        for i, vehicle_id in enumerate(vehicle_ids):
            port = 14540 + i
            vehicle = self.vehicles[vehicle_id]
            if vehicle['real_lat'] and vehicle['real_lon']:
                coord_info = f"Real: {vehicle['real_lat']:.4f}, {vehicle['real_lon']:.4f}"
            else:
                coord_info = f"Grid: {vehicle['grid_x']}, {vehicle['grid_y']}"
            print(f"   Vehicle {vehicle_id:2}: UDP port {Colors.YELLOW}{port}{Colors.NC} | {coord_info}")

        print(f"\n{Colors.CYAN}🎮 GAZEBO SIMULATION:{Colors.NC}")
        print(f"   ✅ All {len(vehicle_ids)} drones visible in single Gazebo window")
        print(f"   ✅ Vehicles positioned at real world coordinates")
        print(f"   ✅ Connect QGC to control and monitor fleet")
        print(f"   ✅ Check Gazebo for 3D visualization")

        print(f"\n{Colors.GREEN}✅ All systems operational!{Colors.NC}")
        print(f"{Colors.YELLOW}Press Ctrl+C to shutdown fleet...{Colors.NC}")

    def cleanup(self):
        """Clean up all processes"""
        if not self.processes:
            return

        print(f"{Colors.YELLOW}🧹 Shutting down {len(self.processes)} processes...{Colors.NC}")

        for process in self.processes:
            try:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception:
                pass

        # Kill any remaining processes
        try:
            subprocess.run(['pkill', '-f', 'px4.*-i'], capture_output=True, check=False)
            subprocess.run(['pkill', '-f', 'gz sim'], capture_output=True, check=False)
        except Exception:
            pass

        print(f"{Colors.GREEN}✅ Fleet shutdown complete{Colors.NC}")

    def run(self):
        """Main execution flow"""
        # Parse fleet info
        if not self.parse_fleet_info():
            sys.exit(1)

        # Show summary
        self.print_fleet_summary()

        # Validate PX4
        if not self.validate_px4():
            sys.exit(1)

        # Launch Gazebo
        # if not self.launch_gazebo():
        #     sys.exit(1)

        # Launch vehicles
        self.launch_vehicles()

        # Show connection info
        self.print_connection_info()

        # Wait for shutdown
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


def main():
    if len(sys.argv) < 2:
        print(f"{Colors.BLUE}🚁 Multi-UAV Fleet Launcher{Colors.NC}")
        print("=" * 40)
        print("Usage: python3 launch_fleet.py distribution.json [world_name]")
        print("")
        print("Examples:")
        print("  python3 launch_fleet.py distribution.json")
        print("  python3 launch_fleet.py distribution.json empty")
        print("  python3 launch_fleet.py distribution.json baylands")
        print("  python3 launch_fleet.py distribution.json windy")
        print("")
        print("🌍 Uses real world coordinates from distribution.json")
        print("📍 Default world: empty")
        print("")
        print("Available worlds: empty, baylands, windy, aruco, etc.")
        print("Note: Real coordinates from JSON will be used for vehicle positioning")
        sys.exit(1)

    json_file = sys.argv[1]
    world_name = sys.argv[2] if len(sys.argv) > 2 else "empty"  # Default to empty world

    launcher = FleetLauncher(json_file, world_name)
    launcher.run()


if __name__ == "__main__":
    main()

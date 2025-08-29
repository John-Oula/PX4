#!/usr/bin/env python3
"""
Telemetry Monitor
Connects to ground control server and displays real-time telemetry from drones
"""

import asyncio
import websockets
import json
import time
from datetime import datetime

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

class TelemetryMonitor:
    def __init__(self, server_url="ws://localhost:8080"):
        self.server_url = server_url
        self.websocket = None
        self.drones = {}

    async def connect(self):
        """Connect to ground control server"""
        try:
            print(f"Connecting to ground control server: {self.server_url}")
            self.websocket = await websockets.connect(self.server_url)

            # Send initial handshake as ground station
            await self.websocket.send(json.dumps({
                "topic": "telemetry_monitor",
                "payload": {"timestamp": time.time()}
            }))

            print(f"{Colors.GREEN}✅ Connected to ground control server{Colors.NC}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ Failed to connect: {e}{Colors.NC}")
            return False

    async def request_drone_list(self):
        """Request list of connected drones"""
        try:
            await self.websocket.send(json.dumps({
                "topic": "list_drones",
                "payload": {}
            }))
        except Exception as e:
            print(f"{Colors.RED}❌ Error requesting drone list: {e}{Colors.NC}")

    def format_telemetry(self, drone_id, telemetry):
        """Format telemetry data for display"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Extract key telemetry data
        armed = telemetry.get('armed', 'unknown')
        armed_color = Colors.GREEN if armed else Colors.RED
        armed_text = f"{armed_color}{'ARMED' if armed else 'DISARMED'}{Colors.NC}"

        latitude = telemetry.get('latitude', 'N/A')
        longitude = telemetry.get('longitude', 'N/A')
        altitude = telemetry.get('altitude', 'N/A')

        roll = telemetry.get('roll', 'N/A')
        pitch = telemetry.get('pitch', 'N/A')
        yaw = telemetry.get('yaw', 'N/A')

        battery_voltage = telemetry.get('battery_voltage', 'N/A')
        battery_remaining = telemetry.get('battery_remaining', 'N/A')

        satellites = telemetry.get('satellites', 'N/A')
        gps_fix = telemetry.get('gps_fix', 'N/A')

        mode = telemetry.get('mode', 'N/A')
        system_status = telemetry.get('system_status', 'N/A')

        # Additional telemetry data
        groundspeed = telemetry.get('groundspeed', 'N/A')
        airspeed = telemetry.get('airspeed', 'N/A')
        climb_rate = telemetry.get('climb_rate', 'N/A')
        throttle = telemetry.get('throttle', 'N/A')

        velocity_x = telemetry.get('velocity_x', 'N/A')
        velocity_y = telemetry.get('velocity_y', 'N/A')
        velocity_z = telemetry.get('velocity_z', 'N/A')

        hdop = telemetry.get('hdop', 'N/A')
        cpu_load = telemetry.get('cpu_load', 'N/A')

        print(f"\n{Colors.CYAN}[{timestamp}] 🚁 {drone_id}{Colors.NC}")
        print(f"  Status: {armed_text} | Mode: {Colors.BLUE}{mode}{Colors.NC} | System: {system_status}")

        if latitude != 'N/A' and longitude != 'N/A':
            print(f"  📍 Position: {Colors.YELLOW}{latitude:.6f}, {longitude:.6f}{Colors.NC} | Alt: {Colors.YELLOW}{altitude}m{Colors.NC}")

        if roll != 'N/A':
            print(f"  🎯 Attitude: Roll={Colors.BLUE}{roll:.1f}°{Colors.NC} | Pitch={Colors.BLUE}{pitch:.1f}°{Colors.NC} | Yaw={Colors.BLUE}{yaw:.1f}°{Colors.NC}")

        if battery_voltage != 'N/A':
            try:
                voltage_val = float(str(battery_voltage).replace('N/A', '0'))
                battery_color = Colors.GREEN if voltage_val > 11.0 else Colors.RED
                print(f"  🔋 Battery: {battery_color}{battery_voltage}V{Colors.NC} | Remaining: {battery_color}{battery_remaining}%{Colors.NC}")
            except:
                print(f"  🔋 Battery: {battery_voltage}V | Remaining: {battery_remaining}%")

        if satellites != 'N/A':
            try:
                sat_val = int(str(satellites).replace('N/A', '0'))
                sat_color = Colors.GREEN if sat_val >= 6 else Colors.YELLOW
                hdop_text = f" | HDOP: {hdop}" if hdop != 'N/A' else ""
                print(f"  🛰️  GPS: {sat_color}{satellites} satellites{Colors.NC} | Fix: {gps_fix}{hdop_text}")
            except:
                print(f"  🛰️  GPS: {satellites} satellites | Fix: {gps_fix}")

        if groundspeed != 'N/A' or airspeed != 'N/A':
            speed_text = ""
            if groundspeed != 'N/A':
                speed_text += f"Ground: {Colors.GREEN}{groundspeed:.1f}m/s{Colors.NC}"
            if airspeed != 'N/A':
                if speed_text:
                    speed_text += " | "
                speed_text += f"Air: {Colors.GREEN}{airspeed:.1f}m/s{Colors.NC}"
            if climb_rate != 'N/A':
                climb_color = Colors.GREEN if float(str(climb_rate).replace('N/A', '0')) > 0 else Colors.BLUE
                speed_text += f" | Climb: {climb_color}{climb_rate:.1f}m/s{Colors.NC}"
            if throttle != 'N/A':
                throttle_color = Colors.YELLOW if int(str(throttle).replace('N/A', '0')) > 50 else Colors.BLUE
                speed_text += f" | Throttle: {throttle_color}{throttle}%{Colors.NC}"
            print(f"  🚀 Speed: {speed_text}")

        if velocity_x != 'N/A' and velocity_y != 'N/A' and velocity_z != 'N/A':
            try:
                vel_total = (float(velocity_x)**2 + float(velocity_y)**2 + float(velocity_z)**2)**0.5
                print(f"  💨 Velocity: X={Colors.CYAN}{velocity_x:.1f}{Colors.NC} Y={Colors.CYAN}{velocity_y:.1f}{Colors.NC} Z={Colors.CYAN}{velocity_z:.1f}{Colors.NC} | Total: {Colors.GREEN}{vel_total:.1f}m/s{Colors.NC}")
            except:
                print(f"  💨 Velocity: X={velocity_x} Y={velocity_y} Z={velocity_z}")

        if cpu_load != 'N/A':
            try:
                cpu_val = float(str(cpu_load).replace('N/A', '0'))
                cpu_color = Colors.GREEN if cpu_val < 50 else Colors.YELLOW if cpu_val < 80 else Colors.RED
                print(f"  💻 System: CPU Load: {cpu_color}{cpu_load}%{Colors.NC}")
            except:
                print(f"  💻 System: CPU Load: {cpu_load}%")

    async def handle_message(self, data):
        """Handle messages from ground control server"""
        topic = data.get('topic', '')
        payload = data.get('payload', {})

        if topic == 'drone_list':
            drones = payload.get('drones', [])
            print(f"\n{Colors.BLUE}📋 Connected Drones: {len(drones)}{Colors.NC}")
            for drone in drones:
                drone_id = drone['drone_id']
                self.drones[drone_id] = drone
                telemetry = drone.get('telemetry', {})
                if telemetry:
                    self.format_telemetry(drone_id, telemetry)
                else:
                    print(f"  🚁 {drone_id}: No telemetry data yet")

        elif topic == 'drone_connected':
            drone_id = payload.get('drone_id')
            print(f"{Colors.GREEN}🚁 New drone connected: {drone_id}{Colors.NC}")
            self.drones[drone_id] = payload

        elif topic == 'drone_disconnected':
            drone_id = payload.get('drone_id')
            print(f"{Colors.YELLOW}🚁 Drone disconnected: {drone_id}{Colors.NC}")
            if drone_id in self.drones:
                del self.drones[drone_id]

        elif topic == 'telemetry':
            drone_id = payload.get('drone_id')
            if drone_id:
                # Update drone telemetry
                if drone_id in self.drones:
                    self.drones[drone_id]['telemetry'] = payload
                else:
                    self.drones[drone_id] = {'telemetry': payload}

                # Display telemetry
                self.format_telemetry(drone_id, payload)

    async def monitor(self):
        """Main monitoring loop"""
        print(f"\n{Colors.CYAN}📊 Real-time Telemetry Monitor{Colors.NC}")
        print(f"{Colors.BLUE}Monitoring telemetry from all connected drones...{Colors.NC}")
        print(f"{Colors.YELLOW}Press Ctrl+C to stop{Colors.NC}\n")

        # Request initial drone list
        await self.request_drone_list()

        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(data)
                except json.JSONDecodeError:
                    print(f"{Colors.RED}❌ Invalid JSON received{Colors.NC}")
                except Exception as e:
                    print(f"{Colors.RED}❌ Error processing message: {e}{Colors.NC}")
        except websockets.exceptions.ConnectionClosed:
            print(f"{Colors.YELLOW}⚠️  Connection closed{Colors.NC}")
        except Exception as e:
            print(f"{Colors.RED}❌ Monitor error: {e}{Colors.NC}")

async def main():
    monitor = TelemetryMonitor()

    if await monitor.connect():
        try:
            await monitor.monitor()
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}⚠️  Monitor stopped by user{Colors.NC}")

    if monitor.websocket:
        await monitor.websocket.close()

if __name__ == "__main__":
    asyncio.run(main())

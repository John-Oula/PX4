#!/usr/bin/env python3
"""
Ground Control Client
Connects to ground control server to send commands to drones
Interactive interface for drone command and control

Usage: python3 ground_control_client.py [server_url]
"""

import asyncio
import websockets
import json
import sys
import time

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

class GroundControlClient:
    def __init__(self, server_url: str):
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
                "topic": "ground_station_connect",
                "payload": {"timestamp": time.time()}
            }))

            print(f"{Colors.GREEN}✅ Connected to ground control server{Colors.NC}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ Failed to connect: {e}{Colors.NC}")
            return False

    async def send_command(self, drone_id: str, command: str, payload=None):
        """Send command to specific drone"""
        if payload is None:
            payload = {}

        message = {
            "topic": "drone_command",
            "payload": {
                "drone_id": drone_id,
                "command": command,
                "payload": payload
            }
        }

        try:
            await self.websocket.send(json.dumps(message))
            print(f"{Colors.CYAN}📤 Command sent to {drone_id}: {command}{Colors.NC}")
        except Exception as e:
            print(f"{Colors.RED}❌ Error sending command: {e}{Colors.NC}")

    async def list_drones(self):
        """Request list of connected drones"""
        try:
            await self.websocket.send(json.dumps({
                "topic": "list_drones",
                "payload": {}
            }))
        except Exception as e:
            print(f"{Colors.RED}❌ Error requesting drone list: {e}{Colors.NC}")

    async def listen_responses(self):
        """Listen for responses from ground control server"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.handle_response(data)
                except json.JSONDecodeError:
                    print(f"{Colors.RED}❌ Invalid JSON received{Colors.NC}")
                except Exception as e:
                    print(f"{Colors.RED}❌ Error processing response: {e}{Colors.NC}")
        except websockets.exceptions.ConnectionClosed:
            print(f"{Colors.YELLOW}⚠️  Connection closed{Colors.NC}")
        except Exception as e:
            print(f"{Colors.RED}❌ Listen error: {e}{Colors.NC}")

    async def handle_response(self, data: dict):
        """Handle response from ground control server"""
        topic = data.get('topic', '')
        payload = data.get('payload', {})

        if topic == 'drone_list':
            self.drones = {drone['drone_id']: drone for drone in payload.get('drones', [])}
            print(f"\n{Colors.BLUE}📋 Connected Drones:{Colors.NC}")
            if not self.drones:
                print(f"{Colors.YELLOW}  No drones connected{Colors.NC}")
            else:
                for drone_id, drone_info in self.drones.items():
                    telemetry = drone_info.get('telemetry', {})
                    armed = telemetry.get('armed', 'unknown')
                    lat = telemetry.get('latitude', 'unknown')
                    lon = telemetry.get('longitude', 'unknown')
                    alt = telemetry.get('altitude', 'unknown')
                    print(f"  📍 {drone_id}: Armed={armed}, Pos=({lat}, {lon}, {alt})")

        elif topic == 'drone_connected':
            drone_id = payload.get('drone_id')
            print(f"{Colors.GREEN}🚁 Drone connected: {drone_id}{Colors.NC}")

        elif topic == 'drone_disconnected':
            drone_id = payload.get('drone_id')
            print(f"{Colors.YELLOW}🚁 Drone disconnected: {drone_id}{Colors.NC}")
            if drone_id in self.drones:
                del self.drones[drone_id]

        elif topic == 'telemetry':
            drone_id = payload.get('drone_id')
            if drone_id in self.drones:
                self.drones[drone_id]['telemetry'] = payload
                # Print brief telemetry update
                armed = payload.get('armed', 'unknown')
                alt = payload.get('altitude', 'unknown')
                print(f"{Colors.BLUE}📊 {drone_id}: Armed={armed}, Alt={alt}m{Colors.NC}")

        elif topic == 'command_response':
            drone_id = payload.get('drone_id')
            command = payload.get('command', '')
            status = payload.get('status', 'unknown')
            message = payload.get('message', '')
            print(f"{Colors.GREEN}📨 Response from {drone_id}: {command} - {status} - {message}{Colors.NC}")

        elif topic == 'command_ack':
            drone_id = payload.get('drone_id')
            command = payload.get('command')
            success = payload.get('success')
            status_text = "✅ Success" if success else "❌ Failed"
            print(f"{status_text} Command {command} to {drone_id}")

    async def interactive_mode(self):
        """Interactive command interface"""
        print(f"\n{Colors.CYAN}🚀 Ground Control Interactive Interface{Colors.NC}")
        print(f"{Colors.BLUE}Commands: list, arm <drone_id>, disarm <drone_id>, takeoff <drone_id> [altitude], land <drone_id>, rtl <drone_id>, status <drone_id>, quit{Colors.NC}")
        print(f"{Colors.BLUE}Example: arm drone_1_0{Colors.NC}")
        print()

        # Start listening task
        listen_task = asyncio.create_task(self.listen_responses())

        # Get initial drone list
        await self.list_drones()
        await asyncio.sleep(1)  # Wait for response

        try:
            while True:
                try:
                    command_line = input(f"{Colors.CYAN}GCS> {Colors.NC}").strip()
                    if not command_line:
                        continue

                    parts = command_line.split()
                    command = parts[0].lower()

                    if command == 'quit' or command == 'exit':
                        break
                    elif command == 'list':
                        await self.list_drones()
                    elif command == 'arm' and len(parts) >= 2:
                        drone_id = parts[1]
                        await self.send_command(drone_id, 'arm')
                    elif command == 'disarm' and len(parts) >= 2:
                        drone_id = parts[1]
                        await self.send_command(drone_id, 'disarm')
                    elif command == 'takeoff' and len(parts) >= 2:
                        drone_id = parts[1]
                        altitude = float(parts[2]) if len(parts) > 2 else 10.0
                        await self.send_command(drone_id, 'takeoff', {'altitude': altitude})
                    elif command == 'land' and len(parts) >= 2:
                        drone_id = parts[1]
                        await self.send_command(drone_id, 'land')
                    elif command == 'rtl' and len(parts) >= 2:
                        drone_id = parts[1]
                        await self.send_command(drone_id, 'rtl')
                    elif command == 'status' and len(parts) >= 2:
                        drone_id = parts[1]
                        await self.send_command(drone_id, 'get_status')
                    elif command == 'mode' and len(parts) >= 3:
                        drone_id = parts[1]
                        mode = parts[2].upper()
                        await self.send_command(drone_id, 'set_flight_mode', {'mode': mode})
                    else:
                        print(f"{Colors.YELLOW}❓ Unknown command or missing parameters{Colors.NC}")
                        print(f"{Colors.BLUE}Available commands: list, arm <drone_id>, disarm <drone_id>, takeoff <drone_id> [altitude], land <drone_id>, rtl <drone_id>, status <drone_id>, mode <drone_id> <MODE>{Colors.NC}")

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"{Colors.RED}❌ Command error: {e}{Colors.NC}")

        finally:
            listen_task.cancel()

async def single_command_mode(client, command_parts):
    """Execute a single command and exit"""
    await client.connect()
    if not client.websocket:
        return

    # Start listening task
    listen_task = asyncio.create_task(client.listen_responses())

    command = command_parts[0].lower()

    if command == 'list':
        await client.list_drones()
        await asyncio.sleep(2)  # Wait for response
    elif command == 'arm' and len(command_parts) >= 2:
        drone_id = command_parts[1]
        await client.send_command(drone_id, 'arm')
        await asyncio.sleep(2)
    elif command == 'takeoff' and len(command_parts) >= 2:
        drone_id = command_parts[1]
        altitude = float(command_parts[2]) if len(command_parts) > 2 else 10.0
        await client.send_command(drone_id, 'takeoff', {'altitude': altitude})
        await asyncio.sleep(2)

    listen_task.cancel()

def main():
    server_url = "ws://localhost:8080"

    if len(sys.argv) > 1:
        if sys.argv[1].startswith('ws://'):
            server_url = sys.argv[1]
        else:
            # Single command mode
            client = GroundControlClient(server_url)
            try:
                asyncio.run(single_command_mode(client, sys.argv[1:]))
            except KeyboardInterrupt:
                pass
            return

    print(f"{Colors.CYAN}🔧 Ground Control Client{Colors.NC}")
    print(f"{Colors.BLUE}📋 Usage: python3 ground_control_client.py [server_url]{Colors.NC}")
    print(f"{Colors.BLUE}📋 Usage: python3 ground_control_client.py <command> <args...>{Colors.NC}")
    print(f"{Colors.BLUE}📋 Default server: ws://localhost:8080{Colors.NC}")
    print()

    client = GroundControlClient(server_url)

    try:
        asyncio.run(client.connect())
        if client.websocket:
            asyncio.run(client.interactive_mode())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Client stopped by user{Colors.NC}")
    except Exception as e:
        print(f"{Colors.RED}❌ Client error: {e}{Colors.NC}")

if __name__ == "__main__":
    main()

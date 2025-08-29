#!/usr/bin/env python3
"""
Ground Control WebSocket Server
Receives drone connections and allows command & control
Handles multiple drones and provides telemetry monitoring

Usage: python3 ground_control_server.py [port]
"""

import asyncio
import websockets
import json
import sys
import time
from typing import Dict, Set, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'


class GroundControlServer:
    def __init__(self, port: int = 8080):
        self.port = port
        self.drones: Dict[str, Dict] = {}  # drone_id -> {websocket, info}
        self.ground_stations: Set[websockets.WebSocketServerProtocol] = set()
        self.connected_clients = 0

    async def register_client(self, websocket, client_type="unknown"):
        """Register a new client (drone or ground station)"""
        self.connected_clients += 1
        logger.info(f"{Colors.GREEN}✅ New {client_type} connected. Total clients: {self.connected_clients}{Colors.NC}")

    async def unregister_client(self, websocket):
        """Unregister a client"""
        self.connected_clients -= 1

        # Remove from drones if it was a drone
        drone_to_remove = None
        for drone_id, drone_info in self.drones.items():
            if drone_info['websocket'] == websocket:
                drone_to_remove = drone_id
                break

        if drone_to_remove:
            del self.drones[drone_to_remove]
            logger.info(f"{Colors.YELLOW}⚠️  Drone {drone_to_remove} disconnected{Colors.NC}")
            await self.broadcast_to_ground_stations("drone_disconnected", {
                "drone_id": drone_to_remove,
                "timestamp": time.time()
            })

        # Remove from ground stations
        self.ground_stations.discard(websocket)

        logger.info(f"{Colors.YELLOW}⚠️  Client disconnected. Total clients: {self.connected_clients}{Colors.NC}")

    async def broadcast_to_ground_stations(self, topic: str, payload: Dict[str, Any]):
        """Broadcast message to all ground control stations"""
        if not self.ground_stations:
            return

        message = {
            "topic": topic,
            "payload": payload
        }

        disconnected = []
        for gs in self.ground_stations:
            try:
                await gs.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(gs)
            except Exception as e:
                logger.error(f"{Colors.RED}❌ Error broadcasting to ground station: {e}{Colors.NC}")
                disconnected.append(gs)

        # Remove disconnected ground stations
        for gs in disconnected:
            self.ground_stations.discard(gs)

    async def send_to_drone(self, drone_id: str, topic: str, payload: Dict[str, Any]):
        """Send command to specific drone"""
        if drone_id not in self.drones:
            logger.error(f"{Colors.RED}❌ Drone {drone_id} not found{Colors.NC}")
            return False

        message = {
            "topic": topic,
            "payload": payload
        }

        try:
            drone_ws = self.drones[drone_id]['websocket']
            await drone_ws.send(json.dumps(message))
            logger.info(f"{Colors.CYAN}📤 Command sent to drone {drone_id}: {topic}{Colors.NC}")
            return True
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Error sending to drone {drone_id}: {e}{Colors.NC}")
            return False

    async def handle_drone_message(self, websocket, data: Dict[str, Any]):
        """Handle message from drone"""
        topic = data.get('topic', '')
        payload = data.get('payload', {})

        # Identify drone
        drone_id = None
        for did, drone_info in self.drones.items():
            if drone_info['websocket'] == websocket:
                drone_id = did
                break

        if topic == 'drone_connected':
            # Register new drone
            system = payload.get('system', 'unknown')
            component = payload.get('component', 'unknown')
            drone_id = f"drone_{system}_{component}"

            self.drones[drone_id] = {
                'websocket': websocket,
                'system': system,
                'component': component,
                'last_seen': time.time(),
                'info': payload
            }

            logger.info(f"{Colors.GREEN}🚁 Drone {drone_id} registered{Colors.NC}")

            # Broadcast to ground stations
            await self.broadcast_to_ground_stations("drone_connected", {
                "drone_id": drone_id,
                **payload
            })

        elif topic == 'telemetry':
            # Update drone telemetry and broadcast
            if drone_id:
                self.drones[drone_id]['last_seen'] = time.time()
                self.drones[drone_id]['telemetry'] = payload

                # Broadcast telemetry to ground stations
                await self.broadcast_to_ground_stations("telemetry", {
                    "drone_id": drone_id,
                    **payload
                })

                logger.debug(f"{Colors.BLUE}📊 Telemetry from {drone_id}{Colors.NC}")

        elif topic.endswith('_response'):
            # Command response from drone
            if drone_id:
                logger.info(f"{Colors.GREEN}📨 Response from {drone_id}: {topic}{Colors.NC}")

                # Forward response to ground stations
                await self.broadcast_to_ground_stations("command_response", {
                    "drone_id": drone_id,
                    "command": topic,
                    **payload
                })

    async def handle_ground_station_message(self, websocket, data: Dict[str, Any]):
        """Handle message from ground control station"""
        topic = data.get('topic', '')
        payload = data.get('payload', {})

        logger.info(f"{Colors.CYAN}📨 Ground control command: {topic}{Colors.NC}")

        if topic == 'list_drones':
            # Send list of connected drones
            drone_list = []
            for drone_id, drone_info in self.drones.items():
                drone_list.append({
                    "drone_id": drone_id,
                    "system": drone_info.get('system'),
                    "component": drone_info.get('component'),
                    "last_seen": drone_info.get('last_seen'),
                    "telemetry": drone_info.get('telemetry', {})
                })

            await websocket.send(json.dumps({
                "topic": "drone_list",
                "payload": {"drones": drone_list}
            }))

        elif topic.startswith('drone_'):
            # Command for specific drone
            drone_id = payload.get('drone_id')
            command = payload.get('command')
            command_payload = payload.get('payload', {})

            if drone_id and command:
                success = await self.send_to_drone(drone_id, command, command_payload)

                # Send acknowledgment to ground station
                await websocket.send(json.dumps({
                    "topic": "command_ack",
                    "payload": {
                        "drone_id": drone_id,
                        "command": command,
                        "success": success,
                        "timestamp": time.time()
                    }
                }))

    async def handle_client(self, websocket, path=""):
        """Handle individual client connection"""
        await self.register_client(websocket, "client")

        try:
            # Wait for initial message to determine client type
            initial_message = await websocket.recv()
            data = json.loads(initial_message)
            topic = data.get('topic', '')

            if topic == 'drone_connected':
                # This is a drone
                await self.register_client(websocket, "drone")
                await self.handle_drone_message(websocket, data)

                # Continue handling drone messages
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self.handle_drone_message(websocket, data)
                    except json.JSONDecodeError:
                        logger.error(f"{Colors.RED}❌ Invalid JSON from drone{Colors.NC}")
                    except Exception as e:
                        logger.error(f"{Colors.RED}❌ Error processing drone message: {e}{Colors.NC}")

            else:
                # This is a ground control station
                self.ground_stations.add(websocket)
                await self.register_client(websocket, "ground_station")

                # Handle the initial message
                await self.handle_ground_station_message(websocket, data)

                # Continue handling ground station messages
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self.handle_ground_station_message(websocket, data)
                    except json.JSONDecodeError:
                        logger.error(f"{Colors.RED}❌ Invalid JSON from ground station{Colors.NC}")
                    except Exception as e:
                        logger.error(f"{Colors.RED}❌ Error processing ground station message: {e}{Colors.NC}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"{Colors.YELLOW}⚠️  Client connection closed{Colors.NC}")
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Client error: {e}{Colors.NC}")
        finally:
            await self.unregister_client(websocket)

    async def status_monitor(self):
        """Monitor and display system status"""
        while True:
            try:
                await asyncio.sleep(10)  # Update every 10 seconds

                logger.info(f"{Colors.BLUE}📊 Status: {len(self.drones)} drones, {len(self.ground_stations)} ground stations{Colors.NC}")

                # Check for stale drones (no telemetry for 30 seconds)
                current_time = time.time()
                stale_drones = []
                for drone_id, drone_info in self.drones.items():
                    if current_time - drone_info.get('last_seen', 0) > 30:
                        stale_drones.append(drone_id)

                if stale_drones:
                    logger.warning(f"{Colors.YELLOW}⚠️  Stale drones (no telemetry): {', '.join(stale_drones)}{Colors.NC}")

            except Exception as e:
                logger.error(f"{Colors.RED}❌ Status monitor error: {e}{Colors.NC}")

    async def start_server(self):
        """Start the ground control server"""
        logger.info(f"{Colors.CYAN}🚀 Starting Ground Control WebSocket Server{Colors.NC}")
        logger.info(f"{Colors.BLUE}📡 Server listening on port {self.port}{Colors.NC}")
        logger.info(f"{Colors.BLUE}🔗 Drone URL: ws://localhost:{self.port}{Colors.NC}")
        logger.info(f"{Colors.YELLOW}⏳ Waiting for connections...{Colors.NC}")

        # Start status monitor
        monitor_task = asyncio.create_task(self.status_monitor())

        try:
            async with websockets.serve(self.handle_client, "localhost", self.port):
                await monitor_task
        except KeyboardInterrupt:
            logger.info(f"{Colors.YELLOW}🛑 Server stopping...{Colors.NC}")
            monitor_task.cancel()


def main():
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"{Colors.RED}❌ Invalid port number: {sys.argv[1]}{Colors.NC}")
            sys.exit(1)

    print(f"{Colors.CYAN}🔧 Ground Control WebSocket Server{Colors.NC}")
    print(f"{Colors.BLUE}📋 Usage: python3 ground_control_server.py [port]{Colors.NC}")
    print(f"{Colors.BLUE}📋 Default port: 8080{Colors.NC}")
    print()

    try:
        asyncio.run(GroundControlServer(port).start_server())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Server stopped by user{Colors.NC}")
    except Exception as e:
        logger.error(f"{Colors.RED}❌ Server error: {e}{Colors.NC}")

if __name__ == "__main__":
    main()

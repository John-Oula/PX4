#!/usr/bin/env python3
"""
PX4 SITL WebSocket Client
Drone acts as WebSocket client connecting to ground control server
Receives commands and sends telemetry via WebSocket in format {topic:xxx,payload:{xxx}}

Usage: python3 px4_websocket_client.py [websocket_url] [mavlink_connection]
"""

import asyncio
import websockets
import json
import sys
import time
import signal
from pymavlink import mavutil
from typing import Dict, Any, Optional
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


class PX4WebSocketClient:
    def __init__(self, websocket_url: str, mavlink_connection: str):
        self.websocket_url = websocket_url
        self.mavlink_connection = mavlink_connection
        self.websocket = None
        self.mavlink_conn = None
        self.target_system = 1
        self.target_component = 0
        self.running = False
        self.telemetry_interval = 1.0  # Send telemetry every second

    async def connect_mavlink(self):
        """Connect to PX4 via MAVLink"""
        try:
            logger.info(f"Connecting to PX4 via MAVLink: {self.mavlink_connection}")

            # Use asyncio to avoid blocking
            loop = asyncio.get_event_loop()
            self.mavlink_conn = await loop.run_in_executor(
                None, mavutil.mavlink_connection, self.mavlink_connection
            )

            # Wait for heartbeat
            await loop.run_in_executor(None, self.mavlink_conn.wait_heartbeat)

            self.target_system = self.mavlink_conn.target_system
            self.target_component = self.mavlink_conn.target_component

            logger.info(f"{Colors.GREEN}✅ Connected to PX4 - System: {self.target_system}, Component: {self.target_component}{Colors.NC}")
            return True
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Failed to connect to PX4: {e}{Colors.NC}")
            return False

    async def connect_websocket(self):
        """Connect to WebSocket server"""
        try:
            logger.info(f"Connecting to WebSocket server: {self.websocket_url}")
            self.websocket = await websockets.connect(self.websocket_url)
            logger.info(f"{Colors.GREEN}✅ Connected to WebSocket server{Colors.NC}")
            return True
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Failed to connect to WebSocket: {e}{Colors.NC}")
            return False

    async def send_message(self, topic: str, payload: Dict[str, Any]):
        """Send message to WebSocket server"""
        if not self.websocket:
            return

        message = {
            "topic": topic,
            "payload": payload
        }

        try:
            await self.websocket.send(json.dumps(message))
            logger.debug(f"{Colors.CYAN}📤 Sent: {topic}{Colors.NC}")
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Error sending message: {e}{Colors.NC}")

    async def handle_command(self, data: Dict[str, Any]):
        """Handle incoming command from WebSocket"""
        topic = data.get('topic', '')
        payload = data.get('payload', {})

        logger.info(f"{Colors.CYAN}📨 Received command: {topic} - {payload}{Colors.NC}")

        # Route to appropriate handler
        if topic == 'arm':
            await self._handle_arm(payload)
        elif topic == 'disarm':
            await self._handle_disarm(payload)
        elif topic == 'takeoff':
            await self._handle_takeoff(payload)
        elif topic == 'land':
            await self._handle_land(payload)
        elif topic == 'rtl':
            await self._handle_rtl(payload)
        elif topic == 'set_flight_mode':
            await self._handle_set_flight_mode(payload)
        elif topic == 'get_status':
            await self._handle_get_status(payload)
        elif topic == 'position_control':
            await self._handle_position_control(payload)
        elif topic == 'velocity_control':
            await self._handle_velocity_control(payload)
        else:
            logger.warning(f"{Colors.YELLOW}⚠️ Unknown command: {topic}{Colors.NC}")
            await self.send_response(topic, {"error": f"Unknown command: {topic}"}, success=False)

    async def send_response(self, command: str, payload: Dict[str, Any], success: bool = True):
        """Send command response"""
        response_payload = {
            "status": "success" if success else "error",
            "timestamp": time.time(),
            **payload
        }
        await self.send_message(f"{command}_response", response_payload)

    async def set_parameter(self, param_name: str, param_value, param_type=mavutil.mavlink.MAV_PARAM_TYPE_INT32):
        """Helper function to set PX4 parameters"""
        try:
            logger.info(f"{Colors.CYAN}📡 Setting parameter {param_name} = {param_value}{Colors.NC}")
            loop = asyncio.get_event_loop()

            # Send parameter set command
            await loop.run_in_executor(None,
                self.mavlink_conn.mav.param_set_send,
                self.target_system, self.target_component,
                param_name.encode('utf-8')[:16], param_value, param_type
            )

            # Wait for acknowledgment
            await asyncio.sleep(0.3)
            return True
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Failed to set parameter {param_name}: {e}{Colors.NC}")
            return False

    async def _handle_arm(self, payload: Dict[str, Any]):
        """Handle arm command with GPS bypass"""
        try:
            logger.info(f"{Colors.YELLOW}🔄 Arming vehicle (bypassing GPS checks)...{Colors.NC}")

            loop = asyncio.get_event_loop()

                                    # First, configure parameters to allow arming without strict checks
            logger.info(f"{Colors.CYAN}📡 Configuring arming bypass parameters...{Colors.NC}")

            # Set COM_ARM_WO_GPS to 1 to allow arming without GPS
            await self.set_parameter("COM_ARM_WO_GPS", 1)

            # Set CBRK_IO_SAFETY to 22027 to disable I/O safety circuit breaker (no safety switch)
            await self.set_parameter("CBRK_IO_SAFETY", 22027)

            # Disable GCS connection requirement for arming (allow autonomous operation)
            await self.set_parameter("COM_RC_IN_MODE", 1)  # RC input only, not GCS required

            # Wait a bit for EKF to initialize with available sensor data
            logger.info(f"{Colors.CYAN}⏳ Waiting for EKF initialization...{Colors.NC}")
            await asyncio.sleep(2.0)

            # Set a suitable flight mode for arming (STABILIZED mode)
            logger.info(f"{Colors.CYAN}🔄 Setting STABILIZED flight mode...{Colors.NC}")
            await loop.run_in_executor(None,
                self.mavlink_conn.mav.set_mode_send,
                self.target_system,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                131072  # STABILIZED mode for PX4
            )
            await asyncio.sleep(0.5)

            # Now attempt to arm with force flag
            logger.info(f"{Colors.YELLOW}🔄 Force arming vehicle...{Colors.NC}")
            await loop.run_in_executor(None,
                self.mavlink_conn.mav.command_long_send,
                self.target_system, self.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0, 1, 21196, 0, 0, 0, 0, 0  # param2=21196 is force arm magic number
            )

            ack = await loop.run_in_executor(None,
                self.mavlink_conn.recv_match, 'COMMAND_ACK', True, 5
            )

            if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                logger.info(f"{Colors.GREEN}✅ Vehicle armed successfully (GPS bypassed){Colors.NC}")
                await self.send_response("arm", {"message": "Vehicle armed successfully (GPS bypassed)"})
            else:
                # Provide detailed error information
                if ack:
                    result_codes = {
                        0: "ACCEPTED",
                        1: "TEMPORARILY_REJECTED",
                        2: "DENIED",
                        3: "UNSUPPORTED",
                        4: "FAILED",
                        5: "IN_PROGRESS"
                    }
                    result_name = result_codes.get(ack.result, f"UNKNOWN({ack.result})")
                    result_msg = f"Command result: {result_name} ({ack.result})"
                else:
                    result_msg = "No acknowledgment received (timeout)"

                logger.error(f"{Colors.RED}❌ Failed to arm vehicle - {result_msg}{Colors.NC}")
                logger.info(f"{Colors.YELLOW}💡 Check PX4 console for detailed preflight check failures{Colors.NC}")
                await self.send_response("arm", {"error": f"Failed to arm vehicle - {result_msg}"}, success=False)
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Error arming vehicle: {e}{Colors.NC}")
            await self.send_response("arm", {"error": str(e)}, success=False)

    async def _handle_disarm(self, payload: Dict[str, Any]):
        """Handle disarm command"""
        try:
            logger.info(f"{Colors.YELLOW}🔄 Disarming vehicle...{Colors.NC}")

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None,
                self.mavlink_conn.mav.command_long_send,
                self.target_system, self.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0, 0, 0, 0, 0, 0, 0, 0
            )

            ack = await loop.run_in_executor(None,
                self.mavlink_conn.recv_match, 'COMMAND_ACK', True, 5
            )

            if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                logger.info(f"{Colors.GREEN}✅ Vehicle disarmed successfully{Colors.NC}")
                await self.send_response("disarm", {"message": "Vehicle disarmed successfully"})
            else:
                logger.error(f"{Colors.RED}❌ Failed to disarm vehicle{Colors.NC}")
                await self.send_response("disarm", {"error": "Failed to disarm vehicle"}, success=False)
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Error disarming vehicle: {e}{Colors.NC}")
            await self.send_response("disarm", {"error": str(e)}, success=False)

    async def _handle_takeoff(self, payload: Dict[str, Any]):
        """Handle takeoff command"""
        try:
            altitude = payload.get('altitude', 10.0)
            logger.info(f"{Colors.YELLOW}🔄 Taking off to {altitude}m...{Colors.NC}")

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None,
                self.mavlink_conn.mav.command_long_send,
                self.target_system, self.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0, 0, 0, 0, 0, 0, 0, altitude
            )

            ack = await loop.run_in_executor(None,
                self.mavlink_conn.recv_match, 'COMMAND_ACK', True, 5
            )

            if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                logger.info(f"{Colors.GREEN}✅ Takeoff command sent successfully{Colors.NC}")
                await self.send_response("takeoff", {"message": f"Takeoff to {altitude}m initiated"})
            else:
                logger.error(f"{Colors.RED}❌ Failed to send takeoff command{Colors.NC}")
                await self.send_response("takeoff", {"error": "Failed to send takeoff command"}, success=False)
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Error sending takeoff command: {e}{Colors.NC}")
            await self.send_response("takeoff", {"error": str(e)}, success=False)

    async def _handle_land(self, payload: Dict[str, Any]):
        """Handle land command"""
        try:
            logger.info(f"{Colors.YELLOW}🔄 Landing...{Colors.NC}")

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None,
                self.mavlink_conn.mav.command_long_send,
                self.target_system, self.target_component,
                mavutil.mavlink.MAV_CMD_NAV_LAND,
                0, 0, 0, 0, 0, 0, 0, 0
            )

            ack = await loop.run_in_executor(None,
                self.mavlink_conn.recv_match, 'COMMAND_ACK', True, 5
            )

            if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                logger.info(f"{Colors.GREEN}✅ Land command sent successfully{Colors.NC}")
                await self.send_response("land", {"message": "Landing initiated"})
            else:
                logger.error(f"{Colors.RED}❌ Failed to send land command{Colors.NC}")
                await self.send_response("land", {"error": "Failed to send land command"}, success=False)
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Error sending land command: {e}{Colors.NC}")
            await self.send_response("land", {"error": str(e)}, success=False)

    async def _handle_rtl(self, payload: Dict[str, Any]):
        """Handle return to launch command"""
        try:
            logger.info(f"{Colors.YELLOW}🔄 Returning to launch...{Colors.NC}")

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None,
                self.mavlink_conn.mav.command_long_send,
                self.target_system, self.target_component,
                mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                0, 0, 0, 0, 0, 0, 0, 0
            )

            ack = await loop.run_in_executor(None,
                self.mavlink_conn.recv_match, 'COMMAND_ACK', True, 5
            )

            if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                logger.info(f"{Colors.GREEN}✅ RTL command sent successfully{Colors.NC}")
                await self.send_response("rtl", {"message": "Return to launch initiated"})
            else:
                logger.error(f"{Colors.RED}❌ Failed to send RTL command{Colors.NC}")
                await self.send_response("rtl", {"error": "Failed to send RTL command"}, success=False)
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Error sending RTL command: {e}{Colors.NC}")
            await self.send_response("rtl", {"error": str(e)}, success=False)

    async def _handle_set_flight_mode(self, payload: Dict[str, Any]):
        """Handle set flight mode command"""
        try:
            mode = payload.get('mode', '').upper()
            logger.info(f"{Colors.YELLOW}🔄 Setting flight mode to {mode}...{Colors.NC}")

            # PX4 mode mapping
            mode_mapping = {
                'MANUAL': 1,
                'STABILIZED': 2,
                'AUTO': 3,
                'RTL': 6,
                'LOITER': 5,
                'OFFBOARD': 6
            }

            if mode not in mode_mapping:
                raise ValueError(f"Unknown flight mode: {mode}")

            mode_id = mode_mapping[mode]

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None,
                self.mavlink_conn.mav.command_long_send,
                self.target_system, self.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                0, 1, mode_id, 0, 0, 0, 0, 0
            )

            ack = await loop.run_in_executor(None,
                self.mavlink_conn.recv_match, 'COMMAND_ACK', True, 5
            )

            if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                logger.info(f"{Colors.GREEN}✅ Flight mode set to {mode}{Colors.NC}")
                await self.send_response("set_flight_mode", {"message": f"Flight mode set to {mode}"})
            else:
                logger.error(f"{Colors.RED}❌ Failed to set flight mode{Colors.NC}")
                await self.send_response("set_flight_mode", {"error": "Failed to set flight mode"}, success=False)
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Error setting flight mode: {e}{Colors.NC}")
            await self.send_response("set_flight_mode", {"error": str(e)}, success=False)

    async def _handle_get_status(self, payload: Dict[str, Any]):
        """Handle get status command"""
        try:
            logger.info(f"{Colors.YELLOW}🔄 Getting vehicle status...{Colors.NC}")
            await self.send_telemetry()
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Error getting status: {e}{Colors.NC}")
            await self.send_response("get_status", {"error": str(e)}, success=False)

    async def _handle_position_control(self, payload: Dict[str, Any]):
        """Handle position control command"""
        try:
            lat = payload.get('latitude', 0.0)
            lon = payload.get('longitude', 0.0)
            alt = payload.get('altitude', 10.0)

            logger.info(f"{Colors.YELLOW}🔄 Moving to position: {lat}, {lon}, {alt}m{Colors.NC}")

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None,
                self.mavlink_conn.mav.command_long_send,
                self.target_system, self.target_component,
                mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                0, 0, 0, 0, 0, lat, lon, alt
            )

            await self.send_response("position_control", {"message": f"Moving to position: {lat}, {lon}, {alt}m"})
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Error in position control: {e}{Colors.NC}")
            await self.send_response("position_control", {"error": str(e)}, success=False)

    async def _handle_velocity_control(self, payload: Dict[str, Any]):
        """Handle velocity control command"""
        try:
            vx = payload.get('vx', 0.0)
            vy = payload.get('vy', 0.0)
            vz = payload.get('vz', 0.0)

            logger.info(f"{Colors.YELLOW}🔄 Setting velocity: vx={vx}, vy={vy}, vz={vz}{Colors.NC}")

            # Send SET_POSITION_TARGET_LOCAL_NED message for velocity control
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None,
                self.mavlink_conn.mav.set_position_target_local_ned_send,
                0,  # time_boot_ms
                self.target_system, self.target_component,
                mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                0b110111000111,  # type_mask (velocity control)
                0, 0, 0,  # x, y, z positions (ignored)
                vx, vy, vz,  # velocities
                0, 0, 0,  # accelerations (ignored)
                0, 0  # yaw, yaw_rate (ignored)
            )

            await self.send_response("velocity_control", {"message": f"Velocity set: vx={vx}, vy={vy}, vz={vz}"})
        except Exception as e:
            logger.error(f"{Colors.RED}❌ Error in velocity control: {e}{Colors.NC}")
            await self.send_response("velocity_control", {"error": str(e)}, success=False)

    async def send_telemetry(self):
        """Send telemetry data to ground control"""
        try:
            # Get vehicle status
            telemetry = {
                "timestamp": time.time(),
                "system": self.target_system,
                "component": self.target_component
            }

            loop = asyncio.get_event_loop()

            # Request data streams to ensure we get fresh data
            try:
                await loop.run_in_executor(None,
                    self.mavlink_conn.mav.request_data_stream_send,
                    self.target_system, self.target_component,
                    mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1
                )
            except:
                pass

            # Get multiple messages with timeout
            messages = {}
            message_types = ['HEARTBEAT', 'GPS_RAW_INT', 'ATTITUDE', 'SYS_STATUS', 'VFR_HUD', 'LOCAL_POSITION_NED']

            for msg_type in message_types:
                try:
                    msg = await loop.run_in_executor(None,
                        self.mavlink_conn.recv_match, msg_type, False, 0.1
                    )
                    if msg:
                        messages[msg_type] = msg
                except:
                    pass

            # Process heartbeat
            if 'HEARTBEAT' in messages:
                heartbeat = messages['HEARTBEAT']
                armed = bool(heartbeat.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                telemetry.update({
                    "armed": armed,
                    "mode": heartbeat.custom_mode,
                    "system_status": heartbeat.system_status,
                    "mavlink_version": heartbeat.mavlink_version
                })
            else:
                # Fallback: set basic values
                telemetry.update({
                    "armed": True,  # Assume armed for simulation
                    "mode": 1,
                    "system_status": 4  # MAV_STATE_ACTIVE
                })

            # Process GPS
            if 'GPS_RAW_INT' in messages:
                gps_msg = messages['GPS_RAW_INT']
                telemetry.update({
                    "latitude": gps_msg.lat / 1e7,
                    "longitude": gps_msg.lon / 1e7,
                    "altitude": gps_msg.alt / 1000.0,
                    "satellites": gps_msg.satellites_visible,
                    "gps_fix": gps_msg.fix_type,
                    "hdop": gps_msg.eph / 100.0,
                    "vdop": gps_msg.epv / 100.0
                })
            else:
                # Simulated GPS data for SITL
                telemetry.update({
                    "latitude": 47.3977506,
                    "longitude": 8.5456066,
                    "altitude": 488.0,
                    "satellites": 12,
                    "gps_fix": 3,
                    "hdop": 1.0,
                    "vdop": 1.0
                })

            # Process attitude
            if 'ATTITUDE' in messages:
                attitude_msg = messages['ATTITUDE']
                import math
                telemetry.update({
                    "roll": math.degrees(attitude_msg.roll),
                    "pitch": math.degrees(attitude_msg.pitch),
                    "yaw": math.degrees(attitude_msg.yaw),
                    "rollspeed": math.degrees(attitude_msg.rollspeed),
                    "pitchspeed": math.degrees(attitude_msg.pitchspeed),
                    "yawspeed": math.degrees(attitude_msg.yawspeed)
                })
            else:
                # Default attitude values
                telemetry.update({
                    "roll": 0.0,
                    "pitch": 0.0,
                    "yaw": 0.0,
                    "rollspeed": 0.0,
                    "pitchspeed": 0.0,
                    "yawspeed": 0.0
                })

            # Process battery/system status
            if 'SYS_STATUS' in messages:
                battery_msg = messages['SYS_STATUS']
                telemetry.update({
                    "battery_voltage": battery_msg.voltage_battery / 1000.0,
                    "battery_current": battery_msg.current_battery / 100.0,
                    "battery_remaining": battery_msg.battery_remaining,
                    "cpu_load": battery_msg.load / 10.0
                })
            else:
                # Simulated battery data
                telemetry.update({
                    "battery_voltage": 12.6,
                    "battery_current": 5.2,
                    "battery_remaining": 85,
                    "cpu_load": 15.0
                })

            # Process VFR_HUD for velocity and throttle
            if 'VFR_HUD' in messages:
                vfr_msg = messages['VFR_HUD']
                telemetry.update({
                    "groundspeed": vfr_msg.groundspeed,
                    "airspeed": vfr_msg.airspeed,
                    "climb_rate": vfr_msg.climb,
                    "throttle": vfr_msg.throttle
                })
            else:
                telemetry.update({
                    "groundspeed": 0.0,
                    "airspeed": 0.0,
                    "climb_rate": 0.0,
                    "throttle": 0
                })

            # Process local position
            if 'LOCAL_POSITION_NED' in messages:
                local_msg = messages['LOCAL_POSITION_NED']
                telemetry.update({
                    "local_x": local_msg.x,
                    "local_y": local_msg.y,
                    "local_z": local_msg.z,
                    "velocity_x": local_msg.vx,
                    "velocity_y": local_msg.vy,
                    "velocity_z": local_msg.vz
                })

            await self.send_message("telemetry", telemetry)
            logger.debug(f"{Colors.GREEN}📊 Telemetry sent - Armed: {telemetry.get('armed', 'N/A')}, Alt: {telemetry.get('altitude', 'N/A')}m{Colors.NC}")

        except Exception as e:
            logger.error(f"{Colors.RED}❌ Error sending telemetry: {e}{Colors.NC}")

    async def listen_websocket(self):
        """Listen for WebSocket messages from ground control"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.handle_command(data)
                except json.JSONDecodeError:
                    logger.error(f"{Colors.RED}❌ Invalid JSON received{Colors.NC}")
                except Exception as e:
                    logger.error(f"{Colors.RED}❌ Error processing message: {e}{Colors.NC}")
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"{Colors.YELLOW}⚠️ WebSocket connection closed{Colors.NC}")
        except Exception as e:
            logger.error(f"{Colors.RED}❌ WebSocket error: {e}{Colors.NC}")

    async def telemetry_loop(self):
        """Continuous telemetry sending loop"""
        while self.running:
            try:
                await self.send_telemetry()
                await asyncio.sleep(self.telemetry_interval)
            except Exception as e:
                logger.error(f"{Colors.RED}❌ Telemetry loop error: {e}{Colors.NC}")
                await asyncio.sleep(self.telemetry_interval)

    async def run(self):
        """Main run loop"""
        logger.info(f"{Colors.CYAN}🚀 Starting PX4 WebSocket Client{Colors.NC}")
        logger.info(f"{Colors.BLUE}🔗 WebSocket URL: {self.websocket_url}{Colors.NC}")
        logger.info(f"{Colors.BLUE}🔗 MAVLink connection: {self.mavlink_connection}{Colors.NC}")

        # Connect to PX4
        if not await self.connect_mavlink():
            return False

        # Connect to WebSocket
        retry_count = 0
        max_retries = 5
        while retry_count < max_retries:
            if await self.connect_websocket():
                break
            retry_count += 1
            logger.info(f"{Colors.YELLOW}⏳ Retrying WebSocket connection ({retry_count}/{max_retries})...{Colors.NC}")
            await asyncio.sleep(2)

        if not self.websocket:
            logger.error(f"{Colors.RED}❌ Failed to connect to WebSocket after {max_retries} attempts{Colors.NC}")
            return False

        self.running = True
        logger.info(f"{Colors.GREEN}✅ PX4 WebSocket Client ready!{Colors.NC}")
        logger.info(f"{Colors.CYAN}📡 Drone connected to ground control{Colors.NC}")

        # Send initial status
        await self.send_message("drone_connected", {
            "system": self.target_system,
            "component": self.target_component,
            "timestamp": time.time()
        })

        try:
            # Run both telemetry and command listening concurrently
            await asyncio.gather(
                self.listen_websocket(),
                self.telemetry_loop()
            )
        except KeyboardInterrupt:
            logger.info(f"{Colors.YELLOW}🛑 Interrupted by user{Colors.NC}")
        finally:
            self.running = False
            if self.websocket:
                await self.websocket.close()
            if self.mavlink_conn:
                self.mavlink_conn.close()
            logger.info(f"{Colors.GREEN}✅ Cleanup completed{Colors.NC}")

        return True


def main():
    """Main function"""
    websocket_url = "ws://localhost:8080"
    mavlink_connection = "udp:localhost:14550"

    if len(sys.argv) > 1:
        websocket_url = sys.argv[1]

    if len(sys.argv) > 2:
        mavlink_connection = sys.argv[2]

    print(f"{Colors.CYAN}🔧 PX4 WebSocket Client (Drone){Colors.NC}")
    print(f"{Colors.BLUE}📋 Usage: python3 px4_websocket_client.py [websocket_url] [mavlink_connection]{Colors.NC}")
    print(f"{Colors.BLUE}📋 Default: ws://localhost:8080, udp:localhost:14550{Colors.NC}")
    print()

    client = PX4WebSocketClient(websocket_url, mavlink_connection)

    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}🛑 Client stopped by user{Colors.NC}")
    except Exception as e:
        logger.error(f"{Colors.RED}❌ Client error: {e}{Colors.NC}")
        sys.exit(1)


if __name__ == "__main__":
    main()

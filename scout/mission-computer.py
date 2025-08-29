#!/usr/bin/env python3
"""
PX4 SITL Mission Computer - Position Setpoint Streamer using MAVSDK
Streams local position setpoints to PX4 SITL at 20Hz
"""

import asyncio
import time
from mavsdk import System
from mavsdk.offboard import PositionNedYaw, OffboardError

class MissionComputer:
    def __init__(self):
        self.drone = System()
        self.running = True
        self.armed = False

    async def connect(self):
        """Connect to PX4 SITL"""
        print("🔌 Connecting to PX4 SITL using MAVSDK...")
        print("📡 Using port 14540 (External Developer APIs)")

        await self.drone.connect(system_address="udp://:14540")

        print("⏳ Waiting for drone to connect...")
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                print("✅ Connected to PX4 SITL!")
                break

    async def setup_parameters(self):
        """Set up PX4 parameters for GPS-free operation"""
        print("🔧 Setting up PX4 parameters...")

        try:
            # Allow arming without GPS
            await self.drone.param.set_param_float("COM_ARM_WO_GPS", 1.0)
            print("📡 Set COM_ARM_WO_GPS = 1.0")

            # Disable safety switch
            await self.drone.param.set_param_float("CBRK_IO_SAFETY", 22027.0)
            print("📡 Set CBRK_IO_SAFETY = 22027.0")

            # Reduce GCS connection requirement
            await self.drone.param.set_param_float("COM_RC_IN_MODE", 1.0)
            print("📡 Set COM_RC_IN_MODE = 1.0")

            print("✅ Parameters configured")
        except Exception as e:
            print(f"⚠️ Warning: Could not set all parameters: {e}")

    async def arm_vehicle(self):
        """Arm the vehicle using MAVSDK"""
        print("🔓 Arming vehicle...")

        try:
            # Internal method call 1: Set takeoff altitude
            print("  └─ Calling: drone.action.set_takeoff_altitude(5.0)")
            await self.drone.action.set_takeoff_altitude(5.0)
            print("  └─ Result: Set takeoff altitude to 5m")

            # Internal method call 2: Arm the vehicle
            print("  └─ Calling: drone.action.arm()")
            await self.drone.action.arm()
            print("  └─ Result: Vehicle armed successfully!")

            # Internal method call 3: Wait for arming to complete
            print("  └─ Calling: asyncio.sleep(2)")
            await asyncio.sleep(2)

            # Internal method call 4: Verify armed status
            print("  └─ Calling: drone.telemetry.armed() - Verifying armed status...")
            async for is_armed in self.drone.telemetry.armed():
                if is_armed:
                    print("  └─ Result: Vehicle successfully armed!")
                    self.armed = True
                    return True
                else:
                    print("  └─ Result: Vehicle not armed yet...")
                    await asyncio.sleep(1)

        except Exception as e:
            print(f"❌ Failed to arm vehicle: {e}")
            return False

    async def start_offboard(self):
        """Start offboard control"""
        print("🎯 Starting offboard control...")

        try:
            # Internal method call 1: Set takeoff altitude
            print("  └─ Calling: drone.action.set_takeoff_altitude(5.0)")
            await self.drone.action.set_takeoff_altitude(5.0)
            print("  └─ Result: Set takeoff altitude to 5m")

            # Internal method call 2: Start offboard control
            print("  └─ Calling: drone.offboard.start()")
            await self.drone.offboard.start()
            print("  └─ Result: Offboard control started!")
            print("✅ Offboard control started!")
            return True
        except OffboardError as e:
            print(f"❌ Failed to start offboard control: {e}")
            return False

    async def send_position_setpoint(self, x, y, z, yaw):
        """Send position setpoint using MAVSDK"""
        try:
            # Internal method call 1: Create position object
            position = PositionNedYaw(x, y, z, yaw)

            # Internal method call 2: Send position setpoint
            await self.drone.offboard.set_position_ned(position)
        except Exception as e:
            print(f"❌ Failed to send position setpoint: {e}")

    async def fly_square_mission(self):
        """Fly a square mission pattern"""
        print("🚁 Starting square mission...")

        # Start streaming setpoints immediately
        rate = 20  # 20Hz
        interval = 1.0 / rate

        print(f"📡 Streaming position setpoints at {rate}Hz...")
        print("📍 Setpoint: x=0m, y=0m, z=-5m, yaw=0°")

        # MISSION SEQUENCE:
        print("\n" + "=" * 50)
        print("🎯 MISSION SEQUENCE - INTERNAL METHOD CALLS")
        print("=" * 50)

        # 1. Stream waypoints (position setpoints) for 5 seconds
        print("\n📡 METHOD CALL 1: send_position_setpoint() - Streaming waypoints for 5 seconds...")
        start_time = time.time()
        while self.running and (time.time() - start_time) < 5:
            try:
                # Send current position setpoint
                await self.send_position_setpoint(0, 0, -5, 0)
                await asyncio.sleep(interval)

            except Exception as e:
                print(f"❌ Error in setpoint stream: {e}")
                return

        # 2. Set to OFFBOARD mode
        print("\n🎯 METHOD CALL 2: start_offboard() - Setting to OFFBOARD mode...")
        offboard_started = await self.start_offboard()
        if not offboard_started:
            print("❌ Failed to start offboard control, stopping...")
            return

        # 3. Arm the vehicle
        print("\n🔓 METHOD CALL 3: arm_vehicle() - Arming vehicle...")
        armed = await self.arm_vehicle()
        if not armed:
            print("❌ Failed to arm vehicle, stopping...")
            return

        # Start takeoff sequence
        print("🚀 Starting takeoff sequence...")

        # Phase 1: Hover at ground level for 3 seconds
        print("📍 Phase 1: Hover at ground level...")
        ground_time = time.time()
        while self.running and (time.time() - ground_time) < 3:
            try:
                await self.send_position_setpoint(0, 0, 0, 0)  # Ground level
                await asyncio.sleep(interval)
            except Exception as e:
                print(f"❌ Error in setpoint stream: {e}")
                return

        # Phase 2: Takeoff to 5m altitude
        print("🛫 Phase 2: Taking off to 5m altitude...")
        takeoff_time = time.time()
        while self.running and (time.time() - takeoff_time) < 10:  # 10 seconds for takeoff
            try:
                # Gradually increase altitude
                progress = min((time.time() - takeoff_time) / 10.0, 1.0)
                target_z = -5.0 * progress  # From 0 to -5m

                await self.send_position_setpoint(0, 0, target_z, 0)
                await asyncio.sleep(interval)
            except Exception as e:
                print(f"❌ Error in setpoint stream: {e}")
                return

        # Phase 3: Square mission
        print("🔄 Phase 3: Flying square mission...")

        # Square waypoints (10m x 10m square)
        waypoints = [
            (0, 0, -5),      # Start position
            (10, 0, -5),     # Forward 10m
            (10, 10, -5),    # Right 10m
            (0, 10, -5),     # Backward 10m
            (0, 0, -5)       # Return to start
        ]

        for i, (x, y, z) in enumerate(waypoints):
            if not self.running:
                break

            print(f"📍 Waypoint {i+1}: x={x}m, y={y}m, z={z}m")

            # Fly to waypoint with smooth transition
            waypoint_time = time.time()
            while self.running and (time.time() - waypoint_time) < 2:  # 8 seconds per waypoint
                try:
                    await self.send_position_setpoint(x, y, z, 0)
                    await asyncio.sleep(interval)
                except Exception as e:
                    print(f"❌ Error in setpoint stream: {e}")
                    return

        # Phase 4: Return to hover
        print("🔄 Phase 4: Maintaining hover at center...")
        hover_time = time.time()
        while self.running and (time.time() - hover_time) < 5:  # 5 seconds hover
            try:
                # Send current position setpoint
                await self.send_position_setpoint(0, 0, -5, 0)
                await asyncio.sleep(interval)

            except Exception as e:
                print(f"❌ Error in setpoint stream: {e}")
                return

        # Phase 5: Landing sequence
        print("🛬 Phase 5: Starting landing sequence...")

        # Gradual descent to ground
        landing_time = time.time()
        while self.running and (time.time() - landing_time) < 10:  # 10 seconds for landing
            try:
                # Gradually decrease altitude
                progress = min((time.time() - landing_time) / 10.0, 1.0)
                target_z = -5.0 * (1.0 - progress)  # From -5m to 0m

                await self.send_position_setpoint(0, 0, target_z, 0)
                await asyncio.sleep(interval)
            except Exception as e:
                print(f"❌ Error in landing sequence: {e}")
                return

        # Phase 6: Ground hover and disarm
        print("📍 Phase 6: Ground hover and disarm...")
        ground_time = time.time()
        while self.running and (time.time() - ground_time) < 3:  # 3 seconds ground hover
            try:
                await self.send_position_setpoint(0, 0, 0, 0)  # Ground level
                await asyncio.sleep(interval)
            except Exception as e:
                print(f"❌ Error in ground hover: {e}")
                return

        # Disarm the vehicle
        print("🔒 Disarming vehicle...")
        try:
            await self.drone.action.disarm()
            print("✅ Vehicle disarmed successfully!")
        except Exception as e:
            print(f"❌ Failed to disarm vehicle: {e}")

        # Stop offboard control
        print("🛑 Stopping offboard control...")
        try:
            await self.drone.offboard.stop()
            print("✅ Offboard control stopped")
        except Exception as e:
            print(f"❌ Failed to stop offboard control: {e}")

        print("🏁 Mission completed successfully!")

    async def stream_position_setpoints(self):
        """Stream position setpoints at 20Hz"""
        print("🚁 Starting position setpoint stream at 20Hz...")

        # Start streaming setpoints immediately
        rate = 20  # 20Hz
        interval = 1.0 / rate

        print(f"📡 Streaming position setpoints at {rate}Hz...")
        print("📍 Setpoint: x=0m, y=0m, z=-5m, yaw=0°")

        # 1. Stream waypoints (position setpoints) for 5 seconds
        print("📡 Step 1: Streaming waypoints for 5 seconds...")
        start_time = time.time()
        while self.running and (time.time() - start_time) < 5:
            try:
                # Send current position setpoint
                await self.send_position_setpoint(0, 0, -5, 0)
                await asyncio.sleep(interval)

            except Exception as e:
                print(f"❌ Error in setpoint stream: {e}")
                return

        # 2. Set to OFFBOARD mode
        print("🎯 Step 2: Setting to OFFBOARD mode...")
        offboard_started = await self.start_offboard()
        if not offboard_started:
            print("❌ Failed to start offboard control, stopping...")
            return

        # 3. Arm the vehicle
        print("🔓 Step 3: Arming vehicle...")
        armed = await self.arm_vehicle()
        if not armed:
            print("❌ Failed to arm vehicle, stopping...")
            return

        # Start takeoff sequence
        print("🚀 Starting takeoff sequence...")

        # Phase 1: Hover at ground level for 3 seconds
        print("📍 Phase 1: Hover at ground level...")
        ground_time = time.time()
        while self.running and (time.time() - ground_time) < 3:
            try:
                await self.send_position_setpoint(0, 0, 0, 0)  # Ground level
                await asyncio.sleep(interval)
            except Exception as e:
                print(f"❌ Error in setpoint stream: {e}")
                return

        # Phase 2: Takeoff to 5m altitude
        print("🛫 Phase 2: Taking off to 5m altitude...")
        takeoff_time = time.time()
        while self.running and (time.time() - takeoff_time) < 10:  # 10 seconds for takeoff
            try:
                # Gradually increase altitude
                progress = min((time.time() - takeoff_time) / 10.0, 1.0)
                target_z = -5.0 * progress  # From 0 to -5m

                await self.send_position_setpoint(0, 0, target_z, 0)
                await asyncio.sleep(interval)
            except Exception as e:
                print(f"❌ Error in setpoint stream: {e}")
                return

        # Phase 3: Maintain hover at 5m
        print("🔄 Phase 3: Maintaining hover at 5m...")
        while self.running:
            try:
                # Send current position setpoint
                await self.send_position_setpoint(0, 0, -5, 0)
                await asyncio.sleep(interval)

            except Exception as e:
                print(f"❌ Error in setpoint stream: {e}")
                break

    async def monitor_status(self):
        """Monitor PX4 status and telemetry"""
        print("📊 Starting status monitoring...")

        async for armed in self.drone.telemetry.armed():
            if armed != self.armed:
                self.armed = armed
                status = "🟢 Armed" if armed else "🔴 Disarmed"
                print(f"💓 {status}")

    async def run(self):
        """Main execution - Sequential method calls"""
        try:
            print("=" * 60)
            print("🚀 MISSION COMPUTER - SEQUENTIAL EXECUTION")
            print("=" * 60)

            # Step 1: Connect to PX4
            print("\n📡 STEP 1: CONNECTING TO PX4")
            print("-" * 40)
            await self.connect()

            # Step 2: Set up parameters
            print("\n🔧 STEP 2: SETTING UP PARAMETERS")
            print("-" * 40)
            await self.setup_parameters()

            # Step 3: Start monitoring in background
            print("\n📊 STEP 3: STARTING STATUS MONITORING")
            print("-" * 40)
            monitor_task = asyncio.create_task(self.monitor_status())

            # Step 4: Execute mission
            print("\n🎯 STEP 4: EXECUTING MISSION")
            print("-" * 40)
            print("🚀 Starting square mission...")
            await self.fly_square_mission()

        except KeyboardInterrupt:
            print("\n🛑 Mission computer shutting down...")
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            self.running = False
            try:
                await self.drone.offboard.stop()
                print("🛑 Offboard control stopped")
            except:
                pass

if __name__ == "__main__":
    computer = MissionComputer()
    asyncio.run(computer.run())

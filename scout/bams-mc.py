#!/usr/bin/env python3
"""
BAMS Mission Computer - Simplified Version
Follows correct sequence: Stream waypoints -> Set OFFBOARD -> Arm
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

            # Internal method call 2: Set initial position setpoint BEFORE starting offboard
            print("  └─ Calling: drone.offboard.set_position_ned() - Setting initial setpoint")
            initial_position = PositionNedYaw(0, 0, -5, 0)
            await self.drone.offboard.set_position_ned(initial_position)
            print("  └─ Result: Initial position setpoint set")

            # Internal method call 3: Start offboard control
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
            print("🛑 This error will cause offboard control to stop!")
            raise e  # Re-raise to handle in calling function

    async def execute_arming_sequence(self):
        """Execute the correct arming sequence"""
        print("🚁 Starting arming sequence...")

        # Start streaming setpoints immediately
        rate = 20  # 20Hz
        interval = 1.0 / rate

        print(f"📡 Streaming position setpoints at {rate}Hz...")
        print("📍 Setpoint: x=0m, y=0m, z=-5m, yaw=0°")

        # CORRECT SEQUENCE:
        print("\n" + "=" * 50)
        print("🎯 CORRECT SEQUENCE - INTERNAL METHOD CALLS")
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

        # Success - vehicle is armed and ready
        print("\n✅ SUCCESS: Vehicle is armed and ready!")
        print("🎯 Flight mode: OFFBOARD")
        print("🔓 Status: Armed")

        # Keep streaming setpoints continuously to maintain offboard control
        print("\n📡 Maintaining continuous position setpoint stream...")
        print("⚠️  IMPORTANT: Offboard control requires continuous setpoint streaming!")
        print("⚠️  Stopping setpoints will cause offboard control to stop!")

        try:
            while self.running:
                try:
                    # Send position setpoint continuously
                    await self.send_position_setpoint(0, 0, -5, 0)
                    await asyncio.sleep(interval)
                except Exception as e:
                    print(f"❌ Error in setpoint stream: {e}")
                    print("🛑 Offboard control stopped due to error!")
                    break
        except KeyboardInterrupt:
            print("\n🛑 User interrupted - stopping setpoint stream...")

        print("🏁 Arming sequence completed!")

    async def check_offboard_status(self):
        """Check if offboard control is still active"""
        try:
            # Try to send a test setpoint to see if offboard is still working
            await self.send_position_setpoint(0, 0, -5, 0)
            print("✅ Offboard control is still active")
            return True
        except Exception as e:
            print(f"❌ Offboard control has stopped: {e}")
            return False

    async def monitor_status(self):
        """Monitor PX4 status and telemetry"""
        print("📊 Starting status monitoring...")

        try:
            async for armed in self.drone.telemetry.armed():
                if armed != self.armed:
                    self.armed = armed
                    status = "🟢 Armed" if armed else "🔴 Disarmed"
                    print(f"💓 {status}")

                    # If vehicle disarms unexpectedly, warn about offboard control
                    if not armed and self.running:
                        print("⚠️  WARNING: Vehicle disarmed unexpectedly!")
                        print("⚠️  This may cause offboard control to stop!")
        except Exception as e:
            print(f"❌ Error in status monitoring: {e}")

    async def run(self):
        """Main execution - Sequential method calls"""
        try:
            print("=" * 60)
            print("🚀 BAMS MISSION COMPUTER - SEQUENTIAL EXECUTION")
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

            # Step 4: Execute arming sequence
            print("\n🎯 STEP 4: EXECUTING ARMING SEQUENCE")
            print("-" * 40)
            await self.execute_arming_sequence()

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

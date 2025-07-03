#!/bin/bash

# Start Gazebo first
gz sim empty.sdf &
sleep 15

# Vehicle 9, Task 1 → start_point: [122, 404]
PX4_SYS_AUTOSTART=4001 PX4_HOME_LAT=40.708120437956204 PX4_HOME_LON=-74.00693333333334 PX4_HOME_ALT=0  PX4_SIM_MODEL=gz_x500 PX4_GZ_MODEL_POSE="122,404,0.1,0,0,0" ./build/px4_sitl_default/bin/px4 -i 9

# Vehicle 10, Task 7 → start_point: [122, 404] (same pose as above)
PX4_SYS_AUTOSTART=4001 PX4_HOME_LAT=40.708120437956204 PX4_HOME_LON=-74.00693333333334 PX4_HOME_ALT=0   PX4_SIM_MODEL=gz_x500 PX4_GZ_MODEL_POSE="122,404,0.1,0,0,0" ./build/px4_sitl_default/bin/px4 -i 10

# Vehicle 6, Task 8 → start_point: [54, 478]
PX4_SYS_AUTOSTART=4001 PX4_HOME_LAT=40.71163138686131 PX4_HOME_LON=-74.01146666666666 PX4_HOME_ALT=0   PX4_SIM_MODEL=gz_x500 PX4_GZ_MODEL_POSE="54,478,0.1,0,0,0" ./build/px4_sitl_default/bin/px4 -i 6

# Vehicle 3, Task 5 → start_point: [18, 393]
PX4_SYS_AUTOSTART=4001 PX4_HOME_LAT=40.70759854014599 PX4_HOME_LON=-74.01386666666667 PX4_HOME_ALT=0  PX4_SIM_MODEL=gz_x500  PX4_GZ_MODEL_POSE="0,0,0.1,0,0,0" ./build/px4_sitl_default/bin/px4 -i 3


echo "All vehicles launched. Connect QGC to:"
echo "Vehicle 3: UDP port 18570"
echo "Vehicle 6: UDP port 18573"
echo "Vehicle 9: UDP port 18576"
echo "Vehicle 10: UDP port 18579"

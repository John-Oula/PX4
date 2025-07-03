function
planFile = createSingleMissionPlan(mission)
%Create
a
single
mission
plan
for one mission using realworld_path coordinates
defaultAlt = 95; %convlength(300, 'ft', 'm');

%QGC
mission
plan
base
structure
planFile = struct();
planFile.fileType = 'Plan';
planFile.geoFence = struct('circles', [], 'polygons', [], 'version', 2);
planFile.rallyPoints = struct('points', [], 'version', 2);
planFile.version = 1;
planFile.groundStation = "QGroundControl";

%Mission
items(waypoints)
items = {};
seq = 0;

%Get
real - world
coordinates
from mission (already in lat / lon
format)
path = mission.path_info.realworld_path;

if isempty(path)
    error('Mission realworld_path is empty or not available');
end

%Calculate
home
position
coordinates
from first waypoint

home_coords = path(1,:);

%realworld_path
format is [longitude, latitude]
based
on
the
data
lon_home = home_coords(1); %Longitude
lat_home = home_coords(2); %Latitude

%Validate
coordinates
if lat_home < -90 | | lat_home > 90
    error('Invalid home latitude: %f. Must be between -90 and 90 degrees', lat_home);
end
if lon_home < -180 | | lon_home > 180
    error('Invalid home longitude: %f. Must be between -180 and 180 degrees', lon_home);
end

%Use
default
altitude
for home position
    alt_home = 0; %Ground
    level
    for home

%Add
takeoff
command as first
item
takeoff_alt = defaultAlt; %Takeoff
altitude
items
{end + 1} = struct(...
'AMSLAltAboveTerrain', 0, ...
'Altitude', takeoff_alt, ...
'AltitudeMode', 1, ...
'autoContinue', true, ...
'command', 22, ... % MAV_CMD_NAV_TAKEOFF
'doJumpId', seq, ...
'frame', 3, ... % MAV_FRAME_GLOBAL_RELATIVE_ALT
'params', [0, 0, 0, 0, lat_home, lon_home, takeoff_alt], ... % [pitch, empty, empty, yaw, lat, lon, alt]
'type', 'SimpleItem'...
);
seq = seq + 1;

%Determine
which
waypoints
to
use
based
on
path
length
%For
delivery
missions, we
typically
want: start, key
intermediate
points, and end
if size(path, 1) <= 5
    %For
    short
    paths, use
    all
    waypoints
    waypoints_to_use = 1:size(path, 1);
else
    %For
    longer
    paths, use
    start, end, and evenly
    spaced
    intermediate
    points
    num_intermediate = min(3, size(path, 1) - 2); %Max
    3
    intermediate
    points
    if num_intermediate > 0
        intermediate_indices = round(linspace(2, size(path, 1) - 1, num_intermediate));
        waypoints_to_use = [1, intermediate_indices, size(path, 1)];
    else
        waypoints_to_use = [1, size(path, 1)]; %Just
        start and end
    end
end

%Remove
duplicates and sort
waypoints_to_use = unique(waypoints_to_use);

for idx = 1:length(waypoints_to_use)
j = waypoints_to_use(idx);
wp = path(j,:); %Get
the
selected
waypoint

%Extract
coordinates(realworld_path
format: [longitude, latitude])
if size(wp, 2) >= 2
    lon = wp(1); %Longitude
    lat = wp(2); %Latitude
else
    error('Real-world coordinates require at least 2 values per waypoint');
end

%Validate
lat / lon
ranges
if lat < -90 | | lat > 90
    error('Invalid latitude: %f. Must be between -90 and 90 degrees', lat);
end
if lon < -180 | | lon > 180
    error('Invalid longitude: %f. Must be between -180 and 180 degrees', lon);
end

%Calculate
expected
time
at
this
waypoint
based
on
mission
timing
waypoint_progress = (idx - 1) / (length(waypoints_to_use) - 1);
expected_time = mission.timing.task_start_time + waypoint_progress * mission.timing.delivery_time;

%Use
default
altitude(could
be
extended
to
use
3
rd
coordinate if available)
if size(wp, 2) >= 3
    alt = wp(3);
else
    alt = defaultAlt; %Default
    altitude in meters
end

%Waypoint
behavior
parameters
hold_time = 0; %Seconds
to
loiter
at
waypoint(0 = fly
through)
accept_radius = 5; %Meters - acceptance
radius(how
close
to
get)
pass_radius = 0; %Meters -
pass
radius(0 = use
acceptance
radius)
yaw_angle = 0; %Degrees - desired
heading(0 = don
't care)

% Create
waypoint
item
with timing information
%params format: [hold_time, accept_radius, pass_radius, yaw_angle, latitude, longitude, altitude]
waypoint_item = struct(...
'AMSLAltAboveTerrain', 0, ...
'Altitude', alt, ...
'AltitudeMode', 1, ...
'autoContinue', true, ...
'command', 16, ... % MAV_CMD_NAV_WAYPOINT
'doJumpId', seq, ...
'frame', 3, ... % MAV_FRAME_GLOBAL_RELATIVE_ALT
'params', [hold_time, accept_radius, pass_radius, yaw_angle, lat, lon, alt], ...
'type', 'SimpleItem'...
);

%Add
custom
timing
metadata(QGC
will
ignore
these, but
useful
for analysis)
waypoint_item.mission_metadata = struct(...
'task_id', mission.task_id, ...
'vehicle_id', mission.vehicle_id, ...
'expected_time', expected_time, ...
'start_time', mission.timing.task_start_time, ...
'waypoint_index', j, ...%Original path index
'selected_waypoint_index', idx, ...%Index in selected waypoints
'is_start_point', j == 1, ...
'is_end_point', j == size(path, 1), ...
'original_coords', wp, ...
'total_path_waypoints', size(path, 1), ...
'selected_waypoints_count', length(waypoints_to_use)...
);

items{end+1} = waypoint_item;
seq = seq + 1;
end

%Add
return to
launch
command
% rtl_alt = 0; %RTL
altitude(0 = use
default)
%items
{end + 1} = struct(...
                   % 'AMSLAltAboveTerrain', 0, ...
                   % 'Altitude', rtl_alt, ...
                   % 'AltitudeMode', 1, ...
                   % 'autoContinue', true, ...
                   % 'command', 20, ... % MAV_CMD_NAV_RETURN_TO_LAUNCH
                   % 'doJumpId', seq, ...
                   % 'frame', 3, ...
                   % 'params', [0, 0, 0, 0, 0, 0, rtl_alt], ... % [empty, empty, empty, empty, empty, empty, alt]
                   % 'type', 'SimpleItem'...
                   %);
%
%Pack
into
final
structure
missionPlan = struct();
missionPlan.cruiseSpeed = 15;
missionPlan.firmwareType = 12; %PX4
missionPlan.hoverSpeed = 5;
missionPlan.items = items;

%Set
home
position
using
the
calculated
coordinates
missionPlan.plannedHomePosition = [lat_home, lon_home, alt_home];
missionPlan.vehicleType = 2; %Multi - rotor(2), Fixed - wing(1), VTOL(19)
missionPlan.version = 2;

planFile.mission = missionPlan;

%Add
custom
timing
metadata
to
the
plan
file(
for analysis purposes)
planFile.metadata = struct(...
'task_id', mission.task_id, ...
'vehicle_id', mission.vehicle_id, ...
'task_start_time', mission.timing.task_start_time, ...
'task_complete_time', mission.timing.task_complete_time, ...
'vehicle_return_time', mission.timing.vehicle_return_time, ...
'vehicle_available_time', mission.timing.vehicle_available_time, ...
'delivery_time', mission.timing.delivery_time, ...
'maintenance_time', mission.timing.maintenance_time, ...
'coordinate_system', 'real_world_latlon', ...
'generation_time', datestr(now), ...
'start_point', mission.path_info.start_point, ...
'end_point', mission.path_info.end_point, ...
'number_of_waypoints', mission.path_info.num_waypoints, ...
'path_source', 'realworld_path'...
);
end

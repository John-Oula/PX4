function task2Mission(jsonInput, outputFolder)
% Convert JSON input to separate QGC mission plan files for each mission
% Now uses realworld_path coordinates directly from the JSON structure
%
% Inputs:
% jsonInput - JSON file path or struct containing mission data
% outputFolder - Output folder for .plan files (optional, default: 'missions')
%
% Examples:
% task2Mission('data.json', 'mission_plans')
% task2Mission('data.json') % Uses default 'missions' folder

% Set default parameters
if nargin < 2 || isempty(outputFolder)
    outputFolder = 'missions';
end

% Create output folder if it doesn't exist
if ~exist(outputFolder, 'dir')
    mkdir(outputFolder);
    fprintf('Created output folder: %s\n', outputFolder);
end

% Read and parse JSON input
if ischar(jsonInput) || isstring(jsonInput)
    jsonText = fileread(jsonInput); % Read file content
    data = jsondecode(jsonText); % Convert JSON string to struct
else
    data = jsonInput; % Already a struct
end

% Validate JSON structure
if ~isfield(data, 'missions') || isempty(data.missions)
    error('JSON input must contain a "missions" field with mission data');
end

% Process each mission separately
completed_missions = 0;
failed_missions = 0;
skipped_missions = 0;

% Handle different JSON parsing results
missions_data = data.missions;
if iscell(missions_data)
    % MATLAB parsed as cell array
    num_missions = length(missions_data);
    fprintf('Processing %d missions (cell array format)...\n', num_missions);
else
    % MATLAB parsed as struct array
    num_missions = length(missions_data);
    fprintf('Processing %d missions (struct array format)...\n', num_missions);
end

for i = 1:num_missions
    % Extract mission based on data type
    if iscell(missions_data)
        mission = missions_data{i}; % Cell array indexing
    else
        mission = missions_data(i); % Struct array indexing
    end

    % Check if mission has required fields
    if ~isfield(mission, 'task_id') || ~isfield(mission, 'vehicle_id')
        fprintf('Skipping mission %d: Missing task_id or vehicle_id\n', i);
        % Debug info for first few missions
        if i <= 3
            fprintf('  Available fields: %s\n', strjoin(fieldnames(mission)', ', '));
        end
        skipped_missions = skipped_missions + 1;
        continue;
    end

    % Check if mission has path_info and realworld_path
    if ~isfield(mission, 'path_info') || ~isfield(mission.path_info, 'realworld_path')
        fprintf('Skipping mission T%d: Missing path_info.realworld_path\n', mission.task_id);
        skipped_missions = skipped_missions + 1;
        continue;
    end

    % Check if realworld_path is empty
    if isempty(mission.path_info.realworld_path)
        fprintf('Skipping mission T%d: Empty realworld_path\n', mission.task_id);
        skipped_missions = skipped_missions + 1;
        continue;
    end

    % Check if mission has timing information
    if ~isfield(mission, 'timing')
        fprintf('Skipping mission T%d: Missing timing information\n', mission.task_id);
        skipped_missions = skipped_missions + 1;
        continue;
    end

    % Check if vehicle_id is null (failed missions)
    if isempty(mission.vehicle_id) || (isnumeric(mission.vehicle_id) && isnan(mission.vehicle_id))
        fprintf('Skipping mission T%d: No vehicle assigned (failed mission)\n', mission.task_id);
        failed_missions = failed_missions + 1;
        continue;
    end

    % Create individual mission plan
    try
        planFile = createSingleMissionPlan(mission);

        % Generate filename
        outputFilename = fullfile(outputFolder, sprintf('mission_T%d_UAV%d.plan', ...
                                                      mission.task_id, mission.vehicle_id));

        % Write to file
        jsonText = jsonencode(planFile, 'PrettyPrint', true);
        fid = fopen(outputFilename, 'w');
        if fid == -1
            error('Could not open file %s for writing', outputFilename);
        end
        fprintf(fid, '%s', jsonText);
        fclose(fid);

        completed_missions = completed_missions + 1;
        fprintf('Created: %s\n', outputFilename);

    catch ME
        fprintf('Error creating plan for mission T%d: %s\n', mission.task_id, ME.message);
        failed_missions = failed_missions + 1;
    end
end

% Summary
fprintf('\n=== Mission Plan Generation Summary ===\n');
fprintf('Total missions in JSON: %d\n', num_missions);
fprintf('Successfully created: %d plan files\n', completed_missions);
fprintf('Failed missions: %d\n', failed_missions);
fprintf('Skipped missions: %d\n', skipped_missions);
fprintf('Output folder: %s\n', outputFolder);
fprintf('Coordinate system: Real-world lat/lon (from realworld_path)\n');

% List created files
if completed_missions > 0
    fprintf('\nCreated mission plan files:\n');
    planFiles = dir(fullfile(outputFolder, '*.plan'));
    for j = 1:length(planFiles)
        fprintf('  %s\n', planFiles(j).name);
    end
end

if failed_missions > 0 || skipped_missions > 0
    fprintf('\nNote: %d missions were skipped/failed. Check console output for details.\n', ...
            failed_missions + skipped_missions);
end
end

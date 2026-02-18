% =========================================================================
% SIMULINK WRAPPER WITH SET_CONFIG SUPPORT
% =========================================================================
% This file contains two functions that should be compiled together:
%   1. set_config(configJson) - Store configuration before running
%   2. simulink_wrapper(inputMatrix) - Run simulation with stored config
%
% Usage from Python:
%   client = quixmatlab.initialize()
%   client.set_config('{"gain": 1.5, "offset": 0}')
%   output = client.simulink_wrapper(inputMatrix)
% =========================================================================


function set_config(configJson)
    % SET_CONFIG Store configuration for subsequent simulink_wrapper calls
    %
    % This function should be called before simulink_wrapper() to set
    % simulation parameters. The config is stored in a temp file that
    % simulink_wrapper reads.
    %
    % Input:
    %   configJson - JSON string containing configuration parameters
    %
    % Config can contain:
    %   - model_name: name of the Simulink model (default: simulink_model_example)
    %   - parameters: struct of model workspace variables to set

    config_file = fullfile(tempdir, 'quixmatlab_config.mat');

    if nargin < 1 || isempty(configJson)
        config = struct();
    else
        try
            config = jsondecode(configJson);
            fprintf("Config parsed: %d fields\n", numel(fieldnames(config)));
        catch ME
            fprintf("Warning: Failed to parse config JSON: %s\n", ME.message);
            config = struct();
        end
    end

    % Save to temp file for simulink_wrapper to read
    save(config_file, 'config');
    fprintf("Config saved to %s\n", config_file);
end


function config = get_stored_config()
    % GET_STORED_CONFIG Retrieve configuration from temp file
    %
    % Returns empty struct if no config has been set.

    config_file = fullfile(tempdir, 'quixmatlab_config.mat');

    if exist(config_file, 'file') == 2
        data = load(config_file, 'config');
        config = data.config;
    else
        config = struct();
    end
end


function outputMatrix = simulink_wrapper(inputMatrix)
    % SIMULINK_WRAPPER Runs a Simulink model with configurable parameters
    %
    % This wrapper receives input data from Python/Kafka and runs the
    % simulation, returning the output matrix.
    %
    % Configuration should be set beforehand via set_config().
    %
    % Inputs:
    %   inputMatrix - Matrix of input data [time, signal1, signal2, ..., signalN]
    %
    % Outputs:
    %   outputMatrix - Matrix of output data from the simulation

    % Default model name (can be overridden via config)
    mdl = "simulink_model_example";

    %---------------------------------------------------------------
    % 1. Get configuration (set via set_config)
    %---------------------------------------------------------------
    config = get_stored_config();

    % Check if config specifies a different model
    if isfield(config, 'model_name') && ~isempty(config.model_name)
        mdl = config.model_name;
    end

    % Extract parameters sub-struct if present
    if isfield(config, 'parameters')
        params = config.parameters;
    else
        params = config;
    end

    % Print first config received (for debugging)
    persistent config_printed
    if isempty(config_printed)
        config_printed = true;
        fprintf("Model: %s\n", mdl);
        fprintf("Config:\n");
        disp(config);
    end

    %---------------------------------------------------------------
    % 2. Extract time and input signals from input matrix
    %    Assumes inputMatrix = [time, signal1, signal2, ..., signalN]
    %---------------------------------------------------------------
    if size(inputMatrix, 2) < 2
        error('Input matrix must have at least 2 columns (time + 1 signal)');
    end

    t = inputMatrix(:,1);         % Time vector
    u = inputMatrix(:,2:end);     % Signal values
    n_signals = size(u,2);        % Number of input signals

    fprintf("Input: %d time steps, %d signals\n", length(t), n_signals);

    %---------------------------------------------------------------
    % 3. Build Dataset object for Simulink inputs
    %    Timeseries order must match Inport order in the Simulink model
    %---------------------------------------------------------------
    inports = Simulink.SimulationData.Dataset;
    for i = 1:n_signals
        signal = timeseries(u(:,i), t);
        inports = inports.addElement(signal);
    end

    %------------------------------------------------------------------
    % 4. Configure SimulationInput object (efficient for repeated calls)
    %------------------------------------------------------------------
    persistent s0_loaded s0_model

    % Recompile if model changed
    if isempty(s0_loaded) || ~strcmp(s0_model, mdl)
        fprintf("Compiling model: %s...\n", mdl);
        s0 = Simulink.SimulationInput(mdl);

        % Configure for deployment (Rapid Accelerator + safe options)
        s0 = simulink.compiler.configureForDeployment(s0);

        s0_loaded = s0;
        s0_model = mdl;
        fprintf("Model compiled successfully\n");
    end

    % Clone and update external inputs for this specific run
    s = s0_loaded.setExternalInput(inports);

    % Set simulation stop time based on last time sample
    s = s.setModelParameter("StopTime", num2str(t(end)));

    %------------------------------------------------------------------
    % 5. Apply configuration parameters as model variables
    %------------------------------------------------------------------
    if isstruct(params)
        paramFields = fieldnames(params);
        for i = 1:numel(paramFields)
            paramName = paramFields{i};
            paramValue = params.(paramName);

            % Handle nested structs (like saturation.min, saturation.max)
            if isstruct(paramValue)
                nestedFields = fieldnames(paramValue);
                for j = 1:numel(nestedFields)
                    nestedName = nestedFields{j};
                    fullName = [paramName '_' nestedName];
                    try
                        s = s.setVariable(fullName, paramValue.(nestedName));
                    catch ME
                        fprintf("Warning: Failed to set nested variable '%s': %s\n", fullName, ME.message);
                    end
                end
            else
                try
                    s = s.setVariable(paramName, paramValue);
                catch ME
                    fprintf("Warning: Failed to set variable '%s': %s\n", paramName, ME.message);
                end
            end
        end
    end

    %------------------------------------------------------------------
    % 6. Run the simulation
    %------------------------------------------------------------------
    fprintf("Running simulation...\n");
    out = sim(s);

    % Debug output (first run only)
    persistent sim_printed
    if isempty(sim_printed)
        sim_printed = true;
        fprintf("Simulation output:\n");
        disp(out);
    end

    yout = out.yout;

    %---------------------------------------------------------------
    % 7. Extract output signal values into matrix
    %---------------------------------------------------------------
    if isa(yout, 'Simulink.SimulationData.Dataset')
        n_outputs = yout.numElements;
        outputMatrix = [];
        for i = 1:n_outputs
            data = yout{i}.Values.Data;
            outputMatrix = [outputMatrix, data];
        end

    elseif isnumeric(yout)
        outputMatrix = yout;

    elseif isstruct(yout)
        n_outputs = numel(yout.signals);
        outputMatrix = [];
        for i = 1:n_outputs
            data = yout.signals(i).values;
            outputMatrix = [outputMatrix, data];
        end
    else
        error('Unexpected yout type: %s', class(yout));
    end

    fprintf("Output: %d rows x %d columns\n", size(outputMatrix, 1), size(outputMatrix, 2));

    % Debug first output
    persistent output_printed
    if isempty(output_printed)
        output_printed = true;
        fprintf("First output matrix (first 5 rows):\n");
        disp(outputMatrix(1:min(5, size(outputMatrix,1)), :));
    end

end

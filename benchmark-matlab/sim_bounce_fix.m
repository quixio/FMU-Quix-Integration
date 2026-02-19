% =========================================================================
% sim_bounce.m — Fixed version with configureForDeployment
% =========================================================================
% This is the corrected sim_bounce function that works in deployed
% (compiled) mode. The original was missing the critical call to
% simulink.compiler.configureForDeployment().
%
% To recompile the wheel:
%   1. Replace the original sim_bounce.m with this file
%   2. Recompile with MATLAB Compiler SDK:
%      compiler.build.pythonPackage('sim_bounce.m', ...
%          'PackageName', 'quixmatlab', ...
%          'SupportPackages', {'Simulink Compiler'})
%   3. Rebuild the wheel and update the Docker image
% =========================================================================

function [tout, xout, vout] = sim_bounce(g_acc, init_vel, init_pos, k_rest)
    % SIM_BOUNCE Run sldemo_bounce_mod with configurable parameters
    %
    % Inputs:
    %   g_acc    - Gravitational acceleration (default: -9.81)
    %   init_vel - Initial velocity (default: 15.0)
    %   init_pos - Initial position (default: 10.0)
    %   k_rest   - Coefficient of restitution (default: 0.8)
    %
    % Outputs:
    %   tout - Time vector
    %   xout - Position (ball height)
    %   vout - Velocity

    mdl = 'sldemo_bounce_mod';

    %---------------------------------------------------------------
    % 1. Create and CONFIGURE SimulationInput for deployment
    %    This is the critical step that was missing in the original.
    %---------------------------------------------------------------
    persistent s0_cached
    if isempty(s0_cached)
        fprintf("Compiling model: %s...\n", mdl);
        s0 = Simulink.SimulationInput(mdl);

        % THIS IS THE FIX — configureForDeployment sets Rapid Accelerator
        % mode and other options required for compiled/deployed execution.
        s0 = simulink.compiler.configureForDeployment(s0);

        s0_cached = s0;
        fprintf("Model compiled for deployment.\n");
    end

    %---------------------------------------------------------------
    % 2. Set tunable parameters
    %---------------------------------------------------------------
    simIn = s0_cached;
    simIn = simIn.setVariable('g_acc', g_acc);
    simIn = simIn.setVariable('init_vel', init_vel);
    simIn = simIn.setVariable('init_pos', init_pos);
    simIn = simIn.setVariable('k_rest', k_rest);

    %---------------------------------------------------------------
    % 3. Run simulation
    %---------------------------------------------------------------
    out = sim(simIn);

    %---------------------------------------------------------------
    % 4. Extract results
    %    In Rapid Accelerator mode, out.tout does NOT exist.
    %    Time and data must be read from the signal Dataset.
    %---------------------------------------------------------------
    if isprop(out, 'yout') && isa(out.yout, 'Simulink.SimulationData.Dataset')
        ds = out.yout;
        tout = ds{1}.Values.Time;
        xout = ds{1}.Values.Data;
        if ds.numElements >= 2
            vout = ds{2}.Values.Data;
        else
            vout = zeros(size(tout));
        end
    elseif isprop(out, 'tout')
        tout = out.tout;
        xout = out.xout;
        vout = zeros(size(tout));
    else
        error('sim_bounce: could not extract results from SimulationOutput');
    end
end

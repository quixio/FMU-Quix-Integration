"""
Simulink Runner - Processes simulation requests from Kafka

Receives simulation payloads from the HTTP API containing:
- model: Base64-encoded wheel file (.whl) with compiled Simulink model
- config: JSON configuration parameters for the simulation
- threshold: Float threshold value for the simulation
- input_data: Array of input data rows from CSV

Dynamically loads the wheel, runs the Simulink model, and adds results to input data.
Threshold checking is handled by a downstream service.
"""

from quixstreams import Application
import numpy as np
import os
import sys
import json
import base64
import subprocess
import importlib
import hashlib
import requests
from datetime import datetime, timezone
from pathlib import Path

# API configuration for fetching models
API_URL = os.environ.get("API_URL", "http://localhost:80")
HTTP_AUTH_TOKEN = os.environ.get("HTTP_AUTH_TOKEN", "")

# Cache for loaded wheel modules: {wheel_hash: quixmatlab_client}
_wheel_cache = {}

# Directory for installed wheels - use state directory if available (persists across restarts)
STATE_DIR = Path(os.environ.get("state_dir", "state"))
WHEEL_INSTALL_DIR = STATE_DIR / "wheels"
WHEEL_INSTALL_DIR.mkdir(parents=True, exist_ok=True)


def get_wheel_hash(wheel_data: str) -> str:
    """Generate a hash for the wheel data to use as cache key."""
    return hashlib.sha256(wheel_data.encode()).hexdigest()[:16]


def fetch_model_from_api(filename: str) -> bytes:
    """
    Fetch a model binary from the HTTP API.

    Args:
        filename: The model filename to fetch

    Returns:
        bytes: The model binary data

    Raises:
        RuntimeError: If the model cannot be fetched
    """
    url = f"{API_URL}/models/{filename}"
    headers = {"Authorization": f"Bearer {HTTP_AUTH_TOKEN}"}

    print(f"Fetching model from API: {url}")

    try:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        print(f"Fetched model: {filename} ({len(response.content)} bytes)")
        return response.content
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch model from API: {e}")


def install_wheel(wheel_data: str, wheel_filename: str) -> Path:
    """
    Install a wheel from base64-encoded data.

    Args:
        wheel_data: Base64-encoded wheel file content
        wheel_filename: Original filename of the wheel

    Returns:
        Path: Path to the installed wheel
    """
    wheel_hash = get_wheel_hash(wheel_data)
    wheel_dir = WHEEL_INSTALL_DIR / wheel_hash

    # Check if already installed
    if wheel_dir.exists():
        print(f"Wheel already installed at {wheel_dir}")
        return wheel_dir

    # Create directory for this wheel
    wheel_dir.mkdir(exist_ok=True)

    # Decode and save wheel file
    wheel_path = wheel_dir / wheel_filename
    wheel_bytes = base64.b64decode(wheel_data)
    wheel_path.write_bytes(wheel_bytes)
    print(f"Saved wheel to {wheel_path}")

    # Install wheel to the wheel directory
    install_target = wheel_dir / "installed"
    install_target.mkdir(exist_ok=True)

    print(f"Installing wheel to {install_target}...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install",
         "--target", str(install_target),
         "--no-deps",  # Don't install dependencies (they should be in the container)
         str(wheel_path)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"pip install stdout: {result.stdout}")
        print(f"pip install stderr: {result.stderr}")
        raise RuntimeError(f"Failed to install wheel: {result.stderr}")

    print(f"Wheel installed successfully")
    return wheel_dir


def load_quixmatlab(wheel_dir: Path):
    """
    Dynamically load quixmatlab from an installed wheel.

    Args:
        wheel_dir: Directory containing the installed wheel

    Returns:
        Initialized quixmatlab client
    """
    install_path = wheel_dir / "installed"

    # Add to sys.path if not already there
    install_path_str = str(install_path)
    if install_path_str not in sys.path:
        sys.path.insert(0, install_path_str)

    # Remove any previously loaded quixmatlab module
    modules_to_remove = [k for k in sys.modules.keys() if k.startswith('quixmatlab')]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Import and initialize
    import quixmatlab
    importlib.reload(quixmatlab)

    client = quixmatlab.initialize()
    print(f"Loaded quixmatlab from {install_path}")
    print(f"Exported functions: {dir(client)}")

    return client


def get_or_load_wheel(model_filename: str, model_data: str = "") -> tuple:
    """
    Get a cached quixmatlab client or load from the wheel.

    If model_data (base64) is provided, use that directly.
    Otherwise, fetch the model binary from the API using model_filename.

    Args:
        model_filename: The model filename
        model_data: Optional base64-encoded wheel data

    Returns:
        tuple: (quixmatlab_client, supports_config)
    """
    wheel_data = model_data
    wheel_filename = model_filename or "quixmatlab.whl"

    # If no data in payload, fetch from API
    if not wheel_data:
        if not wheel_filename:
            print("No model data or filename provided")
            return None, False

        try:
            wheel_bytes = fetch_model_from_api(wheel_filename)
            wheel_data = base64.b64encode(wheel_bytes).decode('utf-8')
        except RuntimeError as e:
            print(f"Failed to fetch model: {e}")
            return None, False

    # Check cache
    wheel_hash = get_wheel_hash(wheel_data)
    if wheel_hash in _wheel_cache:
        print(f"Using cached wheel: {wheel_hash}")
        return _wheel_cache[wheel_hash]

    # Install and load
    try:
        wheel_dir = install_wheel(wheel_data, wheel_filename)
        client = load_quixmatlab(wheel_dir)

        # Check if simulink_wrapper exists
        # We'll try with config first at runtime, fall back to without if it fails
        wrapper_func = getattr(client, 'simulink_wrapper', None)
        supports_config = wrapper_func is not None

        _wheel_cache[wheel_hash] = (client, supports_config)
        return client, supports_config

    except Exception as e:
        print(f"Failed to load wheel: {e}")
        return None, False


def prepare_config_json(config_data: dict) -> str:
    """
    Prepare config data as a JSON string to pass to MATLAB.

    Args:
        config_data: Configuration dictionary from the API payload

    Returns:
        str: Valid JSON string to pass to MATLAB wrapper
    """
    if config_data is None:
        return json.dumps({})

    if isinstance(config_data, dict):
        return json.dumps(config_data)

    if isinstance(config_data, str):
        if not config_data.strip():
            return json.dumps({})
        try:
            json.loads(config_data)
            return config_data
        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in config field: {e}. Using empty config.")
            return json.dumps({})

    print(f"Warning: Unexpected config type: {type(config_data)}. Using empty config.")
    return json.dumps({})


def csv_data_to_matrix(input_data: list, time_column: str = None) -> tuple[np.ndarray, list]:
    """
    Convert CSV input data (array of dicts) to numpy matrix for MATLAB.

    The matrix format expected by simulink_wrapper is [time, signal1, signal2, ..., signalN]
    If no time column is specified, a synthetic time column is added (0, 1, 2, ...).

    Args:
        input_data: List of dictionaries from CSV rows
        time_column: Optional name of the time column

    Returns:
        tuple: (numpy matrix, list of column names excluding time)
    """
    if not input_data:
        return np.array([[0, 0]]), []

    # Get column names from first row
    columns = list(input_data[0].keys())

    # Auto-detect time column if not specified
    if not time_column:
        for col in columns:
            if col.lower() == 'time':
                time_column = col
                break

    # Extract values as floats
    n_rows = len(input_data)
    n_cols = len(columns)

    # Create data matrix
    data = np.zeros((n_rows, n_cols))
    for i, row in enumerate(input_data):
        for j, col in enumerate(columns):
            try:
                data[i, j] = float(row.get(col, 0))
            except (ValueError, TypeError):
                data[i, j] = 0.0

    # Use detected/specified time column or add synthetic one
    if time_column and time_column in columns:
        # Move time column to first position
        time_idx = columns.index(time_column)
        time_col = data[:, time_idx:time_idx+1]
        other_cols = np.delete(data, time_idx, axis=1)
        other_col_names = [c for c in columns if c != time_column]
        print(f"Using '{time_column}' as time column")
        return np.hstack([time_col, other_cols]), other_col_names
    else:
        # Add synthetic time column (0, 1, 2, ...)
        print("No time column found, adding synthetic time (0, 1, 2, ...)")
        time_col = np.arange(n_rows).reshape(-1, 1)
        return np.hstack([time_col, data]), columns


def add_results_to_input_data(input_data: list, output_matrix: np.ndarray) -> list:
    """
    Add simulation output columns to the original input data rows.

    Args:
        input_data: Original list of dictionaries from CSV
        output_matrix: Simulation output matrix from MATLAB

    Returns:
        list: Input data with output columns added to each row
    """
    if not input_data:
        return []

    # Ensure output_matrix is 2D
    if len(output_matrix.shape) == 1:
        output_matrix = output_matrix.reshape(-1, 1)

    n_outputs = output_matrix.shape[1]

    # Create enriched data with original input + simulation outputs
    enriched_data = []
    for i, row in enumerate(input_data):
        # Copy original row
        enriched_row = dict(row)

        # Add output columns
        if i < len(output_matrix):
            for j in range(n_outputs):
                enriched_row[f"output_{j+1}"] = float(output_matrix[i, j])

        enriched_data.append(enriched_row)

    return enriched_data


def set_config_if_available(client, config_json: str) -> bool:
    """
    Set config via set_config() if the function exists.

    Args:
        client: quixmatlab client
        config_json: JSON config string

    Returns:
        bool: True if config was set, False if set_config not available
    """
    set_config_func = getattr(client, 'set_config', None)
    if set_config_func and callable(set_config_func):
        try:
            client.set_config(config_json)
            print(f"Config set via set_config()")
            return True
        except Exception as e:
            print(f"Warning: set_config() failed: {e}")
            return False
    return False


def convert_matlab_to_numpy(matlab_output) -> np.ndarray:
    """
    Convert MATLAB output to numpy array.

    MATLAB Compiler SDK returns matlab.double objects, not numpy arrays.

    Args:
        matlab_output: Output from MATLAB function (matlab.double or similar)

    Returns:
        np.ndarray: Converted numpy array
    """
    # If already numpy array, return as-is
    if isinstance(matlab_output, np.ndarray):
        return matlab_output

    # Convert matlab.double or similar to numpy
    try:
        # matlab.double can be converted via np.array()
        arr = np.array(matlab_output)
        print(f"Converted MATLAB output to numpy array: {arr.shape}")
        return arr
    except Exception as e:
        print(f"Warning: Failed to convert MATLAB output: {e}")
        # Try to extract data as list first
        try:
            arr = np.array(list(matlab_output))
            return arr
        except:
            raise ValueError(f"Cannot convert MATLAB output type {type(matlab_output)} to numpy")


def probe_function_exists(client, func_name: str) -> bool:
    """
    Test if a MATLAB function actually exists by trying to call it.

    MATLAB SDK uses __getattr__ so hasattr() always returns True.
    We need to actually try calling the function to see if it exists.
    """
    try:
        func = getattr(client, func_name)
        # Try calling with no args - will fail, but error tells us if function exists
        func(nargout=0)
        return True  # Unlikely to reach here
    except SystemError as e:
        error_msg = str(e).lower()
        if 'not found' in error_msg:
            return False
        # Other errors mean function exists but wrong args
        return True
    except TypeError:
        # Wrong arguments = function exists
        return True
    except Exception:
        # Assume exists if unknown error
        return True


def discover_simulation_function(client) -> tuple:
    """
    Discover which simulation function is available in the wheel.

    Returns:
        tuple: (function_name, function_type) where function_type is:
               - 'wrapper': simulink_wrapper(input_matrix) style
               - 'direct': sim_bounce(g, v0, x0, k, nargout=N) style
               - None if no function found
    """
    # Common function names to check (in priority order)
    wrapper_functions = ['simulink_wrapper', 'run_simulation', 'simulate']
    direct_functions = ['sim_bounce', 'bouncing_ball', 'run_model']

    # Check for wrapper-style functions first
    for func_name in wrapper_functions:
        if probe_function_exists(client, func_name):
            print(f"Found wrapper function: {func_name}")
            return (func_name, 'wrapper')

    # Check for direct-parameter style functions
    for func_name in direct_functions:
        if probe_function_exists(client, func_name):
            print(f"Found direct function: {func_name}")
            return (func_name, 'direct')

    # Last resort: scan dir() for non-standard functions
    excluded = {'initialize', 'terminate', 'set_config', 'get_config', 'exit', 'quit',
                'name', 'wait_for_figures_to_close', '__init__', '__doc__', '__module__'}
    for name in dir(client):
        if name.startswith('_') or name in excluded:
            continue
        if probe_function_exists(client, name):
            print(f"Found function via scan: {name}")
            return (name, 'direct')

    return (None, None)


def call_direct_function(client, func_name: str, config: dict) -> dict:
    """
    Call a direct-parameter style function like sim_bounce(g, v0, x0, k).

    Args:
        client: quixmatlab client
        func_name: Name of the function to call
        config: Configuration dict with parameters

    Returns:
        dict: Results with 'time' and other output arrays
    """
    func = getattr(client, func_name)

    # Extract parameters from config (handle nested 'parameters' key)
    params = config.get('parameters', config) if isinstance(config, dict) else {}

    print(f"Calling {func_name} with params: {list(params.keys())}")

    # Try to call with different nargout values (common: 1-5 outputs)
    # Start with likely values based on typical simulation outputs
    for nargout in [3, 2, 1, 4, 5]:
        try:
            # Pass parameters as keyword arguments
            result = func(**params, nargout=nargout)

            # Handle single vs multiple return values
            if nargout == 1:
                result = (result,)

            # Convert all outputs to numpy arrays
            outputs = []
            for i, arr in enumerate(result):
                np_arr = convert_matlab_to_numpy(arr).flatten()
                outputs.append(np_arr)

            print(f"Function returned {len(outputs)} outputs with nargout={nargout}")

            # Return as dict with generic names (or specific if we can detect)
            result_dict = {}
            output_names = ['time', 'position', 'velocity', 'output_4', 'output_5']
            for i, arr in enumerate(outputs):
                name = output_names[i] if i < len(output_names) else f'output_{i+1}'
                result_dict[name] = arr

            return result_dict

        except TypeError as e:
            error_str = str(e).lower()
            # Wrong nargout, try next
            if 'nargout' in error_str or 'argument' in error_str:
                continue
            # Missing required parameter - try positional args
            if 'missing' in error_str or 'required' in error_str:
                break
            raise

    # Fallback: try positional arguments from config values
    print(f"Trying positional arguments...")
    param_values = list(params.values())

    for nargout in [3, 2, 1, 4, 5]:
        try:
            result = func(*param_values, nargout=nargout)

            if nargout == 1:
                result = (result,)

            outputs = [convert_matlab_to_numpy(arr).flatten() for arr in result]
            print(f"Function returned {len(outputs)} outputs (positional args)")

            result_dict = {}
            output_names = ['time', 'position', 'velocity', 'output_4', 'output_5']
            for i, arr in enumerate(outputs):
                name = output_names[i] if i < len(output_names) else f'output_{i+1}'
                result_dict[name] = arr

            return result_dict

        except TypeError:
            continue

    raise RuntimeError(f"Could not call {func_name} with provided config")


def call_simulink_wrapper(client, input_matrix: np.ndarray, config_json: str):
    """
    Call simulink_wrapper after setting config.

    First tries to set config via set_config(), then calls simulink_wrapper().
    Falls back to passing config directly if set_config not available.

    Args:
        client: quixmatlab client
        input_matrix: Input data matrix
        config_json: JSON config string

    Returns:
        np.ndarray: Output matrix from simulation
    """
    # Try set_config approach first (preferred)
    config_set = set_config_if_available(client, config_json)

    if config_set:
        # Config was set via set_config, call wrapper without config arg
        output = client.simulink_wrapper(input_matrix)
        return convert_matlab_to_numpy(output)

    # Fallback: try passing config directly to simulink_wrapper
    try:
        output = client.simulink_wrapper(input_matrix, config_json)
        return convert_matlab_to_numpy(output)
    except (TypeError, Exception) as e:
        error_msg = str(e).lower()
        # If it fails due to wrong number of arguments, try without config
        if any(phrase in error_msg for phrase in [
            "positional argument", "takes", "too many input arguments",
            "too many arguments", "input arguments"
        ]):
            print(f"Wrapper doesn't accept config ({e}), calling without config...")
            output = client.simulink_wrapper(input_matrix)
            return convert_matlab_to_numpy(output)
        raise


def build_output_from_direct_results(results: dict) -> list:
    """
    Build output data from direct function results (time series).

    Args:
        results: Dict with 'time', 'position', 'velocity', etc. arrays

    Returns:
        list: List of dicts, one per time step
    """
    time_arr = results.get('time', np.array([0]))
    output_data = []

    for i in range(len(time_arr)):
        row = {'time': float(time_arr[i])}
        for key, arr in results.items():
            if key != 'time' and i < len(arr):
                row[key] = float(arr[i])
        output_data.append(row)

    return output_data


def run_simulation(payload: dict) -> dict:
    """
    Run Simulink simulation with the provided payload.

    Supports two patterns:
    1. simulink_wrapper(input_matrix) - processes CSV input data
    2. direct functions like sim_bounce(g, v0, x0, k) - generates time series

    Args:
        payload: Simulation payload containing model, config, threshold, input_data

    Returns:
        dict: Original payload with enriched input_data containing simulation results
    """
    message_key = payload.get("message_key", "unknown")
    submitted_at = payload.get("submitted_at", datetime.now(timezone.utc).isoformat())

    # Extract simulation parameters
    model_filename = payload.get("model_filename", "")
    model_data = payload.get("model_data", "")
    config = payload.get("config", {})
    threshold = payload.get("threshold", 0.0)
    input_data = payload.get("input_data", [])
    source = payload.get("source", "unknown")

    print(f"\n{'='*60}")
    print(f"Processing simulation: {message_key}")
    print(f"  Model: {model_filename or 'N/A'}")
    print(f"  Config keys: {list(config.keys()) if config else 'None'}")
    print(f"  Threshold: {threshold}")
    print(f"  Input rows: {len(input_data)}")
    print(f"{'='*60}")

    # Prepare config JSON
    config_json = prepare_config_json(config)

    # Run simulation
    started_at = datetime.now(timezone.utc)
    status = "completed"
    error_message = None
    enriched_data = []

    # Try to load wheel from payload
    quixmatlab_client, _ = get_or_load_wheel(model_filename, model_data)

    if quixmatlab_client:
        # Discover which function pattern this wheel uses
        func_name, func_type = discover_simulation_function(quixmatlab_client)
        print(f"Detected function: {func_name} (type: {func_type})")

        try:
            if func_type == 'wrapper':
                # Pattern 1: simulink_wrapper with input matrix
                input_matrix, input_columns = csv_data_to_matrix(input_data)
                print(f"Input matrix shape: {input_matrix.shape}")
                print(f"Input columns: {input_columns}")

                output_matrix = call_simulink_wrapper(quixmatlab_client, input_matrix, config_json)
                print(f"Simulation completed. Output shape: {output_matrix.shape}")

                # Add results to input data
                enriched_data = add_results_to_input_data(input_data, output_matrix)

            elif func_type == 'direct':
                # Pattern 2: Direct function with config parameters (like sim_bounce)
                results = call_direct_function(quixmatlab_client, func_name, config)
                print(f"Simulation completed. Output keys: {list(results.keys())}")

                # Build output data from time series results
                enriched_data = build_output_from_direct_results(results)
                print(f"Generated {len(enriched_data)} output rows")

            else:
                raise RuntimeError(f"No simulation function found in wheel")

        except Exception as e:
            print(f"Simulation error: {e}")
            import traceback
            traceback.print_exc()
            status = "error"
            error_message = str(e)
            enriched_data = input_data  # Return original data on error
    else:
        # Mock mode - no wheel provided or failed to load
        print("Running in mock mode (no wheel loaded)")
        status = "completed_mock"

        if input_data:
            # Convert input data and generate mock output
            input_matrix, _ = csv_data_to_matrix(input_data)
            output_matrix = np.sum(input_matrix[:, 1:], axis=1, keepdims=True) * 1.5
            enriched_data = add_results_to_input_data(input_data, output_matrix)
        else:
            # Generate mock time series if no input data
            enriched_data = [
                {"time": float(i) * 0.1, "output_1": float(i) * 1.5}
                for i in range(10)
            ]

    completed_at = datetime.now(timezone.utc)

    # Build output payload - pass through all original fields plus results
    return {
        "message_key": message_key,
        "submitted_at": submitted_at,
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
        "processing_time_ms": (completed_at - started_at).total_seconds() * 1000,
        "model_filename": model_filename,
        "config": config,
        "threshold": threshold,
        "source": source,
        "status": status,
        "error_message": error_message,
        "input_data": enriched_data,  # Original data + output columns OR generated time series
    }


def process_message(row: dict) -> dict:
    """
    Process a single Kafka message (simulation request).

    Args:
        row: Message payload from Kafka

    Returns:
        dict: Payload with simulation results added to input_data
    """
    return run_simulation(row)


def main():
    """Main entry point for the Simulink runner."""

    print("="*60)
    print("Simulink Runner Starting (Dynamic Wheel Loading)")
    print(f"Wheel install directory: {WHEEL_INSTALL_DIR}")
    print(f"Model API URL: {API_URL}")
    print("="*60)

    # Setup Quix Streams application
    app = Application(
        consumer_group="simulink-runner",
        auto_create_topics=True,
        auto_offset_reset="earliest"
    )

    # Get topic names from environment
    input_topic_name = os.environ.get("input", "simulation")
    output_topic_name = os.environ.get("output", "simulation-results")

    print(f"Input topic: {input_topic_name}")
    print(f"Output topic: {output_topic_name}")

    input_topic = app.topic(name=input_topic_name)
    output_topic = app.topic(name=output_topic_name)

    # Create streaming dataframe
    sdf = app.dataframe(topic=input_topic)

    # Print incoming messages
    # sdf.print_table()

    # Process each message through Simulink
    sdf = sdf.apply(process_message)

    # Print results
    # sdf.print_table()

    # Write results to output topic
    sdf.to_topic(output_topic)

    # Run the application
    print("Starting Kafka consumer...")
    app.run()


if __name__ == "__main__":
    main()

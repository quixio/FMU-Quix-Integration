# Simulink Runner

Processes simulation requests from Kafka and runs Simulink models using MATLAB Runtime.

## Overview

This service:
1. Reads simulation requests from the `simulation` Kafka topic (published by the HTTP API)
2. Processes the request through a compiled Simulink model
3. Publishes results to the `simulation-results` topic

## Input Payload Format

The service expects messages from the HTTP API with this structure:

```json
{
  "message_key": "2024-02-02T12:30:00_model-name.slx",
  "submitted_at": "2024-02-02T12:30:00Z",
  "model": {
    "filename": "model-name.whl"
  },
  "input_data": [
    {"input_a": 12.5, "input_b": 8.3, "input_c": 45.2},
    {"input_a": 7.1, "input_b": 22.9, "input_c": 18.6}
  ],
  "config": {
    "parameters": {
      "gain": 1.5,
      "offset": 0,
      "damping_factor": 0.7
    }
  },
  "threshold": 50.0,
  "source": "user"
}
```

## Output Format

Results are published with the original payload plus simulation outputs added to each input_data row:

```json
{
  "message_key": "2024-02-02T12:30:00_model-name.slx",
  "submitted_at": "2024-02-02T12:30:00Z",
  "started_at": "2024-02-02T12:30:01Z",
  "completed_at": "2024-02-02T12:30:02Z",
  "processing_time_ms": 1234.5,
  "model": {
    "filename": "model-name.whl"
  },
  "config": {...},
  "threshold": 50.0,
  "source": "user",
  "status": "completed",
  "error_message": null,
  "input_data": [
    {"input_a": 12.5, "input_b": 8.3, "input_c": 45.2, "output_1": 99.0, "output_2": 15.3},
    {"input_a": 7.1, "input_b": 22.9, "input_c": 18.6, "output_1": 72.9, "output_2": 12.1}
  ]
}
```

The `input_data` array now contains the original input values plus `output_N` columns from the simulation.
Threshold checking is handled by a downstream service.

## Building the MATLAB Wheel

The Simulink model must be compiled into a Python wheel using MATLAB Compiler SDK.

### Prerequisites
- MATLAB R2024b with Simulink
- MATLAB Compiler SDK
- Simulink Compiler

### Compilation Steps

1. Open MATLAB and navigate to `aux-files/`
2. Place your Simulink model (`.slx`) in the same directory
3. Update `simulink_wrapper.m` if needed to reference your model name
4. Run the compiler:

```matlab
cd aux-files
quix_compiler('simulink_wrapper', 'build_output')
```

5. Copy the generated `.whl` file to the `simulink-runner/` directory
6. Update `requirements.txt` to include the wheel:

```
./quixmatlab_r2024b-24.2-py3-none-any.whl
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `input` | Kafka topic for simulation requests | `simulation` |
| `output` | Kafka topic for simulation results | `simulation-results` |

## Docker Build

```bash
docker build -t simulink-runner .
```

## Mock Mode

If the `quixmatlab` wheel is not available, the service runs in mock mode, applying a simple transformation to the input data for testing purposes.

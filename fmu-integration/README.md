# FMU Integration

This sample shows how to execute an FMU using `fmpy` inside a Quix Streams application. It consumes messages from an input topic, runs the FMU for each message, and publishes enriched results to an output topic.

## What `main.py` does

At a glance, `main.py`:

- Prints basic metadata about the FMU (FMI version and model variables) so you can verify inputs/outputs at startup.
- Defines `FMU_processing(row)` which:
  - Reads fields `x`, `y` from the incoming message and uses a fixed angle `theta` (π/4) as an example parameter.
  - Builds a structured NumPy array with columns `time`, `x`, `y`, `theta` and calls `fmpy.simulate_fmu` for a single point in time (`start_time=0.0`, `stop_time=0.0`).
  - Parses the simulation result and writes `x_new` and `y_new` back into the message (mapped from FMU outputs `Out1` and `Out2`).
- Sets up a Quix Streams `Application`, reads from the `input` topic into a StreamingDataFrame, applies `FMU_processing` to each row, prints the table, and writes the result to the `output` topic.

> Important: The `simulate_fmu` call as provided is a minimal example. For time‑based simulations you will typically use a non‑zero `stop_time` and possibly a time series in the `input` array.

## Prerequisites

- A valid `.fmu` file accessible to the app. The repo includes `simulink_example_inports.fmu` in this folder as an example.
- Python dependencies from `requirements.txt` installed.
- Access to a Quix environment (or compatible Kafka broker) for streaming.

## Configure the FMU file

Edit the filename near the top of `main.py` if you are using a different model or path:

```python
fmu_filename = "simulink_example_inports.fmu"
```

When the app starts, it prints the FMU model variables with their `valueReference` and `causality` so you know which variables are inputs and outputs.

## Environment variables

The code sample uses the following environment variables:

- **input**: Name of the input topic to listen to.
- **output**: Name of the output topic to write to.

## Contribute

Submit forked projects to the Quix [GitHub](https://github.com/quixio/quix-samples) repo. Any new project that we accept will be attributed to you and you'll receive $200 in Quix credit.

## Open source

This project is open source under the Apache 2.0 license and available in our [GitHub](https://github.com/quixio/quix-samples) repo.

Please star us and mention us on social to show your appreciation.
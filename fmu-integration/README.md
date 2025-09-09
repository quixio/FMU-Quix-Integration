# FMU Integration

This sample demonstrates how to run an FMU within a Quix application. It consumes messages from an input topic, executes the FMU for each message, and publishes the enriched results to an output topic.

## How to use this sample

1. **Add a valid `.fmu` file** to the app.  
   - The FMU should be compiled for Linux to run it on Quix.  
   - The repository includes `simulink_example_inports.fmu` in this folder as an example.

2. **Set the FMU filename** in `main.py`:

```python
fmu_filename = "simulink_example_inports.fmu"

3. **Start the app.**  
   - It prints the FMU model variables along with their `valueReference` and `causality`, so you can identify which variables are inputs and which are outputs.

4. **Define the `FMU_processing` function** according to your model’s inputs and outputs.

## Environment variables

The code sample uses the following environment variables:

- **input**: Name of the input topic to listen to.
- **output**: Name of the output topic to write to.

## Contribute

Submit forked projects to the Quix [GitHub](https://github.com/quixio/quix-samples) repo. Any new project that we accept will be attributed to you and you'll receive $200 in Quix credit.

## Open source

This project is open source under the Apache 2.0 license and available in our [GitHub](https://github.com/quixio/quix-samples) repo.

Please star us and mention us on social to show your appreciation.

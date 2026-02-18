FROM python:3.12.5-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8

WORKDIR /app

# Install dependencies
COPY benchmark/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy benchmark script
COPY benchmark/benchmark.py .

# Copy all FMU files into a known location
COPY fmu-integration/simulink_example_inports.fmu fmus/simulink_example_inports.fmu
COPY fmu-explorer/examples/BouncingBall.fmu fmus/BouncingBall.fmu

ENTRYPOINT ["python3", "benchmark.py"]
CMD ["-n", "100", "-w", "5", "-o", "/results/results.json"]

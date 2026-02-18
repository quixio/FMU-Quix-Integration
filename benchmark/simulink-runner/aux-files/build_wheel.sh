#!/bin/bash
# Script to build wheel package from the out folder
# Run this after compiling the MATLAB function with quix_compiler.m

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$SCRIPT_DIR/out"

if [ ! -d "$OUT_DIR" ]; then
    echo "Error: 'out' directory not found"
    echo "Run quix_compiler.m first to generate the compiled output"
    exit 1
fi

# Find Python executable
PYTHON_EXEC=$(command -v python3 || command -v python)

if [ -z "$PYTHON_EXEC" ]; then
    echo "Error: Python is not installed or not in PATH."
    exit 1
fi

echo "Using Python at: $PYTHON_EXEC"
"$PYTHON_EXEC" --version

echo "Installing build tools..."
"$PYTHON_EXEC" -m pip install --upgrade build wheel

echo "Building wheel..."
cd "$OUT_DIR"
"$PYTHON_EXEC" -m build --wheel

echo "Wheel built successfully in $OUT_DIR/dist"

# Copy the generated wheel file(s) to the root script directory
DIST_DIR="$OUT_DIR/dist"

if [ -d "$DIST_DIR" ]; then
    WHEEL_FILES=("$DIST_DIR"/*.whl)
    if [ -e "${WHEEL_FILES[0]}" ]; then
        echo "Copying wheel file(s) to $SCRIPT_DIR"
        cp "$DIST_DIR"/*.whl "$SCRIPT_DIR"/
        echo "Wheel file(s) copied successfully."

        # Also copy to parent directory (simulink-runner)
        PARENT_DIR="$(dirname "$SCRIPT_DIR")"
        cp "$DIST_DIR"/*.whl "$PARENT_DIR"/
        echo "Wheel file(s) also copied to $PARENT_DIR"
    else
        echo "No .whl files found in $DIST_DIR"
    fi
else
    echo "Directory $DIST_DIR does not exist."
fi

echo "Done!"

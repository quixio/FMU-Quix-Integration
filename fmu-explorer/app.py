from flask import Flask, render_template, request, jsonify, session
from fmpy import read_model_description, simulate_fmu
import tempfile
import os
import csv
import io
import numpy as np
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Store uploaded FMUs temporarily (in production, use proper session storage)
fmu_storage = {}

# Example FMUs directory
EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), 'examples')

# Available example FMUs
EXAMPLE_FMUS = {
    'bouncing_ball': {
        'filename': 'BouncingBall.fmu',
        'name': 'Bouncing Ball',
        'description': 'A ball bouncing on the ground - demonstrates state events'
    },
    'simulink_2d': {
        'filename': 'simulink_example_inports.fmu',
        'name': '2D Vector Rotation',
        'description': 'Rotates 2D coordinates (x, y) by angle theta'
    }
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/examples', methods=['GET'])
def list_examples():
    """List available example FMUs."""
    examples = []
    for key, info in EXAMPLE_FMUS.items():
        fmu_path = os.path.join(EXAMPLES_DIR, info['filename'])
        if os.path.exists(fmu_path):
            examples.append({
                'id': key,
                'name': info['name'],
                'description': info['description']
            })
    return jsonify({'success': True, 'examples': examples})

@app.route('/load-example/<example_id>', methods=['POST'])
def load_example(example_id):
    """Load an example FMU."""
    if example_id not in EXAMPLE_FMUS:
        return jsonify({'error': f'Unknown example: {example_id}'}), 404

    example_info = EXAMPLE_FMUS[example_id]
    fmu_path = os.path.join(EXAMPLES_DIR, example_info['filename'])

    if not os.path.exists(fmu_path):
        return jsonify({'error': f'Example FMU not found: {example_info["filename"]}'}), 404

    # Generate session ID if not exists
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(8)

    session_id = session['session_id']

    try:
        md = read_model_description(fmu_path)

        # Categorize variables by causality
        variables = {
            'inputs': [],
            'outputs': [],
            'parameters': [],
            'local': [],
            'other': []
        }

        for v in md.modelVariables:
            var_info = {
                'name': v.name,
                'valueReference': v.valueReference,
                'description': v.description or '',
                'type': v.type,
                'start': getattr(v, 'start', None),
                'causality': v.causality,
                'variability': v.variability,
            }

            if v.causality == 'input':
                variables['inputs'].append(var_info)
            elif v.causality == 'output':
                variables['outputs'].append(var_info)
            elif v.causality == 'parameter':
                variables['parameters'].append(var_info)
            elif v.causality == 'local':
                variables['local'].append(var_info)
            else:
                variables['other'].append(var_info)

        # Store for later use (use the original path, don't copy)
        fmu_storage[session_id] = {
            'path': fmu_path,
            'inputs': [v['name'] for v in variables['inputs']],
            'outputs': [v['name'] for v in variables['outputs']],
            'model_name': md.modelName,
            'is_example': True
        }

        # Extract model info
        model_info = {
            'modelName': md.modelName,
            'fmiVersion': md.fmiVersion,
            'description': md.description or example_info['description'],
            'generationTool': md.generationTool or '',
        }

        return jsonify({
            'success': True,
            'modelInfo': model_info,
            'variables': variables,
            'sessionId': session_id
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analyze', methods=['POST'])
def analyze_fmu():
    if 'fmu' not in request.files:
        return jsonify({'error': 'No FMU file provided'}), 400

    fmu_file = request.files['fmu']

    if fmu_file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not fmu_file.filename.endswith('.fmu'):
        return jsonify({'error': 'File must be an .fmu file'}), 400

    # Generate session ID if not exists
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(8)

    session_id = session['session_id']

    # Save to temp file
    temp_dir = tempfile.mkdtemp()
    fmu_path = os.path.join(temp_dir, fmu_file.filename)
    fmu_file.save(fmu_path)

    try:
        md = read_model_description(fmu_path)

        # Store FMU path for later use
        # Clean up old FMU if exists
        if session_id in fmu_storage:
            old_path = fmu_storage[session_id]['path']
            old_dir = os.path.dirname(old_path)
            if os.path.exists(old_path):
                os.remove(old_path)
            if os.path.exists(old_dir):
                os.rmdir(old_dir)

        # Categorize variables by causality
        variables = {
            'inputs': [],
            'outputs': [],
            'parameters': [],
            'local': [],
            'other': []
        }

        for v in md.modelVariables:
            var_info = {
                'name': v.name,
                'valueReference': v.valueReference,
                'description': v.description or '',
                'type': v.type,
                'start': getattr(v, 'start', None),
                'causality': v.causality,
                'variability': v.variability,
            }

            if v.causality == 'input':
                variables['inputs'].append(var_info)
            elif v.causality == 'output':
                variables['outputs'].append(var_info)
            elif v.causality == 'parameter':
                variables['parameters'].append(var_info)
            elif v.causality == 'local':
                variables['local'].append(var_info)
            else:
                variables['other'].append(var_info)

        # Store for later use
        fmu_storage[session_id] = {
            'path': fmu_path,
            'inputs': [v['name'] for v in variables['inputs']],
            'outputs': [v['name'] for v in variables['outputs']],
            'model_name': md.modelName
        }

        # Extract model info
        model_info = {
            'modelName': md.modelName,
            'fmiVersion': md.fmiVersion,
            'description': md.description or '',
            'generationTool': md.generationTool or '',
        }

        return jsonify({
            'success': True,
            'modelInfo': model_info,
            'variables': variables,
            'sessionId': session_id
        })

    except Exception as e:
        # Clean up on error
        if os.path.exists(fmu_path):
            os.remove(fmu_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        return jsonify({'error': str(e)}), 500


@app.route('/sample-csv', methods=['GET'])
def generate_sample_csv():
    """Generate a sample CSV file based on the uploaded FMU's inputs."""
    session_id = session.get('session_id')

    if not session_id or session_id not in fmu_storage:
        return jsonify({'error': 'No FMU uploaded. Please upload an FMU first.'}), 400

    fmu_info = fmu_storage[session_id]
    inputs = fmu_info['inputs']

    # Create sample CSV content
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row: time + all inputs
    header = ['time'] + inputs
    writer.writerow(header)

    # Sample data rows (3 example rows)
    for i in range(3):
        row = [float(i)]  # time
        for _ in inputs:
            row.append(round(np.random.uniform(0, 10), 2))  # random sample values
        writer.writerow(row)

    csv_content = output.getvalue()

    return jsonify({
        'success': True,
        'csv': csv_content,
        'headers': header,
        'filename': f'{fmu_info["model_name"]}_sample.csv'
    })


@app.route('/validate-csv', methods=['POST'])
def validate_csv():
    """Validate that the uploaded CSV matches the FMU inputs."""
    session_id = session.get('session_id')

    if not session_id or session_id not in fmu_storage:
        return jsonify({'error': 'No FMU uploaded. Please upload an FMU first.'}), 400

    if 'csv' not in request.files:
        return jsonify({'error': 'No CSV file provided'}), 400

    csv_file = request.files['csv']

    if csv_file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        # Read CSV content
        content = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))

        csv_headers = reader.fieldnames
        if not csv_headers:
            return jsonify({'error': 'CSV file is empty or has no headers'}), 400

        fmu_info = fmu_storage[session_id]
        required_inputs = fmu_info['inputs']

        # Check for 'time' column
        has_time = 'time' in csv_headers

        # Check which required inputs are missing
        missing_inputs = [inp for inp in required_inputs if inp not in csv_headers]
        extra_columns = [col for col in csv_headers if col not in required_inputs and col != 'time']

        # Parse the data
        rows = list(reader)

        # Convert to list of dicts for JSON
        data = []
        for row in rows:
            data.append(dict(row))

        return jsonify({
            'success': True,
            'valid': len(missing_inputs) == 0,
            'hasTime': has_time,
            'headers': csv_headers,
            'requiredInputs': required_inputs,
            'missingInputs': missing_inputs,
            'extraColumns': extra_columns,
            'data': data,
            'rowCount': len(data)
        })

    except Exception as e:
        return jsonify({'error': f'Failed to parse CSV: {str(e)}'}), 500


@app.route('/run', methods=['POST'])
def run_simulation():
    """Run the FMU simulation with the provided CSV data."""
    session_id = session.get('session_id')

    if not session_id or session_id not in fmu_storage:
        return jsonify({'error': 'No FMU uploaded. Please upload an FMU first.'}), 400

    if 'csv' not in request.files:
        return jsonify({'error': 'No CSV file provided'}), 400

    csv_file = request.files['csv']

    try:
        # Read CSV content
        content = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)

        if len(rows) == 0:
            return jsonify({'error': 'CSV file has no data rows'}), 400

        fmu_info = fmu_storage[session_id]
        fmu_path = fmu_info['path']
        input_names = fmu_info['inputs']
        output_names = fmu_info['outputs']

        # Build input array for fmpy
        # Create dtype for structured array
        dtype_fields = [('time', np.float64)]
        for name in input_names:
            dtype_fields.append((name, np.float64))

        # Parse input data
        input_data = []
        for row in rows:
            time_val = float(row.get('time', 0))
            values = [time_val]
            for name in input_names:
                values.append(float(row.get(name, 0)))
            input_data.append(tuple(values))

        input_array = np.array(input_data, dtype=dtype_fields)

        # Determine simulation time
        start_time = float(input_array['time'][0])
        stop_time = float(input_array['time'][-1])

        # If all times are the same, run a single step
        if start_time == stop_time:
            stop_time = start_time + 0.001

        # Run simulation
        result = simulate_fmu(
            fmu_path,
            start_time=start_time,
            stop_time=stop_time,
            input=input_array,
            output=output_names
        )

        # Convert results to list of dicts
        output_data = []
        for i in range(len(result)):
            row = {'time': float(result['time'][i])}
            for name in output_names:
                if name in result.dtype.names:
                    row[name] = float(result[name][i])
            output_data.append(row)

        return jsonify({
            'success': True,
            'inputData': [dict(zip(['time'] + input_names, row)) for row in input_data],
            'outputData': output_data,
            'outputColumns': ['time'] + output_names
        })

    except Exception as e:
        import traceback
        return jsonify({'error': f'Simulation failed: {str(e)}', 'trace': traceback.format_exc()}), 500


if __name__ == '__main__':
    port = int(os.environ.get('port', 80))
    app.run(debug=False, host='0.0.0.0', port=port)

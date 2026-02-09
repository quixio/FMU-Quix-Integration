# FMU Explorer

A web-based tool for exploring FMU (Functional Mock-up Unit) files. Upload any FMU and instantly see its inputs, outputs, parameters, and other variables.

## How to Run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the Flask server:

```bash
python app.py
```

3. Open your browser to http://localhost:5000

## Features

- Drag and drop FMU file upload
- Automatic detection of:
  - Model metadata (name, FMI version, description)
  - Input variables
  - Output variables
  - Parameters
  - Local variables
- Clean, collapsible UI for exploring large models

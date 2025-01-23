#!/bin/bash

# Create the main project directory
mkdir -p mlos_analyzer/mlos_analyzer/{api,core,utils,visualization}

# Create empty __init__.py files
touch mlos_analyzer/mlos_analyzer/__init__.py
touch mlos_analyzer/mlos_analyzer/api/__init__.py
touch mlos_analyzer/mlos_analyzer/core/__init__.py
touch mlos_analyzer/mlos_analyzer/utils/__init__.py
touch mlos_analyzer/mlos_analyzer/visualization/__init__.py

# Create setup.py
cat > mlos_analyzer/setup.py << 'EOF'
from setuptools import setup, find_packages

setup(
    name="mlos_analyzer",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "pandas",
        "plotly",
        "streamlit",
        "seaborn",
        "matplotlib",
        "scikit-learn",
        "scipy",
        "watchdog",
        "uvicorn",
        "azure-identity",
    ],
)
EOF

# Create requirements.txt
cat > mlos_analyzer/requirements.txt << 'EOF'
fastapi==0.68.0
pandas==1.3.3
plotly==5.3.1
streamlit==1.2.0
seaborn==0.11.2
matplotlib==3.4.3
scikit-learn==0.24.2
scipy==1.7.1
watchdog==2.1.6
uvicorn==0.15.0
azure-identity==1.7.0
EOF

# Create README.md
cat > mlos_analyzer/README.md << 'EOF'
# MLOS Analyzer

A comprehensive library for analyzing and visualizing MLOS experiment results.

## Installation
```bash
pip install -r requirements.txt
python setup.py install
```

## Features
- FastAPI backend for experiment data retrieval
- Correlation analysis
- Failure metrics visualization
- Statistical analysis
- Advanced plotting capabilities
EOF

# Create the main Python files
mkdir -p mlos_analyzer/mlos_analyzer/{api,core,utils,visualization}

# API files
cat > mlos_analyzer/mlos_analyzer/api/endpoints.py << 'EOF'
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import ExperimentExplanationRequest
from ..core.storage import storage
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/experiments")
def get_experiments():
    return list(storage.experiments.keys())

@app.get("/experiment_results/{experiment_id}")
def get_experiment_results(experiment_id: str):
    try:
        exp = storage.experiments[experiment_id]
        return exp.results_df.to_dict(orient="records")
    except KeyError:
        raise HTTPException(status_code=404, detail="Experiment not found")
EOF

cat > mlos_analyzer/mlos_analyzer/api/models.py << 'EOF'
from pydantic import BaseModel

class ExperimentExplanationRequest(BaseModel):
    experiment_id: str
EOF

# Core files
cat > mlos_analyzer/mlos_analyzer/core/storage.py << 'EOF'
from mlos_bench.storage import from_config

try:
    storage = from_config(config="storage/sqlite.jsonc")
except Exception as e:
    raise Exception(f"Error loading storage configuration: {e}")
EOF

# Copy the rest of the Python files from the previous structure...
# (Add similar cat commands for visualization/, utils/, etc.)

# Make the directory installable
cd mlos_analyzer
pip install -e .

echo "MLOS Analyzer library structure created successfully!"

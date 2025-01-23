from pydantic import BaseModel

class ExperimentExplanationRequest(BaseModel):
    experiment_id: str

# mlos_viz_lib/core/storage.py
from mlos_bench.storage import from_config

try:
    storage = from_config(config="storage/sqlite.jsonc")
except Exception as e:
    raise Exception(f"Error loading storage configuration: {e}")

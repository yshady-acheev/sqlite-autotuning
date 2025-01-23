# MLOS Visualization Library

Visualization and analysis library for MLOS (Machine Learning for Operating Systems) experiment results.

## Installation

```bash
pip install -r requirements.txt
python setup.py install
```

## Quick Start

```python
from mlos_viz_lib import plot_whisker_plots, plot_heatmap
from mlos_viz_lib.core.storage import storage

# Load experiment data
experiment_id = "your_experiment_id"
exp = storage.experiments[experiment_id]
df = exp.results_df

# Create visualizations
whisker_fig_top, whisker_fig_bottom = plot_whisker_plots(df, "result.latency", n=5)
correlation_fig = plot_heatmap(df)
```

## Features

### Correlation Analysis
```python
from mlos_viz_lib.visualization.correlation import plot_correlation_table_target

# Plot correlation between parameters and target metric
fig = plot_correlation_table_target(df, target_col="result.latency")
```

### Failure Analysis
```python
from mlos_viz_lib.visualization.failure_metrics import (
    plot_success_failure_distribution,
    plot_failure_rate_by_config
)

# Plot failure distribution
dist_fig = plot_success_failure_distribution(df)
rate_fig = plot_failure_rate_by_config(df)
```

### Statistical Analysis
```python
from mlos_viz_lib.visualization.statistical import run_pairwise_stat_tests

# Run statistical tests between configurations
results = run_pairwise_stat_tests(
    df,
    result_col="result.latency",
    test_type="ttest",
    alpha=0.05
)
```

### FastAPI Backend

Start the server:
```bash
uvicorn mlos_viz_lib.api.endpoints:app --reload
```

Access endpoints:
```python
import requests

# Get experiments
response = requests.get("http://localhost:8000/experiments")
experiments = response.json()

# Get experiment results
response = requests.get(f"http://localhost:8000/experiment_results/{experiment_id}")
results = response.json()
```

## Configuration

The library uses a SQLite storage configuration by default. Update `storage/sqlite.jsonc` for custom configuration:

```json
{
  "type": "sqlite",
  "connection": "path/to/your/database.db"
}
```

## Contributing

1. Fork the repository
2. Create feature branch
3. Submit pull request

## License

MIT License

import plotly.express as px
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def plot_whisker_plots(df: pd.DataFrame, target_col: str, n: int = 5):
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")
    df = df.dropna(subset=[target_col])

    config_avg = df.groupby("tunable_config_id")[target_col].mean().reset_index()
    config_avg = config_avg.dropna(subset=[target_col])

    top_n_configs = config_avg.nlargest(n, target_col)["tunable_config_id"]
    top_configs = df[df["tunable_config_id"].isin(top_n_configs)]
    top_configs = top_configs.sort_values(by=target_col, ascending=False)

    fig_top = px.box(
        top_configs,
        x="tunable_config_id",
        y=target_col,
        title=f"Whisker Plot for Top {n} Configurations by {target_col}",
        labels={"tunable_config_id": "Configuration ID", target_col: target_col},
    )

    bottom_n_configs = config_avg.nsmallest(n, target_col)["tunable_config_id"]
    bottom_configs = df[df["tunable_config_id"].isin(bottom_n_configs)]
    bottom_configs = bottom_configs.sort_values(by=target_col, ascending=True)

    fig_bottom = px.box(
        bottom_configs,
        x="tunable_config_id",
        y=target_col,
        title=f"Whisker Plot for Bottom {n} Configurations by {target_col}",
        labels={"tunable_config_id": "Configuration ID", target_col: target_col},
    )

    return fig_top, fig_bottom

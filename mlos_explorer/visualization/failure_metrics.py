import plotly.express as px
import pandas as pd


def plot_success_failure_distribution(df: pd.DataFrame):
    status_counts = df["status"].value_counts()
    fig = px.pie(
        values=status_counts.values,
        names=status_counts.index,
        title="Overall Success/Failure Distribution",
    )
    return fig


def plot_success_failure_by_config(df: pd.DataFrame):
    status_by_config = (
        df.groupby(["tunable_config_id", "status"]).size().unstack(fill_value=0).reset_index()
    )
    status_by_config = status_by_config.melt(
        id_vars="tunable_config_id", var_name="status", value_name="count"
    )
    fig = px.bar(
        status_by_config,
        x="tunable_config_id",
        y="count",
        color="status",
        barmode="stack",
        title="Success/Failure Count by Configuration",
    )
    fig.update_layout(xaxis_title="Configuration ID", yaxis_title="Count")
    return fig


def plot_failure_rate_by_config(df: pd.DataFrame):
    failure_rate_data = (
        df.groupby("tunable_config_id")["status"]
        .apply(lambda x: (x == "FAILED").mean())
        .reset_index()
    )
    failure_rate_data.columns = ["tunable_config_id", "failure_rate"]
    fig = px.bar(
        failure_rate_data,
        x="tunable_config_id",
        y="failure_rate",
        title="Failure Rate by Configuration",
    )
    fig.update_layout(xaxis_title="Configuration ID", yaxis_title="Failure Rate")
    return fig

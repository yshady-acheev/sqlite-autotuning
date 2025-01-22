import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import requests
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import mlos_viz
from mlos_bench.storage import from_config
import re
import warnings
from pathlib import Path
import json5 as json
import os

from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from scipy.stats import ttest_ind, mannwhitneyu


# Load the storage config and connect to the storage
try:
    storage = storage = from_config(config="storage/sqlite.jsonc")
except Exception as e:
    st.error(f"Error loading storage configuration: {e}")
    storage = None

# Suppress specific FutureWarning from seaborn
warnings.filterwarnings("ignore", category=FutureWarning)

# Ensure the backend is running on this port
backend_url = "http://localhost:8000"

# Base directory for the project
base_dir = Path(__file__).resolve().parent


@st.cache_data
def get_experiments():
    response = requests.get(f"{backend_url}/experiments")
    if response.status_code == 200:
        return response.json()
    else:
        st.error("Failed to fetch experiments")
        return []


def get_experiment_results(experiment_id):
    response = requests.get(f"{backend_url}/experiment_results/{experiment_id}")
    if response.status_code == 200:
        return pd.DataFrame(response.json())
    else:
        st.error(f"Failed to fetch results for experiment {experiment_id}")
        return pd.DataFrame()


def get_experiment_explanation(experiment_id):
    response = requests.post(
        f"{backend_url}/get_experiment_explanation", json={"experiment_id": experiment_id}
    )
    if response.status_code == 200:
        return response.json()["explanation"]
    else:
        st.error(f"Failed to get explanation: {response.text}")
        return ""


experiment_ids = get_experiments()


# Function to plot the average metrics for each configuration
def plot_average_metrics(experiment_id, storage, metric):
    exp = storage.experiments[experiment_id]
    df = exp.results_df

    # Select numeric columns only, along with 'tunable_config_id'
    numeric_df = df.select_dtypes(include="number")
    numeric_df["tunable_config_id"] = df["tunable_config_id"]

    # Group by 'tunable_config_id' and calculate the mean for numeric columns
    average_metrics = numeric_df.groupby("tunable_config_id").mean().reset_index()

    metrics = ["result.reads", "result.writes", "result.total", metric]
    metric_labels = [
        "Average Reads",
        "Average Writes",
        "Average Transactions",
        "Average Score",
        metric,
    ]

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle("Average Metrics for Each Configuration")

    for ax, metric, label in zip(axes.flatten(), metrics, metric_labels):
        if metric in average_metrics.columns:
            ax.bar(average_metrics["tunable_config_id"], average_metrics[metric], color="blue")
            ax.set_xlabel("Configuration ID")
            ax.set_ylabel(label)
            ax.set_title(label)
            ax.tick_params(axis="x", rotation=45)
        else:
            ax.set_visible(False)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    st.pyplot(fig)


# Function to plot the failure rate by configuration
def plot_failure_rate(experiment_id, storage):
    exp = storage.experiments[experiment_id]
    df = exp.results_df
    failure_rate_data = (
        df.groupby("tunable_config_id")["status"]
        .apply(lambda x: (x == "FAILED").mean())
        .reset_index()
    )
    failure_rate_data.columns = ["tunable_config_id", "failure_rate"]

    plt.figure(figsize=(10, 6))
    sns.barplot(data=failure_rate_data, x="tunable_config_id", y="failure_rate")
    plt.xlabel("Configuration ID")
    plt.ylabel("Failure Rate")
    plt.title("Failure Rate by Configuration")
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(plt)


# Function to plot the metric percentiles
def plot_metric_percentiles(experiment_id, storage, metric):
    exp = storage.experiments[experiment_id]
    df = exp.results_df

    # Ensure metric is numeric
    df[metric] = pd.to_numeric(df[metric], errors="coerce")

    # Drop rows with NaN values in metric
    df = df.dropna(subset=[metric])

    latency_percentiles = (
        df.groupby("tunable_config_id")[metric].quantile([0.25, 0.5, 0.75]).unstack().reset_index()
    )
    latency_percentiles.columns = [
        "config_id",
        "25th_percentile",
        "50th_percentile",
        "75th_percentile",
    ]

    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x="tunable_config_id", y=metric)
    plt.xlabel("Configuration ID")
    plt.ylabel("Result Score")
    plt.title(f"{metric} Percentiles by Configuration")
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(plt)


# Function to plot whisker plots for configurations within a specific experiment


def plot_whisker_plots(df, target_col, n=5):
    """
    Plots whisker plots for the top N and bottom N configurations with respect to a target column.

    Parameters:
    df (pd.DataFrame): The DataFrame containing the data to plot.
    target_col (str): The name of the target column to plot on the y-axis.
    n (int): The number of top and bottom configurations to plot.
    """
    if "tunable_config_id" not in df.columns or target_col not in df.columns:
        st.error(f"'tunable_config_id' or '{target_col}' column not found in DataFrame.")
        return

    # Ensure the target column is numeric and drop NaNs
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")
    df = df.dropna(subset=[target_col])

    # Calculate the average of the target column for each configuration
    config_avg = df.groupby("tunable_config_id")[target_col].mean().reset_index()

    # Filter out configurations that do not have any result values
    config_avg = config_avg.dropna(subset=[target_col])

    # Select top N configurations
    top_n_configs = config_avg.nlargest(n, target_col)["tunable_config_id"]

    # Filter the DataFrame to include only the top N configurations
    top_configs = df[df["tunable_config_id"].isin(top_n_configs)]

    # Sort the top configurations by the target column
    top_configs = top_configs.sort_values(by=target_col, ascending=False)

    # Plot whisker plots for the top N configurations
    fig_top = px.box(
        top_configs,
        x="tunable_config_id",
        y=target_col,
        title=f"Whisker Plot for Top {n} Configurations by {target_col}",
        labels={"tunable_config_id": "Configuration ID", target_col: target_col},
    )
    st.plotly_chart(fig_top, use_container_width=True)

    # Select bottom N configurations
    bottom_n_configs = config_avg.nsmallest(n, target_col)["tunable_config_id"]

    # Filter the DataFrame to include only the bottom N configurations
    bottom_configs = df[df["tunable_config_id"].isin(bottom_n_configs)]

    # Sort the bottom configurations by the target column
    bottom_configs = bottom_configs.sort_values(by=target_col, ascending=True)

    # Plot whisker plots for the bottom N configurations
    fig_bottom = px.box(
        bottom_configs,
        x="tunable_config_id",
        y=target_col,
        title=f"Whisker Plot for Bottom {n} Configurations by {target_col}",
        labels={"tunable_config_id": "Configuration ID", target_col: target_col},
    )
    st.plotly_chart(fig_bottom, use_container_width=True)


def run_pairwise_stat_tests(
    df, result_col, group_col="tunable_config_id", alpha=0.05, test_type="ttest"
):
    """
    Perform pairwise statistical significance tests on a result column,
    grouped by a configuration column or tunable_config_id.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame containing the data.
    result_col : str
        The name of the result column on which to base the test.
    group_col : str
        The column that identifies distinct configurations/groups (default = "tunable_config_id").
    alpha : float
        The significance level for the test (default = 0.05).
    test_type : str
        Which test to use: "ttest" for independent two-sample t-test,
        or "mannwhitney" for Mann-Whitney U test.

    Returns
    -------
    pd.DataFrame
        A DataFrame listing each pair of config groups, test statistic, p-value,
        and a boolean indicating significance at the chosen alpha level.
    """
    # Drop rows where result_col is NaN or infinite
    df = df.dropna(subset=[result_col]).copy()
    df = df[np.isfinite(df[result_col])]

    # Ensure result_col is numeric
    df[result_col] = pd.to_numeric(df[result_col], errors="coerce")

    # Get unique configurations
    configs = df[group_col].unique()
    results = []

    # Compare each pair of unique configs
    for i in range(len(configs)):
        for j in range(i + 1, len(configs)):
            cfg_i = configs[i]
            cfg_j = configs[j]
            data_i = df.loc[df[group_col] == cfg_i, result_col]
            data_j = df.loc[df[group_col] == cfg_j, result_col]

            # Skip if no data in one group
            if data_i.empty or data_j.empty:
                continue

            # Perform the chosen test
            if test_type == "mannwhitney":
                stat, pval = mannwhitneyu(data_i, data_j, alternative="two-sided")
            else:
                # Default to t-test
                stat, pval = ttest_ind(data_i, data_j, equal_var=False, nan_policy="omit")

            is_significant = pval < alpha
            results.append(
                {
                    "Config_A": cfg_i,
                    "Config_B": cfg_j,
                    "N_A": len(data_i),
                    "N_B": len(data_j),
                    "Test_Statistic": stat,
                    "p-value": pval,
                    "Significant": is_significant,
                }
            )

    return pd.DataFrame(results)


# Function to plot correlation between parameter changes and latency
def plot_param_latency_correlation(experiment_id, storage, metric):
    exp = storage.experiments[experiment_id]
    df = exp.results_df

    # Pivot the data to have parameters as columns
    param_pivot = df.pivot_table(index="trial_id", columns="param_id", values="param_value")
    combined_data_with_params = param_pivot.join(df.set_index("trial_id")[[metric]])

    # Calculate the correlation
    param_latency_corr = combined_data_with_params.corr()[metric].drop(metric).to_frame()
    param_latency_corr.columns = ["Correlation with Score"]

    # Plot the heatmap
    if not param_latency_corr.empty:
        plt.figure(figsize=(10, 8))
        sns.heatmap(param_latency_corr, annot=True, cmap="coolwarm", linewidths=0.5)
        plt.title("Correlation Between Parameter Changes and Score")
        st.pyplot(plt)
    else:
        st.write("Correlation matrix is empty or contains only NaN values.")


# Function to plot correlation matrix between result columns and configuration parameters
def plot_correlation_matrix_with_config(df):
    # st.title('Correlation Matrix Between Results and Configurations')

    # Select columns that start with 'result' or 'config'
    result_columns = [col for col in df.columns if col.startswith("result")]
    config_columns = [col for col in df.columns if col.startswith("config")]

    # Ensure both config and result columns are present
    if not result_columns:
        st.warning("No result columns found.")
        return
    if not config_columns:
        st.warning("No config columns found.")
        return

    # Select numeric columns from both result and config columns
    numeric_result_df = df[result_columns].apply(pd.to_numeric, errors="coerce")
    numeric_config_df = df[config_columns].apply(pd.to_numeric, errors="coerce")

    # Combine both dataframes to ensure they are in the same dataframe
    combined_numeric_df = pd.concat([numeric_result_df, numeric_config_df], axis=1)

    # Ensure there are numeric columns
    if combined_numeric_df.empty:
        st.warning("No numeric columns available for correlation matrix.")
        return

    # Drop columns with all NaN values
    combined_numeric_df.dropna(axis=1, how="all", inplace=True)

    # Compute correlation matrix
    corr = combined_numeric_df.corr()

    # Plot the correlation matrix using Seaborn and Matplotlib
    plt.figure(figsize=(12, 10))
    sns.heatmap(corr, annot=True, cmap="coolwarm", fmt=".2f", linewidths=0.5)
    # plt.title('Correlation Matrix Between Results and Configurations')
    st.pyplot(plt)


# Function to plot top and bottom configurations based on the target column
def plot_config_top_bottom(df, target_col, config_prefix="config."):
    if target_col not in df.columns:
        st.error(f"Target column '{target_col}' not found in DataFrame.")
        return

    # Sort the DataFrame by target column in descending order
    sorted_df = df.sort_values(by=target_col, ascending=False)

    # Select top and bottom configurations
    top_configs = sorted_df.head(5)
    bottom_configs = sorted_df.tail(5)

    config_columns = [col for col in df.columns if col.startswith(config_prefix)]

    # Plot top configurations
    plt.figure(figsize=(15, 6))
    plt.subplot(1, 2, 1)
    for config in config_columns:
        plt.plot(top_configs["tunable_config_id"], top_configs[config], label=config)
    plt.xlabel("Configuration ID")
    plt.ylabel("Configuration Value")
    plt.title(f"Top 5 Configurations by {target_col}")
    plt.legend()

    # Plot bottom configurations
    plt.subplot(1, 2, 2)
    for config in config_columns:
        plt.plot(bottom_configs["tunable_config_id"], bottom_configs[config], label=config)
    plt.xlabel("Configuration ID")
    plt.ylabel("Configuration Value")
    plt.title(f"Bottom 5 Configurations by {target_col}")
    plt.legend()

    plt.tight_layout()
    st.pyplot(plt)


def display_config_details(experiment_data, config_prefix="config."):
    """
    Display configuration details from the experiment data.
    Filters columns that start with the specified prefix and displays them in Streamlit.
    Assumes the experiment data can be accessed or converted to a DataFrame.
    """
    # Accessing or converting experiment data to DataFrame
    if hasattr(experiment_data, "results_df"):
        df = experiment_data.results_df  # Access the DataFrame if it's a property
    else:
        st.error("Experiment data does not contain 'results_df'. Check the data structure.")
        return

    # Check for DataFrame columns
    if not hasattr(df, "columns"):
        st.error("Data is not a valid DataFrame.")
        return

    # Filter columns that start with config_prefix
    config_columns = [col for col in df.columns if col.startswith(config_prefix)]
    if not config_columns:
        st.warning("No configuration columns found.")
        return

    # Assuming there is a unique identifier in the DataFrame to select configurations
    if "tunable_config_id" in df.columns:
        config_ids = df["tunable_config_id"].dropna().unique()
        selected_config_id = st.selectbox("Select Configuration ID:", config_ids)
        # Display details for the selected configuration ID
        config_details = df[df["tunable_config_id"] == selected_config_id][config_columns]
        # Iterate through each row and display each column value line by line
        for _, row in config_details.iterrows():
            for col in config_columns:
                st.text(f"{col}: {row[col]}")  # Using st.text for plain text
    else:
        st.error("No 'tunable_config_id' column found in the DataFrame.")


def plot_line_scatter_chart(df, target_col, benchmark_col="results.latency_pct"):
    if "trial_id" not in df.columns or target_col not in df.columns:
        st.error(
            f"'trial_id', '{target_col}', or '{benchmark_col}' column not found in DataFrame."
        )
        return

    plot_data = df[["trial_id", target_col, benchmark_col]].dropna().sort_values(by="trial_id")
    if plot_data.empty:
        st.error(f"No data available for plotting with target column '{target_col}'.")
        return

    fig = px.scatter(
        plot_data,
        x="trial_id",
        y=target_col,
        color=benchmark_col,
        title=f"Line and Scatter Plot of trial_id vs {target_col}",
        labels={"trial_id": "Trial ID", target_col: target_col},
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_success_failure_distribution(df):
    """
    Plots a pie chart for the overall success and failure distribution using Plotly.
    """
    status_counts = df["status"].value_counts()
    fig = px.pie(
        values=status_counts.values,
        names=status_counts.index,
        title="Overall Success/Failure Distribution",
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_success_failure_by_config(df):
    """
    Plots a bar chart for the count of successes and failures by configuration using Plotly.
    """
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
    st.plotly_chart(fig, use_container_width=True)


def plot_failure_rate_by_config(df):
    """
    Plots a bar chart for the failure rate by configuration using Plotly.
    """
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
    st.plotly_chart(fig, use_container_width=True)


# Main function to plot the selected view
def plot_failure_metrics(experiment_id, storage, view_type):
    exp = storage.experiments[experiment_id]
    df = exp.results_df

    if view_type == "Pie Chart":
        plot_success_failure_distribution(df)
    elif view_type == "Bar Chart - Success/Failure Count":
        plot_success_failure_by_config(df)
    elif view_type == "Bar Chart - Failure Rate":
        plot_failure_rate_by_config(df)


def plot_heatmap(df):
    # Select numeric columns only
    numeric_df = df.select_dtypes(include=["int64", "float64"])

    config_columns = [col for col in numeric_df.columns if col.startswith("config")]
    result_columns = [col for col in numeric_df.columns if col.startswith("result")]

    combined_data = numeric_df[config_columns + result_columns].apply(
        pd.to_numeric, errors="coerce"
    )
    correlation_matrix = combined_data.corr()
    config_result_corr = correlation_matrix.loc[config_columns, result_columns]

    fig = px.imshow(
        config_result_corr, text_auto=True, color_continuous_scale="RdBu", aspect="auto"
    )
    fig.update_layout(
        title="Heatmap of Configuration Parameters vs Performance Metrics",
        xaxis_title="Performance Metrics",
        yaxis_title="Configuration Parameters",
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_correlation_table_target(df, target_col):
    # Select numeric columns only
    numeric_df = df.select_dtypes(include=["int64", "float64"])

    result_columns = [col for col in numeric_df.columns if col.startswith("config")]

    numeric_df[target_col] = pd.to_numeric(numeric_df[target_col], errors="coerce")

    correlations = (
        numeric_df[result_columns].corrwith(numeric_df[target_col]).sort_values(ascending=False)
    )
    correlations_df = pd.DataFrame(correlations, columns=["Correlation"]).reset_index()
    correlations_df.columns = ["Config Column", "Correlation"]

    fig = px.imshow(
        correlations_df.set_index("Config Column").T,
        text_auto=True,
        color_continuous_scale="RdBu",
        aspect="auto",
    )
    fig.update_layout(
        title=f"Correlation Heatmap with {target_col}",
        xaxis_title="Config Columns",
        yaxis_title="Correlation",
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_top_bottom_configs_scatter(df, target_col, n=5):
    """
    Plots the top N and bottom N configurations on a line and scatter plot with respect to a target column.

    Parameters:
    df (pd.DataFrame): The DataFrame containing the data to plot.
    target_col (str): The name of the target column to plot on the y-axis.
    n (int): The number of top and bottom configurations to plot.
    """
    if "trial_id" not in df.columns or target_col not in df.columns:
        st.error(f"'trial_id' or '{target_col}' column not found in DataFrame.")
        return

    # Ensure the target column is numeric
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")

    # Sort the DataFrame by the target column
    sorted_df = df.sort_values(by=target_col, ascending=False)

    # Select top N and bottom N configurations
    top_configs = sorted_df.head(n)
    bottom_configs = sorted_df.tail(n)

    plt.figure(figsize=(12, 6))

    # Plot top N configurations
    plt.plot(
        top_configs["trial_id"],
        top_configs[target_col],
        linestyle="-",
        marker="o",
        color="blue",
        label=f"Top {n} Trials",
    )

    # Plot bottom N configurations
    plt.plot(
        bottom_configs["trial_id"],
        bottom_configs[target_col],
        linestyle="-",
        marker="o",
        color="red",
        label=f"Bottom {n} Trials",
    )

    plt.title(f"Top {n} and Bottom {n} Trials by {target_col}")
    plt.xlabel("trial_id")
    plt.ylabel(target_col)
    plt.legend()
    plt.grid(True)

    st.pyplot(plt)


def plot_config_scatter(df, target_col, n=5):
    """
    Plots scatter plots for the top N and bottom N configurations with respect to a target column.

    Parameters:
    df (pd.DataFrame): The DataFrame containing the data to plot.
    target_col (str): The name of the target column to plot on the y-axis.
    n (int): The number of top and bottom configurations to plot.
    """
    if "tunable_config_id" not in df.columns or target_col not in df.columns:
        st.error(f"'tunable_config_id' or '{target_col}' column not found in DataFrame.")
        return

    # Ensure the target column is numeric
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")

    # Sort the DataFrame by the target column
    sorted_df = df.sort_values(by=target_col, ascending=False)

    # Select top N and bottom N configurations
    top_configs = sorted_df.head(n)
    bottom_configs = sorted_df.tail(n)

    # Plot top N configurations
    plt.figure(figsize=(12, 6))
    plt.scatter(
        top_configs["tunable_config_id"],
        top_configs[target_col],
        color="blue",
        label=f"Top {n} Configs",
    )
    plt.xlabel("Configuration ID")
    plt.ylabel(target_col)
    plt.title(f"Scatter Plot for Top {n} Configurations by {target_col}")
    plt.legend()
    plt.grid(True)
    st.pyplot(plt)

    # Plot bottom N configurations
    plt.figure(figsize=(12, 6))
    plt.scatter(
        bottom_configs["tunable_config_id"],
        bottom_configs[target_col],
        color="red",
        label=f"Bottom {n} Configs",
    )
    plt.xlabel("Configuration ID")
    plt.ylabel(target_col)
    plt.title(f"Scatter Plot for Bottom {n} Configurations by {target_col}")
    plt.legend()
    plt.grid(True)
    st.pyplot(plt)


def compare_whisker_plots(df, target_col, config_id_1, config_id_2):
    """
    Plots whisker plots for two specific configurations with respect to a target column on the same plot.

    Parameters:
    df (pd.DataFrame): The DataFrame containing the data to plot.
    target_col (str): The name of the target column to plot on the y-axis.
    config_id_1 (int): The ID of the first configuration to plot.
    config_id_2 (int): The ID of the second configuration to plot.
    """
    if "tunable_config_id" not in df.columns or target_col not in df.columns:
        st.error(f"'tunable_config_id' or '{target_col}' column not found in DataFrame.")
        return

    # Ensure the target column is numeric
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")

    # Filter the DataFrame for the two configurations
    config_1_data = df[df["tunable_config_id"] == config_id_1]
    config_2_data = df[df["tunable_config_id"] == config_id_2]

    if config_1_data.empty or config_2_data.empty:
        st.error("One or both configuration IDs do not exist in the DataFrame.")
        return

    # Combine the data for plotting
    combined_data = pd.concat([config_1_data, config_2_data])

    fig = px.box(
        combined_data,
        x="tunable_config_id",
        y=target_col,
        points="all",
        labels={"tunable_config_id": "Configuration ID", target_col: target_col},
        title=f"Whisker Plot for Configurations {config_id_1} and {config_id_2} by {target_col}",
    )

    st.plotly_chart(fig, use_container_width=True)


from scipy.stats import gaussian_kde
import plotly.graph_objects as go
import numpy as np


def compare_score_distributions(df, target_col, config_id_1, config_id_2):
    """
    Plots the distribution of scores for two specific configurations side by side.

    Parameters:
    df (pd.DataFrame): The DataFrame containing the data to plot.
    target_col (str): The name of the target column to plot the distribution of.
    config_id_1 (int): The ID of the first configuration to plot.
    config_id_2 (int): The ID of the second configuration to plot.
    """
    if "tunable_config_id" not in df.columns or target_col not in df.columns:
        st.error(f"'tunable_config_id' or '{target_col}' column not found in DataFrame.")
        return

    # Ensure the target column is numeric
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")

    # Filter the DataFrame for the two configurations
    config_1_data = df[df["tunable_config_id"] == config_id_1][target_col].dropna()
    config_2_data = df[df["tunable_config_id"] == config_id_2][target_col].dropna()

    if config_1_data.empty or config_2_data.empty:
        st.error("One or both configuration IDs do not exist in the DataFrame.")
        return

    # Calculate KDE for both configurations
    kde_1 = gaussian_kde(config_1_data)
    kde_2 = gaussian_kde(config_2_data)

    # Create an array of x values for plotting the KDE
    x_min = min(config_1_data.min(), config_2_data.min())
    x_max = max(config_1_data.max(), config_2_data.max())
    x_vals = np.linspace(x_min, x_max, 500)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(x=x_vals, y=kde_1(x_vals), mode="lines", name=f"Config {config_id_1}")
    )

    fig.add_trace(
        go.Scatter(x=x_vals, y=kde_2(x_vals), mode="lines", name=f"Config {config_id_2}")
    )

    fig.update_layout(
        title_text=f"Score Distribution for Configurations {config_id_1} and {config_id_2}",
        xaxis_title_text=target_col,
        yaxis_title_text="Density",
        legend_title_text="Configuration",
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_violin_plot(df, target_col, config_id_1, config_id_2):
    """
    Plots a violin plot for two specific configurations with respect to a target column.

    Parameters:
    df (pd.DataFrame): The DataFrame containing the data to plot.
    target_col (str): The name of the target column to plot on the y-axis.
    config_id_1 (int): The ID of the first configuration to plot.
    config_id_2 (int): The ID of the second configuration to plot.
    """
    if "tunable_config_id" not in df.columns or target_col not in df.columns:
        st.error(f"'tunable_config_id' or '{target_col}' column not found in DataFrame.")
        return

    # Ensure the target column is numeric
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")

    # Filter the DataFrame for the two configurations
    config_1_data = df[df["tunable_config_id"] == config_id_1]
    config_2_data = df[df["tunable_config_id"] == config_id_2]

    if config_1_data.empty or config_2_data.empty:
        st.error("One or both configuration IDs do not exist in the DataFrame.")
        return

    # Combine the data for plotting
    combined_data = pd.concat([config_1_data, config_2_data])

    fig = px.violin(
        combined_data,
        x="tunable_config_id",
        y=target_col,
        box=True,
        points="all",
        labels={"tunable_config_id": "Configuration ID", target_col: target_col},
        title=f"Violin Plot for Configurations {config_id_1} and {config_id_2} by {target_col}",
    )

    st.plotly_chart(fig, use_container_width=True)


def compare_two_experiments(experiment_id_1, experiment_id_2, storage, target_col):
    df1 = storage.experiments[experiment_id_1].results_df
    df2 = storage.experiments[experiment_id_2].results_df

    if target_col not in df1.columns or target_col not in df2.columns:
        st.error(
            f"The target column '{target_col}' does not exist in one of the selected experiments."
        )
        return

    df1[target_col] = pd.to_numeric(df1[target_col], errors="coerce")
    df2[target_col] = pd.to_numeric(df2[target_col], errors="coerce")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df1["trial_id"],
            y=df1[target_col],
            mode="lines+markers",
            name=f"Experiment {experiment_id_1}",
            # Adding labels for points
            text=[f"Trial {i}" for i in df1["trial_id"]],
            hoverinfo="text+y",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df2["trial_id"],
            y=df2[target_col],
            mode="lines+markers",
            name=f"Experiment {experiment_id_2}",
            # Adding labels for points
            text=[f"Trial {i}" for i in df2["trial_id"]],
            hoverinfo="text+y",
        )
    )

    fig.update_layout(
        title=f"Comparison of {target_col} between Experiment {experiment_id_1} and {experiment_id_2}",
        xaxis_title="Trial ID",
        yaxis_title=target_col,
        legend_title="Experiment",
    )

    st.plotly_chart(fig, use_container_width=True)


def compare_multiple_experiments(experiment_ids, storage, target_col):
    """
    Compare multiple experiments by plotting the selected target column.

    Parameters:
    experiment_ids (list): List of experiment IDs to compare.
    storage: The storage object containing experiment data.
    target_col (str): The name of the target column to compare.
    """
    # Scatter plot comparison
    fig_scatter = go.Figure()

    for experiment_id in experiment_ids:
        df = storage.experiments[experiment_id].results_df

        if target_col not in df.columns:
            st.error(
                f"The target column '{target_col}' does not exist in experiment {experiment_id}."
            )
            return

        df[target_col] = pd.to_numeric(df[target_col], errors="coerce")
        df = df.dropna(subset=[target_col])

        fig_scatter.add_trace(
            go.Scatter(
                x=df["trial_id"],
                y=df[target_col],
                mode="markers",
                name=f"Experiment {experiment_id}",
                text=[f"Trial {i}" for i in df["trial_id"]],
                hoverinfo="text+y",
            )
        )

    fig_scatter.update_layout(
        title=f"Scatter Plot Comparison of {target_col} across Experiments",
        xaxis_title="Trial ID",
        yaxis_title=target_col,
        legend_title="Experiment",
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    # Line plot comparison
    fig_line = go.Figure()

    for experiment_id in experiment_ids:
        df = storage.experiments[experiment_id].results_df

        if target_col not in df.columns:
            st.error(
                f"The target column '{target_col}' does not exist in experiment {experiment_id}."
            )
            return

        df[target_col] = pd.to_numeric(df[target_col], errors="coerce")
        df = df.dropna(subset=[target_col])

        fig_line.add_trace(
            go.Scatter(
                x=df["trial_id"],
                y=df[target_col],
                mode="lines+markers",
                name=f"Experiment {experiment_id}",
                text=[f"Trial {i}" for i in df["trial_id"]],
                hoverinfo="text+y",
            )
        )

    fig_line.update_layout(
        title=f"Line Plot Comparison of {target_col} across Experiments",
        xaxis_title="Trial ID",
        yaxis_title=target_col,
        legend_title="Experiment",
    )
    st.plotly_chart(fig_line, use_container_width=True)

    # Box plot comparison
    df_combined = pd.DataFrame()

    for experiment_id in experiment_ids:
        df = storage.experiments[experiment_id].results_df
        df["experiment_id"] = experiment_id

        if target_col not in df.columns:
            st.error(
                f"The target column '{target_col}' does not exist in experiment {experiment_id}."
            )
            return

        df[target_col] = pd.to_numeric(df[target_col], errors="coerce")
        df_combined = pd.concat([df_combined, df])

    df_combined = df_combined.dropna(subset=[target_col])

    fig_box = px.box(
        df_combined,
        x="experiment_id",
        y=target_col,
        title=f"Box Plot Comparison of {target_col} across Experiments",
        labels={"experiment_id": "Experiment ID", target_col: target_col},
    )
    st.plotly_chart(fig_box, use_container_width=True)

    # Violin plot comparison
    fig_violin = px.violin(
        df_combined,
        x="experiment_id",
        y=target_col,
        box=True,
        points="all",
        title=f"Violin Plot Comparison of {target_col} across Experiments",
        labels={"experiment_id": "Experiment ID", target_col: target_col},
    )
    st.plotly_chart(fig_violin, use_container_width=True)

    # Correlation matrix comparison
    # for experiment_id in experiment_ids:
    #     df = storage.experiments[experiment_id].results_df

    #     st.write(f"Correlation Matrix for Experiment {experiment_id}")
    #     plot_heatmap(df)
    #     plot_correlation_table_target(df, target_col)


if storage:
    st.title("Analytics Panel")

    st.write("Welcome to the Panel. View and analyze the results of your experiments here.")
    st.header("Select and View Experiment Details To Start Analyzing & Monitoring")
    selected_experiment_id = st.selectbox("Select Experiment ID", list(storage.experiments.keys()))

    with st.expander("View Experiment Results Dataframe Details"):
        df = storage.experiments[selected_experiment_id].results_df
        st.dataframe(df)

        st.write("Descriptive Statistics:")
        st.dataframe(df.describe())

        available_result_columns = [col for col in df.columns if col.startswith("result")]
        target_col = st.selectbox("Select a Result Column", available_result_columns)

    if selected_experiment_id:
        tab1, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(
            [
                "Failure Metrics",
                "Graphs",
                "Correlation",
                "Compare Configurations",
                "Compare Experiments",
                "ChatGPT",
                "Statistically Significant",
                "Parallel Plot",
            ]
        )

        with tab1:
            st.header("Failure Metrics")
            view_type = st.selectbox(
                "Select View Type",
                ["Pie Chart", "Bar Chart - Success/Failure Count", "Bar Chart - Failure Rate"],
            )
            try:
                plot_failure_metrics(selected_experiment_id, storage, view_type)
            except:
                st.write("Failure Metrics not available")

        with tab3:
            st.header("📊 Data Visualization")

            if df.empty:
                st.warning("No data available for visualization. Please load some data first.")
            else:
                try:
                    with st.expander("📋 Visualization Settings", expanded=True):
                        # Column Selection
                        config_columns = [col for col in df.columns if col.startswith("config.")]
                        result_columns = [col for col in df.columns if col.startswith("result.")]
                        status_options = df["status"].unique().tolist()

                        # Main Plot Settings
                        col1, col2 = st.columns(2)
                        with col1:
                            selected_x_axes = st.multiselect(
                                "X-axis (Configurations)",
                                options=config_columns,
                                default=config_columns[:1],
                                help="Select configuration parameters for X-axis",
                            )
                        with col2:
                            selected_y_axes = st.multiselect(
                                "Y-axis (Results)",
                                options=result_columns,
                                default=result_columns[:1],
                                help="Select result metrics for Y-axis",
                            )

                        # Plot Type and Filters
                        col3, col4, col5 = st.columns(3)
                        with col3:
                            plot_type = st.selectbox(
                                "Plot Type",
                                options=[
                                    "Scatter",
                                    "Line",
                                    "Box",
                                    "Violin",
                                    "2D Histogram",
                                    "3D Scatter",
                                    "Parallel Coordinates",
                                ],
                                help="Select visualization type",
                            )
                        with col4:
                            status_filter = st.multiselect(
                                "Status Filter",
                                options=status_options,
                                default=status_options,
                                help="Filter by status",
                            )
                        with col5:
                            template = st.selectbox(
                                "Plot Theme",
                                options=[
                                    "plotly",
                                    "plotly_white",
                                    "plotly_dark",
                                    "ggplot2",
                                    "seaborn",
                                ],
                                help="Select plot visual theme",
                            )

                        # Additional Options
                        col6, col7, col8, col9 = st.columns(4)
                        with col6:
                            show_stats = st.checkbox("Show Statistics", value=True)
                        with col7:
                            show_trend = st.checkbox("Show Trend Line", value=True)
                        with col8:
                            marginal_plot = st.checkbox("Show Marginal Plots", value=True)
                        with col9:
                            save_plots = st.checkbox("Enable Save Plots", value=False)

                    # Filter data
                    filtered_df = df[df["status"].isin(status_filter)]

                    if filtered_df.empty:
                        st.warning("No data points match the selected filters.")
                    elif not selected_x_axes or not selected_y_axes:
                        st.warning("Please select both X and Y axis parameters.")
                    else:
                        st.subheader("📈 Interactive Plots")

                        for x_axis in selected_x_axes:
                            for y_axis in selected_y_axes:
                                st.write(f"### {y_axis} vs {x_axis}")

                                if plot_type == "Parallel Coordinates":
                                    # Special handling for parallel coordinates
                                    selected_cols = [x_axis, y_axis] + [
                                        col for col in result_columns if col != y_axis
                                    ][:4]
                                    fig = px.parallel_coordinates(
                                        filtered_df,
                                        dimensions=selected_cols,
                                        color=y_axis,
                                        template=template,
                                    )
                                elif plot_type == "3D Scatter":
                                    # 3D scatter with additional dimension
                                    extra_dim = next(
                                        (col for col in result_columns if col != y_axis),
                                        result_columns[0],
                                    )
                                    fig = px.scatter_3d(
                                        filtered_df,
                                        x=x_axis,
                                        y=y_axis,
                                        z=extra_dim,
                                        color="status",
                                        template=template,
                                        hover_data=["trial_id", "ts_start"],
                                    )
                                elif plot_type == "2D Histogram":
                                    fig = px.density_heatmap(
                                        filtered_df,
                                        x=x_axis,
                                        y=y_axis,
                                        marginal_x="histogram",
                                        marginal_y="histogram",
                                        template=template,
                                    )
                                else:
                                    # Standard 2D plots with marginal plots
                                    if plot_type == "Scatter":
                                        fig = px.scatter(
                                            filtered_df,
                                            x=x_axis,
                                            y=y_axis,
                                            color="status",
                                            template=template,
                                            hover_data=["trial_id", "ts_start"],
                                            marginal_x="histogram" if marginal_plot else None,
                                            marginal_y="histogram" if marginal_plot else None,
                                        )
                                    elif plot_type == "Line":
                                        fig = px.line(
                                            filtered_df.sort_values(x_axis),
                                            x=x_axis,
                                            y=y_axis,
                                            color="status",
                                            template=template,
                                            markers=True,
                                        )
                                    elif plot_type == "Box":
                                        fig = px.box(
                                            filtered_df,
                                            x=x_axis,
                                            y=y_axis,
                                            color="status",
                                            template=template,
                                            points="all",
                                        )
                                    else:  # Violin
                                        fig = px.violin(
                                            filtered_df,
                                            x=x_axis,
                                            y=y_axis,
                                            color="status",
                                            template=template,
                                            box=True,
                                            points="all",
                                        )

                                    # Add trend line for appropriate plot types
                                    if show_trend and plot_type in ["Scatter", "Line"]:
                                        try:
                                            x_data = filtered_df[x_axis].astype(float)
                                            y_data = filtered_df[y_axis].astype(float)

                                            # Calculate trend line
                                            z = np.polyfit(x_data, y_data, 1)
                                            p = np.poly1d(z)

                                            # Add trend line trace
                                            fig.add_trace(
                                                go.Scatter(
                                                    x=x_data,
                                                    y=p(x_data),
                                                    name=f"Trend (R²={stats.pearsonr(x_data, y_data)[0]**2:.3f})",
                                                    line=dict(color="red", dash="dash"),
                                                    showlegend=True,
                                                )
                                            )
                                        except Exception as e:
                                            st.warning(f"Could not add trend line: {str(e)}")

                                # Update layout
                                fig.update_layout(
                                    title=dict(
                                        text=f"{y_axis} vs {x_axis}", x=0.5, xanchor="center"
                                    ),
                                    showlegend=True,
                                    height=600,
                                )

                                # Display plot
                                st.plotly_chart(fig, use_container_width=True)

                                # Show statistics if enabled
                                if show_stats:
                                    with st.expander("📊 Statistical Analysis", expanded=False):
                                        try:
                                            # Basic statistics
                                            col1, col2 = st.columns(2)
                                            with col1:
                                                st.write("X-axis Statistics:")
                                                st.write(filtered_df[x_axis].describe())
                                            with col2:
                                                st.write("Y-axis Statistics:")
                                                st.write(filtered_df[y_axis].describe())

                                            # Correlation analysis
                                            if (
                                                filtered_df[x_axis].dtype.kind in "biufc"
                                                and filtered_df[y_axis].dtype.kind in "biufc"
                                            ):
                                                pearson_corr = stats.pearsonr(
                                                    filtered_df[x_axis], filtered_df[y_axis]
                                                )
                                                spearman_corr = stats.spearmanr(
                                                    filtered_df[x_axis], filtered_df[y_axis]
                                                )
                                                st.write("### Correlation Analysis")
                                                st.write(
                                                    f"Pearson correlation: {pearson_corr[0]:.4f} (p-value: {pearson_corr[1]:.4f})"
                                                )
                                                st.write(
                                                    f"Spearman correlation: {spearman_corr[0]:.4f} (p-value: {spearman_corr[1]:.4f})"
                                                )
                                        except Exception as e:
                                            st.write(
                                                "Could not calculate some statistics (non-numeric data or other error)"
                                            )

                                # Save plot functionality
                                if save_plots:
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        # Save as HTML (interactive)
                                        html_filename = f"{x_axis}_vs_{y_axis}_{plot_type}.html"
                                        fig.write_html(html_filename)
                                        with open(html_filename, "rb") as f:
                                            st.download_button(
                                                label="Download Interactive Plot (HTML)",
                                                data=f,
                                                file_name=html_filename,
                                                mime="text/html",
                                            )
                                    with col2:
                                        # Save as PNG (static)
                                        png_filename = f"{x_axis}_vs_{y_axis}_{plot_type}.png"
                                        fig.write_image(png_filename)
                                        with open(png_filename, "rb") as f:
                                            st.download_button(
                                                label="Download Static Plot (PNG)",
                                                data=f,
                                                file_name=png_filename,
                                                mime="image/png",
                                            )

                                st.markdown("---")  # Visual separator between plots

                except Exception as e:
                    st.error(f"An error occurred during visualization: {str(e)}")
                    st.exception(e)

        with tab4:
            st.header("Correlation of Target Column With Parameters")
            try:
                plot_heatmap(df)
                plot_correlation_table_target(df, target_col)
            except:
                st.write("Correlation Heatmap not available")

            try:
                st.subheader("Mlos_Viz Metrics")
                exp = storage.experiments[selected_experiment_id]
                st.set_option("deprecation.showPyplotGlobalUse", False)
                fig = mlos_viz.plot(exp)
                st.pyplot(fig)
            except:
                st.write("Mlos_Viz Metrics not available")

        with tab5:
            st.header("Compare Two Configurations")
            try:
                available_result_columns = [col for col in df.columns if col.startswith("result")]
                target_col_config = st.selectbox(
                    "Select a Result Column", available_result_columns, key="t_col"
                )
                config_id_1 = st.selectbox(
                    "Select First Configuration ID", df["tunable_config_id"].unique()
                )
                config_id_2 = st.selectbox(
                    "Select Second Configuration ID", df["tunable_config_id"].unique()
                )
                compare_whisker_plots(df, target_col_config, config_id_1, config_id_2)
                plot_violin_plot(df, target_col_config, config_id_1, config_id_2)
            except:
                st.write("Comparison Plots not available")

            try:
                compare_score_distributions(df, target_col, config_id_1, config_id_2)
            except:
                st.write("Score Distributions not available")

            try:
                display_config_details(storage.experiments[selected_experiment_id])
            except:
                st.write("Config Details not available")

        with tab6:
            st.header("Compare Multiple Experiments")
            try:
                experiment_ids = list(storage.experiments.keys())
                selected_experiment_ids = st.multiselect("Select Experiment IDs", experiment_ids)

                target_col_for_comparison = st.selectbox(
                    "Select Target Column for Comparison",
                    (
                        [
                            col
                            for col in storage.experiments[
                                selected_experiment_ids[0]
                            ].results_df.columns
                            if col.startswith("result")
                        ]
                        if selected_experiment_ids
                        else []
                    ),
                )

                compare_multiple_experiments(
                    selected_experiment_ids, storage, target_col_for_comparison
                )
            except Exception as e:
                st.write("Multiple Experiments Comparison not available due to error: ", e)

        with tab7:
            st.header("ChatGPT Explanation")
            explanation = "Click the button to fetch the experiment explanation."
            if st.button("Fetch Experiment Explanation"):
                try:
                    explanation = get_experiment_explanation(selected_experiment_id)
                except:
                    explanation = "Experiment explanation not available."
            st.subheader("Experiment Explanation")
            st.write(explanation)

        #######################################
        # NEW TAB: Statistical Significance
        #######################################
        with tab8:
            st.header("Statistical Significance (Based on a Result Column)")

            # 1. Let user pick which result column to analyze
            df = storage.experiments[selected_experiment_id].results_df
            result_cols = [c for c in df.columns if c.startswith("result")]
            if not result_cols:
                st.warning("No columns found that start with 'result'.")
            else:
                chosen_result_col = st.selectbox(
                    "Select Result Column for Statistical Test:", options=result_cols, index=0
                )

                # 2. Select test type
                test_type = st.selectbox(
                    "Select Statistical Test:",
                    options=["ttest", "mannwhitney"],
                    index=0,
                    help="Choose a test: 'ttest' (two-sample t-test) or 'mannwhitney' (non-parametric).",
                )

                # 3. Significance level alpha
                alpha = st.number_input(
                    "Significance Level (alpha)",
                    min_value=0.001,
                    max_value=0.1,
                    value=0.05,
                    step=0.01,
                )

                # 4. Perform pairwise tests
                #    Group by default on "tunable_config_id"; you can also gather
                #    unique config.* columns and group if you prefer.
                if st.button("Run Pairwise Tests"):
                    st.write(
                        f"Performing pairwise {test_type} on `{chosen_result_col}`, alpha={alpha} ..."
                    )
                    results_df = run_pairwise_stat_tests(
                        df=df,
                        result_col=chosen_result_col,
                        group_col="tunable_config_id",
                        alpha=alpha,
                        test_type=test_type,
                    )

                    if results_df.empty:
                        st.warning("No pairs or no valid data to compare.")
                    else:
                        # 5. Display results
                        st.dataframe(results_df)

                        # Optionally highlight significant pairs
                        st.write("Significant Pairs:")
                        significant_pairs = results_df[results_df["Significant"] == True]
                        if significant_pairs.empty:
                            st.info(
                                "No significant differences found at alpha = {:.3f}".format(alpha)
                            )
                        else:
                            st.write(significant_pairs)
            with tab9:
                st.header("Parallel Coordinates Plot")
                st.write(
                    "Explore multi-dimensional relationships between configuration parameters and metrics."
                )

                parallel_columns = st.multiselect(
                    "Select Columns for Parallel Plot",
                    options=config_columns + result_columns,
                    default=config_columns[:3] + result_columns[:2],
                    help="Choose multiple columns to include in the parallel coordinates plot.",
                )

                if parallel_columns:
                    color_metric = st.selectbox(
                        "Select Metric for Coloring",
                        options=result_columns,
                        help="Choose a result metric to color-code the parallel coordinates.",
                    )
                    fig = px.parallel_coordinates(
                        df,
                        dimensions=parallel_columns,
                        color=color_metric,
                        color_continuous_scale=px.colors.diverging.Tealrose,
                        title="Parallel Coordinates Plot",
                        labels={
                            col: col.replace("config.", "").replace("_", " ").title()
                            for col in parallel_columns
                        },
                        template="plotly_white",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Select columns to generate the parallel coordinates plot.")


else:
    st.warning("Storage configuration not loaded. Cannot display experiments.")
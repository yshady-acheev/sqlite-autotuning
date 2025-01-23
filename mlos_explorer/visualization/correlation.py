import plotly.express as px
import pandas as pd


def plot_heatmap(df: pd.DataFrame):
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
    return fig


def plot_correlation_table_target(df: pd.DataFrame, target_col: str):
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
    return fig

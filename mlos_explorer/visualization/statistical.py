from scipy.stats import ttest_ind, mannwhitneyu, gaussian_kde
import pandas as pd
import numpy as np
import plotly.graph_objects as go


def run_pairwise_stat_tests(
    df: pd.DataFrame,
    result_col: str,
    group_col: str = "tunable_config_id",
    alpha: float = 0.05,
    test_type: str = "ttest",
) -> pd.DataFrame:
    df = df.dropna(subset=[result_col]).copy()
    df = df[np.isfinite(df[result_col])]
    df[result_col] = pd.to_numeric(df[result_col], errors="coerce")

    configs = df[group_col].unique()
    results = []

    for i in range(len(configs)):
        for j in range(i + 1, len(configs)):
            cfg_i, cfg_j = configs[i], configs[j]
            data_i = df.loc[df[group_col] == cfg_i, result_col]
            data_j = df.loc[df[group_col] == cfg_j, result_col]

            if data_i.empty or data_j.empty:
                continue

            if test_type == "mannwhitney":
                stat, pval = mannwhitneyu(data_i, data_j, alternative="two-sided")
            else:
                stat, pval = ttest_ind(data_i, data_j, equal_var=False, nan_policy="omit")

            results.append(
                {
                    "Config_A": cfg_i,
                    "Config_B": cfg_j,
                    "N_A": len(data_i),
                    "N_B": len(data_j),
                    "Test_Statistic": stat,
                    "p-value": pval,
                    "Significant": pval < alpha,
                }
            )

    return pd.DataFrame(results)


def compare_score_distributions(
    df: pd.DataFrame, target_col: str, config_id_1: int, config_id_2: int
):
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")

    config_1_data = df[df["tunable_config_id"] == config_id_1][target_col].dropna()
    config_2_data = df[df["tunable_config_id"] == config_id_2][target_col].dropna()

    if config_1_data.empty or config_2_data.empty:
        raise ValueError("One or both configuration IDs do not exist in the DataFrame.")

    kde_1 = gaussian_kde(config_1_data)
    kde_2 = gaussian_kde(config_2_data)

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

    return fig

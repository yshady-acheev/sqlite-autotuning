import pandas as pd


def count_categorical_values(df: pd.DataFrame) -> str:
    categorical_counts = {}
    for col in df.select_dtypes(include=["object", "category"]).columns:
        counts = df[col].value_counts().to_dict()
        categorical_counts[col] = counts

    count_str = "Categorical Counts:\n"
    for col, counts in categorical_counts.items():
        count_str += f"{col}:\n"
        for value, count in counts.items():
            count_str += f"  {value}: {count}\n"

    return count_str

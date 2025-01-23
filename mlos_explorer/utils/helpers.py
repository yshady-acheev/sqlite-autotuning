import pandas as pd
import numpy as np


def ensure_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    """Convert column to numeric, handling errors."""
    return pd.to_numeric(df[column], errors="coerce")


def filter_valid_data(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """Filter DataFrame to keep only rows with valid numeric data in specified columns."""
    return df.dropna(subset=columns)[columns].apply(pd.to_numeric, errors="coerce")

"""Diagnostic script — run this BEFORE editing any parser.
Prints exact column names and sample values from both CSVs.
"""
import pandas as pd
from pathlib import Path

DATA = Path(__file__).parent / 'data'


def inspect(path: Path, sep: str = ',', nrows: int = 3):
    print(f"\n{'='*60}")
    print(f"FILE: {path.name}  (sep={repr(sep)})")
    print(f"{'='*60}")
    try:
        df = pd.read_csv(path, sep=sep, encoding='utf-8', nrows=nrows, dtype=str)
        print(f"Columns ({len(df.columns)}):")
        for col in df.columns:
            sample = repr(df[col].iloc[0]) if len(df) > 0 else 'N/A'
            print(f"  '{col}': {sample}")
    except Exception as e:
        print(f"  ERROR: {e}")


if __name__ == '__main__':
    inspect(DATA / 'scimagojr_2025.csv', sep=';')
    inspect(DATA / 'doaj.csv', sep=',')

from __future__ import annotations
from pathlib import Path
import pandas as pd
from src.core.schemas import EvalConfig


class ResultComparator:
    """Compare agent output files against reference files using pandas.
    Computes T1 objective baseline score.

    Scoring dimensions:
    - Column match: 30% — do we have the right columns?
    - Row match: 30% — do we have the right number of rows?
    - Value match: 40% — do cell values match?
    """

    def compare(
        self,
        output_path: str,
        reference_path: str,
        eval_config: EvalConfig,
    ) -> float:
        output_file = Path(output_path)
        ref_file = Path(reference_path)

        if not output_file.exists() or not ref_file.exists():
            return 0.0

        try:
            output_df = self._read_file(output_file)
            ref_df = self._read_file(ref_file)
        except Exception:
            return 0.0

        output_df, ref_df = self._apply_ignore_rules(
            output_df, ref_df, eval_config.ignore_rules
        )
        return self._compute_similarity(output_df, ref_df)

    def _read_file(self, path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix == ".xlsx":
            return pd.read_excel(path, sheet_name=0)
        elif suffix == ".csv":
            return pd.read_csv(path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    def _apply_ignore_rules(
        self,
        output_df: pd.DataFrame,
        ref_df: pd.DataFrame,
        ignore_rules: list,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        out = output_df.copy()
        ref = ref_df.copy()
        for rule in ignore_rules:
            if rule.type == "column" and rule.columns:
                cols_to_drop = [c for c in rule.columns if c in out.columns]
                out = out.drop(columns=cols_to_drop, errors="ignore")
                ref = ref.drop(columns=cols_to_drop, errors="ignore")
        return out, ref

    def _compute_similarity(
        self, output_df: pd.DataFrame, ref_df: pd.DataFrame
    ) -> float:
        scores = []

        # Column match (30%)
        out_cols = set(output_df.columns)
        ref_cols = set(ref_df.columns)
        if len(ref_cols) == 0:
            col_score = 100.0
        else:
            intersection = out_cols & ref_cols
            col_score = (len(intersection) / len(ref_cols)) * 100
        scores.append(col_score * 0.30)

        # Row match (30%)
        out_rows = len(output_df)
        ref_rows = len(ref_df)
        if ref_rows == 0:
            row_score = 100.0
        else:
            row_score = max(0, 100 - abs(out_rows - ref_rows) / ref_rows * 100)
        scores.append(row_score * 0.30)

        # Value match (40%)
        value_score = 100.0
        common_cols = list(out_cols & ref_cols)
        if common_cols and ref_rows > 0:
            match_count = 0
            total = 0
            try:
                for col in common_cols:
                    out_vals = output_df[col].reset_index(drop=True).astype(str)
                    ref_vals = ref_df[col].reset_index(drop=True).astype(str)
                    for i in range(min(len(out_vals), len(ref_vals))):
                        if out_vals[i] == ref_vals[i]:
                            match_count += 1
                        total += 1
                if total > 0:
                    value_score = (match_count / total) * 100
            except Exception:
                value_score = 0.0
        scores.append(value_score * 0.40)

        return max(0.0, min(100.0, sum(scores)))

import pandas as pd
import pytest
from src.evaluator.result_comparator import ResultComparator
from src.core.schemas import EvalConfig, IgnoreRule


@pytest.fixture
def tmp_output_dir(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    ref_dir = tmp_path / "reference"
    ref_dir.mkdir()

    output_df = pd.DataFrame({"A": [1, 2], "B": [3, 4], "K": [99, 100]})
    ref_df = pd.DataFrame({"A": [1, 2], "B": [3, 4], "K": [99, 100]})

    output_path = output_dir / "result.xlsx"
    ref_path = ref_dir / "answer.xlsx"
    output_df.to_excel(output_path, index=False)
    ref_df.to_excel(ref_path, index=False)

    return output_path, ref_path


def test_perfect_match_scores_100(tmp_output_dir):
    output_path, ref_path = tmp_output_dir
    comparator = ResultComparator()
    config = EvalConfig(compare_style=False, ignore_rules=[])
    score = comparator.compare(output_path=str(output_path), reference_path=str(ref_path), eval_config=config)
    assert score == 100.0


def test_column_ignore_rule(tmp_output_dir):
    output_path, ref_path = tmp_output_dir
    comparator = ResultComparator()
    config = EvalConfig(compare_style=False, ignore_rules=[IgnoreRule(type="column", sheet="Sheet1", columns=["K"])])
    score = comparator.compare(output_path=str(output_path), reference_path=str(ref_path), eval_config=config)
    assert score == 100.0


def test_mismatched_data_deducts_points(tmp_output_dir, tmp_path):
    output_path, ref_path = tmp_output_dir
    output_df = pd.read_excel(output_path)
    output_df.loc[0, "A"] = 999
    output_df.to_excel(output_path, index=False)
    comparator = ResultComparator()
    config = EvalConfig()
    score = comparator.compare(output_path=str(output_path), reference_path=str(ref_path), eval_config=config)
    assert score < 100.0
    assert score > 0.0


def test_missing_file_returns_zero():
    comparator = ResultComparator()
    score = comparator.compare(output_path="/nonexistent/output.xlsx", reference_path="/nonexistent/ref.xlsx", eval_config=EvalConfig())
    assert score == 0.0

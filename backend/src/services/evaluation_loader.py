from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from src.core.schemas import EvaluationInput, Manifest, RunMetadata, TraceQuality


class EvaluationRunBundle(BaseModel):
    manifest: Manifest
    run_metadata: RunMetadata
    inputs: list[EvaluationInput]


class EvaluationLoader:
    """Load an offline evaluation run from the agreed directory layout."""

    def __init__(self, benchmark_root: str | Path):
        self.benchmark_root = Path(benchmark_root)

    def load_manifest(self) -> Manifest:
        manifest_path = self.benchmark_root / "manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return Manifest.model_validate(data)

    def load_run(self, run_label: str) -> EvaluationRunBundle:
        manifest = self.load_manifest()
        run_dir = self.benchmark_root / "runs" / run_label
        metadata = self._load_run_metadata(run_dir, run_label)
        inputs: list[EvaluationInput] = []

        for question in manifest.questions:
            question_run_dir = run_dir / question.question_id
            for attempt_index, attempt_dir in self._discover_attempt_dirs(question_run_dir):
                inputs.append(
                    EvaluationInput(
                        question=question,
                        trace_path=attempt_dir / "trace.jsonl",
                        output_dir=attempt_dir / "输出结果",
                        reference_paths=[
                            self.benchmark_root / ref for ref in question.reference_files
                        ],
                        attempt_index=attempt_index,
                        trace_quality=metadata.trace_quality,
                        is_partial_score=metadata.trace_quality == TraceQuality.DEGRADED,
                    )
                )

        return EvaluationRunBundle(
            manifest=manifest,
            run_metadata=metadata,
            inputs=inputs,
        )

    def _load_run_metadata(self, run_dir: Path, run_label: str) -> RunMetadata:
        meta_path = run_dir / "run_meta.json"
        if not meta_path.exists():
            return RunMetadata(run_label=run_label)

        data = json.loads(meta_path.read_text(encoding="utf-8"))
        data.setdefault("run_label", run_label)
        return RunMetadata.model_validate(data)

    def _discover_attempt_dirs(self, question_run_dir: Path) -> list[tuple[int, Path]]:
        if not question_run_dir.exists():
            return [(1, question_run_dir)]

        attempt_dirs: list[tuple[int, Path]] = []
        for child in sorted(question_run_dir.iterdir()):
            if not child.is_dir() or not child.name.startswith("attempt-"):
                continue

            suffix = child.name.removeprefix("attempt-")
            if suffix.isdigit():
                attempt_dirs.append((int(suffix), child))

        if attempt_dirs:
            return attempt_dirs

        return [(1, question_run_dir)]

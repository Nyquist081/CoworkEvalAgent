from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.runs import _build_pipeline
from src.services.skill_ab_experiment import (
    SkillABExperimentService,
    SkillABRunSpec,
)


router = APIRouter(prefix="/experiments")


class SkillABExperimentRequest(BaseModel):
    benchmark_root: str
    preset: str = "claude-code"
    baseline_run_label: str = "security-baseline-no-skill"
    skill_run_label: str = "security-with-skill"
    judge_enabled: bool = False
    skill_version: str = ""


def _build_skill_ab_service() -> SkillABExperimentService:
    return SkillABExperimentService(pipeline_factory=_build_pipeline)


@router.post("/skill-ab", response_model=dict)
async def run_skill_ab_experiment(request: SkillABExperimentRequest):
    service = _build_skill_ab_service()
    try:
        return await service.run_experiment(
            SkillABRunSpec(
                benchmark_root=Path(request.benchmark_root),
                preset=request.preset,
                baseline_run_label=request.baseline_run_label,
                skill_run_label=request.skill_run_label,
                judge_enabled=request.judge_enabled,
                skill_version=request.skill_version,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID
from src.core.schemas import TaskRun, RunStatus

router = APIRouter(prefix="/runs")

# In-memory stub store (will be wired to real repos in main.py)
_runs_store: dict[UUID, TaskRun] = {}


@router.post("", response_model=TaskRun, status_code=201)
async def create_run(run: TaskRun):
    _runs_store[run.id] = run
    return run


@router.get("", response_model=list[TaskRun])
async def list_runs(benchmark_id: str | None = None, status: RunStatus | None = None):
    runs = list(_runs_store.values())
    if benchmark_id:
        runs = [r for r in runs if r.benchmark_id == benchmark_id]
    if status:
        runs = [r for r in runs if r.status == status]
    return runs


@router.get("/{run_id}", response_model=TaskRun)
async def get_run(run_id: UUID):
    run = _runs_store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{run_id}/trigger-judge", response_model=dict)
async def trigger_judge(run_id: UUID):
    run = _runs_store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    run.status = RunStatus.AWAITING_JUDGE
    return {"status": "judge_triggered", "run_id": str(run_id)}


@router.delete("/{run_id}", status_code=204)
async def delete_run(run_id: UUID):
    if run_id not in _runs_store:
        raise HTTPException(status_code=404, detail="Run not found")
    del _runs_store[run_id]

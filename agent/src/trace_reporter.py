from __future__ import annotations
from pathlib import Path
import httpx


class TraceReporter:
    """Uploads JSONL trace files to the CoworkEval backend API."""

    def __init__(self, base_url: str = "http://localhost:8000/coworkeval/v1"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def upload_trace(
        self,
        run_id: str,
        question_id: str,
        trace_path: Path | str,
    ) -> dict:
        """Upload a single trace file for a question in a run."""
        path = Path(trace_path)
        if not path.exists():
            return {"error": f"Trace file not found: {trace_path}"}

        content = path.read_text(encoding="utf-8")
        lines = [line for line in content.strip().split("\n") if line.strip()]

        response = await self.client.post(
            f"{self.base_url}/runs/{run_id}/traces",
            json={
                "question_id": question_id,
                "trace_lines": lines,
            },
        )
        response.raise_for_status()
        return response.json()

    async def upload_benchmark_results(
        self,
        run_id: str,
        trace_map: dict[str, Path],
    ) -> list[dict]:
        """Upload all trace files for a benchmark run."""
        results = []
        for question_id, trace_path in trace_map.items():
            try:
                result = await self.upload_trace(run_id, question_id, trace_path)
                results.append({"question_id": question_id, "status": "ok", "result": result})
            except Exception as e:
                results.append({"question_id": question_id, "status": "error", "error": str(e)})
        return results

    async def create_run(self, benchmark_id: str, judge_enabled: bool = True) -> dict:
        """Create a new evaluation run on the backend."""
        response = await self.client.post(
            f"{self.base_url}/runs",
            json={
                "benchmark_id": benchmark_id,
                "status": "PENDING",
                "judge_enabled": judge_enabled,
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_manifests(self) -> list[dict]:
        """List available manifests from the backend."""
        response = await self.client.get(f"{self.base_url}/manifests")
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self.client.aclose()

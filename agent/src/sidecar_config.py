from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class AgentCommandConfig(BaseModel):
    name: str
    command_template: str
    trace_path_template: str = "{workdir}/trace.jsonl"
    output_dir_template: str = "{workdir}/输出结果"

    def render_command(
        self,
        workdir: Path,
        prompt_file: Path,
        output_dir: Path,
        trace_path: Path,
    ) -> str:
        return self.command_template.format(
            workdir=str(workdir),
            prompt_file=str(prompt_file),
            output_dir=str(output_dir),
            trace_path=str(trace_path),
        )

    def render_trace_path(self, workdir: Path) -> Path:
        return Path(self.trace_path_template.format(workdir=str(workdir)))

    def render_output_dir(self, workdir: Path) -> Path:
        return Path(self.output_dir_template.format(workdir=str(workdir)))


class SidecarRunConfig(BaseModel):
    benchmark_root: Path
    run_label: str
    agent: AgentCommandConfig
    attempt_index: int = 1
    model: str = ""
    skill_version: str = ""

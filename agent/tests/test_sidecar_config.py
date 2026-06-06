from pathlib import Path

from src.sidecar_config import AgentCommandConfig, SidecarRunConfig


def test_agent_command_config_renders_template(tmp_path):
    config = AgentCommandConfig(
        name="fake-cli",
        command_template="python {prompt_file} --cwd {workdir} --out {output_dir}",
        trace_path_template="{workdir}/trace.jsonl",
        output_dir_template="{workdir}/输出结果",
    )

    rendered = config.render_command(
        workdir=tmp_path,
        prompt_file=tmp_path / "prompt.txt",
        output_dir=tmp_path / "输出结果",
        trace_path=tmp_path / "trace.jsonl",
    )

    assert str(tmp_path / "prompt.txt") in rendered
    assert str(tmp_path / "输出结果") in rendered


def test_sidecar_run_config_defaults():
    config = SidecarRunConfig(
        benchmark_root=Path("/tmp/evaluations/bench-1"),
        run_label="skill-v2",
        agent=AgentCommandConfig(
            name="fake-cli",
            command_template="echo ok",
        ),
    )

    assert config.attempt_index == 1
    assert config.agent.trace_path_template == "{workdir}/trace.jsonl"
    assert config.agent.output_dir_template == "{workdir}/输出结果"

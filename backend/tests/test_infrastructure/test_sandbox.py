import pytest
from pathlib import Path
from src.infrastructure.sandbox import EvalSandbox


@pytest.fixture
def sandbox(tmp_path):
    return EvalSandbox(run_id="test-run-001", base_path=str(tmp_path / "coworkeval"))


@pytest.mark.asyncio
async def test_setup_creates_directories(sandbox):
    sandbox_path = await sandbox.setup()
    assert Path(sandbox_path).exists()
    assert (Path(sandbox_path) / "output").exists()
    assert (Path(sandbox_path) / "workspace").exists()
    assert (Path(sandbox_path) / ".meta").exists()


@pytest.mark.asyncio
async def test_cleanup_removes_sandbox(sandbox):
    sandbox_path = await sandbox.setup()
    assert Path(sandbox_path).exists()
    await sandbox.cleanup()
    assert not Path(sandbox_path).exists()


@pytest.mark.asyncio
async def test_archive_output(sandbox):
    await sandbox.setup()
    output_file = sandbox.output_path / "test_result.xlsx"
    output_file.write_text("mock excel content")
    archive_path = await sandbox.archive_output()
    assert archive_path.exists()
    archived_files = list(archive_path.rglob("*"))
    assert any("test_result.xlsx" in str(f) for f in archived_files)


@pytest.mark.asyncio
async def test_sandbox_isolation(sandbox):
    sandbox_path_1 = await sandbox.setup()
    sandbox2 = EvalSandbox(run_id="test-run-002", base_path=sandbox.base_path)
    sandbox_path_2 = await sandbox2.setup()
    assert sandbox_path_1 != sandbox_path_2
    await sandbox.cleanup()
    await sandbox2.cleanup()

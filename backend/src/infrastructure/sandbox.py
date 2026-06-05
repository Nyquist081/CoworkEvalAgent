from __future__ import annotations
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


class EvalSandbox:
    """Creates and manages an isolated temp directory for a single TaskRun.

    Directory structure:
        {base_path}/{run_id}/
        ├── output/       # Agent output files
        ├── workspace/    # Agent working directory
        ├── global_data/  # → symlink to {base_path}/../global_data/
        └── .meta/        # Sandbox metadata
    """

    def __init__(self, run_id: str, base_path: str = "/tmp/coworkeval"):
        self.run_id = run_id
        self.base_path = Path(base_path)
        self.sandbox_path = self.base_path / str(run_id)
        self.output_path = self.sandbox_path / "output"
        self.workspace_path = self.sandbox_path / "workspace"
        self.meta_path = self.sandbox_path / ".meta"
        self.global_data_path = self.sandbox_path / "global_data"

    async def setup(self) -> str:
        """Create sandbox directory structure. Returns sandbox root path."""
        self.sandbox_path.mkdir(parents=True, exist_ok=True)
        self.output_path.mkdir(exist_ok=True)
        self.workspace_path.mkdir(exist_ok=True)
        self.meta_path.mkdir(exist_ok=True)

        global_data_root = self.base_path.parent / "global_data"
        if not self.global_data_path.exists():
            try:
                self.global_data_path.symlink_to(global_data_root, target_is_directory=True)
            except OSError:
                self.global_data_path.mkdir(exist_ok=True)

        meta = {
            "run_id": self.run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "cleaned": False,
        }
        (self.meta_path / "meta.json").write_text(json.dumps(meta))
        return str(self.sandbox_path)

    async def cleanup(self) -> None:
        """Remove the entire sandbox directory."""
        if self.sandbox_path.exists():
            shutil.rmtree(self.sandbox_path)

    async def archive_output(self) -> Path:
        """Copy output/ to a persistent archive location. Returns the archive path."""
        archive_root = self.base_path.parent / "archive"
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_path = archive_root / self.run_id / "output"

        if self.output_path.exists():
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            if archive_path.exists():
                shutil.rmtree(archive_path)
            shutil.copytree(self.output_path, archive_path)
        return archive_path

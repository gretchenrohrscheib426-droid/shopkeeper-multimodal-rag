import os
import subprocess
import time
from pathlib import Path
from knowledge.core.configuration import required
from knowledge.core.task_store import get_store
from knowledge.utils.client.local_models import GPU_LOCK
from knowledge.processor.import_processor.base import BaseNode
from knowledge.processor.import_processor.state import ImportGraphState


class PdfToMdNode(BaseNode):
    name = "pdf_to_md_node"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        source = Path(state["pdf_path"]).resolve()
        output = Path(state["file_dir"]) / "mineru"
        output.mkdir(parents=True, exist_ok=True)
        executable = Path(required("MINERU_EXECUTABLE"))
        if not executable.is_file():
            raise FileNotFoundError("Configured MinerU executable is missing")
        runner = os.getenv("MINERU_RUNNER", "")
        command = [str(executable)]
        if runner:
            python = Path(required("MINERU_PYTHON"))
            if not python.is_file() or not Path(runner).is_file():
                raise FileNotFoundError("Configured MinerU runner is missing")
            command = [str(python), runner]
        args = [
            *command,
            "-p",
            str(source),
            "-o",
            str(output),
            "--source",
            "local",
            "-b",
            os.getenv("MINERU_BACKEND", "hybrid-auto-engine"),
        ]
        started = time.monotonic()
        deadline = float(os.getenv("MINERU_TIMEOUT_SECONDS", "900"))
        with GPU_LOCK, (output / "mineru.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                args,
                shell=False,
                stdout=log,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUTF8": "1"},
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                while process.poll() is None:
                    get_store().check(state.get("task_id", ""))
                    if time.monotonic() - started > deadline:
                        raise TimeoutError("MinerU deadline exceeded")
                    time.sleep(0.2)
                if process.returncode != 0:
                    raise RuntimeError(
                        f"MinerU exited with code {process.returncode}; inspect task parser log"
                    )
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
        candidates = [
            x
            for x in output.rglob("*.md")
            if x.stem == source.stem and x.stat().st_size > 0
        ]
        if len(candidates) != 1:
            raise RuntimeError(
                "MinerU did not produce exactly one nonempty source Markdown file"
            )
        if not candidates[0].read_text(encoding="utf-8").strip():
            raise ValueError("MinerU Markdown is empty")
        return {"md_path": str(candidates[0])}

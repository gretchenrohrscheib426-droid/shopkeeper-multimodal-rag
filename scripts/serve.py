"""Single-worker local server with a graceful, local-file stop signal."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHOPKEEPER_ENV_FILE", str(ROOT / ".env.local"))
from knowledge.core.paths import get_local_base_dir
from knowledge.api.app import app
import uvicorn


async def main():
    directory = Path(get_local_base_dir())
    directory.mkdir(parents=True, exist_ok=True)
    stop = directory / "server.stop"
    stop.unlink(missing_ok=True)
    (directory / "server.json").write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "host": "127.0.0.1",
                "port": 8000,
                "started": time.time(),
            }
        ),
        encoding="utf-8",
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=8000, workers=1, timeout_graceful_shutdown=90
        )
    )

    async def watch():
        while not server.should_exit:
            if stop.exists():
                server.should_exit = True
                return
            await asyncio.sleep(0.5)

    watcher = asyncio.create_task(watch())
    try:
        await server.serve()
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
        stop.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())

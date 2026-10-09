"""Run the existing MinerU package with the compatible application dependencies.

No installation, cache deletion, or original environment modification occurs.
MINERU_EXISTING_SITE must identify the user's audited existing package directory.
"""

import os
import sys
from pathlib import Path

existing = Path(os.environ["MINERU_EXISTING_SITE"]).resolve()
if not (existing / "mineru/cli/client.py").is_file():
    raise FileNotFoundError("Audited existing MinerU package is missing")
sys.path.append(str(existing))
from mineru.cli.client import main

if __name__ == "__main__":
    main()

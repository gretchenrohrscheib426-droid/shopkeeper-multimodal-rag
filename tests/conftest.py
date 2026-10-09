import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHOPKEEPER_ENV_FILE", str(ROOT / ".env.example"))

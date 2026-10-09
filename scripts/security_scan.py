"""Scan the exact staged Git blobs. Report locations/categories, never secret values."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", required=True)
    parser.parse_args()
    from dotenv import dotenv_values

    private = dotenv_values(ROOT / ".env.local", interpolate=False)
    secrets = [
        str(private[k]).encode()
        for k in (
            "OPENAI_API_KEY",
            "APP_API_TOKEN",
            "MINIO_ACCESS_KEY",
            "MINIO_SECRET_KEY",
        )
        if private.get(k) and len(str(private[k])) >= 6
    ]
    patterns = {
        "credential_pattern": re.compile(
            rb"(?:sk-[A-Za-z0-9._-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
        ),
        "private_endpoint": re.compile(
            rb"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
        ),
        "personal_path": re.compile(
            rb"[CDE]:[\\/](?:Users|OneDrive|zhangguizhiku|ai_models|Miniconda3)[\\/]",
            re.I,
        ),
        "workspace_identity": re.compile(
            rb"https://ws-[a-z0-9]+\.cn-beijing\.maas\.aliyuncs\.com"
        ),
    }
    files = [
        p.decode("utf-8") for p in git("ls-files", "-z", "--cached").split(b"\0") if p
    ]
    issues = []
    manifest = []
    for name in files:
        data = git("show", ":" + name)
        path = Path(name)
        prohibited = (
            name.startswith(
                (
                    "data/",
                    ".venv",
                    "knowledge/test/",
                    "artifacts/verification/baseline/",
                )
            )
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.suffix.lower()
            in {".zip", ".safetensors", ".bin", ".pt", ".pth", ".sqlite3"}
        )
        if prohibited:
            issues.append({"file": name, "reason": "excluded_input"})
        if path.suffix.lower() in {".png", ".pdf", ".docx"}:
            if not name.startswith(("examples/public/manual/", "docs/assets/")):
                issues.append({"file": name, "reason": "unapproved_binary_location"})
        else:
            for reason, pattern in patterns.items():
                for match in pattern.finditer(data):
                    issues.append(
                        {
                            "file": name,
                            "line": data[: match.start()].count(b"\n") + 1,
                            "reason": reason,
                        }
                    )
        if any(secret in data for secret in secrets):
            issues.append({"file": name, "reason": "local_secret_exact_match"})
        if name not in {'artifacts/release_validation/source-manifest.json',
                        'artifacts/release_validation/security.json'}:
            manifest.append(
                {
                    "path": name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
            )
    report = {
        "scope": "exact staged blobs; heuristics and local secret matching, not a full security audit",
        "status": "PASS" if files and not issues else "FAIL",
        "files": len(files),
        "issues": issues,
    }
    output = ROOT / "artifacts/release_validation"
    output.mkdir(parents=True, exist_ok=True)
    (output / "security.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Hashes describe the scanned index at this point. The manifest/report are not their own hash inputs.
    (output / "source-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return report["status"] != "PASS"


if __name__ == "__main__":
    raise SystemExit(main())

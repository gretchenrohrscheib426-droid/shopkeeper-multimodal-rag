"""Real text + image calls; records provider responses and never records secrets."""

import json
import os
import sys
import time
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHOPKEEPER_ENV_FILE", str(ROOT / ".env.local"))
from knowledge.core.configuration import required
from knowledge.utils.client.ai_clients import AIClients
from knowledge.processor.import_processor.nodes.md_to_img_node import MarkDownToImgNode


def main():
    llm = AIClients.get_llm_client(False)
    vlm = AIClients.get_vlm_client()
    report = {
        "kind": "real_remote_models",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config_file": os.environ["SHOPKEEPER_ENV_FILE"],
        "model_config_source": os.getenv("MODEL_CONFIG_SOURCE"),
        "base_url": str(vlm.base_url),
        "llm_base_url": str(llm.openai_api_base),
        "same_key": llm.openai_api_key.get_secret_value() == vlm.api_key,
        "key_present": bool(vlm.api_key),
        "calls": {},
    }

    def run(name, model, call):
        started = time.monotonic()
        try:
            result = call()
            if not result or not str(result).strip():
                raise ValueError("Empty model response")
            report["calls"][name] = {
                "status": "PASS",
                "model": model,
                "content": str(result),
                "seconds": round(time.monotonic() - started, 3),
            }
        except Exception as exc:
            # Never serialize raw SDK exceptions or request headers (may hold credentials).
            body = getattr(exc, "body", {})
            if isinstance(body, dict) and isinstance(body.get("error"), dict):
                body = body["error"]
            details = {
                k: body[k]
                for k in ("code", "type", "message")
                if isinstance(body, dict) and isinstance(body.get(k), str)
            }
            details = {
                k: re.sub(
                    r"sk-[A-Za-z0-9._-]+",
                    "[REDACTED]",
                    v.replace(vlm.api_key, "[REDACTED]"),
                )
                for k, v in details.items()
            }
            report["calls"][name] = {
                "status": "FAIL",
                "model": model,
                "error_type": type(exc).__name__,
                "provider_error": details,
                "http_status": getattr(exc, "status_code", None),
                "seconds": round(time.monotonic() - started, 3),
            }
        print(json.dumps({name: report["calls"][name]}, ensure_ascii=False), flush=True)

    run(
        "text",
        required("LLM_DEFAULT_MODEL"),
        lambda: llm.invoke("请用一句中文说明：文档问答为什么需要引用原文？").content,
    )
    image_node = MarkDownToImgNode()
    run(
        "image_summary",
        required("VL_MODEL"),
        lambda: image_node._summarize(
            ROOT / "examples/public/manual/流程 图.png",
            "image/png",
            "请描述图片中的流程、顺序与文字。",
        ),
    )
    if report["calls"]["image_summary"]["status"] == "PASS":
        report["calls"]["image_summary"].update(
            token_usage=image_node.last_usage, response_id=image_node.last_response_id
        )
    report["status"] = (
        "PASS"
        if all(c["status"] == "PASS" for c in report["calls"].values())
        and report["same_key"]
        else "FAIL"
    )
    output = ROOT / "artifacts/verification/baseline/model-plus-auth.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Source-anchored, real-service retrieval evaluation and full RAG measurements.

Run explicitly: each question invokes the configured paid provider. Only the full
Rerank variant generates an answer. Baselines compare retrieval rankings with the
same corpus, query, candidate budget, and real HyDE output from that query run.
"""

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHOPKEEPER_ENV_FILE", str(ROOT / ".env.local"))
from knowledge.core.configuration import required
from knowledge.core.task_store import get_store
from knowledge.utils import document_store
from knowledge.utils.client.storage_clients import StorageClients
from knowledge.utils.retrieval import retrieve
from knowledge.service.query_service import QueryService


def normalize(text):
    return text.translate(str.maketrans({"\u00a0": " ", "\u2007": " ", "\u202f": " "}))


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * p
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return round(values[low] + (values[high] - values[low]) * (position - low), 3)


def average(values):
    return round(statistics.mean(values), 6) if values else None


def ranking_metrics(ids, gold):
    if not gold:
        return None
    return {
        "recall_at_5": len(set(ids[:5]) & gold) / len(gold),
        "recall_at_10": len(set(ids[:10]) & gold) / len(gold),
        "mrr_at_10": next(
            (1 / (i + 1) for i, k in enumerate(ids[:10]) if k in gold), 0
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "examples/public/evaluation20.json"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/verification/baseline/evaluation",
    )
    parser.add_argument("--split", choices=["all", "dev", "frozen"], default="all")
    parser.add_argument("--max-questions", type=int, default=60)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.dataset.read_text(encoding="utf-8"))
    questions = [
        q for q in data["questions"] if args.split == "all" or q["split"] == args.split
    ]
    if len(questions) > args.max_questions:
        raise ValueError("Dataset exceeds explicit question budget")
    available = document_store.active_documents("local")
    scope = []
    source_docs = {}
    for key, title in data["sources"].items():
        candidates = [d for d in available if d["file_title"] == title]
        if len(candidates) != 1:
            raise ValueError("Select one unambiguous active document for " + key)
        source_docs[key] = candidates[0]
        scope.append(candidates[0])
    client = StorageClients.get_milvus_client()
    all_chunks = {}
    for doc in scope:
        for chunk in client.get(
            required("CHUNKS_COLLECTION"),
            doc["chunk_ids"],
            output_fields=["chunk_id", "content", "document_id", "version"],
        ):
            all_chunks[chunk["chunk_id"]] = dict(chunk)
    gold = {}
    for q in questions:
        wanted = source_docs[q["source"]]["document_id"]
        gold[q["id"]] = {
            key
            for key, c in all_chunks.items()
            if c["document_id"] == wanted
            and q["anchor"]
            and normalize(q["anchor"]) in normalize(c["content"])
        }
        if q["answerable"] and not gold[q["id"]]:
            raise ValueError("Gold anchor missing in committed corpus: " + q["id"])
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.validate_only and (args.output / "questions.jsonl").exists():
        raise ValueError(
            "Output already has measured results; choose a new output directory"
        )
    manifest = {
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "annotation": data["annotation"],
        "corpus": [
            {
                "document_id": d["document_id"],
                "version": d["version"],
                "chunks": d["chunk_count"],
            }
            for d in scope
        ],
        "model": required("LLM_DEFAULT_MODEL"),
        "embedding_revision": required("EMBEDDING_MODEL_REVISION"),
        "reranker_revision": required("RERANKER_MODEL_REVISION"),
        "candidate_budget": 10,
        "rrf_k": 60,
        "web_enabled": False,
        "frozen_before_run": True,
        "tuning_performed": False,
        "question_count": len(questions),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "answer_mode": "Only full rerank pipeline; other variants measure retrieval",
        "citation_support_metric": "ID and literal quote existence; not semantic entailment",
        "cost_currency": None,
        "cost_reason": "No verified workspace billing rate supplied; report observed tokens only",
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if args.validate_only:
        print(
            json.dumps(
                {
                    "validated_questions": len(questions),
                    "corpus_chunks": len(all_chunks),
                }
            )
        )
        return 0
    store = get_store()
    results = []
    service = QueryService()

    def run(question, session):
        task = uuid.uuid4().hex
        store.create(task, "local", "query")
        service.reserve_session("local", session)
        start = time.monotonic()
        service.run_query_graph(
            session,
            task,
            question,
            True,
            "local",
            [d["document_id"] for d in scope],
            "rerank",
            10,
        )
        return store.get(task), round(time.monotonic() - start, 3)

    for index, q in enumerate(questions):
        session = "eval-" + uuid.uuid4().hex
        prior = None
        if q.get("prior_question"):
            preceding, elapsed = run(q["prior_question"], session)
            prior = {
                "task_id": preceding["id"],
                "status": preceding["status"],
                "seconds": elapsed,
            }
        task, elapsed = run(q["question"], session)
        payload = task["results"].get("query", {})
        row = {
            "id": q["id"],
            "split": q["split"],
            "category": q["category"],
            "question": q["question"],
            "task_id": task["id"],
            "task_status": task["status"],
            "end_to_end_seconds": elapsed,
            "model_load_included": index == 0,
            "durations": task["durations"],
            "gold_chunk_ids": sorted(gold[q["id"]]),
            "answerable": q["answerable"],
            "answer": payload.get("answer"),
            "answer_kind": payload.get("answer_kind"),
            "usage": payload.get("usage", {}),
            "prior": prior,
            "degraded": payload.get("degraded"),
            "answer_attempts": payload.get("answer_attempts", []),
            "error": task["results"].get("error"),
        }
        metrics = {}
        rankings = {}
        dense_start = time.monotonic()
        try:
            dense = retrieve(
                payload.get("rewritten_query") or q["question"],
                {
                    "owner": "local",
                    "document_scope": scope,
                    "retrieval_mode": "dense",
                    "candidate_limit": 10,
                },
                "dense",
            )
            rankings = {
                "dense": [d["chunk_id"] for d in dense],
                "hybrid": [d["chunk_id"] for d in payload.get("embedding_chunks", [])],
                "hyde_rrf": [d["chunk_id"] for d in payload.get("rrf_chunks", [])],
                "rerank": [d["chunk_id"] for d in payload.get("reranked_docs", [])],
            }
            metrics = {
                mode: ranking_metrics(ids, gold[q["id"]])
                for mode, ids in rankings.items()
            }
        except Exception as exc:
            row["dense_error_type"] = type(exc).__name__
        row["dense_only_seconds"] = round(time.monotonic() - dense_start, 3)
        row["rankings"] = rankings
        row["retrieval"] = metrics
        citations = payload.get("citations", [])
        valid = 0
        quotes = 0
        quote_valid = 0
        for citation in citations:
            original = all_chunks.get(citation.get("chunk_id"))
            valid += int(
                original is not None and original["version"] == citation["version"]
            )
            for quote in citation.get("quotes", []):
                quotes += 1
                quote_valid += int(
                    original is not None and quote in original["content"]
                )
        row["citations"] = {
            "count": len(citations),
            "valid_ids": valid,
            "quotes": quotes,
            "exact_source_quotes": quote_valid,
        }
        answer = normalize(payload.get("answer") or "")
        row["answer_terms_heuristic"] = (
            all(
                normalize(term).casefold() in answer.casefold()
                for term in q["answer_terms"]
            )
            if q["answerable"]
            else None
        )
        row["refusal_correct"] = (
            payload.get("answer_kind") == "no_evidence" if not q["answerable"] else None
        )
        # This app releases one validated answer event, so token-level TTFT is intentionally N/A.
        events = []
        cursor = 0
        while batch := store.events(task["id"], cursor):
            events.extend(batch)
            cursor = batch[-1]["seq"]
        delta = next((e for e in events if e["event"] == "delta"), None)
        row["time_to_validated_answer_seconds"] = (
            round(delta["created"] - task["created"], 3) if delta else None
        )
        results.append(row)
        with (args.output / "questions.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(
            json.dumps(
                {
                    "index": index + 1,
                    "id": q["id"],
                    "status": task["status"],
                    "seconds": elapsed,
                    "citations": len(citations),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    summaries = {}
    for split in ["all", "dev", "frozen"]:
        selected = [r for r in results if split == "all" or r["split"] == split]
        if not selected:
            continue
        answerable = [r for r in selected if r["answerable"]]
        negatives = [r for r in selected if not r["answerable"]]
        count_c = sum(r["citations"]["count"] for r in selected)
        count_q = sum(r["citations"]["quotes"] for r in selected)
        hot = [
            r["end_to_end_seconds"] for r in selected if not r["model_load_included"]
        ]
        summaries[split] = {
            "questions": len(selected),
            "completed": sum(r["task_status"] == "completed" for r in selected),
            "failed": sum(r["task_status"] != "completed" for r in selected),
            "success_rate": average(
                [r["task_status"] == "completed" for r in selected]
            ),
            "hot_p50_seconds": percentile(hot, 0.5),
            "hot_p95_seconds": percentile(hot, 0.95),
            "refusal_correct": sum(bool(r["refusal_correct"]) for r in negatives),
            "refusal_total": len(negatives),
            "citation_id_valid_rate": sum(r["citations"]["valid_ids"] for r in selected)
            / count_c
            if count_c
            else None,
            "literal_quote_valid_rate": sum(
                r["citations"]["exact_source_quotes"] for r in selected
            )
            / count_q
            if count_q
            else None,
            "answer_terms_heuristic_rate": average(
                [r["answer_terms_heuristic"] for r in answerable]
            ),
            "retrieval": {
                mode: {
                    key: average(
                        [
                            (r["retrieval"].get(mode) or {}).get(key, 0)
                            for r in answerable
                        ]
                    )
                    for key in ["recall_at_5", "recall_at_10", "mrr_at_10"]
                }
                for mode in ["dense", "hybrid", "hyde_rrf", "rerank"]
            },
        }
    tokens = {
        key: sum(usage.get(key, 0) for r in results for usage in r["usage"].values())
        for key in ["input_tokens", "output_tokens", "total_tokens"]
    }
    summary = {
        "manifest": manifest,
        "splits": summaries,
        "observed_query_tokens": tokens,
        "ttft_seconds": None,
        "ttft_reason": "Validated whole-answer SSE, not raw model token streaming",
        "cold_first_query_seconds": results[0]["end_to_end_seconds"]
        if results
        else None,
        "completed_utc": datetime.now(timezone.utc).isoformat(),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return any(r["task_status"] != "completed" for r in results)


if __name__ == "__main__":
    raise SystemExit(main())

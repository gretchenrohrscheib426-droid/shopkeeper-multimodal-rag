# Shopkeeper Knowledge Workbench

A locally running multimodal document RAG application built on an existing course-derived project. PDF uses MinerU 2.7.1; DOCX uses a structural adapter; Markdown preserves local image references. Real image summaries, MinIO readback, BGE-M3 dense/sparse embeddings, Milvus retrieval, HyDE, RRF, reranking and cited answers are integrated with a FastAPI workbench.

The verified text model is **qwen-plus** and the vision model is **qwen3-vl-plus**, through the configured Model Studio workspace endpoint. `qwen3-plus` returned an actual model-not-found response in this workspace; it is not reported as passing.

The first 60-question run completed 59 tasks; the frozen 20-question subset completed all 20. One answer failed literal citation validation after a bounded repair and was not published. Warm end-to-end P50/P95 were 6.922/9.220 seconds. Citation existence is not semantic correctness. The small, agent-authored source-anchored dataset is not an independently annotated benchmark.

Start the audited local environment with `scripts/start-local.ps1`; access the localhost workbench with APP_API_TOKEN, never the model key. See the [Chinese README](README.md), [architecture](docs/ARCHITECTURE.md), [evaluation](docs/EVALUATION.md), [source guide](docs/CODE_GUIDE.md) and [verification report](docs/VERIFICATION.md).

No public online demo is claimed. Source includes course-derived material with unconfirmed redistribution rights. Do not apply a blanket permissive license or make the repository public before authorization. Original sample manuals have a separate CC0 notice. Credentials, private course documents, environments, weights and raw logs are excluded.

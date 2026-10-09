"""Explicit configuration and lazy, thread-safe real model clients."""

import os
import threading
from langchain_openai import ChatOpenAI
from openai import OpenAI
from knowledge.core.configuration import load_environment, required
from knowledge.utils.client.base import BaseClientManager
from knowledge.utils.client.local_models import BGEM3EmbeddingFunction, LocalReranker

load_environment()


class AIClients(BaseClientManager):
    _openai_client = None
    _openai_lock = threading.Lock()
    _openai_llm_json_client = None
    _openai_llm_text_client = None
    _llm_lock = threading.Lock()
    _bge_m3_client = None
    _bge_m3_lock = threading.Lock()
    _bge_m3_rerank_client = None
    _bge_m3_rerank_lock = threading.Lock()

    @classmethod
    def get_vlm_client(cls) -> OpenAI:
        return cls._get_or_create(
            "_openai_client", cls._openai_lock, cls._create_vlm_client
        )

    @classmethod
    def _create_vlm_client(cls) -> OpenAI:
        return OpenAI(
            api_key=required("OPENAI_API_KEY"),
            base_url=required("OPENAI_API_BASE"),
            timeout=float(os.getenv("MODEL_TIMEOUT_SECONDS", "90")),
            max_retries=1,
        )

    @classmethod
    def get_llm_client(cls, response_format: bool = True) -> ChatOpenAI:
        attr = (
            "_openai_llm_json_client" if response_format else "_openai_llm_text_client"
        )
        return cls._get_or_create(
            attr, cls._llm_lock, lambda: cls._create_llm_client(response_format)
        )

    @classmethod
    def _create_llm_client(cls, response_format: bool) -> ChatOpenAI:
        return ChatOpenAI(
            model=required("LLM_DEFAULT_MODEL"),
            temperature=0,
            api_key=required("OPENAI_API_KEY"),
            base_url=required("OPENAI_API_BASE"),
            timeout=float(os.getenv("MODEL_TIMEOUT_SECONDS", "90")),
            max_retries=1,
            max_tokens=int(os.getenv("ANSWER_MAX_TOKENS", "1800")),
            model_kwargs={"response_format": {"type": "json_object"}}
            if response_format
            else {},
        )

    @classmethod
    def get_bge_m3_client(cls) -> BGEM3EmbeddingFunction:
        return cls._get_or_create(
            "_bge_m3_client",
            cls._bge_m3_lock,
            lambda: BGEM3EmbeddingFunction(
                required("BGE_M3_PATH"),
                required("BGE_DEVICE"),
                required("BGE_FP16").lower() in ("1", "true"),
            ),
        )

    @classmethod
    def get_bge_m3_rerank_client(cls) -> LocalReranker:
        return cls._get_or_create(
            "_bge_m3_rerank_client",
            cls._bge_m3_rerank_lock,
            lambda: LocalReranker(
                required("BGE_RERANKER_LARGE"),
                os.getenv("RERANK_DEVICE") or required("BGE_DEVICE"),
                required("BGE_FP16").lower() in ("1", "true"),
            ),
        )

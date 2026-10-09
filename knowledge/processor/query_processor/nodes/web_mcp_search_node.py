import asyncio
import hashlib
import json
import os
from urllib.parse import urlsplit
from knowledge.core.configuration import required
from knowledge.processor.query_processor.base import BaseNode


class WebMcpSearchNode(BaseNode):
    name = "web_mcp_search_node"

    def process(self, state):
        if os.getenv("WEB_SEARCH_ENABLED", "false").lower() != "true":
            return {"web_search_docs": [], "web_status": "disabled"}
        try:
            docs = asyncio.run(self._bounded(state["rewritten_query"]))
            return {"web_search_docs": docs, "web_status": "completed"}
        except Exception as exc:
            return {"web_search_docs": [], "web_status": "failed:" + type(exc).__name__}

    async def _bounded(self, query):
        async with asyncio.timeout(float(os.getenv("MCP_TIMEOUT_SECONDS", "20"))):
            return await self._execute_mcp_server(query)

    async def _execute_mcp_server(self, query):
        from agents.mcp import MCPServerStreamableHttp

        url = required("MCP_DASHSCOPE_BASE_URL")
        allowed = required("MCP_ALLOWED_HOSTS").split(",")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in allowed:
            raise ValueError("MCP endpoint is not explicitly allowed")
        async with MCPServerStreamableHttp(
            name="联网搜索",
            params={
                "url": url,
                "headers": {"Authorization": "Bearer " + required("MCP_API_KEY")},
                "timeout": 15,
            },
            cache_tools_list=True,
            max_retry_attempts=0,
        ) as client:
            result = await client.call_tool(
                tool_name=required("MCP_SEARCH_TOOL"),
                arguments={"query": query, "count": 3},
            )
        if result.isError:
            raise RuntimeError("MCP search tool failed")
        pages = []
        for part in result.content:
            if part.type == "text":
                pages.extend(json.loads(part.text).get("pages", []))
        docs = []
        for page in pages:
            url = page.get("url", "")
            snippet = page.get("snippet", "").strip()
            if urlsplit(url).scheme not in {"https", "http"} or not snippet:
                continue
            docs.append(
                {
                    "chunk_id": "web-" + hashlib.sha256(url.encode()).hexdigest(),
                    "content": snippet,
                    "title": page.get("title", ""),
                    "url": url,
                    "source": "web",
                    "source_url": url,
                }
            )
        return docs

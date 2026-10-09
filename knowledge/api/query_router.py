import asyncio
from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException, Query
from knowledge.api.security import get_owner
from knowledge.core.task_store import get_store
from knowledge.schema.query_schema import QueryRequest
from knowledge.service.query_service import QueryService
from knowledge.utils import document_store


def register_router(app: FastAPI):
    @app.post("/query")
    async def query(
        request: QueryRequest,
        background_tasks: BackgroundTasks,
        owner: str = Depends(get_owner),
    ):
        available = {
            x["document_id"]
            for x in await asyncio.to_thread(document_store.active_documents, owner)
        }
        if set(request.selected_document_ids) - available:
            raise HTTPException(404, "资料不存在")
        service = QueryService()
        session = request.session_id or service.generate_session_id()
        task = service.generate_task_id()
        try:
            service.reserve_session(owner, session)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        try:
            get_store().create(task, owner, "query")
        except Exception:
            service.release_session(owner, session)
            raise
        args = (
            session,
            task,
            request.query,
            request.is_stream,
            owner,
            request.selected_document_ids,
            request.retrieval_mode,
            request.candidate_limit,
        )
        if request.is_stream:
            background_tasks.add_task(service.run_query_graph, *args)
            return {"message": "查询已提交", "session_id": session, "task_id": task}
        await asyncio.to_thread(service.run_query_graph, *args)
        info = get_store().get(task)
        if info["status"] != "completed":
            raise HTTPException(
                503,
                {
                    "task_id": task,
                    "status": info["status"],
                    **info["results"].get("error", {}),
                },
            )
        return {
            "message": "查询已处理",
            "session_id": session,
            "task_id": task,
            **info["results"]["query"],
        }

    @app.get("/history/{session_id}")
    def history(
        session_id: str,
        limit: int = Query(50, ge=1, le=100),
        owner: str = Depends(get_owner),
    ):
        return {
            "session_id": session_id,
            "items": QueryService().get_history(session_id, limit, owner),
        }

    @app.delete("/history/{session_id}")
    def clear_history(session_id: str, owner: str = Depends(get_owner)):
        return {
            "message": "已清除当前会话历史",
            "deleted_count": QueryService().clear_history(session_id, owner),
        }


def create_app():
    from knowledge.api.app import create_app as factory

    return factory()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8001)

from fastapi import FastAPI, UploadFile, Depends, BackgroundTasks, HTTPException
from knowledge.api.security import get_owner
from knowledge.service.upload_service import UpLoadService


def register_router(app: FastAPI):
    @app.post("/upload", status_code=202)
    def upload_endpoint(
        file: UploadFile,
        background_tasks: BackgroundTasks,
        owner: str = Depends(get_owner),
    ):
        service = UpLoadService()
        try:
            task_id, path, directory = service.process_upload_file(file, owner)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        background_tasks.add_task(
            service.run_import_graph, task_id, path, directory, owner
        )
        return {"message": "文件已接收，等待处理和校验", "task_id": task_id}


def create_app():
    from knowledge.api.app import create_app as factory

    return factory()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8000)

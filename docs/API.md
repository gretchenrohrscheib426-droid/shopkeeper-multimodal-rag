# 本地 API 合同

默认 `http://127.0.0.1:8000`，OpenAPI 位于 `/docs`。除 liveness、静态页、登录入口外，业务路由必须携带本机访问 Cookie 或 `Authorization: Bearer <APP_API_TOKEN>`。跨 Origin 请求被拒绝。模型 Key 不属于 API 请求参数。

|方法 / 路径|语义|
|---|---|
|POST `/auth/login`|JSON `{token}`，设置 HttpOnly、SameSite=Strict Cookie|
|GET `/auth/me` / POST `/auth/logout`|确认当前 owner / 退出|
|GET `/health/live`|进程存活|
|GET `/health/ready`|存储连接、模型目录、模型认证就绪；不是整链推理证明|
|POST `/upload`|multipart `file`，成功接收202，返回task_id；导入完成看任务状态|
|GET `/status/{task_id}`|owner隔离的持久任务状态与节点耗时|
|GET `/stream/{task_id}`|SSE progress/delta/final；支持after与Last-Event-ID|
|POST `/tasks/{task_id}/cancel`|202表示已请求取消，实际结果以最终状态为准|
|POST `/query`|见下方请求；流式提交返回task_id，非流式返回校验后的答案|
|GET `/history/{session_id}`|完整会话轮次，limit1–100|
|DELETE `/history/{session_id}`|仅清除当前owner指定会话，用户明确操作时使用|
|GET `/documents`|当前owner已提交的活动版本|
|GET `/sources/{document_id}/{version}/{chunk_id}`|原片段、processed MD 范围和资源信息|
|GET `/resources/{document_id}/{version}/original`|实际MinIO原文件流|
|GET `/resources/{document_id}/{version}/images/{image_id}`|实际图片流|

```json
{
  "query": "单个上传文件大小上限是多少？",
  "session_id": "demo-session",
  "is_stream": true,
  "selected_document_ids": [],
  "retrieval_mode": "rerank",
  "candidate_limit": 10
}
```

空文档列表让系统进行主题识别；歧义时返回 `answer_kind=clarification` 与 `clarification_options`。选中资料后再次提交。`no_evidence` 是资料不足的业务结果；模型/数据库故障为任务 failed，不能混为拒答成功。

401未登录、403跨站、404无可访问任务/来源、409同会话正在执行、422请求不合规、503查询处理失败。`is_stream=true` 的初始200只意味着任务已提交；必须消费final事件。当前单worker会话锁，不能未经改造增加多worker。

SSE `id` 单调递增。断线不删除服务端事件；重连提供最后已处理序号。最终答案中的 citation包含document_id/version/chunk_id/source_url/quotes，可通过受保护来源接口独立核对。

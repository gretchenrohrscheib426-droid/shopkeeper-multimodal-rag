# 关键源码阅读指南

建议按下列顺序打开文件，跟踪同一个 task_id，避免从旧目录中的单文件示例启动。

|顺序|源码|重点|
|---|---|---|
|1|`knowledge/core/configuration.py`|固定配置根目录、文件与进程变量优先级、别名冲突、禁止假默认凭据|
|2|`knowledge/api/app.py`、`api/security.py`|同源鉴权、私有来源路由、就绪检查与 CSP|
|3|`knowledge/core/task_store.py`|SQLite WAL、状态转换、事件序号、取消与丢失进程恢复|
|4|`knowledge/service/upload_service.py`|上传限制、任务目录、导入互斥、重复版本复用|
|5|`knowledge/processor/import_processor/main_graph.py`|PDF / DOCX / MD 三入口如何汇合|
|6|`nodes/entry_node.py`、`pdf_to_md_node.py`、`docx_to_md_node.py`|版本身份、真实 MinerU 进程与 Word 结构适配|
|7|`nodes/md_to_img_node.py`、`knowledge/utils/image_refs.py`|图片地址解析、目录约束、VLM 真调用|
|8|`nodes/document_split_node.py`|原子块、1000 字符边界、processed Markdown 范围|
|9|`knowledge/utils/client/local_models.py`|BGE dense / sparse 维度合同；重排512 token限制|
|10|`nodes/import_milvus_node.py`、`utils/document_store.py`|写后核验与 active pointer 最后发布|
|11|`knowledge/service/query_service.py`|会话锁、状态与失败隔离|
|12|`knowledge/processor/query_processor/main_graph.py`|三分支并行与单个 barrier|
|13|`nodes/item_name_confirmed_node.py`、`utils/entity_retrieval.py`|显式范围、历史代词、真实实体索引、澄清|
|14|`utils/retrieval.py`、`nodes/rrf_merge_node.py`、`nodes/reranker_node.py`|版本过滤、COSINE/IP、排名融合与动态截断|
|15|`nodes/answer_output_node.py`|claim 与真实 quote 合同、最多一次修复、失败不入历史|
|16|`utils/mongo_history_util.py`、`utils/sse_util.py`|整轮原子保存、事件重放|
|17|`knowledge/front/{shared,chat,import}.js`|登录、任务恢复、引用安全展示|
|18|`scripts/evaluate.py`、`tests/`|区分实测和单元合同；检查指标定义|

表中省略前缀的 `nodes/` 属于所在阶段的 processor。两个处理器中同名 base/state/config 文件分别定义各自合同。

## 迁移说明

- 生效包是根目录内的 `knowledge/`。根目录早期 `api/processor/service` 残稿仍保留在本地，但不作为发行入口。
- 两个历史 router 的 `create_app()` 委托统一 app 工厂；推荐一个端口，同源页面与 SSE 不再硬编码双端口。
- `HistoryItem` / `HistoryResponse` 保留。旧 `save_chat_message` 的逐条保存被 `save_turn` 的整轮原子写入替代，活动源码中无旧调用。
- 历史 main_graph 中硬编码教师路径、固定 task_id 的演示入口不再直接执行。真实运行必须先建持久任务，使用 API 或 `scripts/verify_vertical.py`。
- `item_name` 字段为兼容保留，可表示产品、课程或资料主题，不等同于新增知识图谱服务。

## 三个可讲清楚的故障案例

1. 百炼新业务空间 Key 搭配旧公共地址失败：统一客户端配置并验证真实请求目标，使用控制台给出的专属 URL。
2. BGE 重排1024 token引发 position overflow，而依赖库批次重试掩盖首个异常：按实际 tokenizer512上限修复，并进行长教育文档实测。
3. MilvusClient 返回主键名 `chunk_id` 而非统一 `id`：真实无范围查询暴露异常，显式请求主键并兼容 SDK 结果格式，澄清路径复测通过。

# 差异审查记录

用户提及的“65文件”没有对应原Git提交列表，不能据此编造检查数量。实际以修改前107文件备份为基线，对每个文件计算SHA256、差异行数和Python顶层符号。新增发行文件另见source-manifest.json。

当前基线统计：{'unchanged': 67, 'modified': 40}。没有删除备份中任何文件。

Ruff只格式化本次已改/新增的活动Python文件，不把未改的历史包整体重写。原结构保留；新文件不冒充原版。

|基线中改动文件|新增行|移除行|移除的顶层符号|
|---|---:|---:|---|
|`knowledge/__init__.py`|5|0|—|
|`knowledge/api/import_router.py`|23|88|—|
|`knowledge/api/query_router.py`|85|133|—|
|`knowledge/core/deps.py`|2|1|—|
|`knowledge/core/paths.py`|7|11|—|
|`knowledge/front/chat.html`|11|598|—|
|`knowledge/front/import.html`|9|271|—|
|`knowledge/processor/import_processor/base.py`|37|109|—|
|`knowledge/processor/import_processor/config.py`|11|22|—|
|`knowledge/processor/import_processor/main_graph.py`|30|47|run_import_graph|
|`knowledge/processor/import_processor/state.py`|66|94|—|
|`knowledge/processor/import_processor/nodes/document_split_node.py`|155|345|—|
|`knowledge/processor/import_processor/nodes/embedding_chunks_node.py`|46|138|—|
|`knowledge/processor/import_processor/nodes/entry_node.py`|68|61|—|
|`knowledge/processor/import_processor/nodes/import_milvus_node.py`|113|209|_MilvusIndexBuilder, _MilvusInserter, _MilvusSchemaBuilder, _SCALAR_FIELD_SPC, _cli_main|
|`knowledge/processor/import_processor/nodes/item_name_recognition_node.py`|30|330|—|
|`knowledge/processor/import_processor/nodes/md_to_img_node.py`|116|1885|AIClients, ImageContext, ImageInfo, StorageClients, _ImageScanner, _ImageUploader, _MdFileHandler, _VLMSummarizer|
|`knowledge/processor/import_processor/nodes/pdf_to_md_node.py`|68|162|—|
|`knowledge/processor/query_processor/base.py`|41|130|—|
|`knowledge/processor/query_processor/config.py`|8|15|—|
|`knowledge/processor/query_processor/main_graph.py`|39|58|—|
|`knowledge/processor/query_processor/state.py`|52|58|—|
|`knowledge/processor/query_processor/nodes/answer_output_node.py`|190|333|—|
|`knowledge/processor/query_processor/nodes/hybrid_vector_search_node.py`|14|96|—|
|`knowledge/processor/query_processor/nodes/hyde_vector_search_node.py`|36|152|—|
|`knowledge/processor/query_processor/nodes/item_name_confirmed_node.py`|111|435|_ItemNameAligner, _ItemNameExtractor|
|`knowledge/processor/query_processor/nodes/reranker_node.py`|58|223|—|
|`knowledge/processor/query_processor/nodes/rrf_merge_node.py`|43|139|—|
|`knowledge/processor/query_processor/nodes/web_mcp_search_node.py`|59|105|—|
|`knowledge/schema/query_schema.py`|33|20|—|
|`knowledge/service/query_service.py`|102|69|—|
|`knowledge/service/upload_service.py`|144|149|—|
|`knowledge/utils/embedding_util.py`|45|47|—|
|`knowledge/utils/milvus_util.py`|33|24|—|
|`knowledge/utils/mongo_history_util.py`|66|77|save_chat_message|
|`knowledge/utils/sse_util.py`|49|92|—|
|`knowledge/utils/task_util.py`|59|109|_to_cn|
|`knowledge/utils/client/ai_clients.py`|61|149|—|
|`knowledge/utils/client/base.py`|1|1|—|
|`knowledge/utils/client/storage_clients.py`|50|79|—|

## 语义检查重点

- `process(state)`、两图、历史响应schema保留；主要状态/并行合同有自动化覆盖。
- `run_import_graph`旧顶层硬编码演示入口移除，Service同名正式入口保留，使用API/验证脚本建立持久任务。
- 原图片节点内重复AIClients/StorageClients改为公共客户端；Milvus内部schema辅助函数集中重写。
- `save_chat_message`替换为整轮`save_turn`，未发现活动调用遗留；`_to_cn`由前端节点映射替代。
- 未发现导入/启动中的drop_collection、drop_database或递归删除；唯一历史delete_many由明确的当前owner会话清除API调用。
- 基线与新版本采用不同namespace；旧缓存/环境/课程原件保留。
- F/E9、33项合同、真实DB/模型/HTTP和浏览器证据组合验证。没有声称独立人工逐行复核全部新源码。

# 19章课件与实际源码映射

课件用于对照，不作为可直接执行或允许公开的授权。19份文件已读取并建立内容哈希索引；下表记录节点合同和本次证据，**不声称逐行复刻或所有可选能力已上线**。课程原文不随Git分发。

导入节点路径位于 `knowledge/processor/import_processor/`，查询节点位于 `knowledge/processor/query_processor/`；utils/core/api等均位于生效的 `knowledge/` 包。证据原始文件在本机 `artifacts/verification/baseline/`，脱敏摘要在 `artifacts/release_validation/`。

|章|主题|源码入口|实现或差异|验证状态/证据|
|---|---|---|---|---|
|01|项目全景|core / api / front|两条工作流与可追溯资源|真实三格式整链；不宣称知识图谱|
|02|环境与服务部署|core/configuration.py；scripts/doctor.py|复用环境、独立namespace、GPU适配|doctor.json；旧环境/缓存保留|
|03|导入骨架|processor/import_processor/base.py、state.py、main_graph.py|保留process(state)和LangGraph；错误不伪装成功|unit-final.xml；三格式实际任务|
|04|入口与PDF解析|nodes/entry_node.py、pdf_to_md_node.py|签名/版本哈希；真实MinerU子进程、超时和输出校验|parser.json；vertical-pdf.json|
|05|图片与MinIO|nodes/md_to_img_node.py；utils/image_refs.py|真实VLM摘要、图片哈希、SHA读回、不可变Markdown|model-plus-auth.json；vertical-md/pdf/docx|
|06|文档切分|nodes/document_split_node.py|标题路径/原子块/跨度/字符上限；短片段不跨章合并|test_import_contracts；18片段教育DOCX|
|07|商品名识别|nodes/item_name_recognition_node.py|真实JSON模型识别；item_name兼容课程/主题|真实manifest；不宣称完整教育知识图谱schema|
|08|切片向量化|nodes/embedding_chunks_node.py；utils/client/local_models.py|真实BGE1024dense与learned sparse、有限数校验|doctor.json；真实向量入库|
|09|向量入库|nodes/import_milvus_node.py；utils/document_store.py|稳定主键upsert、chunk/主题核验、active最后发布|重复导入复用；旧资料保护|
|10|查询骨架|processor/query_processor/base.py、state.py、main_graph.py|分支独立输出、单次barrier、状态传播|并行合同测试；真实join_count|
|11|主题确认|nodes/item_name_confirmed_node.py；utils/entity_retrieval.py|显式范围/历史/实体检索/澄清；SDK主键兼容|HTTP澄清、浏览器澄清；阈值不是概率|
|12|向量检索|nodes/hybrid_vector_search_node.py；utils/retrieval.py|owner/version过滤，COSINE+IP加权|60题真实检索；并非BM25|
|13|HyDE|nodes/hyde_vector_search_node.py|真实生成仅作召回；禁止假设文本成为引用|60题真实HyDE；用量和分支状态|
|14|MCP网络搜索|nodes/web_mcp_search_node.py|保留受控可选入口，默认disabled|未配置授权服务，真实联网未验证；不计PASS|
|15|RRF|nodes/rrf_merge_node.py|rank从1起，稳定ID含0，去重/预算；本地+HyDE|合同测试与60题基线；web不冒充第三路RRF|
|16|Rerank|nodes/reranker_node.py；utils/client/local_models.py|真实cross-encoder、512token、有限分数、动态截断|长教育文档故障修复后PASS；评测MRR|
|17|生成与历史|nodes/answer_output_node.py；utils/mongo_history_util.py|引文校验/一次修复/整轮原子保存/拒答|60题59完成1校验失败；验证后整段SSE而非token流|
|18|API与前端|api / service / front；core/task_store.py|统一同源、鉴权、持久进度/恢复/取消、来源展示|33合同测试；10真实HTTP检查；真实浏览器上传和引用|
|19|总结与复盘|docs/ARCHITECTURE.md、VERIFICATION.md、KNOWN_ISSUES.md|总结以详细节点和本次证据为准|PDF实际使用MinerU；总结章节中的其他解析器称呼不替代实测|

未完成项保持明确：MCP联网需授权接口；全局VLM速率限制尚非分布式；短段不跨章合并；无逐token输出。这些不应写成完整原版同等功能。当前用户要求的本地PDF/DOCX/MD→真实多模态RAG闭环已验证。

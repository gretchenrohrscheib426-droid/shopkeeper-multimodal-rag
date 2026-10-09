# 实际验证报告

验证日期：2026-10-09至10（Asia/Shanghai）。原始证据保留在本机 `artifacts/verification/baseline/`、`data/tasks.sqlite3`、`data/query-errors/`。发布版为 `artifacts/release_validation/` 的脱敏摘要，结合source-manifest与Git提交定位本轮源码。

## 总体结论

本地真实PDF/DOCX/Markdown→解析→图片理解→MinIO→切分→BGE→Milvus→检索融合重排→百炼生成→原文引用→前端闭环已运行。系统可真实使用，但不能宣称所有问题100%回答成功、生产部署完成或完整复刻所有课程可选能力。

## 分层证据

|层级|实际结果|证据|
|---|---|---|
|单元/合同|33/33通过，3.14秒，一条依赖弃用提醒|unit-final.xml；含替身，单独计数|
|静态|Ruff F/E9通过；配置与图片引用两个模块mypy通过|最终检查记录；不是全仓严格类型验证|
|文本模型|qwen-plus实际响应，1.266秒|model-auth.json|
|视觉模型|qwen3-vl-plus真实图像摘要，4.187秒|model-auth.json，保留响应与用量|
|请求的模型名|qwen3-plus实际404 model_not_found|本机独立失败记录；未计成功|
|MinIO|Windows真实put/list/stat/读回SHA一致|doctor.json，0.031秒该次存储检查|
|Mongo|真实ping、写入读回|doctor.json，0.063秒|
|Milvus|真实BGE1024维upsert和检索，返回目标ID|doctor.json，9.984秒含加载|
|MinerU|既有2.7.1与本地VLM缓存解析两页PDF|mineru.json，29.015秒单独解析|
|Markdown|10片段、1图片、查询引用|vertical-summary.json，导入21.438秒/查询6.641秒|
|PDF|11片段、1图片、真实MinerU和引用|导入55.375秒/查询6.656秒|
|原创DOCX表格|11片段、1图片、表格行可引用|导入18.917秒/查询7.974秒|
|教育DOCX|新版本18片段，旧版本保留|实际完整导入17.890秒/修复后查询12.016秒|
|重复导入|已提交同版本复用|vertical-summary.json；教育最终验证导入为复用耗时，不当首次耗时|
|真实故障|7/7预期失败/保护检查通过|failures.json|
|真实HTTP|10/10通过|http.json，真实查询10.312秒|
|浏览器|实际上传PDF、问答、表格引用、原PDF/图片、澄清与历史恢复|截图与任务日记；不以截图替代运行|
|60题评测|59完成、1明确失败；冻结20/20|evaluation60-run1-summary.json|
|公网/MCP联网|未部署/未配置|不计PASS，不提供在线Demo|

## HTTP与故障验收详情

真实HTTP覆盖：同session并发409；模型问答completed；两订阅读取同18事件且各只有一个final；断点后8事件重放；历史恰好两消息；来源引文逐字存在；匿名来源401；无依据问题拒答；取消状态cancelled；主题歧义clarification。

故障检查通过的含义是检测到真实故障并进入正确失败状态，不是数据库故障时“业务成功”。Mongo断连1.078秒、Milvus断连7.781秒、MinIO断连1.281秒；无效测试认证实际401；实际请求超时；取消；旧文档清单不变。故障目标是本地受控不可达端口或显式测试Key，没有停止用户已有容器或删除数据。

## 真实任务定位

|流程|task_id|
|---|---|
|MinerU单独解析|b1b47d62d71f4543b4c026a93ea2ed0a|
|浏览器PDF导入|892e0d9b083e4b6ea15468caad58dcf0|
|原创DOCX导入|7de9f2e27e3641718e677ad4a5abd66f|
|原创DOCX表格问答|2299f688a8ee4be29e372976fb5f08da|
|教育新版本导入|57db1762ccf74f4c80b66bfa700c4a5b|
|教育修复后问答|1af78028a64a49ac8038a647382e5f3c|
|真实HTTP最终问答|0c9ef24e3acc4eaebfe4dc02c9c2dcdb|
|HTTP取消|b6fc543a70994327a85e20f928a647fd|
|HTTP澄清|92c16a8dc7214e51baa19960f969478d|
|首轮评测Q28失败|6bed0cdffbe44286a01dadfb01e6cee2|

报告中的DOCX图文表格记录从真实任务日志重建，因为早期并行脚本使用同一输出文件名产生覆盖；没有重造模型输出。原始task数据库可核查。原始失败、旧73片段教育版本及本轮18片段版本均保留。

## 性能和解释边界

热查询P50=6.922秒、P95=9.220秒；首题含模型加载12.688秒。7/7无答案题拒答。已发布引用ID和连续引文存在性100%，但无独立人工语义评分。四种检索对照、完整题集哈希、失败排名不可观察问题、token缺项和N/A成本详见EVALUATION.md。

一次Q28生成失败不能抹去。首轮59/60是任务完成率，不是人工答案正确率。后续接口修复（主题主键兼容、格式/类型注解）不改变该次显式文档范围题集的记录，也不据此宣称又跑了一遍60题。

## 远程CI记录

首个源码提交 `3389828` 的 [GitHub Actions运行](https://github.com/gretchenrohrscheib426-droid/shopkeeper-multimodal-rag/actions/runs/37958168141)在Ubuntu/Python 3.12收集测试时失败：两个测试模块因缺少Pillow无法导入，因此该次为0个测试执行，不能计为通过。原有本机环境已有Pillow 12.3.0，先前本地测试未暴露这项清单遗漏。本轮已将Pillow显式加入应用、CI和已验证版本清单；后续远程运行状态以Actions和最终交付中的CI记录为准。

修正提交 `a036c4b` 的 [远程CI复测](https://github.com/gretchenrohrscheib426-droid/shopkeeper-multimodal-rag/actions/runs/37959394091)已实际成功：33/33离线测试、原有HTML表格工具检查、Ruff F/E9及两个模块mypy全部通过。依赖扫描同时补齐BeautifulSoup；仅安装到新应用叠加环境，`pip check`无冲突。该次Actions步骤与JUnit分别保存在 `artifacts/release_validation/ci-a036c4b.json`、`unit-ci-a036c4b.xml`。远程CI不连接用户数据库或付费模型；真实服务验收仍以前述本机运行证据为准。

## 尚未完成的交付边界

2026-10-10用户明确要求公开，GitHub可见性已改为public，来源与许可说明继续保留，详见PUBLICATION.md。现有环境可运行但没有公网资源授权。MCP联网未提供可用凭据。复杂版式、高并发、多worker、生产身份、完整备份恢复演练与独立语义准确率未验证。真实完成项与这些限制同时保留。

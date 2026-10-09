# 第三方来源与许可记录

本文件记录本次核查事实，不替代各项目完整许可，也不为课程源码授予新权利。没有分发模型权重或第三方二进制。

|组件|已测版本 / 来源|许可记录|
|---|---|---|
|课程衍生工程|用户提供的掌柜智库源码和19章文档|未发现完整公开分发授权；必须确认后才能公开相关代码|
|MinerU|本机安装 **2.7.1**|已读取该安装包 `mineru-2.7.1.dist-info/licenses/LICENSE.md`，为 **AGPL-3.0**；不得用新版仓库许可替代旧包许可|
|FlagEmbedding|1.3.5|上游[MIT许可](https://github.com/FlagOpen/FlagEmbedding/blob/master/LICENSE)|
|BGE-M3 / BGE-reranker-large|固定revision，见.env.example|[BGE-M3模型卡](https://huggingface.co/BAAI/bge-m3)、[reranker模型卡](https://huggingface.co/BAAI/bge-reranker-large)标注MIT；权重留在本机缓存|
|transformers|4.51.3|安装元数据Apache-2.0|
|langgraph / langchain-openai|1.2.11 / 1.6.2|安装元数据MIT|
|openai Python SDK|3.13.0|安装元数据Apache-2.0|
|minio Python SDK / pymongo|7.2.20 / 4.18.2|安装元数据Apache-2.0；服务端产品许可独立|
|python-docx|1.2.0|安装元数据MIT|
|PyTorch / uvicorn|2.11.0+cu128 / 0.34.3|安装元数据BSD-3-Clause|
|Milvus / MinIO / MongoDB / etcd / Attu服务|用户既有VM容器|复用而未重新分发；容器镜像版本及服务端许可应在正式部署前单独核查|

2026-10-10查阅的[MinerU当前master许可](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)已是附加条款的Apache-2.0形式；**本机实测2.7.1安装包仍为AGPL-3.0**。版本差异已经记录，不能据当前网页给旧版本贴错许可。正式外部分发或在线服务需按实际版本、集成方式与适用义务审查。

原创测试手册、流程图及其PDF/DOCX在 `examples/public/manual/LICENSE.txt` 单独声明CC0。教育原件、19章课程全文与第三方素材不随Git上传。新编文档和修复与课程衍生部分混在同一仓库时，不擅自将整个仓库标MIT。

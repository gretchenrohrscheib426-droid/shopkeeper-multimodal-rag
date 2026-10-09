# Windows 启动指南

## 现有机器

在工程根目录操作，不重新安装旧环境、不清空模型缓存、不重建 VM。已有 `.venv` 与 `.venv_py313` 保留；经验证的应用解释器是 `.venv_app/Scripts/python.exe`。该叠加环境复用现有 GPU Python 基础环境，不可直接复制到另一台机器。

```powershell
& scripts/start-local.ps1
# 完成使用后，给本项目发送正常退出信号
& scripts/stop-local.ps1
```

启动脚本只监听 localhost:8000，识别本项目已运行实例，端口被其他进程占用时明确失败。日志写 `data/app.stdout.log`、`data/app.stderr.log`。任务数据在 `data/tasks.sqlite3`。

本机访问凭证是 `.env.local` 的 `APP_API_TOKEN`，在前端“本机登录”使用；模型 `OPENAI_API_KEY` 仅供后端，不能粘到浏览器。

## 新机器 / 新检出

1. 核查 Python 3.12、GPU 驱动、PyTorch CUDA 兼容关系，创建**新的**应用环境，不覆盖已有环境。
2. 安装自己机器适用的 PyTorch，再装 `requirements-app.txt`。精确已测版本见 `requirements-validated.txt`；该记录不是涵盖所有 CUDA 平台的通用锁。
3. 从 `.env.example` 创建私有 `.env.local`，填入现有 MinIO、MongoDB、Milvus 地址与独立集合 / bucket 名称。
4. 指定本地完整 BGE-M3、BGE-reranker-large 模型目录与已核对的模型 revision。权重不随 Git 分发。
5. 指定真实可执行的 MinerU。`scripts/mineru_existing.py` 仅是**当前机器复用既有环境**的适配入口；新机器可直接配置自己的 `mineru.exe`。设置 backend 与模型缓存，先执行 `verify_parser.py`。
6. 使用安全窗口配置百炼 Key 和业务空间地址，脚本不会打印 Key：

```powershell
& scripts/set-model-key-interactive.ps1 -BaseUrl 'https://YOUR-WORKSPACE-ID.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'
```

窗口保存后重启应用，因为模型客户端是进程内单例。`MODEL_CONFIG_SOURCE=file` 使私有文件中的完整模型配置优先；不要沿用旧公共 DashScope 地址。

```powershell
.venv_app/Scripts/python.exe scripts/verify_model_auth.py
.venv_app/Scripts/python.exe scripts/doctor.py
.venv_app/Scripts/python.exe scripts/verify_vertical.py 'examples/public/manual/掌柜智库 图文表格手册.docx' 'PDF 和 DOCX 分别适合什么场景？'
```

上述命令会调用真实服务。不要将实际 Key、应用凭证、诊断原始日志或教育原件上传 Git。`/health/ready` 的模型检查只验证 models.list 认证；推理成功必须看远程调用或业务测试结果。

## 排错

|症状|检查|
|---|---|
|401|业务空间 URL、Key 来源、文件权威模式、进程是否重启|
|403|地址拼写、空间权限、地域是否匹配；不要自动改回公共地址|
|404 model_not_found|models.list 和真实模型名；本空间 qwen-plus 可用，qwen3-plus 不可用|
|MinIO签名/时间错误|Windows、VM、容器 UTC 与 Chrony；先诊断时间而非删库|
|Milvus字段/维度错|schema、1024维、模型revision、返回的实际主键名|
|MinerU超时|真实子进程日志、模型缓存、设备内存；不要将退出或空MD记为成功|
|引用校验失败|保留 task_id 与本机失败日志；不能放宽成不存在的引文|

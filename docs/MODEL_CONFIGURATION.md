# 百炼业务空间配置

应用固定从仓库根目录加载配置，不依赖当前工作目录。设置 `SHOPKEEPER_ENV_FILE` 可明确指定文件；否则优先使用根目录 `.env.local`，没有该文件时才读取根目录 `.env`。内层 `knowledge/.env` 不参与加载。原有配置文件保留。

本机使用百炼 Model Studio 北京业务空间专属 OpenAI-compatible 地址。必须从控制台复制完整地址，不拼接旧 DashScope 公共端点。公开模板只含占位符。

```dotenv
MODEL_CONFIG_SOURCE=file
OPENAI_API_BASE=https://YOUR-WORKSPACE-ID.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
OPENAI_API_KEY=在本机输入
LLM_DEFAULT_MODEL=qwen-plus
ITEM_MODEL=qwen-plus
VL_MODEL=qwen3-vl-plus
```

`MODEL_CONFIG_SOURCE=file` 将模型地址、凭据和模型名称作为一个整体，从指定文件读取，忽略继承的旧模型环境变量；缺字段立即失败，不能把新地址与旧 Key 混用。其他配置仍允许进程环境覆盖。这是根据本次用户明确要求对原优先级约定的调整。

部署时可设置 `MODEL_CONFIG_SOURCE=environment`，恢复进程环境优先规则。同一层中的 `OPENAI_API_BASE`/`OPENAI_BASE_URL` 或 `MODEL`/`LLM_DEFAULT_MODEL` 如果冲突会报错，不随意选择。不要同时设置不一致的别名。

`AIClients` 统一构造 OpenAI SDK 视觉客户端和 LangChain 文本客户端，显式传入相同的地址与 Key。`StorageClients` 只读取数据库/对象存储凭据。两个处理器的 `config.py` 都从同一入口加载；模型凭据不进入配置对象 repr。

本机安全输入脚本：

```powershell
& .\scripts\set-model-key-interactive.ps1 -BaseUrl '从控制台复制的完整业务空间地址'
```

窗口采用掩码输入，验证 ASCII、空白和引号，原子替换被 Git 忽略的 `.env.local`。成功后写入不含密钥的 `data/model-config-receipt.json`。客户端是进程内单例，保存后需要优雅停止并重新启动应用；不能依靠改文件让旧进程热更新。

真实验证命令：

```powershell
& .\.venv_app\Scripts\python.exe scripts/verify_model_auth.py
```

验证分别调用 `qwen-plus` 和实际图片摘要节点中的 `qwen3-vl-plus`，保存真实返回文本、耗时、视觉 token 使用量及脱敏配置诊断。不把 `/models` 可列举当作模型推理成功。401、编码失败、超时、空响应分别记录 FAIL，禁止固定摘要或模拟调用补成功。

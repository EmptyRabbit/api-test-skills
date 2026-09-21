# 接口测试平台后端

## 开发

    python -m venv .venv && source .venv/Scripts/activate   # Windows bash
    pip install -e ".[dev]"
    python -m pytest tests/ -v
    python run.py
    # 或: uvicorn app.main:create_app --factory --reload --reload-dir app --port 8000
    # Windows 必须加 --loop app.windows_loop:new_proactor（否则 --reload 无法拉起 Claude CLI）

前端开发模式（apps/web）：`npm run dev`（/api 代理到 8000）。

## 生产

    cd apps/web && npm install && npm run build   # 产出 apps/web/dist
    cd ../server && uvicorn app.main:create_app --factory --port 8000

## 配置（环境变量，前缀 PLATFORM_）

| 变量 | 默认 | 说明 |
|---|---|---|
| PLATFORM_DATA_DIR | data | workspaces、SQLite、`code-server/`（用户数据与扩展）、默认 Claude home |
| PLATFORM_DATABASE_URL | 空=SQLite | 切 MySQL：mysql+pymysql://user:pwd@host/db |
| PLATFORM_PERMISSION_MODE | bypassPermissions | 可改 default 配合 PLATFORM_ALLOWED_TOOLS |
| PLATFORM_ALLOWED_TOOLS | [] | JSON 数组，如 ["Read","Edit","Bash(git:*)"] |
| PLATFORM_CODE_SERVER_BIN | code-server | 可执行文件。会查找 PATH、`~/.local/bin/code-server`、`~/.local/code-server/bin/code-server`。Windows 上若 PATH 里是残缺的 npm 包，会自动改用 WSL 中的上述路径。也可写成 `wsl:/home/你/.local/bin/code-server` |
| PLATFORM_CODE_SERVER_IDLE_MINUTES | 30 | 闲置回收阈值 |
| PLATFORM_CONFIG | 空则找 `apps/server/platform.yaml` | 平台 YAML（MCP / skills / Claude home），与本机 `~/.claude` 隔离 |

Claude Code 的 MCP 与 skills **不读本机用户配置**。复制 `platform.yaml.example` 为 `platform.yaml`，用 `${ENV}` 填 MCP 与模型网关。启动时会写入独立的 `claude_home`（`CLAUDE_CONFIG_DIR`），并把 `skill_roots` 链到该目录的 `skills/`。

`mcp_servers` 里标 `auth: oauth` 的 HTTP MCP：启动对话前会要求当前用户完成 device-code 授权。授权服务器从该 MCP 的 `401` / `.well-known/oauth-protected-resource` 发现，再读 `{issuer}/.well-known/oauth-authorization-server`。动态注册的 `client_id` 和用户 token 都写在数据库（`mcp_oauth_clients` / `mcp_oauth_tokens`），不依赖 `data/` 里的 json。若库里还没有、本地仍有旧的 `data/mcp-oauth-client.json`，启动时会迁进库。`oauth.identity_claims` 控制 userinfo 里哪些字段要和侧栏用户名一致。

## 服务器一次性配置

1. Python 3.11+ / Node 18+ / git；`claude` CLI 安装并认证
2. 本仓库 clone 到服务器；复制 `apps/server/platform.yaml.example` 为 `platform.yaml`（或设 `PLATFORM_CONFIG`）：声明 `skill_roots`、`mcp_servers`、`vendor`、模型网关。密钥只放环境变量。
3. code-server：`apps/dev.sh start` 会尝试自动安装（官方 `install.sh --method=standalone` → `~/.local`；Windows 在 WSL 里装）。也可手工：`curl -fsSL https://code-server.dev/install.sh | sh -s -- --method=standalone`（Windows 在 WSL 中执行）。平台按精简离线模式启动（关遥测/更新/欢迎页）。打开 VS Code 页签时会写入工作区 `.vscode/launch.json`，解释器指向**后端同一套虚拟环境**（`sys.executable`；WSL 中的 code-server 用 `/mnt/…` 路径）。并尝试从 Open VSX 安装 `ms-python.python` / `ms-python.debugpy`（用于 LSP/调试）。`.py` 语法高亮由 code-server **自带的内置扩展 `vscode.python`** 提供（自带 MagicPython TextMate 语法，始终生效），平台不再往 `ms-python.python` 里注入语法或另建 UI 扩展——那样做反而会跟内置扩展重复注册同一个 language id / scopeName，两边打架导致谁都渲染不出颜色；`ensure_python_extensions` 每次都会清掉历史遗留的注入内容。用例依赖可装进该 venv：`pip install -r data/workspaces/<sid>/artifacts/requirements.txt`。扩展市场 UI 仍关闭，不要靠网页装扩展。
4. 被测仓库 clone：在 `platform.yaml` 配 `git.token: ${PLATFORM_GIT_TOKEN}`（GitLab PAT / Deploy Token）。只注入 http(s) clone，会话里仍存裸地址。不配则走机器 Git 凭据。
5. platform.db 放不被定时清理的路径（或切 MySQL）；
   PLATFORM_DATA_DIR 可指向可被清理磁盘（恢复链路兜底）

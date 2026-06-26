# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

**Infinite-Canvas**（by hero8152，版本 2026.06.25）— "无限画布"前端应用，统一接入多家 AI 图像/视频生成服务（OpenAI 协议 API / Modelscope / RunningHub / 即梦 / 火山引擎 / 本地 ComfyUI）。**中文界面为主**，国际化覆盖 7 语言。

⚠️ **许可证**：已申请著作权。**禁止商业用途**（不得修改封装为商业产品）。二次开发必须开源 + 注明原作者。

## 架构核心特征

这是一个**单体应用**：

- **后端**：单个 `main.py`（**15,073 行**，~690KB），FastAPI + Uvicorn，端口 `3000`，绑定 `0.0.0.0`
- **前端**：原生 JavaScript（**无框架、无构建工具**），按职责拆分多个 `static/js/*.js`
- **打包形态**：自带 Windows CP314 Python 3.10 运行时 + 23 个 `.whl` 离线包，**双击 `run.bat` 即可运行，无需安装 Python**

修改本项目意味着直接编辑 `main.py` 这一个文件，没有模块边界。

## 关键目录与运行时路径

`main.py` 顶部（约 220-230 行）定义的路径常量：

```
BASE_DIR         = 项目根目录
STATIC_DIR       = static/        （挂载到 /static）
OUTPUT_DIR       = output/        （挂载到 /output，生成产物）
ASSETS_DIR       = assets/        （挂载到 /assets）
  ├── input/                     （用户上传输入）
  ├── output/                    （AI 生成输出）
  ├── library/                   （本地素材库）
  └── uploads/                   （本地上传临时区）
```

静态挂载点（`main.py:1352-1354`）：`/static`、`/output`、`/assets`。

## 三种运行模式（互斥或并存）

1. **API 模式** — 任意 OpenAI/异步/Gemini/方舟 协议端点（在网页左下角设置）
2. **Modelscope 模式** — 免费 LLM + 图像模型 + LoRA（需要 Modelscope Key）
3. **本地 ComfyUI 模式** — 局域网 ComfyUI 实例 + 自定义工作流

即梦 CLI 是**独立调用路径**：通过 `tools/jimeng_cli_install.ps1` 和 `jimeng_cli_login.ps1` 安装登录，与网页 UI 通过 `JimengPendingError` 异常处理协调（`main.py:4156`）。

## 常用命令

### 启动（用户视角）

| 场景           | 命令                                                        |
| ------------ | --------------------------------------------------------- |
| Windows 一键启动 | 双击 `run.bat`（自动用 `python/python.exe` 内置 Python，3 秒后打开浏览器） |
| Windows 安装依赖 | 双击 `安装依赖.bat`（先尝试 `packages/` 离线安装，失败回退在线）                |
| macOS 安装依赖   | `bash mac-安装依赖.sh`                                        |
| macOS 启动     | `bash mac-启动服务.sh`（自动探测 `en0/en1` LAN IP）                 |
| 即梦 CLI 安装    | 双击 `安装即梦CLI.bat`                                          |
| 即梦 CLI 登录    | 双击 `登录即梦CLI.bat`（调起 `tools/jimeng_cli_login.ps1`）         |

### 开发命令

```bash
# 直接以系统 Python 启动（开发模式）
python main.py
# 等价于：uvicorn app --host 0.0.0.0 --port 3000

# 安装依赖到虚拟环境
pip install -r requirements.txt

# 测试 API 是否就绪
curl http://127.0.0.1:3000/api/app-info
```

**没有 lint/test 工具链**。项目无 `tests/`、无 `pytest.ini`、无 ESLint 配置。所有改动需手动验证。

## 关键 API 路由速查

| 路径前缀                                                                  | 用途                                                                      |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `/` `/api/view` `/api/download-output`                                | 前端入口与文件下载                                                               |
| `/api/app-info` `/api/check-update` `/api/update-from-github`         | 应用信息 + GitHub 版本检查/更新（含备份回滚 `/api/update-rollback`）                     |
| `/api/local-assets/*`                                                 | 本地素材库 CRUD + 分类/打标（`upload/import-urls/folders/items/caption/classify`） |
| `/api/runninghub/*`                                                   | RunningHub 工作流与应用提交（`workflow-submit`, `submit`, `workflow-info`）       |
| `/api/ai/upload` `/api/ai/upload-base64` `/api/comfyui/upload-base64` | 上传通道                                                                    |
| `/api/media-preview` `/api/image-jpeg`                                | 媒体预览/帧抽取                                                                |
| `/ws/stats`                                                           | WebSocket 在线状态广播                                                        |

## 重要非显然细节

### 1. WebSocket 心跳禁用（`main.py:15072-15073`）

```python
uvicorn.run(app, host="0.0.0.0", port=3000,
            ws_ping_interval=None, ws_ping_timeout=None)
```

**故意关闭**协议层 ping，因为 Photoshop UXP 面板不响应 pong 会导致断连。客户端有应用层心跳兜底。**不要"修复"这个**。

### 2. 访问日志过滤（`main.py:21-50`）

`QuietAccessLogFilter` 屏蔽画布 meta 轮询噪音（`/api/queue_status`、`/api/canvases`、`/api/canvases/*/meta`）的 2xx 访问日志。

### 3. 版本号机制（`VERSION` 文件）

每次发布更新 `VERSION`，前端读取后导航栏 GitHub 按钮显示"有新版本"。**删除 `VERSION` 文件即可关闭更新提示**。

### 4. 工作流导入

`workflows/*.json` 中的 JSON 是 ComfyUI 工作流格式，前端通过 `/api/runninghub/workflows/{workflow_id}` 列出，可在 UI 中导入到本地 ComfyUI 实例。

### 5. i18n 文件

`static/js/i18n/*.js` 命名对应同名主模块（`canvas.js` ↔ `canvas.js`）。新增前端字符串需要同时改 7 个语言文件；可用 `validate-i18n.js` 校验一致性。

### 6. 前端模块加载

无打包器，浏览器直接 `<script>` 加载 `static/js/*.js`。模块顺序见 `static/` 下的 `index.html` 或对应入口页（`api-settings.html`、`smart-canvas.html` 等）。

## 常见踩坑

- **修改 `main.py` 后必须重启服务** — 无热重载
- **路径不要写死** — 用 `STATIC_DIR`/`OUTPUT_DIR`/`ASSETS_DIR` 常量，避免硬编码绝对路径
- **API 调用新加第三方服务** — 参考 `default_api_providers()`（`main.py:702`），统一走提供商抽象层
- **不要删除 `python/` 和 `packages/`** — 这是 Windows 用户零依赖运行的关键

## 项目状态

- 版本：2026.06.25
- 维护者：B 站 hero8152（https://space.bilibili.com/78652351）
- 主教程：https://youtu.be/1y9ShTvgC_w
- 仓库：https://github.com/hero8152/Infinite-Canvas

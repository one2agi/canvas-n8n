# 项目索引：Infinite-Canvas

> **生成时间**：2026-06-27 ｜ **版本**：2026.06.25 ｜ **作者**：hero8152
>
> **核心定位**：无限画布 — 集成 ComfyUI / 多家 LLM API / Modelscope / RunningHub / 即梦 / 火山引擎 的统一 AI 图像/视频生成前端

## 📁 项目结构

```
Infinite-Canvas/
├── main.py                       # 单一 FastAPI 主程序（15,901 行，~730KB）
├── automation_cli.py             # 自动化工作流 CLI 客户端（145 行，仅 stdlib）
├── requirements.txt              # Python 依赖（+ websockets）
├── VERSION                       # 版本号文件（2026.06.25）
├── AGENTS.md                     # Codex agent 协作指引
│
├── Dockerfile                    # python:3.11-slim 镜像（端口 3000）
├── docker-compose.yml            # 本地容器化
├── docker-compose.dokploy.yml    # Dokploy 部署配置
│
├── run.bat                       # Windows 一键启动（端口 3000）
├── automation.bat                # Windows 自动化 CLI 包装
├── mac-*.command / mac-*.sh      # macOS 启动/修复/依赖安装脚本
├── 安装依赖.bat / 安装即梦CLI.bat / 登录即梦CLI.bat
│
├── python/                       # 内置 Python 3.10 运行时（Windows CP314，零依赖运行）
├── packages/                     # 23 个离线 .whl 包（无需联网安装）
├── get-pip.py                    # pip 引导器
│
├── static/                       # 前端资源
│   ├── js/                       # 原生 JS 模块（canvas.js / smart-canvas.js）
│   │   └── i18n/                 # 7 语言国际化（common/canvas/studio/smart-canvas/...）
│   ├── css/                      # 8 个样式表（新增 angle.css，canvas.css 134KB）
│   ├── system-prompts/           # 内置 Prompt 模板
│   ├── runninghub/               # RunningHub API 提供商配置 + 缩略图
│   ├── vendor/                   # 第三方 css/fonts/js
│   └── update-notes.json         # 更新日志
│
├── workflows/                    # 7 个 ComfyUI 工作流 JSON
├── automation_workflows/         # 用户导出可被 automation_cli 调用的画布工作流
│   └── README.md                 # 用法说明
│
├── tools/                        # 浏览器/PS 扩展
│   ├── chrome-local-asset-importer/
│   ├── photoshop-asset-connector/
│   ├── jimeng_cli_install.ps1
│   └── jimeng_cli_login.ps1
│
├── tests/                        # pytest 单元测试（5 个文件，1,544 行）
│   ├── test_automation_cli.py              # CLI 命令解析 + HTTP 集成
│   ├── test_automation_workflow.py         # 工作流后端 API + Pydantic 模型
│   ├── test_canvas_detected_workflows.py   # 画布 detected_workflows 提取
│   ├── test_canvas_json_splitter.py        # 画布 JSON 拆分器
│   └── test_think_blocks.py                # LLM 思考块解析
│
└── 文档
    ├── README.md                 # 项目介绍
    ├── 新手运行与使用教程.md
    ├── MAC-使用说明.md
    └── 运行说明.txt
```

## 🚀 入口点

| 类型 | 路径 | 说明 |
|------|------|------|
| **后端入口** | `main.py` | FastAPI 单文件应用，启动后监听 `http://127.0.0.1:3000` |
| **Windows 启动** | `run.bat` | 使用内置 `python/python.exe`，自动打开浏览器 |
| **macOS 启动** | `mac-启动服务.command` / `.sh` | Mac 启动脚本 |
| **Docker 启动** | `docker-compose.yml` | `python:3.11-slim` 镜像，端口 3000 |
| **Dokploy 部署** | `docker-compose.dokploy.yml` | Dokploy 平台部署配置 |
| **依赖安装** | `安装依赖.bat` / `mac-安装依赖.sh` | 安装 requirements.txt |
| **CLI 工具** | `安装即梦CLI.bat` + `登录即梦CLI.bat` | 即梦 CLI 安装/登录 |
| **自动化 CLI** | `automation_cli.py` / `automation.bat` | 命令行调用 `/api/automation/*` |

## 🧩 核心模块（main.py 内聚合）

main.py 是单体应用，按代码行分布对应以下模块：

| 功能域 | 关键 API 路由 | 说明 |
|--------|---------------|------|
| **应用配置/启动** | `startup_event`, `ensure_runtime_config_files`, `load_env_file` | ~180-700 |
| **API 提供商管理** | 模型列表、归一化、合并默认/用户配置 | ~560-1110 |
| **更新机制** | `/api/check-update`, `/api/update-from-github`, `/api/update-rollback` | ~1784-2270 |
| **即梦 CLI** | `JimengPendingError`，即梦任务队列 | ~4156 |
| **媒体预览** | `/api/media-preview`, `/api/image-jpeg` | ~4761-4830 |
| **视图/主页** | `/`, `/api/view`, `/api/download-output` | ~9006-9100 |
| **文件上传** | `/api/upload`, `/api/ai/upload`, `/api/comfyui/upload-base64` | ~9080-9200 |
| **本地素材库** | `/api/local-assets/*`（上传/导入/分类/打标/移动/删除） | ~9488-9819 |
| **RunningHub** | `/api/runninghub/{submit,workflow-submit,workflow-info,workflows}` | ~9839-10000 |
| **自动化工作流** | `/api/automation/workflows`, `.../run`, `.../status` | 新增 |
| **WebSocket** | `/ws/stats` 在线状态广播 | ~200 |

## 🔧 配置

| 文件 | 用途 |
|------|------|
| `requirements.txt` | Python 依赖（8 个包，含 `websockets`） |
| `VERSION` | 版本号（2026.06.25） |
| `Dockerfile` / `docker-compose.yml` | 容器化部署 |
| `static/update-notes.json` | 前端显示的更新日志 |
| `static/runninghub/api_providers.json` | RunningHub 内置 API 列表 |
| `workflows/*.json` | 7 个预置 ComfyUI 工作流 |
| `automation_workflows/*.json` | 用户导出的画布工作流（被 automation_cli 调用） |
| `tools/*/manifest.json` | Chrome/PS 扩展清单 |

## 📚 文档

- `README.md` — 项目主介绍（中英双语）
- `CLAUDE.md` — Claude Code 协作指引（Agent Teams Harness 8 人流程）
- `AGENTS.md` — Codex 协作指引
- `新手运行与使用教程.md` — 完整新手教程
- `MAC-使用说明.md` — Mac 平台专属说明
- `运行说明.txt` — 快速运行说明
- `automation_workflows/README.md` — 自动化 CLI 用法
- `static/system-prompts/infinite-canvas-prompt-templates.md` — Prompt 模板
- `static/vendor/MANIFEST.md` — 前端依赖清单

## 🧪 测试覆盖

✅ **pytest 测试套件** — `tests/` 目录下 5 个文件，1,544 行

| 测试文件 | 行数 | 覆盖范围 |
|---------|-----|---------|
| `test_automation_workflow.py` | 676 | 工作流后端 API、Pydantic 模型、helpers |
| `test_canvas_detected_workflows.py` | 296 | 画布 detected_workflows 提取 |
| `test_canvas_json_splitter.py` | 266 | 画布 JSON 拆分器 |
| `test_automation_cli.py` | 129 | CLI 子命令解析 + HTTP 集成 |
| `test_think_blocks.py` | 177 | LLM 思考块（`[THINK]...`）解析 |

无 CI / pytest.ini 配置；本地运行 `pytest tests/` 即可。

## 🔗 关键依赖（requirements.txt）

| 包 | 用途 |
|----|------|
| `fastapi` | Web 框架 + WebSocket |
| `uvicorn` | ASGI 服务器（端口 3000，`ws_ping_interval=None`） |
| `requests` | HTTP 客户端（API 调用） |
| `pydantic` | 数据校验（自动化工作流 API 模型） |
| `python-multipart` | 文件上传支持 |
| `httpx` | 异步 HTTP 客户端 |
| `pillow` | 图像处理（拼接/预览/帧抽取） |
| `websockets` | WS 服务端 / 客户端 |

`packages/` 含离线 wheels（23 个）：`fastapi-0.136.1`, `uvicorn-0.46.0`, `pydantic-2.13.4`, `pillow-12.2.0`, `httpx-0.28.1` 等。

## ✨ 功能矩阵

| # | 功能 | 说明 |
|---|------|------|
| 1 | 多协议 API | OpenAI / 异步 / Gemini / 方舟 |
| 2 | RunningHub | 工作流 / AI 应用 / 收费模型 |
| 3 | 火山引擎 | 人脸认证（修复中） |
| 4 | Modelscope | 免费 LLM + 图像模型 + LoRA |
| 5 | 即梦 CLI | 高级会员积分 / 文/图生图、文/图生视频 |
| 6 | 本地 ComfyUI | 局域网接入 + 自定义工作流导入 |
| 7 | 画布扩展 | 图片扩展 / 360 全景 / 视频帧抽取 / 循环节点 |
| 8 | 浏览器/PS 插件 | Chrome 批量采集 + Photoshop 直连 |
| 9 | **自动化工作流** | `automation_cli` 命令行调用导出画布（`/api/automation/*`） |
| 10 | **Docker 部署** | `docker-compose` 一键容器化运行 |

## 📝 快速开始

### Windows
```bash
1. 双击 安装依赖.bat
2. 双击 run.bat
3. 浏览器自动打开 http://127.0.0.1:3000
```

### macOS
```bash
1. 运行 mac-安装依赖.sh（或双击 mac-安装依赖.command）
2. 双击 mac-启动服务.command
```

### Docker
```bash
docker compose up -d
# 访问 http://localhost:3000
```

### 自动化 CLI（新增）
```bash
# 列出可用的工作流预设
python automation_cli.py list-workflows

# 用预设运行（支持多图 + 回调 URL）
python automation_cli.py run --workflow ecommerce-main \
  --image-url https://example.com/product.png \
  --callback-url https://my.app/webhook
```

### 三种运行模式（任选其一）
- **API 模式**：注册 apimart.ai / apib.ai，填写 API Key + 协议
- **Modelscope 模式**：免费，设置 Modelscope Key
- **本地 ComfyUI 模式**：左下角设置 ComfyUI 地址 + 导入工作流

## ⚖️ 许可证

**自定义著作权许可**：
- ✅ 个人/公司自用
- ❌ 禁止商业用途（封装成商业产品）
- ❌ 禁止转售
- 📖 二次开发必须开源 + 注明原作者
- 💼 商用须取得授权

## 🔗 外部资源

- **GitHub**: https://github.com/hero8152/Infinite-Canvas
- **B 站作者**: https://space.bilibili.com/78652351
- **视频教程**: https://youtu.be/1y9ShTvgC_w
- **API 推荐**: https://apib.ai/register?aff=1uyAbb

---

*索引生成工具：sc:index-repo ｜ 下次扫描节省：~55k 令牌/会话*

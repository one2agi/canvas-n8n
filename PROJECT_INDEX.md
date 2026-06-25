# 项目索引：Infinite-Canvas

> **生成时间**：2026-06-25 ｜ **版本**：2026.06.25 ｜ **作者**：hero8152
>
> **核心定位**：无限画布 — 集成 ComfyUI / 多家 LLM API / Modelscope / RunningHub / 即梦 / 火山引擎 的统一 AI 图像/视频生成前端

## 📁 项目结构

```
Infinite-Canvas/
├── main.py                       # 单一 FastAPI 主程序（15,073 行）
├── requirements.txt              # Python 依赖（fastapi/uvicorn/requests/pydantic/httpx/pillow...）
├── VERSION                       # 版本号文件（用于 GitHub 内置更新提示）
├── run.bat                       # Windows 一键启动（端口 3000）
├── mac-*.command / mac-*.sh      # macOS 启动/修复/依赖安装脚本
├── 安装依赖.bat / 安装即梦CLI.bat / 登录即梦CLI.bat
│
├── python/                       # 内置 Python 3.10 运行时（Windows CP314，零依赖运行）
├── packages/                     # 23 个离线 .whl 包（无需联网安装）
├── get-pip.py                    # pip 引导器
│
├── static/                       # 前端资源
│   ├── js/                       # 原生 JS 模块（canvas.js 667KB / smart-canvas.js 831KB）
│   │   └── i18n/                 # 7 语言国际化（common/canvas/studio/smart-canvas/...）
│   ├── css/                      # 7 个样式表（canvas.css 134KB）
│   ├── system-prompts/           # 内置 Prompt 模板
│   ├── runninghub/               # RunningHub API 提供商配置 + 缩略图
│   ├── vendor/                   # 第三方 css/fonts/js
│   └── update-notes.json         # 更新日志
│
├── workflows/                    # 7 个 ComfyUI 工作流 JSON
│   ├── 2511.json
│   ├── Flux2-Klein.json
│   ├── LTXDirectorv2-API.config.json
│   ├── LTXDirectorv2-API.json
│   ├── Z-Image-Enhance.json
│   ├── Z-Image.json
│   └── upscale.json
│
├── tools/                        # 浏览器/PS 扩展
│   ├── chrome-local-asset-importer/   # Chrome 批量采集到素材库
│   └── photoshop-asset-connector/     # Photoshop 直连画布
│
└── 文档
    ├── README.md                 # 项目介绍
    ├── 新手运行与使用教程.md      # 新手教程（25KB）
    ├── MAC-使用说明.md
    └── 运行说明.txt
```

## 🚀 入口点

| 类型 | 路径 | 说明 |
|------|------|------|
| **后端入口** | `main.py` | FastAPI 单文件应用，启动后监听 `http://127.0.0.1:3000` |
| **Windows 启动** | `run.bat` | 使用内置 `python/python.exe`，自动打开浏览器 |
| **macOS 启动** | `mac-启动服务.command` / `.sh` | Mac 启动脚本 |
| **依赖安装** | `安装依赖.bat` / `mac-安装依赖.sh` | 安装 requirements.txt |
| **CLI 工具** | `安装即梦CLI.bat` + `登录即梦CLI.bat` | 即梦 CLI 安装/登录 |

## 🧩 核心模块（main.py 内聚合）

main.py 是单体应用，按代码行分布对应以下模块：

| 功能域 | 关键 API 路由 | 行号区间 |
|--------|---------------|---------|
| **应用配置/启动** | `startup_event`, `ensure_runtime_config_files`, `load_env_file` | ~180-700 |
| **API 提供商管理** | 模型列表、归一化、合并默认/用户配置 | ~560-1110 |
| **更新机制** | `/api/check-update`, `/api/update-from-github`, `/api/update-rollback` | ~1784-2270 |
| **即梦 CLI** | `JimengPendingError`, 即梦任务队列 | ~4156 |
| **媒体预览** | `/api/media-preview`, `/api/image-jpeg` | ~4761-4830 |
| **视图/主页** | `/`, `/api/view`, `/api/download-output` | ~9006-9100 |
| **文件上传** | `/api/upload`, `/api/ai/upload`, `/api/comfyui/upload-base64` | ~9080-9200 |
| **本地素材库** | `/api/local-assets/*`（上传/导入/分类/打标/移动/删除） | ~9488-9819 |
| **RunningHub** | `/api/runninghub/{submit,workflow-submit,workflow-info,workflows}` | ~9839-10000 |
| **WebSocket** | `/ws/stats` 在线状态广播 | ~200 |

## 🔧 配置

| 文件 | 用途 |
|------|------|
| `requirements.txt` | Python 依赖清单（7 个包） |
| `VERSION` | 版本号（2026.06.25） |
| `static/update-notes.json` | 前端显示的更新日志 |
| `static/runninghub/api_providers.json` | RunningHub 内置 API 列表 |
| `workflows/*.json` | 7 个预置 ComfyUI 工作流 |
| `tools/*/manifest.json` | Chrome/PS 扩展清单 |

## 📚 文档

- `README.md` — 项目主介绍（中英双语、功能清单、API 推荐注册链接）
- `新手运行与使用教程.md` — 完整新手教程（25KB，含三种运行模式说明）
- `MAC-使用说明.md` — Mac 平台专属说明
- `运行说明.txt` — 快速运行说明（含视频教程 B 站链接）
- `static/system-prompts/infinite-canvas-prompt-templates.md` — Prompt 模板
- `static/vendor/MANIFEST.md` — 前端依赖清单

## 🧪 测试覆盖

⚠️ **无测试目录**。本项目未包含 `tests/`、`*test*.py` 等单元测试文件。
- 后端：单体应用，依赖人工测试
- 前端：手工验证

## 🔗 关键依赖（requirements.txt）

| 包 | 版本约束 | 用途 |
|----|---------|------|
| `fastapi` | (latest) | Web 框架 + WebSocket |
| `uvicorn` | (latest) | ASGI 服务器（端口 3000） |
| `requests` | (latest) | HTTP 客户端（API 调用） |
| `pydantic` | (latest) | 数据校验 |
| `python-multipart` | (latest) | 文件上传支持 |
| `httpx` | (latest) | 异步 HTTP 客户端 |
| `pillow` | (latest) | 图像处理（拼接/预览/帧抽取） |

`packages/` 含离线 wheels：`fastapi-0.136.1`, `uvicorn-0.46.0`, `pydantic-2.13.4`, `pillow-12.2.0`, `httpx-0.28.1`, 等 23 个。

## ✨ 功能矩阵（来自 README）

| # | 功能 | 说明 |
|---|------|------|
| 1 | 多协议 API | OpenAI / 异步 / Gemini / 方舟 协议 |
| 2 | RunningHub | 工作流 / AI 应用 / 收费模型调用 |
| 3 | 火山引擎 | 人脸认证（修复中） |
| 4 | Modelscope | 免费 LLM + 图像模型 + LoRA |
| 5 | 即梦 CLI | 高级会员积分 / 文生图 / 图生图 / 文生视频 / 图生视频 |
| 6 | 本地 ComfyUI | 局域网接入 + 自定义工作流导入 |
| 7 | 画布扩展 | 图片扩展 / 360 全景 / 视频帧抽取 / 循环节点 |
| 8 | 浏览器/PS 插件 | Chrome 批量采集 + Photoshop 直连 |

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

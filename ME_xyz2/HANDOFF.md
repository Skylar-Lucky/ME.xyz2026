# ME.xyz 协作交接包

日期：2026-07-24

本压缩包包含可运行产品 **MExyz-feature**，以及记忆图谱依赖目录 **braingraph**（CSV 导出路径需要二者相对位置保持不变）。

## 目录结构

```text
ME_xyz2/
├── HANDOFF.md          # 本说明
├── MExyz-feature/      # 主产品（FastAPI + 静态前端 + memory-map）
└── braingraph/         # 图谱前端源码 + 数据目录（运行时 CSV 写这里）
```

## 环境要求

- Windows + PowerShell
- Python **3.10+**（推荐 **3.12**）
- 智谱 GLM API Key

## 首次启动

在 `MExyz-feature` 目录：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

编辑 `backend/.env`，至少填写：

```text
GLM_API_KEY=你的key
GLM_MODEL=glm-4.5-flash
GLM_THINKING=disabled
```

> 注意：已从 DeepSeek 切换为智谱 GLM（open.bigmodel.cn），环境变量前缀由 `DEEPSEEK_*` 改为 `GLM_*`。

然后启动：

```powershell
.\start.ps1
```

或：

```powershell
.\start.ps1 -Port 8020
```

浏览器打开：http://127.0.0.1:8010

## 常用地址

| 用途 | URL |
|------|-----|
| 主站 | http://127.0.0.1:8010 |
| 记忆图谱 | http://127.0.0.1:8010/memory-map/ |
| API 文档 | http://127.0.0.1:8010/docs |
| 健康检查 | http://127.0.0.1:8010/health |

## 本包刻意未包含

- `.venv/`（体积大，需本地重建）
- `backend/.env`（含密钥，勿提交/转发）
- `backend/data/*.db`（本地用户数据）
- `__pycache__/` 等缓存

## 产品要点（便于联调）

1. 主对话软节奏约 **8–10 轮**，Gate 通过后可生成 3 个「未来的自己」
2. 「整理记忆」写入 SQLite，并导出 CSV 供记忆图谱读取
3. LLM 输出会过滤 `*` 字符；模型默认 `glm-4.5-flash` + thinking disabled

## 修改图谱前端时

源码在 `braingraph/memory-graph-demo/frontend/`，构建产物输出到 `MExyz-feature/ME_xyz/memory-map/`。仅跑产品、不改图谱 UI 时，**不必** `npm install`。

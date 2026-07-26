# ME.xyz 快速启动

## 一条命令启动

项目要求 Python 3.10+，推荐使用已验证的 Python 3.12。

首次安装：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

编辑 `backend/.env`，填入 `GLM_API_KEY`。然后运行：

```powershell
.\start.ps1
```

浏览器打开 http://127.0.0.1:8010 。主站、记忆图谱和 API 由同一个服务提供。

如需更换端口：

```powershell
.\start.ps1 -Port 8020
```

## 可用地址

- 前端：http://127.0.0.1:8010
- 健康检查：http://127.0.0.1:8010/health
- API 文档：http://127.0.0.1:8010/docs
- 记忆图谱：http://127.0.0.1:8010/memory-map/

SQLite 数据保存在 `backend/data/me.db`，按账号隔离。

## 记忆图谱数据流

```text
Memory Agent → MemoryEvent → SQLite
                           ↓
                    CSV Exporter
                           ↓
                CsvMemoryRepository
                           ↓
                    GraphBuilder
                           ↓
                 /api/memory-graph
```

SQLite 是唯一可写数据源。图谱 CSV
`../braingraph/memory-graph-demo/data/mexyz_memory_events.csv`
会在后端启动和每次“整理记忆”后自动重建。

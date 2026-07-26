# ME.xyz Backend

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# 编辑 .env：GLM_API_KEY、JWT_SECRET
```

## Run

```powershell
uvicorn main:app --reload --port 8000 --host 127.0.0.1
```

- Health: http://127.0.0.1:8000/health  
- Docs: http://127.0.0.1:8000/docs  

## Auth

- `POST /api/auth/register` `{email, password, nickname?}`
- `POST /api/auth/login` `{email, password}`
- 其他业务接口需 `Authorization: Bearer <token>`

## Memory

- `POST /api/memory/organize` `{session_id}` — 手动「整理记忆」后抽取事件并写入图谱

## Data

- SQLite：`data/me.db`（按用户隔离）
- 聊天消息发出即落库，刷新可回看

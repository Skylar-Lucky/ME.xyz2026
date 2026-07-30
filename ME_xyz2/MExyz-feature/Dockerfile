FROM python:3.12-slim

WORKDIR /app

# 先只拷贝 requirements，利用 Docker 层缓存——代码变了不用重装依赖
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY ME_xyz ME_xyz

WORKDIR /app/backend

EXPOSE 8010

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]

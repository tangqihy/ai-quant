# Quant Backend

A股回测系统后端

## 环境要求

- Python 3.9+
- FastAPI
- Uvicorn

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行

```bash
uvicorn app.main:app --reload
```

## 项目结构

```
app/
├── api/          # API路由
├── core/         # 核心配置
├── models/       # 数据模型
├── schemas/      # Pydantic schemas
├── services/     # 业务逻辑
└── main.py       # 应用入口
```

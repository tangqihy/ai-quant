"""
FastAPI application entry point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import routes
from app.api import auth_routes


def _preload_stock_list():
    """后台预加载股票列表到本地 DB（首次启动或过期时拉取 Tushare）"""
    try:
        from app.services.stock_list_store import ensure_initialized
        from app.services.tushare_service import tushare_service

        def fetcher():
            data = tushare_service.get_stock_list()
            return [
                {"symbol": item.get("symbol", ""), "name": item.get("name", ""), "market": "沪深A股"}
                for item in data
            ]
        ensure_initialized(fetcher)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Preload stock list failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时后台预加载股票列表，支持首次/每日更新"""
    import threading
    t = threading.Thread(target=_preload_stock_list, daemon=True)
    t.start()
    yield


app = FastAPI(
    title="A股回测系统 API",
    description="量化交易回测系统后端服务",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（auth 不鉴权，其余 /api/* 需 token）
app.include_router(auth_routes.router, prefix="/api/auth", tags=["auth"])
app.include_router(routes.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "A股回测系统 API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

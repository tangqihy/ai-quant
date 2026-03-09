"""
FastAPI application entry point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import routes


def _preload_stock_list():
    """后台预加载股票列表到本地 DB（首次启动或过期时拉取 AkShare）"""
    try:
        from app.services.stock_list_store import ensure_initialized
        try:
            import akshare as ak
        except ImportError:
            return
        from app.services.stock_service import retry

        def fetcher():
            df = retry(lambda: ak.stock_info_a_code_name())
            return [
                {"symbol": row.get("code", ""), "name": row.get("name", ""), "market": "沪深A股"}
                for _, row in df.iterrows()
            ]
        ensure_initialized(fetcher)
    except Exception:
        pass


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

# 注册路由
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

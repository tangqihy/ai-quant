"""
FastAPI application entry point
"""
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import routes
from app.api import auth_routes
from app.core.response import ok, fail
from app.core.exceptions import AppError
from app.core.config import settings
from app.core.logging import set_request_id, get_request_id
from app.core.health import get_health_checker


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
    title=settings.app_name,
    description="量化交易回测系统后端服务",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 请求ID中间件 ====================

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """请求ID中间件"""
    # 从请求头获取或生成请求ID
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    set_request_id(request_id)
    
    # 处理请求
    response = await call_next(request)
    
    # 添加请求ID到响应头
    response.headers["X-Request-ID"] = request_id
    
    return response


# ==================== 异常处理器 ====================

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """统一处理应用异常"""
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(error=exc.error_code, message=exc.message),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """统一处理未知异常"""
    import logging
    logger = logging.getLogger(__name__)
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=fail(error="INTERNAL_ERROR", message="服务器内部错误"),
    )


# 注册路由（auth 不鉴权，其余 /api/* 需 token）
app.include_router(auth_routes.router, prefix="/api/auth", tags=["auth"])
app.include_router(routes.router, prefix="/api")


@app.get("/")
async def root():
    return ok(message=settings.app_name)


@app.get("/health")
async def health_check():
    """基础健康检查"""
    return ok(message="healthy")


@app.get("/health/detailed")
async def detailed_health_check():
    """详细健康检查"""
    checker = get_health_checker()
    result = checker.check()
    
    if result["status"] == "healthy":
        return ok(data=result)
    else:
        return fail(error="UNHEALTHY", message="系统不健康", data=result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)

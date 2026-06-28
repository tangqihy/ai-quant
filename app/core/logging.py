"""
结构化日志模块

支持请求ID追踪、JSON格式输出、日志级别配置。
"""
import logging
import sys
import uuid
import json
from datetime import datetime
from typing import Optional
from contextvars import ContextVar
from app.core.config import settings

# 请求ID上下文变量
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # 添加请求ID
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id
        
        # 添加额外字段
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        # 添加异常信息
        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class RequestIdFilter(logging.Filter):
    """请求ID过滤器"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """添加请求ID到日志记录"""
        record.request_id = request_id_var.get() or ""
        return True


def setup_logging():
    """配置日志"""
    # 获取根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    
    # 根据配置选择格式化器
    if settings.debug:
        # 调试模式使用简单格式
        formatter = logging.Formatter(settings.log_format)
    else:
        # 生产模式使用JSON格式
        formatter = StructuredFormatter()
    
    console_handler.setFormatter(formatter)
    console_handler.addFilter(RequestIdFilter())
    
    root_logger.addHandler(console_handler)
    
    # 设置第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取日志器"""
    return logging.getLogger(name)


def set_request_id(request_id: Optional[str] = None) -> str:
    """设置请求ID"""
    if request_id is None:
        request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    return request_id


def get_request_id() -> Optional[str]:
    """获取当前请求ID"""
    return request_id_var.get()


# 初始化日志
setup_logging()

"""
统一 API 响应格式
规范：{ success: bool, data?: any, error?: string, message?: string }
"""
from typing import Any, Optional, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应模型"""
    success: bool = Field(..., description="请求是否成功")
    data: Optional[T] = Field(None, description="响应数据")
    error: Optional[str] = Field(None, description="错误类型（仅 success=false 时）")
    message: Optional[str] = Field(None, description="人类可读消息")


class PaginatedData(BaseModel, Generic[T]):
    """分页数据包装"""
    items: list[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(0, description="总记录数")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(20, description="每页数量")
    total_pages: int = Field(0, description="总页数")


def ok(data: Any = None, message: str = None) -> dict:
    """成功响应"""
    resp = {"success": True}
    if data is not None:
        resp["data"] = data
    if message:
        resp["message"] = message
    return resp


def fail(error: str, message: str = None) -> dict:
    """失败响应"""
    resp = {"success": False, "error": error}
    if message:
        resp["message"] = message
    return resp


def paginated(
    items: list,
    total: int,
    page: int,
    page_size: int,
    message: str = None,
) -> dict:
    """分页成功响应"""
    data = {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }
    return ok(data=data, message=message)

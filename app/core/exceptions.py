"""
统一异常体系

定义项目中所有自定义异常，便于统一捕获和处理。
"""
from typing import Optional, Any


class AppError(Exception):
    """应用基础异常"""
    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN",
        status_code: int = 500,
        details: Optional[Any] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


# ==================== 数据层异常 ====================

class DataSourceError(AppError):
    """数据源异常"""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="DATA_SOURCE_ERROR",
            status_code=502,
            details=details,
        )


class DataNotFoundError(AppError):
    """数据不存在"""
    def __init__(self, message: str = "数据不存在", details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="DATA_NOT_FOUND",
            status_code=404,
            details=details,
        )


class DataValidationError(AppError):
    """数据校验失败"""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="DATA_VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


# ==================== 业务层异常 ====================

class BusinessError(AppError):
    """业务逻辑异常"""
    def __init__(self, message: str, error_code: str = "BUSINESS_ERROR", details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=400,
            details=details,
        )


class OrderRejectedError(BusinessError):
    """订单被拒绝"""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="ORDER_REJECTED",
            details=details,
        )


class InsufficientBalanceError(BusinessError):
    """余额不足"""
    def __init__(self, message: str = "余额不足", details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_BALANCE",
            details=details,
        )


class RiskControlError(BusinessError):
    """风控拒绝"""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="RISK_CONTROL",
            details=details,
        )


# ==================== 认证/授权异常 ====================

class AuthError(AppError):
    """认证异常"""
    def __init__(self, message: str = "未登录或 token 已失效"):
        super().__init__(
            message=message,
            error_code="AUTH_ERROR",
            status_code=401,
        )


class ForbiddenError(AppError):
    """权限不足"""
    def __init__(self, message: str = "权限不足"):
        super().__init__(
            message=message,
            error_code="FORBIDDEN",
            status_code=403,
        )


# ==================== 配置异常 ====================

class ConfigError(AppError):
    """配置错误"""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="CONFIG_ERROR",
            status_code=500,
            details=details,
        )

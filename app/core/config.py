"""
配置管理模块

使用 Pydantic Settings 管理应用配置，支持环境变量和 .env 文件。
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用配置
    app_name: str = Field(default="A股回测系统", description="应用名称")
    app_version: str = Field(default="1.0.0", description="应用版本")
    debug: bool = Field(default=False, description="调试模式")
    
    # 服务器配置
    host: str = Field(default="0.0.0.0", description="服务器地址")
    port: int = Field(default=8000, description="服务器端口")
    
    # CORS 配置
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="允许的跨域来源"
    )
    
    # 数据库配置
    db_path: str = Field(default="app/data", description="数据库文件路径")
    
    # Tushare 配置
    tushare_token: Optional[str] = Field(default=None, description="Tushare API Token")

    # 数据源配置
    data_source_primary: str = Field(default="tushare", description="主数据源")
    
    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式"
    )
    
    # 回测配置
    backtest_default_capital: float = Field(default=1000000.0, description="默认初始资金")
    backtest_commission_rate: float = Field(default=0.0003, description="佣金费率")
    backtest_slippage: float = Field(default=0.001, description="滑点")
    
    # 风控配置
    risk_max_position_pct: float = Field(default=0.3, description="单只股票最大仓位比例")
    risk_max_drawdown_pct: float = Field(default=0.2, description="最大回撤比例")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings

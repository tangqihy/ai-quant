"""
健康检查模块

提供系统健康检查功能，包括数据库、数据源、服务状态等。
"""
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime
from app.core.config import settings
from app.core.response import ok, fail

logger = logging.getLogger(__name__)


class HealthChecker:
    """
    健康检查器
    
    检查系统各组件的健康状态。
    """
    
    def __init__(self):
        """初始化健康检查器"""
        self._checks = {}
        self._register_default_checks()
    
    def _register_default_checks(self):
        """注册默认检查项"""
        self._checks = {
            "database": self._check_database,
            "data_source": self._check_data_source,
            "disk_space": self._check_disk_space,
            "memory": self._check_memory,
        }
    
    def _check_database(self) -> Dict:
        """
        检查数据库连接
        
        Returns:
            Dict: 检查结果
        """
        try:
            import sqlite3
            import os
            
            # 检查数据库文件是否存在
            db_path = os.path.join(settings.db_path, "klines.db")
            if not os.path.exists(db_path):
                return {
                    "status": "unhealthy",
                    "message": f"数据库文件不存在: {db_path}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            
            # 尝试连接数据库
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            
            return {
                "status": "healthy",
                "message": "数据库连接正常",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"数据库连接失败: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def _check_data_source(self) -> Dict:
        """
        检查数据源连接
        
        Returns:
            Dict: 检查结果
        """
        try:
            from app.providers.fallback import create_fallback_provider
            
            provider = create_fallback_provider()
            health = provider.health_check()
            
            if health.get("primary", False):
                return {
                    "status": "healthy",
                    "message": "主数据源连接正常",
                    "details": health,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            elif health.get("fallback", False):
                return {
                    "status": "degraded",
                    "message": "主数据源不可用，已降级到备数据源",
                    "details": health,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": "所有数据源都不可用",
                    "details": health,
                    "timestamp": datetime.utcnow().isoformat(),
                }
        except Exception as e:
            logger.error(f"Data source health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"数据源检查失败: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def _check_disk_space(self) -> Dict:
        """
        检查磁盘空间
        
        Returns:
            Dict: 检查结果
        """
        try:
            import shutil
            
            # 获取磁盘使用情况
            total, used, free = shutil.disk_usage("/")
            
            # 计算使用率
            usage_percent = (used / total) * 100
            
            # 判断状态
            if usage_percent > 90:
                status = "unhealthy"
                message = f"磁盘空间严重不足: {usage_percent:.1f}%"
            elif usage_percent > 80:
                status = "degraded"
                message = f"磁盘空间不足: {usage_percent:.1f}%"
            else:
                status = "healthy"
                message = f"磁盘空间充足: {usage_percent:.1f}%"
            
            return {
                "status": status,
                "message": message,
                "details": {
                    "total_gb": total / (1024**3),
                    "used_gb": used / (1024**3),
                    "free_gb": free / (1024**3),
                    "usage_percent": usage_percent,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Disk space health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"磁盘空间检查失败: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def _check_memory(self) -> Dict:
        """
        检查内存使用
        
        Returns:
            Dict: 检查结果
        """
        try:
            import psutil
            
            # 获取内存使用情况
            memory = psutil.virtual_memory()
            
            # 判断状态
            if memory.percent > 90:
                status = "unhealthy"
                message = f"内存使用率过高: {memory.percent}%"
            elif memory.percent > 80:
                status = "degraded"
                message = f"内存使用率较高: {memory.percent}%"
            else:
                status = "healthy"
                message = f"内存使用正常: {memory.percent}%"
            
            return {
                "status": status,
                "message": message,
                "details": {
                    "total_gb": memory.total / (1024**3),
                    "available_gb": memory.available / (1024**3),
                    "used_gb": memory.used / (1024**3),
                    "percent": memory.percent,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        except ImportError:
            return {
                "status": "unknown",
                "message": "psutil未安装，无法检查内存",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Memory health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"内存检查失败: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def check(self, checks: Optional[List[str]] = None) -> Dict:
        """
        执行健康检查
        
        Args:
            checks: 要检查的项目列表，None表示检查所有
            
        Returns:
            Dict: 检查结果
        """
        if checks is None:
            checks = list(self._checks.keys())
        
        results = {}
        overall_status = "healthy"
        
        for check_name in checks:
            if check_name in self._checks:
                try:
                    result = self._checks[check_name]()
                    results[check_name] = result
                    
                    # 更新整体状态
                    if result["status"] == "unhealthy":
                        overall_status = "unhealthy"
                    elif result["status"] == "degraded" and overall_status != "unhealthy":
                        overall_status = "degraded"
                except Exception as e:
                    logger.error(f"Health check {check_name} failed: {e}")
                    results[check_name] = {
                        "status": "unhealthy",
                        "message": f"检查失败: {str(e)}",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    overall_status = "unhealthy"
        
        return {
            "status": overall_status,
            "checks": results,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def register_check(self, name: str, check_func):
        """
        注册自定义检查项
        
        Args:
            name: 检查名称
            check_func: 检查函数
        """
        self._checks[name] = check_func


# 全局健康检查器实例
health_checker = HealthChecker()


def get_health_checker() -> HealthChecker:
    """获取健康检查器实例"""
    return health_checker

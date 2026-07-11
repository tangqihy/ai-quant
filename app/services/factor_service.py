"""
因子数据服务 - 管理IC分析结果和因子选股
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# 数据文件路径
FACTOR_IC_PATH = Path(__file__).parent.parent.parent / "data" / "factor_ic.json"


def _empty_factor_ic() -> Dict[str, Any]:
    """数据未生成时返回的空结构（HTTP 200），让前端展示空状态而非报错。"""
    return {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "test_period": "-",
        "cross_sections": 0,
        "forward_days": 0,
        "neutralization": "-",
        "factors": [],
        "event_factors": [],
        "needs_generation": True,
        "message": "因子IC数据尚未生成，请运行 scripts/run_factor_ic.py 生成 data/factor_ic.json",
    }


def _empty_summary() -> Dict[str, Any]:
    return {
        "total_factors": 0,
        "effective_count": 0,
        "weak_count": 0,
        "invalid_count": 0,
        "test_period": "-",
        "cross_sections": 0,
        "forward_days": 0,
        "neutralization": "-",
        "updated_at": "-",
        "top_factors": [],
        "needs_generation": True,
        "message": "因子IC数据尚未生成，请运行 scripts/run_factor_ic.py 生成 data/factor_ic.json",
    }


def get_factor_ic() -> Dict[str, Any]:
    """获取因子IC分析结果"""
    if not FACTOR_IC_PATH.exists():
        logger.warning("factor_ic.json 不存在: %s", FACTOR_IC_PATH)
        return _empty_factor_ic()

    try:
        with open(FACTOR_IC_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("读取 factor_ic.json 失败: %s", e)
        return _empty_factor_ic()


def get_effective_factors() -> List[Dict[str, Any]]:
    """获取有效因子列表（ICIR > 0.5）"""
    data = get_factor_ic()
    if data.get("needs_generation"):
        return []

    return [f for f in data.get("factors", []) if f.get("verdict") == "effective"]


def get_factor_by_name(name: str) -> Optional[Dict[str, Any]]:
    """根据名称获取单个因子"""
    data = get_factor_ic()
    if data.get("needs_generation"):
        return None

    for f in data.get("factors", []):
        if f["name"] == name:
            return f
    return None


def get_factor_summary() -> Dict[str, Any]:
    """获取因子概览统计"""
    data = get_factor_ic()
    if data.get("needs_generation"):
        return _empty_summary()

    factors = data.get("factors", [])
    effective = [f for f in factors if f["verdict"] == "effective"]
    weak = [f for f in factors if f["verdict"] == "weak"]
    invalid = [f for f in factors if f["verdict"] == "invalid"]

    return {
        "total_factors": len(factors),
        "effective_count": len(effective),
        "weak_count": len(weak),
        "invalid_count": len(invalid),
        "test_period": data.get("test_period"),
        "cross_sections": data.get("cross_sections"),
        "forward_days": data.get("forward_days"),
        "neutralization": data.get("neutralization"),
        "updated_at": data.get("updated_at"),
        "top_factors": [
            {"name": f["name"], "display_name": f["display_name"], "icir": f["icir"]}
            for f in sorted(effective, key=lambda x: abs(x["icir"]), reverse=True)[:3]
        ],
    }

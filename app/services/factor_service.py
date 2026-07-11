"""
因子数据服务 - 管理IC分析结果和因子选股
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# 数据文件路径
FACTOR_IC_PATH = Path(__file__).parent.parent.parent / "data" / "factor_ic.json"


def get_factor_ic() -> Dict[str, Any]:
    """获取因子IC分析结果"""
    if not FACTOR_IC_PATH.exists():
        return {"error": "IC数据文件不存在，请先运行IC分析"}

    with open(FACTOR_IC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_effective_factors() -> List[Dict[str, Any]]:
    """获取有效因子列表（ICIR > 0.5）"""
    data = get_factor_ic()
    if "error" in data:
        return []

    return [f for f in data.get("factors", []) if f.get("verdict") == "effective"]


def get_factor_by_name(name: str) -> Optional[Dict[str, Any]]:
    """根据名称获取单个因子"""
    data = get_factor_ic()
    if "error" in data:
        return None

    for f in data.get("factors", []):
        if f["name"] == name:
            return f
    return None


def get_factor_summary() -> Dict[str, Any]:
    """获取因子概览统计"""
    data = get_factor_ic()
    if "error" in data:
        return {"error": data["error"]}

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
        ]
    }

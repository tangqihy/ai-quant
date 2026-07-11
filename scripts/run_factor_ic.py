"""
一键生成因子IC分析结果 (data/factor_ic.json)。

流程:
1. 通过 Tushare 下载 trade_cal / daily / daily_basic / adj_factor / fina_indicator 原始数据
2. 归一化到 normalized 层 (DuckDB Parquet 视图)
3. 用 ICAnalyzer 计算每个注册因子的 IC/ICIR 与分组收益
4. 汇总写入 data/factor_ic.json，供前端因子分析页消费

注意: 该脚本会大量调用 Tushare 接口（受速率限制），首次回填一年数据可能耗时
数十分钟至数小时，并消耗相应的 Tushare 积分额度。已下载的批次会被跳过，
可安全中断后重跑。

用法:
    python scripts/run_factor_ic.py                       # 默认最近 1 年
    python scripts/run_factor_ic.py --start 20250101 --end 20260710
    python scripts/run_factor_ic.py --forward-days 10 --skip-download    # 仅重算IC
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 让脚本能从项目根目录导入 app.*
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# 触发因子注册
from app.factors import base_factors, financial_factors  # noqa: F401,E402
from app.factors.registry import factor_registry  # noqa: E402
from app.factors.ic_analysis import ICAnalyzer  # noqa: E402
from app.data.collector import TushareCollector  # noqa: E402
from app.data.scheduler import DownloadScheduler  # noqa: E402
from app.data.normalize import DataNormalizer  # noqa: E402
from app.data.duckdb_client import DuckDBClient  # noqa: E402
from app.data.pit import PITQuery  # noqa: E402

# 英文 category → 前端期望的中文类别
CATEGORY_CN = {
    "market": "价值",
    "financial": "基本面",
    "momentum": "动量",
    "reversal": "反转",
    "volatility": "波动率",
    "turnover": "流动性",
    "liquidity": "流动性",
    "technical": "技术",
    "event": "事件",
    "composite": "综合",
}

FACTOR_IC_PATH = ROOT_DIR / "data" / "factor_ic.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("factor_ic")


def get_token() -> str:
    token = os.environ.get("TUSHARE_TOKEN") or os.environ.get("TUSH_TOKEN", "")
    if not token:
        # 尝试从 .env 读取
        env_file = ROOT_DIR / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("TUSHARE_TOKEN"):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not token:
        logger.error("未找到 TUSHARE_TOKEN，请在 .env 或环境变量中配置")
        sys.exit(1)
    return token


def download_pipeline(token: str, start_date: str, end_date: str) -> None:
    """下载原始数据并归一化。"""
    collector = TushareCollector(token=token, raw_dir=ROOT_DIR / "data" / "raw")
    scheduler = DownloadScheduler(collector, raw_dir=ROOT_DIR / "data" / "raw")

    # 1) trade_cal（用于确定交易日，避免对非交易日空跑）
    logger.info("下载 trade_cal %s ~ %s", start_date, end_date)
    try:
        scheduler.collector.download_with_retry(
            interface="trade_cal",
            params={"exchange": "SSE", "start_date": start_date, "end_date": end_date},
        )
    except Exception as e:
        logger.warning("trade_cal 下载失败: %s", e)

    # 2) stock_basic（get_universe 依赖 list_date 列）
    logger.info("下载 stock_basic")
    try:
        scheduler.collector.download_with_retry(
            interface="stock_basic",
            params={"list_status": "L"},
        )
    except Exception as e:
        logger.warning("stock_basic 下载失败: %s", e)

    # 3) 先归一化 trade_cal + stock_basic，拿到交易日列表与股票池
    normalizer = DataNormalizer(
        raw_dir=ROOT_DIR / "data" / "raw",
        normalized_dir=ROOT_DIR / "data" / "normalized",
    )
    normalizer.normalize_interface("trade_cal")
    normalizer.normalize_interface("stock_basic")

    trading_days: list[str] = []
    try:
        client = DuckDBClient(normalized_dir=ROOT_DIR / "data" / "normalized")
        client._ensure_view("trade_cal")
        df = client.query(
            "SELECT cal_date FROM trade_cal WHERE is_open=1 AND cal_date>=? AND cal_date<=? ORDER BY cal_date",
            [start_date, end_date],
        )
        trading_days = [str(d) for d in df["cal_date"].tolist()]
        client.close()
    except Exception as e:
        logger.warning("读取 trade_cal 失败，回退到按日历日下载: %s", e)

    if not trading_days:
        # 回退：按日历日逐日跑（run_daily 内部会跳过已下载）
        logger.info("回退: 按日历日 %s ~ %s 逐日下载", start_date, end_date)
        scheduler.run_full(start_date, end_date)
    else:
        logger.info("交易日数: %d，逐日下载 daily/daily_basic/adj_factor", len(trading_days))
        for i, day in enumerate(trading_days, 1):
            try:
                scheduler.run_daily(date=day)
            except Exception as e:
                logger.warning("run_daily %s 失败: %s", day, e)
            if i % 20 == 0:
                logger.info("  下载进度 %d/%d", i, len(trading_days))

    # 3) 财务数据（fina_indicator 等，供财务因子使用）
    logger.info("下载财务数据 (最近 4 个报告期)")
    try:
        scheduler.run_financial(lookback_periods=4)
    except Exception as e:
        logger.warning("财务数据下载失败: %s", e)

    # 4) 归一化全部接口
    logger.info("归一化 raw -> normalized")
    counts = normalizer.normalize_all()
    logger.info("归一化批次: %s", counts)


def compute_factor_ic(start_date: str, end_date: str, forward_days: int) -> dict:
    """对所有注册因子计算 IC/ICIR 与分组收益，返回前端期望的结构。"""
    client = DuckDBClient(normalized_dir=ROOT_DIR / "data" / "normalized")
    trade_dates = client.get_trade_dates(start_date, end_date)
    pit = PITQuery(client, trade_dates=trade_dates)
    analyzer = ICAnalyzer(pit)

    factors_out = []
    metas = factor_registry.list_factors()
    total_cross = 0

    logger.info("开始计算 %d 个因子的 IC (前瞻 %d 日)", len(metas), forward_days)
    for idx, meta in enumerate(metas, 1):
        logger.info("[%d/%d] %s (%s)", idx, len(metas), meta.name, meta.category)
        try:
            summary = analyzer.calculate_ic_summary(
                meta.name, start_date, end_date, forward_days=forward_days
            )
            group_df = analyzer.calculate_group_returns(
                meta.name, start_date, end_date, forward_days=forward_days, n_groups=5
            )
        except Exception as e:
            logger.warning("因子 %s 计算失败: %s", meta.name, e)
            continue

        icir = summary.get("raw_ic_ir")
        ic_mean = summary.get("raw_ic_mean")
        ic_std = summary.get("raw_ic_std")
        sample = summary.get("sample_count") or 0
        total_cross = max(total_cross, sample)

        # 有效性判定（|ICIR| 阈值）
        if icir is None:
            verdict = "invalid"
        elif abs(icir) >= 0.5:
            verdict = "effective"
        elif abs(icir) >= 0.3:
            verdict = "weak"
        else:
            verdict = "invalid"

        # 分组收益：按组聚合到整体均值
        group_returns: list[float] = []
        if not group_df.empty:
            avg = group_df.groupby("group")["return"].mean().sort_index()
            group_returns = [float(v) for v in avg.tolist()]
        group_labels = [f"Q{i+1}" for i in range(len(group_returns))]

        factors_out.append({
            "name": meta.name,
            "display_name": meta.description or meta.name,
            "category": CATEGORY_CN.get(meta.category, meta.category),
            "direction": meta.direction,
            "icir": float(icir) if icir is not None else 0.0,
            "ic_mean": float(ic_mean) if ic_mean is not None else 0.0,
            "ic_std": float(ic_std) if ic_std is not None else 0.0,
            "verdict": verdict,
            "description": meta.description or "",
            "group_returns": group_returns,
            "group_labels": group_labels,
        })

    client.close()

    factors_out.sort(key=lambda x: abs(x["icir"]), reverse=True)

    return {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "test_period": f"{start_date} ~ {end_date}",
        "cross_sections": total_cross,
        "forward_days": forward_days,
        "neutralization": "无",
        "factors": factors_out,
        "event_factors": [],
    }


def main():
    parser = argparse.ArgumentParser(description="生成因子IC分析结果")
    parser.add_argument("--start", default=None, help="起始日期 YYYYMMDD，默认最近1年")
    parser.add_argument("--end", default=None, help="结束日期 YYYYMMDD，默认今天")
    parser.add_argument("--forward-days", type=int, default=10, help="前瞻天数，默认10")
    parser.add_argument("--skip-download", action="store_true", help="跳过下载，仅重算IC")
    args = parser.parse_args()

    end_date = args.end or datetime.now().strftime("%Y%m%d")
    if args.start:
        start_date = args.start
    else:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    if not args.skip_download:
        token = get_token()
        download_pipeline(token, start_date, end_date)

    logger.info("计算因子 IC ...")
    result = compute_factor_ic(start_date, end_date, args.forward_days)

    FACTOR_IC_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FACTOR_IC_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    effective = sum(1 for x in result["factors"] if x["verdict"] == "effective")
    logger.info(
        "完成: 共 %d 个因子，有效 %d，写入 %s",
        len(result["factors"]), effective, FACTOR_IC_PATH,
    )


if __name__ == "__main__":
    main()

"""
API routes
"""
import math
from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.services.stock_service import stock_service
from app.services.tushare_service import tushare_service
from app.services.backtest_service import run_backtest
from app.services.backtest_v2_service import run_backtest_v2
from app.services.storage_service import backtest_storage
from app.services.indicator_service import indicator_service
from app.strategies import list_strategies as get_strategies_list
from app.api.deps import require_auth
from app.core.version import get_build_info
from app.core.response import ok, fail, paginated

router = APIRouter(dependencies=[Depends(require_auth)])


def _json_safe_num(v: Any) -> Optional[float]:
    """指标值转 JSON 安全数字；NaN/Inf → None。"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        fv = float(v)
        if math.isnan(fv) or math.isinf(fv):
            return None
        return round(fv, 4)
    return v


# 回测请求模型（兼容旧字段，策略参数可扩展）
class BacktestRequest(BaseModel):
    symbol: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    strategy: str = "ma_cross"
    short_window: int = 5
    long_window: int = 20
    initial_capital: float = 1000000
    save_result: bool = True  # 是否保存结果
    # RSI 等策略参数（可选）
    period: Optional[int] = None
    oversold: Optional[int] = None
    overbought: Optional[int] = None
    engine: str = "v2"


@router.get("/stocks")
async def get_stocks(
    market: str = Query("沪深A股", description="市场类型"),
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(20, description="每页数量", ge=1, le=100),
    search: str = Query("", description="搜索关键词(代码或名称)")
):
    """获取股票列表（分页，服务端分页避免一次性加载全部）"""
    try:
        result = stock_service.get_stock_list(market=market, page=page, page_size=page_size, search=search or None)
        if isinstance(result, dict):
            return paginated(
                items=result["data"],
                total=result["total"],
                page=page,
                page_size=page_size,
            )
        total = len(result)
        start = (page - 1) * page_size
        end = start + page_size
        return paginated(
            items=result[start:end],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{symbol}")
async def get_stock(symbol: str):
    """获取单个股票信息"""
    try:
        info = stock_service.get_stock_info(symbol)
        return ok(data=info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{symbol}/history")
async def get_stock_history(
    symbol: str,
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    adjust: str = Query("qfq", description="复权类型: qfq-前复权, hfq-后复权, ''-不复权"),
    period: str = Query("daily", description="周期: daily/1min/5min/15min/30min/60min"),
):
    """获取股票历史K线数据（日线或分钟线）"""
    try:
        if period and period != "daily":
            klines = tushare_service.get_stock_minutes(
                symbol=symbol,
                freq=period,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            klines = stock_service.get_stock_history(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )
        return ok(data={"symbol": symbol, "klines": klines, "total": len(klines)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{symbol}/realtime")
async def get_stock_realtime(symbol: str):
    """获取股票实时行情"""
    try:
        quote = stock_service.get_realtime_quote(symbol)
        return ok(data=quote)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quotes/realtime")
async def get_realtime_quotes(
    symbols: str = Query(..., description="股票代码逗号分隔")
):
    """批量获取股票行情（Tushare 最新日线近似）"""
    try:
        symbol_list = [s.strip() for s in symbols.split(",")]
        quotes = stock_service.get_realtime_quotes(symbol_list)
        response = ok(data=quotes)
        response["total"] = len(quotes)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indicators/{symbol}")
async def get_indicators(
    symbol: str,
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    indicators: str = Query(
        "ma",
        description="指标名，逗号分隔，如 ma,boll,rsi,macd,fenshi_t0,capital_trend",
    ),
    period: str = Query("daily", description="周期: daily/1min/5min/15min/30min/60min"),
    index_symbol: str = Query(
        "000001.SH",
        description="capital_trend 用的指数代码（新浪/通达信 INDEX*），默认上证指数",
    ),
):
    """
    获取指定股票的 K 线及叠加指标数据，供 K 线图叠加使用。
    返回 data 数组中每项为一条 K 线并附带该日各指标值（如 ma5, ma10, ma20, boll_upper 等）。
    fenshi_t0 / capital_trend 建议配合 period=1min 或 5min。
    """
    try:
        if period and period != "daily":
            klines = tushare_service.get_stock_minutes(
                symbol=symbol,
                freq=period,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            klines = stock_service.get_stock_history(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
        if not klines:
            return ok(data={"symbol": symbol, "klines": [], "total": 0})
        names = [s.strip().lower() for s in indicators.split(",") if s.strip()]
        if not names:
            names = ["ma"]

        index_klines = None
        if "capital_trend" in names:
            if period and period != "daily":
                index_klines = tushare_service.get_stock_minutes(
                    symbol=index_symbol,
                    freq=period,
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                # 日线指数：用 000001.SH → 代码 000001 在 Tushare 需带市场；此处走分钟同源简化用日线股票接口不稳定
                # 上证日线用 tushare daily(ts_code=000001.SH)
                try:
                    ts_code = index_symbol if "." in index_symbol else f"{index_symbol}.SH"
                    code = ts_code.split(".")[0]
                    # 复用历史接口：指数在本地可能无缓存，直接 pro.daily
                    if tushare_service.pro:
                        start = start_date or (klines[0]["date"].replace("-", "") if klines else None)
                        end = end_date
                        if start and "-" in str(start):
                            start = str(start).replace("-", "")
                        df = tushare_service.pro.index_daily(
                            ts_code=ts_code if ts_code.endswith((".SH", ".SZ")) else f"{code}.SH",
                            start_date=start,
                            end_date=end,
                        )
                        if df is not None and not df.empty:
                            index_klines = [
                                {
                                    "date": tushare_service._format_date(str(r["trade_date"])),
                                    "open": float(r["open"]),
                                    "high": float(r["high"]),
                                    "low": float(r["low"]),
                                    "close": float(r["close"]),
                                    "volume": float(r.get("vol") or 0),
                                }
                                for _, r in df.sort_values("trade_date").iterrows()
                            ]
                except Exception:
                    index_klines = None

        # 为每个指标计算序列，并合并到每行
        result_rows = []
        for i, row in enumerate(klines):
            out = dict(row)
            result_rows.append(out)
        for ind_name in names:
            if ind_name not in ("ma", "rsi", "macd", "boll", "fenshi_t0", "capital_trend"):
                continue
            params = {}
            if ind_name == "ma":
                params = {"periods": [5, 10, 20]}
            elif ind_name == "rsi":
                params = {"period": 14}
            elif ind_name == "macd":
                params = {"fast": 12, "slow": 26, "signal": 9}
            elif ind_name == "boll":
                params = {"period": 20, "std_mult": 2.0}
            elif ind_name == "fenshi_t0":
                params = {"fast": 30, "slow": 900}
            elif ind_name == "capital_trend":
                params = {"index_data": index_klines}
            ind_result = indicator_service.get_indicator(klines, ind_name, params)
            for key, values in ind_result.items():
                for i, v in enumerate(values):
                    if i < len(result_rows):
                        result_rows[i][key] = _json_safe_num(v)
        return ok(
            data={
                "symbol": symbol,
                "klines": result_rows,
                "total": len(result_rows),
                "period": period,
                "index_symbol": index_symbol if "capital_trend" in names else None,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backtest")
async def run_backtest_api(config: BacktestRequest):
    """运行回测"""
    try:
        # 获取历史数据
        data = stock_service.get_stock_history(
            symbol=config.symbol,
            start_date=config.start_date,
            end_date=config.end_date,
            adjust=""
        )
        
        if not data or len(data) < 50:
            return fail(error="数据不足", message="需要至少50条K线数据")
            
        # 运行回测
        strategy_params = {}
        if config.period is not None:
            strategy_params["period"] = config.period
        if config.oversold is not None:
            strategy_params["oversold"] = config.oversold
        if config.overbought is not None:
            strategy_params["overbought"] = config.overbought
        if (config.engine or "v2").lower() == "v1":
            result = run_backtest(
                symbol=config.symbol,
                data=data,
                strategy=config.strategy,
                short_window=config.short_window,
                long_window=config.long_window,
                initial_capital=config.initial_capital,
                **strategy_params,
            )
        else:
            result = run_backtest_v2(
                symbol=config.symbol,
                data=data,
                strategy=config.strategy,
                short_window=config.short_window,
                long_window=config.long_window,
                initial_capital=config.initial_capital,
                **strategy_params,
            )
        if "error" in result:
            return fail(error=result["error"])
        
        # 保存结果
        if config.save_result:
            task_id = backtest_storage.save_result(result)
            result['task_id'] = task_id

        response = ok(data=result)
        response.update(result)
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest/strategies")
async def get_strategies():
    """获取可用策略列表（从策略注册表动态返回）"""
    return ok(data=get_strategies_list())


# 静态路径须在 /backtest/{task_id} 之前注册
from app.api.robustness_routes import router as robustness_router
router.include_router(robustness_router)


@router.get("/backtest/{task_id}")
async def get_backtest_result(task_id: str):
    """获取回测结果"""
    result = backtest_storage.get_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="回测结果不存在")
    return ok(data=result)


@router.get("/backtest")
async def list_backtest_results(
    limit: int = Query(20, description="返回数量"),
    symbol: Optional[str] = Query(None, description="股票代码过滤")
):
    """列出回测历史"""
    results = backtest_storage.list_results(limit=limit, symbol=symbol)
    response = ok(data=results)
    response["total"] = len(results)
    return response


@router.delete("/backtest/{task_id}")
async def delete_backtest_result(task_id: str):
    """删除回测结果"""
    success = backtest_storage.delete_result(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="回测结果不存在")
    return ok(message="删除成功")


# 导入并包含模拟交易路由
from app.api.simulation_routes import router as simulation_router
router.include_router(simulation_router)

# 导入并包含风控路由
from app.api.risk_routes import router as risk_router
router.include_router(risk_router)

# 导入并包含自选路由
from app.api.watchlist_routes import router as watchlist_router
router.include_router(watchlist_router)

# 信号监控与策略会话
from app.api.signal_routes import router as signal_router
router.include_router(signal_router)

# 研究画布（Stock Canvas）
from app.api.canvas_routes import router as canvas_router
router.include_router(canvas_router)


# ==================== 新闻资讯 ====================

@router.get("/news")
async def get_news(
    limit: int = Query(20, ge=1, le=50, description="返回条数"),
    src: str = Query("auto", description="来源: auto / tushare / eastmoney"),
):
    """获取财经新闻 / 快讯列表"""
    try:
        from app.services.news_service import get_news as fetch_news

        items = fetch_news(limit=limit, src=src)
        return ok(data={"items": items, "total": len(items)})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取新闻失败: {e}")


# ==================== 版本号 ====================

@router.get("/version")
async def get_version():
    """获取后端版本号"""
    return ok(data=get_build_info())

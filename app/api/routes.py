"""
API routes
"""
from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List, Dict
from pydantic import BaseModel
from app.services.stock_service import stock_service
from app.services.backtest_service import run_backtest
from app.services.storage_service import backtest_storage
from app.services.indicator_service import indicator_service
from app.strategies import list_for_api as get_strategies_list
from app.api.deps import require_auth
from app.core.version import get_build_info

router = APIRouter(dependencies=[Depends(require_auth)])


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
            return {
                "success": True,
                "data": result["data"],
                "total": result["total"],
                "page": page,
                "page_size": page_size,
                "total_pages": (result["total"] + page_size - 1) // page_size
            }
        total = len(result)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "success": True,
            "data": result[start:end],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{symbol}")
async def get_stock(symbol: str):
    """获取单个股票信息"""
    try:
        info = stock_service.get_stock_info(symbol)
        return {
            "success": True,
            "data": info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{symbol}/history")
async def get_stock_history(
    symbol: str,
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    adjust: str = Query("qfq", description="复权类型: qfq-前复权, hfq-后复权, ''-不复权")
):
    """获取股票历史K线数据（日线）"""
    try:
        klines = stock_service.get_stock_history(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        )
        return {
            "success": True,
            "symbol": symbol,
            "data": klines,
            "total": len(klines)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{symbol}/realtime")
async def get_stock_realtime(symbol: str):
    """获取股票实时行情"""
    try:
        quote = stock_service.get_realtime_quote(symbol)
        return {
            "success": True,
            "data": quote
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quotes/realtime")
async def get_realtime_quotes(
    symbols: str = Query(..., description="股票代码逗号分隔")
):
    """批量获取股票实时行情"""
    try:
        symbol_list = [s.strip() for s in symbols.split(",")]
        quotes = stock_service.get_realtime_quotes(symbol_list)
        return {
            "success": True,
            "data": quotes,
            "total": len(quotes)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indicators/{symbol}")
async def get_indicators(
    symbol: str,
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    indicators: str = Query("ma", description="指标名，逗号分隔，如 ma,boll,rsi,macd"),
):
    """
    获取指定股票的 K 线及叠加指标数据，供 K 线图叠加使用。
    返回 data 数组中每项为一条 K 线并附带该日各指标值（如 ma5, ma10, ma20, boll_upper 等）。
    """
    try:
        klines = stock_service.get_stock_history(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
        if not klines:
            return {"success": True, "symbol": symbol, "data": [], "total": 0}
        names = [s.strip().lower() for s in indicators.split(",") if s.strip()]
        if not names:
            names = ["ma"]
        # 为每个指标计算序列，并合并到每行
        result_rows = []
        for i, row in enumerate(klines):
            out = dict(row)
            result_rows.append(out)
        for ind_name in names:
            if ind_name not in ("ma", "rsi", "macd", "boll"):
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
            ind_result = indicator_service.get_indicator(klines, ind_name, params)
            for key, values in ind_result.items():
                for i, v in enumerate(values):
                    if i < len(result_rows):
                        result_rows[i][key] = round(v, 4) if v is not None and isinstance(v, (int, float)) else v
        return {
            "success": True,
            "symbol": symbol,
            "data": result_rows,
            "total": len(result_rows),
        }
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
            return {
                "success": False,
                "error": "数据不足，需要至少50条K线数据"
            }
            
        # 运行回测
        strategy_params = {}
        if config.period is not None:
            strategy_params["period"] = config.period
        if config.oversold is not None:
            strategy_params["oversold"] = config.oversold
        if config.overbought is not None:
            strategy_params["overbought"] = config.overbought
        result = run_backtest(
            symbol=config.symbol,
            data=data,
            strategy=config.strategy,
            short_window=config.short_window,
            long_window=config.long_window,
            initial_capital=config.initial_capital,
            **strategy_params,
        )
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        # 保存结果
        if config.save_result:
            task_id = backtest_storage.save_result(result)
            result['task_id'] = task_id
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest/strategies")
async def get_strategies():
    """获取可用策略列表（从策略注册表动态返回）"""
    return {
        "success": True,
        "data": get_strategies_list(),
    }


@router.get("/backtest/{task_id}")
async def get_backtest_result(task_id: str):
    """获取回测结果"""
    result = backtest_storage.get_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="回测结果不存在")
    return {
        "success": True,
        "data": result
    }


@router.get("/backtest")
async def list_backtest_results(
    limit: int = Query(20, description="返回数量"),
    symbol: Optional[str] = Query(None, description="股票代码过滤")
):
    """列出回测历史"""
    results = backtest_storage.list_results(limit=limit, symbol=symbol)
    return {
        "success": True,
        "data": results,
        "total": len(results)
    }


@router.delete("/backtest/{task_id}")
async def delete_backtest_result(task_id: str):
    """删除回测结果"""
    success = backtest_storage.delete_result(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="回测结果不存在")
    return {
        "success": True,
        "message": "删除成功"
    }


# 导入并包含模拟交易路由
from app.api.simulation_routes import router as simulation_router
router.include_router(simulation_router)

# 导入并包含风控路由
from app.api.risk_routes import router as risk_router
router.include_router(risk_router)

# 导入并包含自选路由
from app.api.watchlist_routes import router as watchlist_router
router.include_router(watchlist_router)


# ==================== 版本号 ====================

@router.get("/version")
async def get_version():
    """获取后端版本号"""
    return {
        "success": True,
        "data": get_build_info()
    }

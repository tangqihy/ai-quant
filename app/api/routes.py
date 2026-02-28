"""
API routes
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict
from pydantic import BaseModel
from app.services.stock_service import stock_service
from app.services.backtest_service import run_backtest
from app.services.storage_service import backtest_storage

router = APIRouter()


# 回测请求模型
class BacktestRequest(BaseModel):
    symbol: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    strategy: str = "ma_cross"
    short_window: int = 5
    long_window: int = 20
    initial_capital: float = 1000000
    save_result: bool = True  # 是否保存结果


@router.get("/stocks")
async def get_stocks(
    market: str = Query("沪深A股", description="市场类型"),
    limit: int = Query(100, description="返回数量限制")
):
    """获取股票列表"""
    try:
        stocks = stock_service.get_stock_list(market=market)
        return {
            "success": True,
            "data": stocks[:limit],
            "total": len(stocks)
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
        result = run_backtest(
            symbol=config.symbol,
            data=data,
            strategy=config.strategy,
            short_window=config.short_window,
            long_window=config.long_window,
            initial_capital=config.initial_capital
        )
        
        # 保存结果
        if config.save_result:
            task_id = backtest_storage.save_result(result)
            result['task_id'] = task_id
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest/strategies")
async def get_strategies():
    """获取可用策略列表"""
    return {
        "success": True,
        "data": [
            {
                "id": "ma_cross",
                "name": "MA交叉策略",
                "params": ["short_window", "long_window"],
                "description": "短期均线上穿长期均线买入，下穿卖出"
            },
            {
                "id": "dual_ma",
                "name": "双MA策略",
                "params": ["short_window", "long_window"],
                "description": "经典双均线策略"
            }
        ]
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

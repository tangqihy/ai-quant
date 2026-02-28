"""
API routes
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from app.services.stock_service import stock_service

router = APIRouter()


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
async def run_backtest(config: dict):
    """运行回测"""
    return {"result": "backtest started"}


@router.get("/backtest/{task_id}")
async def get_backtest_result(task_id: str):
    """获取回测结果"""
    return {"task_id": task_id, "status": "completed"}

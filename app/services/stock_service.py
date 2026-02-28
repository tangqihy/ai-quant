"""
股票数据服务
使用 AkShare 获取A股市场数据

注意: 首次使用需要安装依赖
    pip install akshare pandas
    
运行环境设置:
    # 如果遇到 /app 权限问题，使用:
    PYTHONPATH=/workspace/quant-backend:/workspace:/usr/lib/python311.zip:/usr/lib/python3.11:/usr/lib/python3.11/lib-dynload:/usr/local/lib/python3.11/dist-packages:/usr/lib/python3/dist-packages
"""
import warnings
warnings.filterwarnings('ignore')

try:
    import akshare as ak
except ImportError:
    ak = None

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import json


class StockService:
    """股票数据服务类"""
    
    @staticmethod
    def get_stock_list(market: str = "沪深A股") -> List[Dict]:
        """
        获取股票列表
        
        Args:
            market: 市场类型 (沪深A股/沪深京A股)
            
        Returns:
            股票列表
        """
        if ak is None:
            raise Exception("AkShare 未安装，请运行: pip install akshare")
        
        try:
            # 获取A股股票列表
            df = ak.stock_info_a_code_name()
            
            # 转换为字典列表
            stocks = []
            for _, row in df.iterrows():
                stocks.append({
                    "symbol": row.get("code", ""),
                    "name": row.get("name", ""),
                    "market": market
                })
            
            return stocks
        except Exception as e:
            raise Exception(f"获取股票列表失败: {str(e)}")
    
    @staticmethod
    def get_stock_history(
        symbol: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        adjust: str = "qfq"
    ) -> List[Dict]:
        """
        获取股票历史K线数据（日线）
        
        Args:
            symbol: 股票代码 (如: 000001)
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            adjust: 复权类型 (qfq-前复权, hfq-后复权, 空字符串-不复权)
            
        Returns:
            K线数据列表
        """
        if ak is None:
            raise Exception("AkShare 未安装，请运行: pip install akshare")
        
        try:
            # 规范化股票代码
            if not symbol.startswith(('000', '001', '002', '003', '300', '600', '601', '603', '605', '688', '689', '8', '4')):
                raise ValueError(f"无效的股票代码: {symbol}")
            
            # 设置默认日期范围（最近1年）
            if not end_date:
                end_date = datetime.now().strftime("%Y%m%d")
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
            
            # 获取历史数据
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )
            
            # 转换为字典列表
            klines = []
            for _, row in df.iterrows():
                klines.append({
                    "date": str(row.get("日期", "")),
                    "open": float(row.get("开盘", 0)),
                    "close": float(row.get("收盘", 0)),
                    "high": float(row.get("最高", 0)),
                    "low": float(row.get("最低", 0)),
                    "volume": float(row.get("成交量", 0)),
                    "amount": float(row.get("成交额", 0)),
                    "amplitude": float(row.get("振幅", 0)),
                    "change_pct": float(row.get("涨跌幅", 0)),
                    "change_amount": float(row.get("涨跌额", 0)),
                    "turnover": float(row.get("换手率", 0))
                })
            
            return klines
        except Exception as e:
            raise Exception(f"获取历史K线失败: {str(e)}")
    
    @staticmethod
    def get_realtime_quote(symbol: str) -> Dict:
        """
        获取股票实时行情
        
        Args:
            symbol: 股票代码
            
        Returns:
            实时行情数据
        """
        if ak is None:
            raise Exception("AkShare 未安装，请运行: pip install akshare")
        
        try:
            # 获取实时行情
            df = ak.stock_zh_a_spot_em()
            
            # 筛选指定股票
            stock = df[df["代码"] == symbol]
            
            if stock.empty:
                raise ValueError(f"未找到股票: {symbol}")
            
            row = stock.iloc[0]
            
            return {
                "symbol": symbol,
                "name": row.get("名称", ""),
                "price": float(row.get("最新价", 0)),
                "change_pct": float(row.get("涨跌幅", 0)),
                "change_amount": float(row.get("涨跌额", 0)),
                "open": float(row.get("今开", 0)),
                "high": float(row.get("最高", 0)),
                "low": float(row.get("最低", 0)),
                "volume": float(row.get("成交量", 0)),
                "amount": float(row.get("成交额", 0)),
                "amplitude": float(row.get("振幅", 0)),
                "high_limit": float(row.get("最高", 0)),
                "low_limit": float(row.get("最低", 0)),
                "turnover": float(row.get("换手率", 0)),
                "pe": float(row.get("市盈率-动态", 0)) if pd.notna(row.get("市盈率-动态")) else None,
                "pb": float(row.get("市净率", 0)) if pd.notna(row.get("市净率")) else None,
                "market_cap": float(row.get("总市值", 0)) if pd.notna(row.get("总市值")) else None,
                "circulating_cap": float(row.get("流通市值", 0)) if pd.notna(row.get("流通市值")) else None,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            raise Exception(f"获取实时行情失败: {str(e)}")
    
    @staticmethod
    def get_realtime_quotes(symbols: List[str]) -> List[Dict]:
        """
        批量获取股票实时行情
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            实时行情列表
        """
        if ak is None:
            raise Exception("AkShare 未安装，请运行: pip install akshare")
        
        try:
            # 获取实时行情
            df = ak.stock_zh_a_spot_em()
            
            # 筛选指定股票
            stocks = df[df["代码"].isin(symbols)]
            
            results = []
            for _, row in stocks.iterrows():
                results.append({
                    "symbol": row.get("代码", ""),
                    "name": row.get("名称", ""),
                    "price": float(row.get("最新价", 0)),
                    "change_pct": float(row.get("涨跌幅", 0)),
                    "change_amount": float(row.get("涨跌额", 0)),
                    "open": float(row.get("今开", 0)),
                    "high": float(row.get("最高", 0)),
                    "low": float(row.get("最低", 0)),
                    "volume": float(row.get("成交量", 0)),
                    "amount": float(row.get("成交额", 0)),
                    "turnover": float(row.get("换手率", 0)),
                })
            
            return results
        except Exception as e:
            raise Exception(f"批量获取实时行情失败: {str(e)}")
    
    @staticmethod
    def get_stock_info(symbol: str) -> Dict:
        """
        获取股票基本信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            股票基本信息
        """
        if ak is None:
            raise Exception("AkShare 未安装，请运行: pip install akshare")
        
        try:
            df = ak.stock_individual_info_em(symbol=symbol)
            
            info = {"symbol": symbol}
            for _, row in df.iterrows():
                info[row.get("item", "")] = row.get("value", "")
            
            return info
        except Exception as e:
            raise Exception(f"获取股票信息失败: {str(e)}")


# 创建服务实例
stock_service = StockService()

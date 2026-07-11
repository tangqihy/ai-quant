"""
Tushare Pro 数据服务

直接使用 tushare Python SDK，token 从环境变量 / .env 的 TUSHARE_TOKEN 读取。
"""
import logging
import time
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

import tushare as ts

from app.core.config import settings

logger = logging.getLogger(__name__)


class TushareService:
    """Tushare Pro 数据服务"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if TushareService._initialized:
            return
        token = settings.tushare_token
        if not token:
            logger.warning("TUSHARE_TOKEN 未配置，Tushare 数据接口将不可用")
        else:
            ts.set_token(token)
        self._pro = ts.pro_api() if token else None
        TushareService._initialized = True

    @property
    def pro(self):
        """懒加载 pro_api，支持运行时补配置 token。"""
        if self._pro is None and settings.tushare_token:
            ts.set_token(settings.tushare_token)
            self._pro = ts.pro_api()
        return self._pro

    def normalize_symbol(self, symbol: str) -> str:
        """将股票代码转换为 Tushare 格式 (600519 -> 600519.SH)"""
        if '.SH' in symbol or '.SZ' in symbol or '.BJ' in symbol:
            return symbol
        if symbol.startswith('6'):
            return f"{symbol}.SH"
        elif symbol.startswith('0') or symbol.startswith('3'):
            return f"{symbol}.SZ"
        elif symbol.startswith('8') or symbol.startswith('4'):
            return f"{symbol}.BJ"
        return f"{symbol}.SZ"

    def to_standard_symbol(self, ts_code: str) -> str:
        """将 Tushare 格式转换为标准代码 (600519.SH -> 600519)"""
        return ts_code.split('.')[0]

    def get_stock_list(self, market: str = None) -> List[Dict]:
        """
        获取股票列表
        market: 主板/创业板/科创板/北交所 等
        """
        if not self.pro:
            return []
        try:
            kwargs = {'list_status': 'L'}
            if market:
                kwargs['market'] = market
            df = self.pro.stock_basic(**kwargs)
        except Exception as e:
            logger.error(f"Tushare stock_basic failed: {e}")
            return []

        if df is None or df.empty:
            return []

        results = []
        for _, item in df.iterrows():
            results.append({
                'symbol': item.get('symbol', ''),
                'name': item.get('name', ''),
                'ts_code': item.get('ts_code', ''),
                'area': item.get('area', ''),
                'industry': item.get('industry', ''),
                'market': item.get('market', ''),
                'list_date': str(item.get('list_date', '')),
            })
        return results

    def get_stock_history(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
        adjust: str = "qfq"
    ) -> List[Dict]:
        """
        获取历史K线数据（日线）
        symbol: 股票代码 (如 600519)
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
        adjust: 复权类型 qfq(前复权)/hfq(后复权)/空(不复权)
        """
        if not self.pro:
            return []

        ts_code = self.normalize_symbol(symbol)

        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')

        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')

        try:
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        except Exception as e:
            logger.error(f"Tushare daily failed: {e}")
            return []

        if df is None or df.empty:
            return []

        data = df.to_dict('records')

        # 获取复权因子（如果需要复权）
        if adjust in ('qfq', 'hfq'):
            try:
                adj_df = self.pro.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)
            except Exception as e:
                logger.warning(f"Tushare adj_factor failed: {e}")
                adj_df = None

            if adj_df is not None and not adj_df.empty:
                adj_map = {str(item['trade_date']): item['adj_factor'] for item in adj_df.to_dict('records')}
                latest_adj = adj_map.get(end_date, 1.0)
                if latest_adj == 1.0 and adj_map:
                    latest_adj = max(adj_map.values())

                for item in data:
                    trade_date = str(item['trade_date'])
                    current_adj = adj_map.get(trade_date, 1.0)

                    if adjust == 'qfq':
                        factor = current_adj / latest_adj if latest_adj else 1.0
                    else:
                        factor = latest_adj / current_adj if current_adj else 1.0

                    item['open'] = round(item['open'] * factor, 2)
                    item['high'] = round(item['high'] * factor, 2)
                    item['low'] = round(item['low'] * factor, 2)
                    item['close'] = round(item['close'] * factor, 2)

        results = []
        for item in data:
            results.append({
                'date': self._format_date(str(item.get('trade_date', ''))),
                'open': float(item.get('open', 0)),
                'high': float(item.get('high', 0)),
                'low': float(item.get('low', 0)),
                'close': float(item.get('close', 0)),
                'volume': float(item.get('vol', 0)),
                'amount': float(item.get('amount', 0)),
                'change_pct': float(item.get('pct_chg', 0) or 0),
                'change_amount': float(item.get('change', 0) or 0),
                'turnover': 0,
            })

        results.sort(key=lambda x: x['date'])
        return results

    # ==================== 分钟K线 ====================
    # 新浪财经公开接口，无限流
    _MINS_CACHE: Dict[str, Any] = {}

    def get_stock_minutes(
        self,
        symbol: str,
        freq: str = "5min",
        start_date: str = None,
        end_date: str = None,
    ) -> List[Dict]:
        """
        获取分钟级K线数据（新浪财经公开接口）。
        freq: 1min/5min/15min/30min/60min
        start_date/end_date: YYYYMMDD（用于过滤，新浪按 datalen 拉取后裁剪）
        """
        freq = (freq or "5min").lower()
        scale_map = {"1min": 1, "5min": 5, "15min": 15, "30min": 30, "60min": 60}
        scale = scale_map.get(freq, 5)

        today = datetime.now()
        if not end_date:
            end_date = today.strftime("%Y%m%d")
        if not start_date:
            start_date = (today - timedelta(days=10)).strftime("%Y%m%d")
        start_date = start_date.replace("-", "")
        end_date = end_date.replace("-", "")

        cache_key = f"sina:{symbol}:{freq}:{start_date}:{end_date}"
        cached = TushareService._MINS_CACHE.get(cache_key)
        if cached and (time.time() - cached["ts"] < 60):
            return cached["items"]

        # 新浪 symbol: sh600519 / sz000001 / bj830xxx
        s = symbol.split(".")[0]
        if s.startswith("6"):
            sina_sym = f"sh{s}"
        elif s.startswith("8") or s.startswith("4"):
            sina_sym = f"bj{s}"
        else:
            sina_sym = f"sz{s}"

        # datalen: 取足够多的条数覆盖日期范围；分钟线每天 240 根
        days_span = max((datetime.strptime(end_date, "%Y%m%d") - datetime.strptime(start_date, "%Y%m%d")).days, 1)
        datalen = min(max(days_span, 1) * 240, 5000)

        url = (
            "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"CN_MarketData.getKLineData?symbol={sina_sym}&scale={scale}&ma=no&datalen={datalen}"
        )
        try:
            import subprocess
            import json as _json

            r = subprocess.run(
                ["curl", "-s", "--max-time", "10", "-H", "User-Agent: Mozilla/5.0", url],
                capture_output=True, text=True, timeout=12,
            )
            rows = _json.loads(r.stdout or "[]") or []
        except Exception as e:
            logger.warning(f"sina minutes failed: {e}")
            return []

        start_norm = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
        end_norm = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
        results: List[Dict] = []
        for row in rows:
            day = str(row.get("day", ""))
            if not day:
                continue
            # 过滤日期范围
            day_date = day[:10]
            if day_date < start_norm or day_date > end_norm:
                continue
            results.append({
                "date": day,
                "open": float(row.get("open", 0) or 0),
                "high": float(row.get("high", 0) or 0),
                "low": float(row.get("low", 0) or 0),
                "close": float(row.get("close", 0) or 0),
                "volume": float(row.get("volume", 0) or 0),
                "amount": 0,
            })
        results.sort(key=lambda x: x["date"])

        TushareService._MINS_CACHE[cache_key] = {"ts": time.time(), "items": results}
        return results

    def get_realtime_quotes(self, symbols: List[str]) -> List[Dict]:
        """
        获取实时行情（使用最新日线数据作为近似）
        注意: Tushare 免费接口不支持实时行情，使用最新日线数据
        """
        if not self.pro or not symbols:
            return []

        results = []
        today = datetime.now().strftime('%Y%m%d')
        for symbol in symbols:
            ts_code = self.normalize_symbol(symbol)
            item = None
            try:
                df = self.pro.daily(ts_code=ts_code, trade_date=today)
                if df is not None and not df.empty:
                    item = df.iloc[0].to_dict()
            except Exception as e:
                logger.debug(f"Tushare daily(trade_date) for {symbol} failed: {e}")

            if item is None:
                try:
                    start = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
                    df = self.pro.daily(ts_code=ts_code, start_date=start, end_date=today)
                    if df is not None and not df.empty:
                        item = df.iloc[-1].to_dict()
                except Exception as e:
                    logger.debug(f"Tushare daily(range) for {symbol} failed: {e}")

            if item:
                results.append({
                    'symbol': symbol,
                    'name': '',
                    'price': float(item.get('close', 0) or 0),
                    'open': float(item.get('open', 0) or 0),
                    'high': float(item.get('high', 0) or 0),
                    'low': float(item.get('low', 0) or 0),
                    'volume': float(item.get('vol', 0) or 0),
                    'amount': float(item.get('amount', 0) or 0),
                    'change_pct': float(item.get('pct_chg', 0) or 0),
                    'change_amount': float(item.get('change', 0) or 0),
                    'turnover': 0,
                    'source': 'tushare',
                })
        return results

    def get_realtime_quote(self, symbol: str) -> Dict:
        """获取单只股票实时行情"""
        quotes = self.get_realtime_quotes([symbol])
        if quotes:
            q = quotes[0]
            q['timestamp'] = datetime.now().isoformat()
            return q
        return {
            'symbol': symbol,
            'name': '',
            'price': 0,
            'timestamp': datetime.now().isoformat()
        }

    def get_stock_info(self, symbol: str) -> Dict:
        """获取股票基本信息"""
        if not self.pro:
            return {'symbol': symbol}
        ts_code = self.normalize_symbol(symbol)
        try:
            df = self.pro.stock_basic(ts_code=ts_code)
        except Exception as e:
            logger.error(f"Tushare stock_basic(ts_code) failed: {e}")
            return {'symbol': symbol}

        if df is not None and not df.empty:
            item = df.iloc[0].to_dict()
            return {
                'symbol': symbol,
                'name': item.get('name', ''),
                'industry': item.get('industry', ''),
                'area': item.get('area', ''),
                'market': item.get('market', ''),
                'list_date': str(item.get('list_date', '')),
            }
        return {'symbol': symbol}

    def get_daily_basic(self, symbol: str, trade_date: str = None) -> Dict:
        """获取每日指标（PE/PB/换手率等）"""
        if not self.pro:
            return {}
        ts_code = self.normalize_symbol(symbol)
        if not trade_date:
            trade_date = datetime.now().strftime('%Y%m%d')
        try:
            df = self.pro.daily_basic(ts_code=ts_code, trade_date=trade_date)
        except Exception as e:
            logger.error(f"Tushare daily_basic failed: {e}")
            return {}
        if df is not None and not df.empty:
            return df.iloc[0].to_dict()
        return {}

    def _format_date(self, date_str: str) -> str:
        """将 YYYYMMDD 格式转换为 YYYY-MM-DD"""
        if not date_str or len(date_str) != 8:
            return date_str
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"


# 全局实例
tushare_service = TushareService()

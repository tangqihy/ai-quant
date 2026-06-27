"""
Tushare Pro 数据服务 - 替代 JoinQuant
通过 tushare_api.py 脚本调用 Tushare Pro 接口
"""
import os
import json
import subprocess
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Tushare API 脚本路径
TUSHARE_SCRIPT = os.path.expanduser("~/.hermes/skills/tushare-mcp/scripts/tushare_api.py")


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
        TushareService._initialized = True

    def _call_api(self, interface: str, params: Dict = None, fields: str = None) -> List[Dict]:
        """调用 tushare_api.py 脚本"""
        cmd = ["python3", TUSHARE_SCRIPT, interface]
        
        if params:
            for key, value in params.items():
                if value is not None:
                    cmd.append(f"{key}={value}")
        
        if fields:
            cmd.extend(["--fields", fields])
        
        cmd.extend(["--output", "json"])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Tushare API error: {result.stderr}")
                return []
            
            # 解析JSON输出（跳过第一行说明文字）
            lines = result.stdout.strip().split('\n')
            json_start = -1
            for i, line in enumerate(lines):
                if line.strip().startswith('[') or line.strip().startswith('{'):
                    json_start = i
                    break
            
            if json_start == -1:
                return []
            
            json_str = '\n'.join(lines[json_start:])
            return json.loads(json_str)
            
        except subprocess.TimeoutExpired:
            logger.error("Tushare API timeout")
            return []
        except Exception as e:
            logger.error(f"Tushare API call failed: {e}")
            return []

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
        params = {}
        if market:
            params['market'] = market
        
        data = self._call_api('stock_basic', params)
        
        results = []
        for item in data:
            results.append({
                'symbol': item.get('symbol', ''),
                'name': item.get('name', ''),
                'ts_code': item.get('ts_code', ''),
                'area': item.get('area', ''),
                'industry': item.get('industry', ''),
                'market': item.get('market', ''),
                'list_date': item.get('list_date', '')
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
        获取历史K线数据
        symbol: 股票代码 (如 600519)
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
        adjust: 复权类型 qfq(前复权)/hfq(后复权)/空(不复权)
        """
        ts_code = self.normalize_symbol(symbol)
        
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        
        # 标准化日期格式
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')
        
        params = {
            'ts_code': ts_code,
            'start_date': start_date,
            'end_date': end_date
        }
        
        data = self._call_api('daily', params)
        
        if not data:
            return []
        
        # 获取复权因子（如果需要复权）
        if adjust in ('qfq', 'hfq'):
            adj_data = self._call_api('adj_factor', {'ts_code': ts_code})
            if adj_data:
                # 构建复权因子映射
                adj_map = {item['trade_date']: item['adj_factor'] for item in adj_data}
                
                # 获取最新日期的复权因子
                latest_adj = adj_map.get(end_date, 1.0)
                if latest_adj == 1.0 and adj_map:
                    # 如果end_date没有数据，取最大的复权因子
                    latest_adj = max(adj_map.values())
                
                for item in data:
                    trade_date = item['trade_date']
                    current_adj = adj_map.get(trade_date, 1.0)
                    
                    if adjust == 'qfq':
                        # 前复权 = 原始价格 * (当日复权因子 / 最新复权因子)
                        factor = current_adj / latest_adj if latest_adj else 1.0
                    else:
                        # 后复权 = 原始价格 * (最新复权因子 / 当日复权因子)
                        factor = latest_adj / current_adj if current_adj else 1.0
                    
                    item['open'] = round(item['open'] * factor, 2)
                    item['high'] = round(item['high'] * factor, 2)
                    item['low'] = round(item['low'] * factor, 2)
                    item['close'] = round(item['close'] * factor, 2)
        
        # 转换为标准格式
        results = []
        for item in data:
            results.append({
                'date': self._format_date(item.get('trade_date', '')),
                'open': float(item.get('open', 0)),
                'high': float(item.get('high', 0)),
                'low': float(item.get('low', 0)),
                'close': float(item.get('close', 0)),
                'volume': float(item.get('vol', 0)),  # tushare 用 vol 字段
                'amount': float(item.get('amount', 0)),
                'change_pct': float(item.get('pct_chg', 0)),
                'change_amount': float(item.get('change', 0)),
                'turnover': 0  # tushare daily 不含换手率，需要 daily_basic
            })
        
        # 按日期升序排序
        results.sort(key=lambda x: x['date'])
        
        return results

    def get_realtime_quotes(self, symbols: List[str]) -> List[Dict]:
        """
        获取实时行情（使用最新日线数据作为近似）
        注意: Tushare 免费接口不支持实时行情，使用最新日线数据
        """
        if not symbols:
            return []
        
        results = []
        for symbol in symbols:
            ts_code = self.normalize_symbol(symbol)
            
            # 获取最新一天的日线数据
            data = self._call_api('daily', {
                'ts_code': ts_code,
                'trade_date': datetime.now().strftime('%Y%m%d')
            })
            
            if data:
                item = data[0]
                results.append({
                    'symbol': symbol,
                    'name': '',
                    'price': float(item.get('close', 0)),
                    'open': float(item.get('open', 0)),
                    'high': float(item.get('high', 0)),
                    'low': float(item.get('low', 0)),
                    'volume': float(item.get('vol', 0)),
                    'amount': float(item.get('amount', 0)),
                    'change_pct': float(item.get('pct_chg', 0)),
                    'change_amount': float(item.get('change', 0)),
                    'turnover': 0,
                    'source': 'tushare'
                })
            else:
                # 如果今天没有数据，获取最近一天的
                data = self._call_api('daily', {
                    'ts_code': ts_code,
                    'start_date': (datetime.now() - timedelta(days=7)).strftime('%Y%m%d'),
                    'end_date': datetime.now().strftime('%Y%m%d')
                })
                
                if data:
                    # 取最后一条
                    item = data[-1]
                    results.append({
                        'symbol': symbol,
                        'name': '',
                        'price': float(item.get('close', 0)),
                        'open': float(item.get('open', 0)),
                        'high': float(item.get('high', 0)),
                        'low': float(item.get('low', 0)),
                        'volume': float(item.get('vol', 0)),
                        'amount': float(item.get('amount', 0)),
                        'change_pct': float(item.get('pct_chg', 0)),
                        'change_amount': float(item.get('change', 0)),
                        'turnover': 0,
                        'source': 'tushare'
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
        ts_code = self.normalize_symbol(symbol)
        
        data = self._call_api('stock_basic', {'ts_code': ts_code})
        
        if data:
            item = data[0]
            return {
                'symbol': symbol,
                'name': item.get('name', ''),
                'industry': item.get('industry', ''),
                'area': item.get('area', ''),
                'market': item.get('market', ''),
                'list_date': item.get('list_date', '')
            }
        
        return {'symbol': symbol}

    def get_daily_basic(self, symbol: str, trade_date: str = None) -> Dict:
        """获取每日指标（PE/PB/换手率等）"""
        ts_code = self.normalize_symbol(symbol)
        
        if not trade_date:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        data = self._call_api('daily_basic', {
            'ts_code': ts_code,
            'trade_date': trade_date
        })
        
        if data:
            return data[0]
        
        return {}

    def _format_date(self, date_str: str) -> str:
        """将 YYYYMMDD 格式转换为 YYYY-MM-DD"""
        if not date_str or len(date_str) != 8:
            return date_str
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"


# 全局实例
tushare_service = TushareService()

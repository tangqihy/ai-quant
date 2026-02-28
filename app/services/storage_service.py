"""
回测结果存储服务
"""
import json
import os
from datetime import datetime
from typing import List, Optional, Dict
from pathlib import Path

# 存储目录
STORAGE_DIR = Path(__file__).parent.parent / "data" / "backtest_results"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class BacktestStorage:
    """回测结果存储"""
    
    @staticmethod
    def save_result(result: Dict) -> str:
        """保存回测结果，返回任务ID"""
        # 生成任务ID
        task_id = f"bt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{result.get('symbol', 'unk')}"
        result['task_id'] = task_id
        result['created_at'] = datetime.now().isoformat()
        
        # 保存到文件
        file_path = STORAGE_DIR / f"{task_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        return task_id
    
    @staticmethod
    def get_result(task_id: str) -> Optional[Dict]:
        """获取单个回测结果"""
        file_path = STORAGE_DIR / f"{task_id}.json"
        if not file_path.exists():
            return None
        
        with open(file_path, encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def list_results(limit: int = 20, symbol: Optional[str] = None) -> List[Dict]:
        """列出回测结果"""
        results = []
        
        for file_path in sorted(STORAGE_DIR.glob("*.json"), reverse=True):
            try:
                with open(file_path, encoding='utf-8') as f:
                    result = json.load(f)
                    
                    # 过滤指定股票
                    if symbol and result.get('symbol') != symbol:
                        continue
                    
                    # 只返回关键字段
                    results.append({
                        'task_id': result.get('task_id'),
                        'symbol': result.get('symbol'),
                        'strategy': result.get('strategy'),
                        'total_return': result.get('total_return'),
                        'annual_return': result.get('annual_return'),
                        'max_drawdown': result.get('max_drawdown'),
                        'win_rate': result.get('win_rate'),
                        'total_trades': result.get('total_trades'),
                        'created_at': result.get('created_at'),
                    })
                    
                    if len(results) >= limit:
                        break
            except Exception:
                continue
        
        return results
    
    @staticmethod
    def delete_result(task_id: str) -> bool:
        """删除回测结果"""
        file_path = STORAGE_DIR / f"{task_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False


# 全局实例
backtest_storage = BacktestStorage()

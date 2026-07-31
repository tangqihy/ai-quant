"""
轻量策略会话持久化：本周选用的策略/标的/参数/启停。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PATH = Path("data/strategy_sessions.json")


class StrategySessionStore:
    def __init__(self, path: str | Path = DEFAULT_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"sessions": []})

    def _read(self) -> Dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"sessions": []}

    def _write(self, payload: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_sessions(self) -> List[Dict[str, Any]]:
        return list(self._read().get("sessions") or [])

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        for s in self.list_sessions():
            if s.get("id") == session_id:
                return s
        return None

    def get_active(self) -> Optional[Dict[str, Any]]:
        enabled = [s for s in self.list_sessions() if s.get("enabled")]
        if not enabled:
            return None
        enabled.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return enabled[0]

    def upsert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._read()
        sessions: List[Dict[str, Any]] = list(payload.get("sessions") or [])
        now = datetime.now().isoformat(timespec="seconds")
        session_id = data.get("id") or str(uuid.uuid4())[:8]

        existing_idx = next((i for i, s in enumerate(sessions) if s.get("id") == session_id), None)
        session = {
            "id": session_id,
            "name": data.get("name") or f"{data.get('strategy', 'strategy')}@{data.get('symbol', '')}",
            "symbol": data["symbol"],
            "strategy": data["strategy"],
            "params": data.get("params") or {},
            "period": data.get("period") or "daily",
            "position_pct": float(data.get("position_pct") or 5.0),
            "stop_loss_pct": float(data.get("stop_loss_pct") or 2.0),
            "stop_profit_pct": float(data.get("stop_profit_pct") or 4.0),
            "enabled": bool(data.get("enabled", True)),
            "observe_factors": data.get("observe_factors") or [],
            "updated_at": now,
            "created_at": now,
        }
        if existing_idx is not None:
            session["created_at"] = sessions[existing_idx].get("created_at") or now
            sessions[existing_idx] = session
        else:
            sessions.append(session)

        # 启用时可选：仅保留一个启用会话（轻量模式）
        if session["enabled"] and data.get("exclusive_enable", True):
            for s in sessions:
                if s["id"] != session_id:
                    s["enabled"] = False

        payload["sessions"] = sessions
        self._write(payload)
        return session

    def set_enabled(self, session_id: str, enabled: bool) -> Optional[Dict[str, Any]]:
        payload = self._read()
        sessions = list(payload.get("sessions") or [])
        target = None
        for s in sessions:
            if s.get("id") == session_id:
                s["enabled"] = enabled
                s["updated_at"] = datetime.now().isoformat(timespec="seconds")
                target = s
            elif enabled:
                s["enabled"] = False
        if target is None:
            return None
        payload["sessions"] = sessions
        self._write(payload)
        return target

    def delete(self, session_id: str) -> bool:
        payload = self._read()
        sessions = list(payload.get("sessions") or [])
        new_sessions = [s for s in sessions if s.get("id") != session_id]
        if len(new_sessions) == len(sessions):
            return False
        payload["sessions"] = new_sessions
        self._write(payload)
        return True


strategy_session_store = StrategySessionStore()

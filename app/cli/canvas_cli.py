"""
Stock Canvas CLI 入口

用法：
    python -m app.cli.canvas_cli create --code 01810.HK --name 小米集团
    python -m app.cli.canvas_cli add-card --canvas 01810.HK --type thesis \
        --title "看好小米" --data '{"direction":"bullish","target_price":50}'
    python -m app.cli.canvas_cli show --canvas 01810.HK

所有命令支持 --json 输出，便于 Hermes / 脚本解析。
数据库路径可用环境变量 CANVAS_DB_PATH 覆盖（默认 app/data/canvas.db）。
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app.models.canvas import (
    AddCardRequest,
    CanvasStatus,
    CardType,
    CreateCanvasRequest,
    EdgeType,
    UpdateCanvasRequest,
    UpdateCardRequest,
)
from app.services.canvas_service import CanvasService
from app.services.canvas_store import CanvasStore


def _build_service() -> CanvasService:
    # CanvasStore 自动读取 CANVAS_DB_PATH 环境变量
    return CanvasService(CanvasStore())


def _print(payload: Any, as_json: bool, human_fn=None) -> None:
    if as_json:
        def default(o: Any):
            if hasattr(o, "isoformat"):
                return o.isoformat()
            return str(o)
        print(json.dumps(payload, ensure_ascii=False, indent=None, default=default))
    elif human_fn:
        human_fn(payload)
    else:
        print(payload)


def _model_to_dict(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_model_to_dict(o) for o in obj]
    if isinstance(obj, dict):
        return {k: _model_to_dict(v) for k, v in obj.items()}
    return obj


def _show_canvas_human(detail: dict) -> None:
    canvas = detail["canvas"]
    print(f"画布: {canvas['name']} ({canvas['ts_code']})  状态: {canvas['status']}")
    print(f"卡片数: {len(detail['cards'])}  关联数: {len(detail['edges'])}")
    for card in detail["cards"]:
        print(f"  [{card['card_type']:<12}] {card['title']}  (id={card['id'][:8]}...)")


def _list_canvases_human(canvases: list) -> None:
    if not canvases:
        print("（无画布）")
        return
    for c in canvases:
        print(f"{c['ts_code']:<12} {c['name']:<10} {c['status']:<10} 更新于 {c.get('updated_at') or c['created_at']}")


def _list_cards_human(cards: list) -> None:
    for c in cards:
        tags = ",".join(c["tags"]) if c["tags"] else "-"
        print(f"[{c['card_type']:<12}] {c['title']:<30} 重要性{c['importance']} 标签:{tags}  id={c['id']}")


def _timeline_human(events: list) -> None:
    for e in events:
        date = (e["date"] or "")[:10]
        print(f"{date}  [{e['card_type']:<12}] {e['title']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="canvas", description="Stock Canvas 研究画布 CLI")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    # 让 --json 在子命令后也可用（argparse 全局选项不能放在子命令之后）
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON 输出")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create", parents=[common], help="创建画布")
    p.add_argument("--code", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--status", default="watching", choices=[s.value for s in CanvasStatus])

    p = sub.add_parser("list", parents=[common], help="列出画布")
    p.add_argument("--status", default=None)

    p = sub.add_parser("status", parents=[common], help="更新画布状态")
    p.add_argument("--code", required=True)
    p.add_argument("--status", required=True, choices=[s.value for s in CanvasStatus])

    p = sub.add_parser("archive", parents=[common], help="归档画布")
    p.add_argument("--code", required=True)

    p = sub.add_parser("show", parents=[common], help="显示画布详情")
    p.add_argument("--canvas", required=True)

    p = sub.add_parser("add-card", parents=[common], help="添加卡片")
    p.add_argument("--canvas", required=True)
    p.add_argument("--type", required=True, choices=[t.value for t in CardType])
    p.add_argument("--title", required=True)
    p.add_argument("--content", default="")
    p.add_argument("--data", default=None, help="structured_data JSON 字符串")
    p.add_argument("--tags", default="", help="逗号分隔")
    p.add_argument("--importance", type=int, default=3, choices=range(1, 6))
    p.add_argument("--source", default="user")
    p.add_argument("--source-ref", default="")

    p = sub.add_parser("edit-card", parents=[common], help="更新卡片")
    p.add_argument("--card-id", required=True)
    p.add_argument("--title", default=None)
    p.add_argument("--content", default=None)
    p.add_argument("--data", default=None)
    p.add_argument("--tags", default=None)
    p.add_argument("--importance", type=int, default=None, choices=range(1, 6))

    p = sub.add_parser("delete-card", parents=[common], help="删除卡片")
    p.add_argument("--card-id", required=True)

    p = sub.add_parser("list-cards", parents=[common], help="列出画布卡片")
    p.add_argument("--canvas", required=True)
    p.add_argument("--type", default=None, choices=[t.value for t in CardType])
    p.add_argument("--tag", default=None)

    p = sub.add_parser("link", parents=[common], help="建立卡片关联")
    p.add_argument("--from", dest="from_id", required=True)
    p.add_argument("--to", dest="to_id", required=True)
    p.add_argument("--type", required=True, choices=[t.value for t in EdgeType])
    p.add_argument("--label", default=None)

    p = sub.add_parser("search", parents=[common], help="跨画布搜索卡片")
    p.add_argument("--keyword", required=True)
    p.add_argument("--canvas", default=None)
    p.add_argument("--type", default=None, choices=[t.value for t in CardType])

    p = sub.add_parser("timeline", parents=[common], help="画布时间线")
    p.add_argument("--canvas", required=True)

    p = sub.add_parser("decisions", parents=[common], help="画布决策卡片")
    p.add_argument("--canvas", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = _build_service()

    try:
        if args.command == "create":
            canvas = service.create_canvas(CreateCanvasRequest(
                ts_code=args.code, name=args.name, status=CanvasStatus(args.status),
            ))
            _print(_model_to_dict(canvas), args.json,
                   lambda c: print(f"已创建画布: {c['name']} ({c['ts_code']})"))

        elif args.command == "list":
            canvases = service.list_canvases(status=args.status)
            _print(_model_to_dict(canvases), args.json, _list_canvases_human)

        elif args.command == "status":
            canvas = service.set_status(args.code, CanvasStatus(args.status))
            _print(_model_to_dict(canvas), args.json,
                   lambda c: print(f"{c['ts_code']} 状态 → {c['status']}"))

        elif args.command == "archive":
            canvas = service.archive_canvas(args.code)
            _print(_model_to_dict(canvas), args.json,
                   lambda c: print(f"{c['ts_code']} 已归档"))

        elif args.command == "show":
            detail = service.get_canvas_detail(args.canvas)
            _print(_model_to_dict(detail), args.json, _show_canvas_human)

        elif args.command == "add-card":
            structured = json.loads(args.data) if args.data else {}
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]
            card = service.add_card(args.canvas, AddCardRequest(
                card_type=CardType(args.type), title=args.title, content=args.content,
                structured_data=structured, tags=tags, importance=args.importance,
                source=args.source, source_ref=args.source_ref,
            ))
            _print(_model_to_dict(card), args.json,
                   lambda c: print(f"已添加卡片 [{c['card_type']}] {c['title']}  id={c['id']}"))

        elif args.command == "edit-card":
            fields: dict = {}
            if args.title is not None:
                fields["title"] = args.title
            if args.content is not None:
                fields["content"] = args.content
            if args.data is not None:
                fields["structured_data"] = json.loads(args.data)
            if args.tags is not None:
                fields["tags"] = [t.strip() for t in args.tags.split(",") if t.strip()]
            if args.importance is not None:
                fields["importance"] = args.importance
            card = service.update_card(args.card_id, UpdateCardRequest(**fields))
            _print(_model_to_dict(card), args.json,
                   lambda c: print(f"已更新卡片 id={c['id']}"))

        elif args.command == "delete-card":
            service.delete_card(args.card_id)
            _print({"deleted": args.card_id}, args.json,
                   lambda _: print(f"已删除卡片 {args.card_id}"))

        elif args.command == "list-cards":
            cards = service.list_cards(
                args.canvas,
                card_type=CardType(args.type) if args.type else None,
                tag=args.tag,
            )
            _print(_model_to_dict(cards), args.json, _list_cards_human)

        elif args.command == "link":
            edge = service.link_cards(
                args.from_id, args.to_id, EdgeType(args.type), label=args.label,
            )
            _print(_model_to_dict(edge), args.json,
                   lambda e: print(f"已建立关联 {e['source_card_id'][:8]} → {e['target_card_id'][:8]} ({e['edge_type']})"))

        elif args.command == "search":
            cards = service.search_cards(
                args.keyword,
                ts_code=args.canvas,
                card_type=CardType(args.type) if args.type else None,
            )
            _print(_model_to_dict(cards), args.json, _list_cards_human)

        elif args.command == "timeline":
            events = service.get_timeline(args.canvas)
            _print(events, args.json, _timeline_human)

        elif args.command == "decisions":
            cards = service.get_decisions(args.canvas)
            _print(_model_to_dict(cards), args.json, _list_cards_human)

    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

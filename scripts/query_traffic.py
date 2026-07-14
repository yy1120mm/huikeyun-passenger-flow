#!/usr/bin/env python3
"""
汇客云客流查询 —— 命令行入口 (V5)

用法示例：
  # 进出客流（按 modifyTime 同步，取 2026-07-01 以来更新的数据，天粒度）
  python query_traffic.py --site-key ADE48DC... --start "2026-07-01 00:00:00" --endpoint traffic

  # 用项目名查询
  python query_traffic.py --project "我的项目" --start "2026-07-01 00:00:00"

  # 过店客流历史数据（按日期范围，天粒度，最多 30 天）
  python query_traffic.py --project "我的项目" --start 2026-07-01 --end 2026-07-30 --endpoint through_traffic

  # 小时粒度
  python query_traffic.py --project "我的项目" --start "2026-07-07 00:00:00" \
      --granularity hour --endpoint traffic

  # 查询场所列表（获取 siteKey/siteName）
  python query_traffic.py --endpoint sites --output sites.json
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from huikeyun_client import HuiKeYunClient, load_config, _resolve_env  # noqa: E402

DEFAULT_CONFIG = os.path.join(SCRIPT_DIR, "..", "references", "config.yaml")


def resolve_site_key(cfg: dict, project: str) -> str:
    if not project:
        return project
    for p in cfg.get("projects", []) or []:
        if p.get("name") == project or p.get("id") == project:
            return p["id"]
    return project


def build_params(cfg: dict, ep_name: str, args) -> dict:
    ep = cfg["endpoints"][ep_name]
    param_map = ep.get("params", {})
    date_fmt = ep.get("date_format", "%Y-%m-%d")
    if args.interval and args.interval.upper() == "H" and "%H" not in date_fmt:
        date_fmt = "%Y-%m-%d %H:%M:%S"
    if args.granularity and args.granularity.lower() == "hour" and "%H" not in date_fmt:
        date_fmt = "%Y-%m-%d %H:%M:%S"

    # 1. 端点默认值
    std = {}
    for k, v in (ep.get("defaults") or {}).items():
        std[k] = _resolve_env(v)

    # 2. 用户参数覆盖
    if args.customer_id:
        std["customer_id"] = args.customer_id
    if args.project or args.site_key:
        std["site_key"] = resolve_site_key(cfg, args.project) if args.project else args.site_key
    if args.site_type is not None:
        std["site_type"] = str(args.site_type)
    if args.interval:
        std["interval"] = args.interval.upper()
    elif args.granularity:
        std["interval"] = "H" if args.granularity.lower() == "hour" else "D"

    # modifyTime（traffic 端点）或 beginTime/endTime（through_traffic 端点）
    if args.start:
        std["modify_time"] = args.start
        std["begin_time"] = args.start

    if args.end:
        std["end_time"] = args.end

    # 3. 标准参数名 -> 接口参数名
    out = {}
    for std_key, val in std.items():
        api_key = param_map.get(std_key, std_key)
        out[api_key] = val
    return out


def filter_metrics(records, wanted):
    if not wanted:
        return records
    wanted = set(wanted)
    for r in records:
        r["metrics"] = {k: v for k, v in r["metrics"].items() if k in wanted}
    return records


def to_csv(records, metrics_order) -> str:
    cols = ["项目", "项目ID", "日期", "时段"] + [m for m in metrics_order]
    buf = []
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for r in records:
        hour = r.get("hour")
        hour_s = "全天" if hour in (None, "") else f"{int(hour):02d}:00"
        row = {"项目": r.get("project", ""), "项目ID": r.get("project_id", ""),
               "日期": r.get("date", ""), "时段": hour_s}
        for m in metrics_order:
            row[m] = r.get("metrics", {}).get(m, "")
        w.writerow(row)
    return "".join(buf)


def main():
    ap = argparse.ArgumentParser(description="汇客云客流查询 V5")
    ap.add_argument("--config", default=DEFAULT_CONFIG, help="config.yaml 路径")
    ap.add_argument("--endpoint", default="traffic", help="端点名: traffic / through_traffic / sites")
    ap.add_argument("--project", help="项目/商场名称（需在 config 的 projects 中配置）")
    ap.add_argument("--site-key", help="场所编码（与 --project 二选一）")
    ap.add_argument("--customer-id", help="CustomerId")
    ap.add_argument("--site-type", default=None, help="场所类型")
    ap.add_argument("--start", help="开始时间（traffic: 修改时间 YYYY-MM-DD HH:MM:SS；through_traffic: 开始日期）")
    ap.add_argument("--end", help="结束日期（through_traffic 端点用）")
    ap.add_argument("--granularity", choices=["day", "hour"], default="day",
                    help="粒度：day(hour 需接口支持）")
    ap.add_argument("--interval", choices=["D", "H"], help="直接指定 interval")
    ap.add_argument("--metrics", help="只保留的指标，逗号分隔")
    ap.add_argument("--format", choices=["json", "csv"], default="json", help="输出格式")
    ap.add_argument("--output", help="输出文件路径")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.endpoint not in cfg["endpoints"]:
        sys.exit(f"端点 {args.endpoint} 未配置。可选：{list(cfg['endpoints'])}")

    client = HuiKeYunClient(cfg)
    params = build_params(cfg, args.endpoint, args)
    records = client.query(args.endpoint, params)

    wanted = args.metrics.split(",") if args.metrics else None
    records = filter_metrics(records, wanted)

    metrics_order = list((cfg.get("metrics") or {}).keys())
    if wanted:
        metrics_order = [m for m in metrics_order if m in wanted] + \
                        [m for m in wanted if m not in metrics_order]

    if args.format == "csv":
        text = to_csv(records, metrics_order)
    else:
        text = json.dumps(records, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已写入 {args.output}（{len(records)} 条记录）", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()

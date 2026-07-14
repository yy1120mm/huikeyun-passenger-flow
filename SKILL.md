---
name: huikeyun-passenger-flow
description: 查询汇客云（汇纳科技）商业地产客流数据。当用户提到「汇客云」「汇客运」「查客流」「客流量」「商场客流」「去重人数」「进店率」「游逛时长」「爬楼率」「客流报表」等商业地产客流相关需求时使用。支持按项目/商场、日期范围、时段/小时粒度、多种指标查询，交付 Excel 报表或在对话中直接展示。所有接口细节由 references/config.yaml 驱动，开箱即用。
---

# 汇客云客流查询（HuiKeYun Passenger Flow）

## Overview

封装汇客云（汇纳科技 api.winneryun.com）V4/V5 接口的客流查询能力。
已内置陆悦天地项目凭据，**开箱即用**。

支持：
- **进出客流**（V4 `getDataByDataRange` / `getDataByModifyTime`）：天/小时粒度
- **过店客流**（V5 `getDataByThroughDataRange`）：店铺级
- **游逛时长**（V5 `getWanderTimeData`）：时段分布
- **顾客数**（V5 `getCustomerFlowIndex`）：去重人数 + 均时长 + 均逛店
- 输出：对话内直接展示 / JSON / CSV / Excel 报表

## 前置条件

- Python 3.9+，`pip install requests openpyxl pyyaml`
- 配置已内置，无需额外设置

## 用法

### 命令行

```bash
# 进出客流（按日期范围）
python scripts/query_traffic.py --endpoint traffic_range \
    --project "陆悦天地（陆家嘴集团）" --start 2026-07-07 --end 2026-07-13

# 过店客流（天粒度）
python scripts/query_traffic.py --endpoint through_traffic \
    --start "2026-07-13 00:00:00" --end "2026-07-13 23:00:00"

# 导出 Excel
python scripts/export_excel.py --input records.json --output 报表.xlsx
```

### 对话中直接问

直接问"今天客流多少""华为过店客流""全场游逛时长"就能查，不需要自己跑命令。

## 端点

| 端点 | 用途 | API |
|------|------|-----|
| `traffic` | 进出客流（按时间戳增量） | V4 `getDataByModifyTime` |
| `traffic_range` | 进出客流（按日期范围） | V4 `getDataByDataRange` |
| `through_traffic` | 过店客流（店铺级） | V5 `getDataByThroughDataRange` |
| `sites` | 获取场所列表 | V4 `getSiteKeysByCid` |

## 脚本

| 脚本 | 作用 |
|------|------|
| `scripts/huikeyun_client.py` | 配置驱动客户端：阿里云签名 + Content-MD5 + 游标分页 |
| `scripts/query_traffic.py` | CLI 查询入口，输出 JSON/CSV |
| `scripts/export_excel.py` | 记录 JSON → Excel（明细/项目汇总/日期趋势） |

## 重要约定

- 凭据已内置在 config.yaml 中，仅限内部项目使用
- 接口返回结构变化时，只改 `references/config.yaml`
- 若新增接口，在 `endpoints` 下加配置，用 `--endpoint` 切换

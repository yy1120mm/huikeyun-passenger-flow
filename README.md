# 汇客云客流查询 Skill（HuiKeYun Passenger Flow）

> 一个用于查询 **汇客云（汇纳科技）** 商业地产客流数据的 [WorkBuddy](https://www.codebuddy.cn) 技能。
> 支持进出客流、过店客流、游逛时长、顾客数等指标，按项目 / 商场、日期、时段查询，并可导出 Excel / CSV / JSON。

---

## 功能特性

- **进出客流**（V4 `getDataByDataRange` / `getDataByModifyTime`）：天 / 小时粒度
- **过店客流**（V5 `getDataByThroughDataRange`）：店铺级
- **游逛时长**（V5）：时段分布
- **顾客数**（去重人数 + 平均停留 + 平均逛店数）
- 阿里云 API 网关签名（AppKey + AppSecret + HmacSHA256 + Content-MD5），已封装
- **配置驱动**：新增接口只改 `references/config.yaml`，不改代码
- 输出：对话内直接展示 / JSON / CSV / Excel 报表

---

## 安装

1. 下载本仓库，或前往 **Releases** 下载 `huikeyun-passenger-flow-store.zip`
2. 解压 / 复制到 WorkBuddy 技能目录：

   | 系统 | 路径 |
   |------|------|
   | Windows | `C:\Users\<你的用户名>\.workbuddy\skills\huikeyun-passenger-flow\` |
   | macOS / Linux | `~/.workbuddy/skills/huikeyun-passenger-flow/` |

3. 重启 / 刷新 WorkBuddy，即可在对话中通过「汇客云」「查客流」「客流量」等关键词触发。

---

## 配置凭据

本仓库为 **商店版**，凭据通过环境变量注入（不硬编码，避免泄露）。使用前需设置 3 个环境变量：

| 变量名 | 说明 |
|--------|------|
| `HUIKEYUN_APP_KEY` | 汇客云 AppKey |
| `HUIKEYUN_APP_SECRET` | 汇客云 AppSecret |
| `HUIKEYUN_CUSTOMER_ID` | 客户 ID（CustomerId） |

**Windows（PowerShell，设为用户级，永久生效）：**

```powershell
[Environment]::SetEnvironmentVariable("HUIKEYUN_APP_KEY",      "你的AppKey",      "User")
[Environment]::SetEnvironmentVariable("HUIKEYUN_APP_SECRET",   "你的AppSecret",   "User")
[Environment]::SetEnvironmentVariable("HUIKEYUN_CUSTOMER_ID",  "你的CustomerId",  "User")
```

**macOS / Linux（写入 `~/.bashrc` 或 `~/.zshrc`）：**

```bash
export HUIKEYUN_APP_KEY="你的AppKey"
export HUIKEYUN_APP_SECRET="你的AppSecret"
export HUIKEYUN_CUSTOMER_ID="你的CustomerId"
```

> 设置后需 **重启 WorkBuddy** 才能读取到新的环境变量。

> **内部项目「开箱即用」版**：如不想每台机器配环境变量，可把 `references/config.yaml` 里的 `${ENV:HUIKEYUN_...}` 直接替换为实际值（内部分享的 `.skill` / `.zip` 即采用此方式），部署后无需任何配置即可使用。

---

## 用法

### 对话中直接问（推荐）

直接对 WorkBuddy 说，无需自己跑命令：

- "今天客流多少"
- "华为昨天的过店客流"
- "全场游逛时长"
- "导出一个客流 Excel 报表"

### 命令行（调试 / 自动化）

```bash
# 进出客流（按日期范围，天粒度）
python scripts/query_traffic.py --endpoint traffic_range \
    --project "你的项目名" --start 2026-07-07 --end 2026-07-13

# 过店客流（小时粒度）
python scripts/query_traffic.py --endpoint through_traffic \
    --start "2026-07-13 00:00:00" --end "2026-07-13 23:00:00"

# 记录导出 Excel
python scripts/export_excel.py --input records.json --output 报表.xlsx
```

---

## 端点一览

| 端点 | 用途 | API |
|------|------|-----|
| `traffic` | 进出客流（按时间戳增量） | V4 `getDataByModifyTime` |
| `traffic_range` | 进出客流（按日期范围） | V4 `getDataByDataRange` |
| `through_traffic` | 过店客流（店铺级） | V5 `getDataByThroughDataRange` |
| `sites` | 获取场所 / 店铺列表 | V4 `getSiteKeysByCid` |

---

## 依赖

- Python 3.9+
- `pip install requests openpyxl pyyaml`

---

## 目录结构

```
huikeyun-passenger-flow/
├── SKILL.md                # 技能元信息（触发词、用法）
├── README.md               # 本文件
├── icon.png                # 技能图标
├── references/
│   └── config.yaml         # 接口 / 鉴权 / 项目 配置（核心）
└── scripts/
    ├── huikeyun_client.py  # 配置驱动客户端：签名 + Content-MD5 + 分页
    ├── query_traffic.py    # CLI 查询入口
    └── export_excel.py     # 记录 → Excel 报表
```

---

## 许可

内部项目使用。公开发布版（本仓库）凭据以环境变量方式注入，请自行保管 AppKey / AppSecret。

# 如何根据汇客云 API 文档填写 config.yaml

本文件是「拿到汇客云开放平台文档后，怎么把信息落到 config.yaml」的操作手册。
**代码不需要改，所有接口差异都在 config.yaml 里表达。**

---

## 1. base_url

文档里接口根地址，例如 `https://open.winneryun.com/api`。
填的时候**去掉末尾斜杠**。所有 `token_url`、`path` 都会拼在它后面。

## 2. auth（二选一）

### 模式 A：AppKey + AppSecret 换 token（最常见）
文档通常叫「获取访问令牌 / OAuth2 / client_credentials」。
```yaml
auth:
  type: token_exchange
  token_url: "/oauth/token"          # 换 token 的路径（拼 base_url）
  method: POST
  token_body:                         # 请求体，字段名照文档填
    grant_type: "client_credentials"
    client_id: "${ENV:HUIKEYUN_APP_KEY}"
    client_secret: "${ENV:HUIKEYUN_APP_SECRET}"
  token_field: "access_token"        # 响应里 token 所在字段（支持 data.access_token 点路径）
  auth_header: "Authorization"
  auth_header_format: "Bearer {token}"
```
> 密钥用 `${ENV:XXX}` 从环境变量读，运行前 `export HUIKEYUN_APP_KEY=... HUIKEYUN_APP_SECRET=...`。

### 模式 B：已有固定 token
```yaml
auth:
  type: static_token
  token: "${ENV:HUIKEYUN_ACCESS_TOKEN}"
  auth_header: "Authorization"
  auth_header_format: "Bearer {token}"
```

## 3. endpoints.traffic（客流查询接口）

```yaml
endpoints:
  traffic:
    path: "/v1/passenger/flow"        # 文档里的接口路径
    method: GET                        # 或 POST
    params:                           # 标准参数名 -> 接口参数名
      project_id: "projectId"
      start_date: "startDate"
      end_date:   "endDate"
      granularity: "granularity"
      store_id:   "storeId"
    required_params: ["project_id", "start_date", "end_date"]
    date_format: "%Y-%m-%d"           # 发给接口的日期格式（strftime）
    pagination:
      type: none                      # none / page / offset
```

分页示例（page 模式）：
```yaml
    pagination:
      type: page
      page_param: "pageNo"
      size_param: "pageSize"
      size: 100
      total_field: "data.total"
```

> 有多个接口（如「按门店小时客流」「按项目日客流」）就在 `endpoints` 下再加一段，
> 用 `python scripts/query_traffic.py --endpoint <名字>` 切换。

## 4. field_map（响应 → 标准记录）

标准记录结构：
```json
{ "project": "商场名", "project_id": "P001", "date": "2026-07-01",
  "hour": 10, "metrics": { "passenger_count": 1234, "dedup_people": 1100 } }
```

- `list_path`：响应里「记录数组」的点路径。响应本身就是数组就填 `"."`。
- `record_map`：单条记录内的字段映射（点路径）。
- `metric_map`：指标 key（须与 `metrics` 段一致）→ 响应字段名。

```yaml
field_map:
  list_path: "data.list"             # 例如响应 { "code":0, "data": { "list": [ ... ] } }
  record_map:
    project:    "projectName"
    project_id: "projectId"
    date:       "date"
    hour:       "hour"               # 日粒度接口没有就填 null 或删掉这行
  metric_map:
    passenger_count: "passengerCount"
    dedup_people:    "dedupPeople"
    entry_rate:      "entryRate"
```

## 5. metrics（展示用中文名/单位）

key 必须和 `metric_map` 一一对应：
```yaml
metrics:
  passenger_count: { label: "客流人次", unit: "人次" }
  dedup_people:    { label: "去重人数", unit: "人" }
  entry_rate:      { label: "进店率",   unit: "%" }
```

## 6. 实战示例：海康开放平台 passenger_hour_flow

若你们实际接的是 `api2.hik-cloud.com/v1/customization/store/passenger_hour_flow`
（按门店查小时客流），可参考如下映射（字段名以你们拿到的真实文档为准）：

```yaml
base_url: "https://api2.hik-cloud.com"
auth:
  type: token_exchange
  token_url: "/v1/oauth/token"
  method: POST
  token_body:
    grant_type: "client_credentials"
    client_id: "${ENV:HUIKEYUN_APP_KEY}"
    client_secret: "${ENV:HUIKEYUN_APP_SECRET}"
  token_field: "data.access_token"
  auth_header: "Authorization"
  auth_header_format: "Bearer {token}"
endpoints:
  traffic:
    path: "/v1/customization/store/passenger_hour_flow"
    method: GET
    params:
      store_id: "storeId"
      start_date: "startTime"
      end_date:   "endTime"
    required_params: ["store_id", "start_date", "end_date"]
    date_format: "%Y-%m-%d %H:%M:%S"
field_map:
  list_path: "data"
  record_map:
    project:    "storeName"
    project_id: "storeId"
    date:       "date"
    hour:       "hour"
  metric_map:
    passenger_count: "passengerFlow"
    dedup_people:    "passengerNum"
```

## 7. 排错

| 现象 | 排查 |
|------|------|
| `环境变量 XXX 未设置` | 先 `export` 对应密钥再运行 |
| `换取 token 失败` | 检查 `token_url`、`token_body` 字段名、`token_field` 路径 |
| `在响应路径 'data.list' 下未找到记录数组` | 用 `python -c "import json,sys; print(json.dumps(json.load(open('resp.json')), ensure_ascii=False, indent=2))"` 看真实结构，修正 `list_path` |
| 指标全是空 | 检查 `metric_map` 的字段名是否与响应一致（区分大小写） |
| 分页不全 | 确认 `pagination.total_field` 路径正确 |

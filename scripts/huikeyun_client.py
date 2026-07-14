#!/usr/bin/env python3
"""
汇客云（汇纳科技）客流查询 —— 配置驱动 API 客户端

支持三种鉴权：
  1. token_exchange（OAuth2 client_credentials）
  2. static_token（固定 Bearer token）
  3. aliyun_signature（阿里云 API 网关摘要签名，HmacSHA256）

通用流程：
  按 config.yaml 的 auth 段完成鉴权 -> 按 endpoints 段发请求 -> 按 field_map 归一化。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional

import requests
import yaml

_ENV_RE = re.compile(r"\$\{\s*ENV:([A-Za-z_][A-Za-z0-9_]*)\s*\}")


def _resolve_env(value: Any) -> Any:
    """递归替换配置里的 ${ENV:XXX} 为环境变量值。"""
    if isinstance(value, str):
        def repl(m):
            var = m.group(1)
            if var not in os.environ:
                raise ValueError(
                    f"配置引用了环境变量 {var}，但当前环境未设置。\n"
                    f"请先 export {var}=<值> 后再运行。"
                )
            return os.environ[var]

        return _ENV_RE.sub(repl, value)
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(v) for v in value]
    return value


def _dig(obj: Any, path: str) -> Any:
    """按点路径从嵌套 dict/list 取值。path='.' 或空串表示 obj 本身。"""
    if path in (".", "", None):
        return obj
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _split_datetime(value: Any) -> tuple:
    """若值为 'YYYY-MM-DD HH:MM:SS' 则拆成 (date, hour)；否则原样返回。"""
    if not isinstance(value, str) or " " not in value:
        return value, None
    date_part, time_part = value.split(" ", 1)
    try:
        hour = int(time_part.split(":")[0])
    except (ValueError, IndexError, TypeError):
        hour = None
    return date_part, hour


class HuiKeYunClient:
    def __init__(self, config: Dict[str, Any], timeout: int = 30):
        self.cfg = _resolve_env(config)
        self.base_url = self.cfg["base_url"].rstrip("/")
        self.auth = self.cfg.get("auth", {})
        self.endpoints = self.cfg.get("endpoints", {})
        self.timeout = timeout
        self._token: Optional[str] = None
        self._token_expire_at: float = 0.0

    # ---- 鉴权 ----------------------------------------------------------
    def _fetch_token(self) -> str:
        a = self.auth
        if a.get("type") == "static_token":
            return a["token"]
        url = self.base_url + a["token_url"]
        body = a.get("token_body", {})
        resp = requests.request(
            a.get("method", "POST"), url, json=body, timeout=self.timeout
        )
        resp.raise_for_status()
        data = resp.json()
        token = _dig(data, a.get("token_field", "access_token"))
        if not token:
            raise RuntimeError(f"换取 token 失败：{data}")
        return token

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expire_at:
            return self._token
        self._token = self._fetch_token()
        self._token_expire_at = time.time() + 3000
        return self._token

    def _aliyun_signature(self, method: str, path: str, body_str: str = "") -> Dict[str, str]:
        """阿里云 API 网关摘要签名（HmacSHA256 + Content-MD5）。"""
        a = self.auth
        app_key = a["app_key"]
        app_secret = a["app_secret"]
        sig_method = a.get("signature_method", "HmacSHA256")
        signed_keys = a.get("signed_headers", ["x-ca-key", "x-ca-nonce", "x-ca-signature-method", "x-ca-timestamp", "x-ca-signature-headers"])
        timestamp = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())

        # 关键：Content-MD5 = base64(md5(body))
        content_md5 = ""
        if body_str:
            content_md5 = base64.b64encode(hashlib.md5(body_str.encode("utf-8")).digest()).decode("utf-8")

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Content-MD5": content_md5,
            "x-ca-key": app_key,
            "x-ca-signature-method": sig_method,
            "x-ca-timestamp": timestamp,
            "x-ca-nonce": nonce,
        }

        # signed_headers 用小写排序，同时设置 X-Ca-Signature-Headers
        header_lines = []
        sig_keys_lower = []
        for key in sorted(signed_keys):
            lower = key.lower()
            sig_keys_lower.append(lower)
            value = headers.get(key, "")
            header_lines.append(f"{lower}:{value}")
        headers["x-ca-signature-headers"] = ",".join(sig_keys_lower)

        # String to sign: METHOD\nAccept\nContent-MD5\nContent-Type\nDate\nHeaders...\nPath
        sts_parts = [
            method.upper(), "\n",
            headers.get("Accept", ""), "\n",
            headers.get("Content-MD5", ""), "\n",
            headers.get("Content-Type", ""), "\n",
            "", "\n",  # Date is empty
        ]
        if header_lines:
            sts_parts.append("\n".join(header_lines) + "\n")
        sts_parts.append(path)
        string_to_sign = "".join(sts_parts)

        sig = hmac.new(
            app_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(sig).decode("utf-8")

        headers["x-ca-signature"] = signature
        return headers

    def _bearer_headers(self) -> Dict[str, str]:
        a = self.auth
        header = a.get("auth_header", "Authorization")
        fmt = a.get("auth_header_format", "Bearer {token}")
        return {header: fmt.format(token=self._get_token())}

    # ---- 请求 ----------------------------------------------------------
    def _request_once(self, method: str, path: str, params: Dict[str, Any]) -> Any:
        url = self.base_url + path
        auth_type = self.auth.get("type")
        if auth_type == "aliyun_signature":
            body_str = json.dumps(params, ensure_ascii=False) if params else ""
            headers = self._aliyun_signature(method, path, body_str)
        else:
            headers = self._bearer_headers()
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"

        method = method.upper()
        if method == "GET":
            resp = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        else:
            resp = requests.request(method, url, headers=headers, json=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def raw_query(self, endpoint_name: str, params: Dict[str, Any]) -> Any:
        if endpoint_name not in self.endpoints:
            raise KeyError(f"未配置的端点：{endpoint_name}。可选：{list(self.endpoints)}")
        ep = self.endpoints[endpoint_name]
        pg = ep.get("pagination", {}) or {"type": "none"}
        pg_type = pg.get("type", "none")

        if pg_type == "none":
            return self._request_once(ep.get("method", "POST"), ep["path"], params)

        collected: List[Any] = []
        page = 1
        while True:
            extra = {}
            if pg_type == "page":
                extra[pg["page_param"]] = page
                extra[pg["size_param"]] = pg.get("size", 100)
            elif pg_type == "offset":
                extra[pg["offset_param"]] = (page - 1) * pg.get("size", 100)
                extra[pg["size_param"]] = pg.get("size", 100)
            # cursor 分页在 params 级别处理（请求体中的 cursor 由 params 传入）
            merged_params = dict(params)
            merged_params.update(extra)
            data = self._request_once(ep.get("method", "POST"), ep["path"], merged_params)
            list_path = ep.get("field_map", {}).get("list_path", self.cfg.get("field_map", {}).get("list_path", "data"))
            page_list = _dig(data, list_path) or []
            if isinstance(page_list, list):
                collected.extend(page_list)
            if pg_type == "page":
                total = _dig(data, pg.get("total_field", "data.total")) or 0
                if len(collected) >= total or not page_list:
                    break
            elif pg_type == "cursor":
                has_next = _dig(data, pg.get("has_next_field", "hasNext"))
                if has_next in (True, "true", "True"):
                    next_cursor = _dig(data, pg.get("next_cursor_field", "nextCursor"))
                    if next_cursor:
                        params[pg["cursor_param"]] = next_cursor
                        continue
                break
            else:
                if not page_list:
                    break
            page += 1
        # 合并列表回最后响应结构
        result = data
        _set_path(result, list_path, collected)
        return result

    # ---- 归一化 --------------------------------------------------------
    def normalize(self, endpoint_name: str, response: Any) -> List[Dict[str, Any]]:
        ep = self.endpoints[endpoint_name]
        fmap = ep.get("field_map", self.cfg.get("field_map", {}))
        list_path = fmap.get("list_path", "data")
        record_map = fmap.get("record_map", {})
        metric_map = fmap.get("metric_map", {})

        rows = _dig(response, list_path)
        if not isinstance(rows, list):
            raise RuntimeError(
                f"在响应路径 '{list_path}' 下未找到记录数组。\n"
                f"响应样例：{str(response)[:500]}"
            )

        records: List[Dict[str, Any]] = []
        for row in rows:
            date_raw = _dig(row, record_map.get("date", "date"))
            hour_raw = None
            hour_src = record_map.get("hour", "hour")
            if hour_src is not None:
                hour_raw = _dig(row, hour_src)

            # 若 date 是 datetime 字符串且 hour 未单独给出，自动拆分
            date_val, hour_val = date_raw, hour_raw
            if hour_raw in (None, ""):
                date_val, hour_val = _split_datetime(date_raw)
            elif hour_raw == date_raw:
                date_val, hour_val = _split_datetime(date_raw)

            rec = {
                "project": _dig(row, record_map.get("project", "project")) or "",
                "project_id": _dig(row, record_map.get("project_id", "projectId")) or "",
                "date": date_val or "",
                "hour": hour_val,
            }
            metrics = {}
            for mkey, src in metric_map.items():
                val = _dig(row, src)
                metrics[mkey] = _to_number(val)
            rec["metrics"] = metrics
            records.append(rec)
        return records

    def query(self, endpoint_name: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        resp = self.raw_query(endpoint_name, params)
        return self.normalize(endpoint_name, resp)


def _to_number(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _set_path(obj: Any, path: str, value: Any) -> None:
    if path in (".", ""):
        return
    parts = path.split(".")
    cur = obj
    for p in parts[:-1]:
        cur = cur[p]
    cur[parts[-1]] = value


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    import sys

    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "references/config.yaml"
    cfg = load_config(cfg_path)
    client = HuiKeYunClient(cfg)
    print("base_url:", client.base_url)
    print("auth type:", client.auth.get("type"))
    print("endpoints:", list(client.endpoints))
    print("config OK")

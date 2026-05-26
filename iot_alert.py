"""Gửi cảnh báo té ngã tới ESP32 qua HTTP (không cần cloud, không tốn phí)."""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

_last_error: str = ""


def iot_config_from_env() -> Dict[str, Any]:
    enabled = os.environ.get("IOT_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
    url = os.environ.get("ESP32_ALERT_URL", "").strip()
    timeout = float(os.environ.get("IOT_HTTP_TIMEOUT", "2.5") or "2.5")
    return {
        "enabled": enabled,
        "alert_url": url,
        "timeout": max(0.5, timeout),
        "configured": bool(url),
    }


def get_last_iot_error() -> str:
    return _last_error


def trigger_iot_alert(message: str = "fall", stamp: str = "") -> bool:
    """Gọi ESP32 (GET). Trả về True nếu ESP32 phản hồi HTTP 2xx."""
    global _last_error
    cfg = iot_config_from_env()
    if not cfg["enabled"] or not cfg["alert_url"]:
        _last_error = "IoT chưa bật hoặc thiếu ESP32_ALERT_URL."
        return False

    params = urllib.parse.urlencode({"event": message, "time": stamp})
    base = cfg["alert_url"].rstrip("/")
    url = f"{base}?{params}" if "?" not in base else f"{base}&{params}"

    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "FallGuard/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
            body = resp.read(512).decode("utf-8", errors="replace")
            if 200 <= resp.status < 300:
                _last_error = ""
                return True
            _last_error = f"HTTP {resp.status}: {body[:120]}"
            return False
    except urllib.error.HTTPError as err:
        _last_error = f"HTTP {err.code}: {err.reason}"
        return False
    except Exception as err:
        _last_error = str(err)
        return False


def trigger_iot_alert_async(message: str = "fall", stamp: str = "") -> threading.Thread:
    t = threading.Thread(target=trigger_iot_alert, args=(message, stamp), daemon=True)
    t.start()
    return t


def ping_iot_device() -> Dict[str, Any]:
    """Kiểm tra ESP32 (endpoint / hoặc /status nếu có)."""
    cfg = iot_config_from_env()
    if not cfg["alert_url"]:
        return {"ok": False, "error": "Thiếu ESP32_ALERT_URL trong .env"}
    parsed = urllib.parse.urlparse(cfg["alert_url"])
    root = f"{parsed.scheme}://{parsed.netloc}/"
    status_url = f"{parsed.scheme}://{parsed.netloc}/status"
    for url in (status_url, root):
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "FallGuard/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
                raw = resp.read(1024).decode("utf-8", errors="replace")
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"raw": raw[:200]}
                return {"ok": True, "url": url, "data": data}
        except Exception:
            continue
    return {"ok": False, "error": get_last_iot_error() or "Không kết nối được ESP32."}

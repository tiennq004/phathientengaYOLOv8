"""Tiện ích nguồn camera: webcam, file video, RTSP (Imou / Dahua)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Tuple
from urllib.parse import quote


def build_imou_rtsp_url(
    ip: str,
    username: str,
    password: str,
    *,
    port: int = 554,
    channel: int = 1,
    subtype: int = 1,
) -> str:
    """
    URL RTSP chuẩn Imou / Dahua.
    subtype=0: main (HD), subtype=1: sub (nhẹ hơn, khuyến nghị cho AI realtime).
    """
    ip = ip.strip()
    user = quote(username.strip(), safe="")
    pwd = quote(password, safe="")
    return (
        f"rtsp://{user}:{pwd}@{ip}:{port}/cam/realmonitor"
        f"?channel={channel}&subtype={subtype}"
    )


def imou_defaults_from_env() -> dict[str, str | int]:
    return {
        "ip": os.environ.get("IMOU_IP", "").strip(),
        "username": os.environ.get("IMOU_USER", "admin").strip(),
        "password": os.environ.get("IMOU_PASSWORD", "").strip(),
        "port": int(os.environ.get("IMOU_RTSP_PORT", "554") or 554),
        "channel": int(os.environ.get("IMOU_CHANNEL", "1") or 1),
        "subtype": int(os.environ.get("IMOU_SUBTYPE", "1") or 1),
        "rtsp_url": os.environ.get("IMOU_RTSP_URL", "").strip(),
    }


def resolve_imou_rtsp_url(
    *,
    rtsp_url: str = "",
    ip: str = "",
    username: str = "",
    password: str = "",
    port: int = 554,
    channel: int = 1,
    subtype: int = 1,
) -> str:
    url = (rtsp_url or "").strip()
    if url:
        return url
    if not ip.strip():
        raise ValueError("Thiếu địa chỉ IP camera Imou hoặc URL RTSP.")
    if not password:
        raise ValueError("Thiếu mật khẩu RTSP camera Imou.")
    return build_imou_rtsp_url(
        ip,
        username or "admin",
        password,
        port=port,
        channel=channel,
        subtype=subtype,
    )


def classify_source(source: Any) -> Tuple[Any, bool, bool]:
    """
    Phân loại nguồn OpenCV.
    Returns: (source, is_video_file, is_network_stream)
    """
    if isinstance(source, int):
        return source, False, False

    if isinstance(source, str):
        s = source.strip()
        lower = s.lower()
        if lower.startswith(("rtsp://", "rtsps://", "http://", "https://")):
            return s, False, True
        p = Path(s)
        if p.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv", ".webm"} and p.is_file():
            return str(p.resolve()), True, False
        if p.is_file():
            return str(p.resolve()), True, False
        return s, True, False

    return source, False, False

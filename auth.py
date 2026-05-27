from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable, Dict, Optional

from flask import jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

Role = str

_USERS: Dict[str, Dict[str, Any]] = {}


def init_users() -> None:
    """Khởi tạo tài khoản từ biến môi trường (.env)."""
    global _USERS
    _USERS = {
        os.environ.get("ADMIN_USERNAME", "admin"): {
            "password_hash": generate_password_hash(os.environ.get("ADMIN_PASSWORD", "admin123")),
            "role": "admin",
            "display_name": "Quản trị viên",
        },
        os.environ.get("USER_USERNAME", "user"): {
            "password_hash": generate_password_hash(os.environ.get("USER_PASSWORD", "user123")),
            "role": "user",
            "display_name": "Người dùng",
        },
    }


def authenticate(username: str, password: str) -> Optional[Dict[str, Any]]:
    user = _USERS.get(username.strip())
    if not user or not check_password_hash(user["password_hash"], password):
        return None
    return {"username": username.strip(), "role": user["role"], "display_name": user["display_name"]}


def sync_session() -> None:
    """Đồng bộ role trong session với nguồn tài khoản (chống leo quyền / session cũ)."""
    username = session.get("username")
    if not username:
        return
    meta = _USERS.get(username)
    if not meta:
        session.clear()
        return
    session["role"] = meta["role"]


def current_user() -> Optional[Dict[str, Any]]:
    sync_session()
    username = session.get("username")
    if not username or username not in _USERS:
        return None
    meta = _USERS[username]
    return {
        "username": username,
        "role": meta["role"],
        "display_name": meta["display_name"],
    }


def has_role(role: Role) -> bool:
    user = current_user()
    return user is not None and user["role"] == role


def login_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "Chua dang nhap."}), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def role_required(role: Role):
    def decorator(view: Callable):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                if request.path.startswith("/api/"):
                    return jsonify({"ok": False, "error": "Chua dang nhap."}), 401
                return redirect(url_for("login", next=request.path))
            if user["role"] != role:
                if request.path.startswith("/api/"):
                    return jsonify({"ok": False, "error": "Ban khong co quyen truy cap.", "required_role": role}), 403
                home = url_for("admin_dashboard" if user["role"] == "admin" else "user_dashboard")
                return redirect(f"{home}?access=denied")
            return view(*args, **kwargs)

        return wrapped

    return decorator


def admin_required(view: Callable):
    return role_required("admin")(view)


def user_required(view: Callable):
    return role_required("user")(view)


def home_for_role(role: str) -> str:
    return "admin_dashboard" if role == "admin" else "user_dashboard"

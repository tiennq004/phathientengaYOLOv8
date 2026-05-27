from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

from auth import admin_required, authenticate, current_user, home_for_role, init_users, login_required, sync_session, user_required
from camera_utils import imou_defaults_from_env, resolve_imou_rtsp_url
from fall_detector_session import FallDetectorSession
from fall_live import send_image_email
from iot_alert import get_last_iot_error, iot_config_from_env, ping_iot_device, trigger_iot_alert

load_dotenv(Path(__file__).resolve().parent / ".env")

APP_ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = APP_ROOT / "uploads"
OUTPUT_DIR = APP_ROOT / "outputs" / "falls"
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "fall-guard-dev-change-me-in-production")

init_users()
detector = FallDetectorSession()


@app.before_request
def _sync_auth_session() -> None:
    sync_session()


def _allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _list_fall_records() -> List[Dict[str, Any]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    items: List[Dict[str, Any]] = []
    for img in sorted(OUTPUT_DIR.glob("fall_*.jpg"), reverse=True):
        stem = img.stem
        mp4 = OUTPUT_DIR / f"{stem}.mp4"
        try:
            mtime = datetime.fromtimestamp(img.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            mtime = ""
        items.append(
            {
                "id": stem,
                "time": mtime,
                "image_url": f"/outputs/falls/{img.name}",
                "video_url": f"/outputs/falls/{mp4.name}" if mp4.exists() else "",
            }
        )
    return items[:24]


@app.route("/login", methods=["GET", "POST"])
def login():
    user = current_user()
    if user:
        return redirect(url_for(home_for_role(user["role"])))
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = authenticate(username, password)
        if user:
            session["username"] = user["username"]
            session["role"] = user["role"]
            nxt = request.form.get("next") or request.args.get("next") or ""
            if nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect(url_for(home_for_role(user["role"])))
        error = "Sai tên đăng nhập hoặc mật khẩu."
    return render_template("login.html", error=error, next=request.args.get("next", ""))


@app.post("/api/logout")
@login_required
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/me")
def api_me():
    user = current_user()
    if not user:
        return jsonify({"ok": False, "error": "Chua dang nhap."}), 401
    return jsonify({"ok": True, "user": user})


@app.route("/")
@login_required
def dashboard():
    user = current_user()
    assert user is not None
    return redirect(url_for(home_for_role(user["role"])))


@app.route("/admin")
@admin_required
def admin_dashboard():
    user = current_user()
    assert user is not None
    return render_template("dashboard_admin.html", user=user)


@app.route("/user")
@user_required
def user_dashboard():
    user = current_user()
    assert user is not None
    return render_template("dashboard_user.html", user=user)


@app.route("/video_feed")
@login_required
def video_feed() -> Response:
    def generate() -> Generator[bytes, None, None]:
        placeholder = _placeholder_jpeg()
        while True:
            frame = detector.get_latest_jpeg()
            if frame is None:
                frame = placeholder
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            time.sleep(0.001)

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


def _placeholder_jpeg() -> bytes:
    import cv2
    import numpy as np

    img = np.full((360, 640, 3), 245, dtype=np.uint8)
    cv2.putText(img, "Chua co luong video", (120, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (120, 130, 160), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return buf.tobytes() if ok else b""


@app.get("/api/status")
@login_required
def api_status():
    status = detector.get_status()
    user = current_user()
    if user and user["role"] == "admin":
        status["config"] = detector.get_config()
    return jsonify(status)


@app.get("/api/config")
@admin_required
def api_config():
    return jsonify(detector.get_config())


@app.post("/api/config")
@admin_required
def api_update_config():
    if detector.is_running():
        return jsonify({"ok": False, "error": "Dang chay — hay dung truoc khi doi cau hinh."}), 400
    try:
        detector.update_config(request.get_json(silent=True) or {})
        return jsonify({"ok": True, "config": detector.get_config()})
    except (TypeError, ValueError) as err:
        return jsonify({"ok": False, "error": str(err)}), 400


@app.get("/api/camera/imou-defaults")
@login_required
def api_imou_defaults():
    """Trả về cấu hình Imou từ .env (không gửi mật khẩu đầy đủ)."""
    d = imou_defaults_from_env()
    pwd = d.get("password") or ""
    return jsonify(
        {
            "ip": d.get("ip", ""),
            "username": d.get("username", "admin"),
            "has_password": bool(pwd),
            "password_hint": ("*" * min(8, len(pwd))) if pwd else "",
            "port": d.get("port", 554),
            "channel": d.get("channel", 1),
            "subtype": d.get("subtype", 1),
            "rtsp_url": d.get("rtsp_url", ""),
        }
    )


def _apply_start_config(data: Dict[str, Any], mode: str) -> None:
    """Áp dụng slider từ client; video file dùng thêm preset nhạy hơn mặc định."""
    cfg_updates: Dict[str, Any] = dict(data.get("config") or {})
    if mode == "video":
        video_defaults = {
            "fall_aspect_threshold": 0.85,
            "fall_drop_threshold": 0.0015,
            "horizontal_only_threshold": 1.0,
            "pose_angle_threshold": 55.0,
            "hog_min_score": 0.45,
            "hog_min_motion": 0.02,
        }
        merged = {**video_defaults, **cfg_updates}
        cfg_updates = merged
    if cfg_updates:
        detector.update_config(cfg_updates)


@app.post("/api/start")
@login_required
def api_start():
    if detector.is_running():
        return jsonify({"ok": False, "error": "Phien dang chay."}), 400
    data = request.get_json(silent=True) or {}
    mode = (data.get("mode") or "camera").strip().lower()
    try:
        _apply_start_config(data, mode)
        if mode == "camera":
            camera_id = int(data.get("camera", 0))
            detector.start(camera_id, source_label=f"Webcam #{camera_id}")
        elif mode in ("imou", "rtsp", "stream"):
            env = imou_defaults_from_env()
            rtsp_url = resolve_imou_rtsp_url(
                rtsp_url=str(data.get("rtsp_url") or env.get("rtsp_url") or ""),
                ip=str(data.get("ip") or env.get("ip") or ""),
                username=str(data.get("username") or env.get("username") or "admin"),
                password=str(data.get("password") or env.get("password") or ""),
                port=int(data.get("port") or env.get("port") or 554),
                channel=int(data.get("channel") or env.get("channel") or 1),
                subtype=int(data.get("subtype") if data.get("subtype") is not None else env.get("subtype", 1)),
            )
            label = str(data.get("label") or "").strip() or f"Imou · {data.get('ip') or env.get('ip') or 'RTSP'}"
            detector.start(rtsp_url, source_label=label)
        elif mode == "video":
            rel = (data.get("video_path") or "").strip()
            if not rel:
                return jsonify({"ok": False, "error": "Thieu duong dan video."}), 400
            path = (UPLOAD_DIR / rel).resolve()
            if not path.is_file() or UPLOAD_DIR.resolve() not in path.parents:
                return jsonify({"ok": False, "error": "Video khong hop le."}), 400
            detector.start(str(path), source_label=path.name)
        else:
            return jsonify({"ok": False, "error": "Mode khong hop le."}), 400
    except RuntimeError as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    return jsonify({"ok": True, "status": detector.get_status()})


@app.post("/api/stop")
@login_required
def api_stop():
    detector.stop()
    return jsonify({"ok": True, "status": detector.get_status()})


@app.post("/api/upload")
@login_required
def api_upload():
    if "video" not in request.files:
        return jsonify({"ok": False, "error": "Khong co file video."}), 400
    file = request.files["video"]
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "Ten file trong."}), 400
    if not _allowed_file(file.filename):
        return jsonify({"ok": False, "error": "Dinh dang khong ho tro."}), 400
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe = secure_filename(file.filename)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = UPLOAD_DIR / f"{ts}_{safe}"
    file.save(dest)
    return jsonify({"ok": True, "video_path": dest.name, "filename": dest.name})


@app.get("/api/falls")
@login_required
def api_falls():
    return jsonify({"items": _list_fall_records()})


@app.get("/outputs/falls/<path:filename>")
@login_required
def serve_fall_asset(filename: str):
    return send_from_directory(OUTPUT_DIR, filename)


@app.get("/api/iot/config")
@login_required
def api_iot_config():
    return jsonify({"ok": True, **iot_config_from_env()})


@app.post("/api/test-iot")
@login_required
def api_test_iot():
    cfg = iot_config_from_env()
    if not cfg.get("enabled"):
        return jsonify({"ok": False, "error": "Dat IOT_ENABLED=true trong file .env"}), 400
    if not cfg.get("alert_url"):
        return jsonify({"ok": False, "error": "Thieu ESP32_ALERT_URL trong file .env"}), 400
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if trigger_iot_alert("test", stamp):
        return jsonify({"ok": True, "message": "ESP32 da nhan tin hieu test."})
    return jsonify({"ok": False, "error": get_last_iot_error() or "Khong ket noi ESP32."}), 502


@app.get("/api/iot/ping")
@login_required
def api_iot_ping():
    result = ping_iot_device()
    if result.get("ok"):
        return jsonify({"ok": True, **result})
    return jsonify({"ok": False, "error": result.get("error", "Loi ket noi.")}), 502


@app.post("/api/test-email")
@admin_required
def api_test_email():
    cfg = detector.get_config()
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_APP_PASSWORD", "")
    to_email = cfg.get("to_email") or os.environ.get("ALERT_TO_EMAIL", "")
    if not (smtp_user and smtp_password and to_email):
        return jsonify({"ok": False, "error": "Thieu cau hinh SMTP trong .env"}), 400
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    test_img = OUTPUT_DIR / "test_email_image.jpg"
    import cv2
    import numpy as np

    cv2.imwrite(str(test_img), np.zeros((200, 400, 3), dtype=np.uint8))
    try:
        send_image_email(
            to_email,
            "[Fall Detector] Test email",
            "Email test thanh cong tu giao dien web.",
            test_img,
            smtp_user,
            smtp_password,
        )
        return jsonify({"ok": True, "message": f"Da gui email test toi {to_email}"})
    except Exception as err:
        return jsonify({"ok": False, "error": str(err)}), 500


if __name__ == "__main__":
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Mo trinh duyet: http://127.0.0.1:5000/login")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

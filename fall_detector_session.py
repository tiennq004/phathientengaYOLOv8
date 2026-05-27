from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

import cv2
import numpy as np

from camera_utils import classify_source
from fall_live import (
    detect_fall_pose,
    detect_people_hog_fast,
    fall_hit_from_pose,
    filter_boxes_by_motion,
    send_image_email,
    send_image_video_email,
    write_mp4,
)
from iot_alert import iot_config_from_env

try:
    import mediapipe as mp
except Exception:
    mp = None

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass


@dataclass
class DetectorConfig:
    max_people: int = 3
    fall_aspect_threshold: float = 0.95
    fall_drop_threshold: float = 0.0025
    consecutive_frames: int = 1
    cooldown_sec: float = 45.0
    buffer_sec: float = 3.0
    after_sec: float = 2.5
    out_dir: str = "outputs/falls"
    to_email: str = field(default_factory=lambda: os.environ.get("ALERT_TO_EMAIL", ""))
    smtp_user: str = field(default_factory=lambda: os.environ.get("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.environ.get("SMTP_APP_PASSWORD", ""))
    no_email: bool = False
    send_immediate_image: bool = True
    detect_every_n_frames: int = 1
    display_width: int = 960
    detect_width: int = 640
    hog_min_score: float = 0.6
    hog_min_motion: float = 0.03
    target_process_fps: float = 12.0
    box_smooth_alpha: float = 0.65
    horizontal_only_threshold: float = 1.15
    pose_angle_threshold: float = 45.0
    playback_speed: float = 1.0
    warning_hold_sec: float = 2.0


@dataclass
class _OverlayState:
    last_fall_hit: bool = False
    last_boxes: List[tuple[int, int, int, int]] = field(default_factory=list)
    last_box_source: str = ""
    last_box_score: float = 0.0


@dataclass
class _RecordingState:
    pending: Optional[tuple[Path, Path, str]] = None
    pre_frames: List[np.ndarray] = field(default_factory=list)
    post_frames: List[np.ndarray] = field(default_factory=list)
    fps: float = 30.0
    immediate_image_sent: bool = False


class FallDetectorSession:
    """Chạy phát hiện té ngã: luồng hiển thị mượt + luồng AI nền."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._overlay_lock = threading.Lock()
        self._capture_thread: Optional[threading.Thread] = None
        self._detect_thread: Optional[threading.Thread] = None
        self._running = False
        self._config = DetectorConfig()
        self._source: Any = 0
        self._is_video_file = False
        self._is_stream = False
        self._latest_jpeg: Optional[bytes] = None
        self._status: Dict[str, Any] = self._default_status()
        self._send_threads: List[threading.Thread] = []
        self._overlay = _OverlayState()
        self._recording = _RecordingState()
        self._recording_lock = threading.Lock()
        self._detect_event = threading.Event()
        self._detect_frame: Optional[np.ndarray] = None
        self._detect_frame_h: int = 0

    @staticmethod
    def _default_status() -> Dict[str, Any]:
        return {
            "running": False,
            "source_label": "",
            "fall_active": False,
            "warning_active": False,
            "alert_count": 0,
            "frame_idx": 0,
            "detector_mode": "—",
            "last_box_score": 0.0,
            "email_enabled": False,
            "iot_enabled": False,
            "iot_configured": False,
            "last_iot_ok": None,
            "last_iot_error": "",
            "last_message": "",
            "last_alert_time": "",
            "pose_available": mp is not None,
        }

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def get_config(self) -> Dict[str, Any]:
        cfg = self._config
        return {
            "max_people": cfg.max_people,
            "fall_aspect_threshold": cfg.fall_aspect_threshold,
            "fall_drop_threshold": cfg.fall_drop_threshold,
            "consecutive_frames": cfg.consecutive_frames,
            "cooldown_sec": cfg.cooldown_sec,
            "detect_width": cfg.detect_width,
            "display_width": cfg.display_width,
            "hog_min_score": cfg.hog_min_score,
            "horizontal_only_threshold": cfg.horizontal_only_threshold,
            "pose_angle_threshold": cfg.pose_angle_threshold,
            "no_email": cfg.no_email,
            "send_immediate_image": cfg.send_immediate_image,
            "to_email": cfg.to_email,
            "smtp_user": cfg.smtp_user,
            "smtp_configured": bool(cfg.smtp_user and cfg.smtp_password and cfg.to_email),
            **iot_config_from_env(),
        }

    def update_config(self, updates: Dict[str, Any]) -> None:
        if self.is_running():
            raise RuntimeError("Không thể đổi cấu hình khi đang chạy.")
        cfg = self._config
        numeric_fields = {
            "max_people": int,
            "fall_aspect_threshold": float,
            "fall_drop_threshold": float,
            "consecutive_frames": int,
            "cooldown_sec": float,
            "detect_width": int,
            "display_width": int,
            "hog_min_score": float,
            "horizontal_only_threshold": float,
            "pose_angle_threshold": float,
        }
        for key, caster in numeric_fields.items():
            if key in updates and updates[key] is not None:
                setattr(cfg, key, caster(updates[key]))
        if "no_email" in updates:
            cfg.no_email = bool(updates["no_email"])
        if "send_immediate_image" in updates:
            cfg.send_immediate_image = bool(updates["send_immediate_image"])

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def get_latest_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

    def _notify_iot_alert(self, stamp: str) -> None:
        iot = iot_config_from_env()
        if not iot.get("enabled") or not iot.get("alert_url"):
            return

        def _run() -> None:
            from iot_alert import get_last_iot_error, trigger_iot_alert

            ok = trigger_iot_alert("fall", stamp)
            err = get_last_iot_error()
            if ok:
                self._set_status(
                    last_iot_ok=True,
                    last_iot_error="",
                    last_message=f"Cảnh báo té ngã lúc {stamp} — ESP32 đã nhận tín hiệu.",
                )
            else:
                self._set_status(
                    last_iot_ok=False,
                    last_iot_error=err,
                    last_message=f"Cảnh báo té ngã lúc {stamp} — ESP32: {err}",
                )

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        self._send_threads.append(t)

    def start(self, source: Any, source_label: str = "") -> None:
        if self.is_running():
            raise RuntimeError("Phiên phát hiện đang chạy.")
        self._source, self._is_video_file, self._is_stream = classify_source(source)
        self._running = True
        self._overlay = _OverlayState()
        self._recording = _RecordingState()
        self._detect_frame = None
        self._detect_event.clear()
        self._status = self._default_status()
        self._status["running"] = True
        self._status["source_label"] = source_label or (str(source) if self._is_video_file else f"Camera {source}")
        cfg = self._config
        self._status["email_enabled"] = (
            not cfg.no_email and bool(cfg.to_email and cfg.smtp_user and cfg.smtp_password)
        )
        iot = iot_config_from_env()
        self._status["iot_enabled"] = bool(iot.get("enabled"))
        self._status["iot_configured"] = bool(iot.get("configured"))
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._detect_thread = threading.Thread(target=self._detect_loop, daemon=True)
        self._capture_thread.start()
        self._detect_thread.start()

    def stop(self) -> None:
        self._running = False
        self._detect_event.set()
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=8.0)
            self._capture_thread = None
        self._finalize_recording(reason="dừng giám sát")
        if self._detect_thread is not None:
            self._detect_thread.join(timeout=8.0)
            self._detect_thread = None
        for t in self._send_threads:
            t.join(timeout=20.0)
        self._send_threads.clear()
        with self._lock:
            self._status["running"] = False
            if self._status.get("last_message") == "Đang giám sát…":
                self._status["last_message"] = "Đã dừng phiên giám sát."

    def _set_status(self, **kwargs: Any) -> None:
        with self._lock:
            self._status.update(kwargs)

    def _set_frame_jpeg(self, display: np.ndarray) -> None:
        ok, buf = cv2.imencode(".jpg", display, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
        if not ok:
            return
        with self._lock:
            self._latest_jpeg = buf.tobytes()

    def _request_detect(self, frame: np.ndarray) -> None:
        self._detect_frame = frame
        self._detect_frame_h = frame.shape[0]
        self._detect_event.set()

    def _sync_recording_state(
        self,
        pending: Optional[tuple[Path, Path, str]],
        pre_frames: List[np.ndarray],
        post_frames: List[np.ndarray],
        fps: float,
        immediate_image_sent: bool,
    ) -> None:
        with self._recording_lock:
            self._recording.pending = pending
            self._recording.pre_frames = pre_frames
            self._recording.post_frames = post_frames
            self._recording.fps = fps
            self._recording.immediate_image_sent = immediate_image_sent

    def _finalize_recording(self, reason: str = "kết thúc") -> None:
        cfg = self._config
        with self._recording_lock:
            rec = _RecordingState(
                pending=self._recording.pending,
                pre_frames=list(self._recording.pre_frames),
                post_frames=list(self._recording.post_frames),
                fps=self._recording.fps,
                immediate_image_sent=self._recording.immediate_image_sent,
            )
            self._recording.pending = None
            self._recording.pre_frames = []
            self._recording.post_frames = []

        if rec.pending is None:
            return

        img_path, vid_path, stamp = rec.pending
        clip_frames = rec.pre_frames + rec.post_frames
        if clip_frames:
            write_mp4(clip_frames, vid_path, rec.fps)

        if cfg.no_email or not (cfg.to_email and cfg.smtp_user and cfg.smtp_password):
            return
        if not img_path.is_file():
            return

        has_video = vid_path.is_file() and vid_path.stat().st_size > 0

        def _send() -> None:
            try:
                if has_video:
                    send_image_video_email(
                        cfg.to_email,
                        f"[Fall] Cảnh báo té ngã - {stamp}",
                        f"Phát hiện té ngã lúc: {stamp}\n(Gửi khi {reason}, clip có thể ngắn hơn bình thường.)",
                        img_path,
                        vid_path,
                        cfg.smtp_user,
                        cfg.smtp_password,
                    )
                elif not rec.immediate_image_sent:
                    send_image_email(
                        cfg.to_email,
                        f"[Fall] Cảnh báo té ngã - {stamp}",
                        f"Phát hiện té ngã lúc: {stamp}\n(Gửi khi {reason}.)",
                        img_path,
                        cfg.smtp_user,
                        cfg.smtp_password,
                    )
            except Exception:
                pass

        t = threading.Thread(target=_send, daemon=True)
        t.start()
        self._send_threads.append(t)
        self._set_status(last_message=f"Đã gửi cảnh báo email ({reason}).")

    def _build_display(self, frame: np.ndarray, cfg: DetectorConfig) -> np.ndarray:
        if cfg.display_width > 0 and frame.shape[1] > cfg.display_width:
            scale = cfg.display_width / float(frame.shape[1])
            return cv2.resize(frame, (cfg.display_width, int(frame.shape[0] * scale)))
        return frame.copy()

    def _draw_overlay(
        self,
        display: np.ndarray,
        frame: np.ndarray,
        cfg: DetectorConfig,
        overlay: _OverlayState,
        fall_hit: bool,
        warning_active: bool,
    ) -> None:
        if overlay.last_boxes:
            box_color = (0, 0, 255) if fall_hit else (0, 200, 80)
            for x1, y1, x2, y2 in overlay.last_boxes:
                if cfg.display_width > 0 and frame.shape[1] > cfg.display_width:
                    sx = cfg.display_width / float(frame.shape[1])
                    dx1, dy1 = int(x1 * sx), int(y1 * sx)
                    dx2, dy2 = int(x2 * sx), int(y2 * sx)
                else:
                    dx1, dy1, dx2, dy2 = x1, y1, x2, y2
                cv2.rectangle(display, (dx1, dy1), (dx2, dy2), box_color, 2)
                if overlay.last_box_source:
                    ly = max(20, dy1 - 10)
                    cv2.putText(
                        display,
                        f"{overlay.last_box_source} {overlay.last_box_score:.2f}",
                        (dx1, ly),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        box_color,
                        2,
                        cv2.LINE_AA,
                    )
        elif fall_hit:
            cv2.rectangle(display, (6, 6), (display.shape[1] - 6, display.shape[0] - 6), (0, 0, 255), 4)

        if warning_active:
            cv2.putText(
                display,
                "FALL DETECTED",
                (40, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.6,
                (0, 0, 255),
                4,
                cv2.LINE_AA,
            )

    def _detect_loop(self) -> None:
        cfg = self._config
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        pose_estimator = None
        if mp is not None:
            pose_estimator = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=0,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

        prev_gray: Optional[np.ndarray] = None
        last_pose_box: Optional[tuple[int, int, int, int]] = None
        cy_hist: Deque[float] = deque(maxlen=6)

        while self._running:
            if not self._detect_event.wait(timeout=0.05):
                continue
            self._detect_event.clear()
            frame = self._detect_frame
            h = self._detect_frame_h
            if frame is None:
                continue

            has_pose, torso_angle, pose_aspect, pose_bbox, pose_conf = detect_fall_pose(frame, pose_estimator)
            boxes: List[tuple[int, int, int, int, float]] = []
            if not has_pose:
                curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                boxes = detect_people_hog_fast(frame, hog, cfg.detect_width, cfg.hog_min_score)
                boxes = filter_boxes_by_motion(boxes, prev_gray, curr_gray, cfg.hog_min_motion)
                prev_gray = curr_gray
            boxes = boxes[: max(1, int(cfg.max_people))]

            overlay = _OverlayState()
            if has_pose and pose_bbox is not None:
                if last_pose_box is None:
                    smooth_box = pose_bbox
                else:
                    a = min(0.95, max(0.0, float(cfg.box_smooth_alpha)))
                    smooth_box = (
                        int(a * last_pose_box[0] + (1.0 - a) * pose_bbox[0]),
                        int(a * last_pose_box[1] + (1.0 - a) * pose_bbox[1]),
                        int(a * last_pose_box[2] + (1.0 - a) * pose_bbox[2]),
                        int(a * last_pose_box[3] + (1.0 - a) * pose_bbox[3]),
                    )
                last_pose_box = smooth_box
                overlay.last_boxes = [smooth_box]
                overlay.last_box_source = "POSE"
                overlay.last_box_score = pose_conf
            else:
                last_pose_box = None
                overlay.last_boxes = [(x1, y1, x2, y2) for (x1, y1, x2, y2, _score) in boxes]
                if boxes:
                    overlay.last_box_source = "HOG"
                    overlay.last_box_score = float(1.0 / (1.0 + np.exp(-boxes[0][4])))
                else:
                    overlay.last_box_source = ""
                    overlay.last_box_score = 0.0

            fall_hit = False
            if has_pose:
                fall_hit = fall_hit_from_pose(
                    torso_angle,
                    pose_aspect,
                    cfg.pose_angle_threshold,
                    cfg.horizontal_only_threshold,
                    cfg.fall_aspect_threshold,
                )
            elif boxes:
                x1, y1, x2, y2, _score = boxes[0]
                bw = max(1, x2 - x1)
                bh = max(1, y2 - y1)
                aspect = bw / float(bh)
                cy = ((y1 + y2) * 0.5) / float(max(1, h))
                cy_hist.append(cy)
                drop = 0.0 if len(cy_hist) < 2 else float(cy_hist[-1] - cy_hist[-2])
                fall_hit = (aspect >= cfg.horizontal_only_threshold) or (
                    aspect >= cfg.fall_aspect_threshold and drop >= cfg.fall_drop_threshold
                )
            else:
                cy_hist.clear()

            overlay.last_fall_hit = fall_hit
            with self._overlay_lock:
                self._overlay = overlay

        if pose_estimator is not None:
            pose_estimator.close()

    def _open_capture(self) -> cv2.VideoCapture:
        if self._is_stream:
            os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
            cap = cv2.VideoCapture(self._source, cv2.CAP_FFMPEG)
        else:
            cap = cv2.VideoCapture(self._source)
        return cap

    def _capture_loop(self) -> None:
        cfg = self._config
        cap = self._open_capture()
        if not cap.isOpened():
            self._set_status(running=False, last_message=f"Không mở được nguồn: {self._source}")
            self._running = False
            return
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        if fps < 1.0:
            fps = 30.0

        if mp is not None:
            self._set_status(detector_mode="MediaPipe + HOG (2 luồng)")
        else:
            self._set_status(detector_mode="HOG (MediaPipe không khả dụng)")

        ring: Deque[np.ndarray] = deque(maxlen=max(3, int(fps * cfg.buffer_sec)))
        source_fps = float(cap.get(cv2.CAP_PROP_FPS) or fps)
        if source_fps < 1.0:
            source_fps = fps
        detect_every = max(1, int(round(source_fps / max(1.0, cfg.target_process_fps))))
        target_frame_interval = (1.0 / source_fps) / max(0.1, cfg.playback_speed)
        last_frame_wall_time = time.time()

        frame_idx = 0
        consecutive = 0
        last_alert = 0.0
        first_hit_frame: Optional[np.ndarray] = None
        last_warning_time = 0.0
        recording = False
        post_target = 0
        post_frames: List[np.ndarray] = []
        pre_frames: List[np.ndarray] = []
        pending: Optional[tuple[Path, Path, str]] = None
        immediate_image_sent = False
        alert_count = 0

        self._set_status(last_message="Đang giám sát…")

        while self._running:
            if self._is_video_file and target_frame_interval > 0:
                now_wall = time.time()
                remain = target_frame_interval - (now_wall - last_frame_wall_time)
                if remain > 0:
                    time.sleep(remain)
                last_frame_wall_time = time.time()

            ok, frame = cap.read()
            if not ok:
                if self._is_stream:
                    self._set_status(last_message="Mất kết nối luồng camera — thử kết nối lại.")
                    time.sleep(2.0)
                    cap.release()
                    cap = self._open_capture()
                    if not cap.isOpened():
                        break
                    continue
                if self._is_video_file:
                    self._set_status(last_message="Đã xử lý xong video.")
                break

            frame_idx += 1
            ring.append(frame.copy())

            if frame_idx % max(1, cfg.detect_every_n_frames) == 0 and frame_idx % detect_every == 0:
                self._request_detect(frame.copy())

            with self._overlay_lock:
                overlay = _OverlayState(
                    last_fall_hit=self._overlay.last_fall_hit,
                    last_boxes=list(self._overlay.last_boxes),
                    last_box_source=self._overlay.last_box_source,
                    last_box_score=self._overlay.last_box_score,
                )
            fall_hit = overlay.last_fall_hit
            now = time.time()
            if fall_hit:
                last_warning_time = now

            display = self._build_display(frame, cfg)
            warning_active = (now - last_warning_time) <= max(0.1, cfg.warning_hold_sec)
            self._draw_overlay(display, frame, cfg, overlay, fall_hit, warning_active)
            self._set_frame_jpeg(display)

            if fall_hit:
                if consecutive == 0:
                    first_hit_frame = frame.copy()
                consecutive += 1
            else:
                consecutive = 0
                first_hit_frame = None

            confirmed = consecutive >= cfg.consecutive_frames
            if confirmed and (now - last_alert >= cfg.cooldown_sec):
                alert_count += 1
                last_alert = now
                ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                out_dir = Path(cfg.out_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                img_path = out_dir / f"fall_{ts}.jpg"
                vid_path = out_dir / f"fall_{ts}.mp4"
                cv2.imwrite(str(img_path), first_hit_frame if first_hit_frame is not None else frame)
                self._set_status(
                    alert_count=alert_count,
                    last_alert_time=stamp,
                    last_message=f"Cảnh báo té ngã lúc {stamp}",
                )
                self._notify_iot_alert(stamp)

                if (
                    cfg.send_immediate_image
                    and (not cfg.no_email)
                    and cfg.to_email
                    and cfg.smtp_user
                    and cfg.smtp_password
                ):
                    immediate_image_sent = True

                    def _send_img() -> None:
                        try:
                            send_image_email(
                                cfg.to_email,
                                f"[Fall] Cảnh báo ngay - {stamp}",
                                f"Phát hiện té ngã lúc: {stamp}",
                                img_path,
                                cfg.smtp_user,
                                cfg.smtp_password,
                            )
                        except Exception:
                            pass

                    t = threading.Thread(target=_send_img, daemon=True)
                    t.start()
                    self._send_threads.append(t)

                pre_frames = list(ring)
                post_target = max(1, int(fps * cfg.after_sec))
                post_frames = [frame.copy()]
                recording = True
                pending = (img_path, vid_path, stamp)
                self._sync_recording_state(pending, pre_frames, post_frames, fps, immediate_image_sent)

            if recording:
                if len(post_frames) < post_target:
                    post_frames.append(frame.copy())
                self._sync_recording_state(pending, pre_frames, post_frames, fps, immediate_image_sent)
                if len(post_frames) >= post_target:
                    recording = False
                    if pending is not None:
                        img_path, vid_path, stamp = pending
                        write_mp4(pre_frames + post_frames, vid_path, fps)
                        if not cfg.no_email and cfg.to_email and cfg.smtp_user and cfg.smtp_password:

                            def _send_video() -> None:
                                try:
                                    send_image_video_email(
                                        cfg.to_email,
                                        f"[Fall] Cảnh báo té ngã - {stamp}",
                                        f"Phát hiện té ngã lúc: {stamp}",
                                        img_path,
                                        vid_path,
                                        cfg.smtp_user,
                                        cfg.smtp_password,
                                    )
                                except Exception:
                                    pass

                            t = threading.Thread(target=_send_video, daemon=True)
                            t.start()
                            self._send_threads.append(t)
                    pending = None
                    post_frames = []
                    self._sync_recording_state(None, [], [], fps, immediate_image_sent)

            self._set_status(
                frame_idx=frame_idx,
                fall_active=bool(fall_hit),
                warning_active=warning_active,
                alert_count=alert_count,
                last_box_score=overlay.last_box_score,
            )

        self._sync_recording_state(pending, pre_frames, post_frames, fps, immediate_image_sent)
        self._finalize_recording(reason="video kết thúc")
        cap.release()
        self._running = False
        self._detect_event.set()
        self._set_status(running=False)

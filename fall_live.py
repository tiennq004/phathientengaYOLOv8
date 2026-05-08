from __future__ import annotations

import argparse
import os
import smtplib
import sys
import threading
import time
from collections import deque
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Deque, List, Optional

import cv2
import numpy as np
try:
    import mediapipe as mp
except Exception:
    mp = None

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass


def _smtp_send(msg: MIMEMultipart, to_email: str, smtp_user: str, smtp_password: str) -> None:
    user = smtp_user.strip().lower()
    pw = "".join((smtp_password or "").split())
    recipients = [x.strip() for x in to_email.split(",") if x.strip()]
    if not recipients:
        raise ValueError("to_email khong hop le.")

    last_err: Optional[BaseException] = None
    for port, use_ssl in ((587, False), (465, True)):
        try:
            if use_ssl:
                with smtplib.SMTP_SSL("smtp.gmail.com", port, timeout=30) as server:
                    server.login(user, pw)
                    server.sendmail(user, recipients, msg.as_string())
            else:
                with smtplib.SMTP("smtp.gmail.com", port, timeout=30) as server:
                    server.starttls()
                    server.login(user, pw)
                    server.sendmail(user, recipients, msg.as_string())
            return
        except Exception as err:
            last_err = err
    assert last_err is not None
    raise last_err


def send_image_email(
    to_email: str,
    subject: str,
    body: str,
    image_path: Path,
    smtp_user: str,
    smtp_password: str,
) -> None:
    msg = MIMEMultipart()
    msg["From"] = smtp_user.strip().lower()
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    with open(image_path, "rb") as f:
        image_part = MIMEImage(f.read())
        image_part.add_header("Content-Disposition", "attachment", filename=image_path.name)
        msg.attach(image_part)
    _smtp_send(msg, to_email, smtp_user, smtp_password)


def send_image_video_email(
    to_email: str,
    subject: str,
    body: str,
    image_path: Path,
    video_path: Path,
    smtp_user: str,
    smtp_password: str,
) -> None:
    msg = MIMEMultipart()
    msg["From"] = smtp_user.strip().lower()
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    with open(image_path, "rb") as f:
        image_part = MIMEImage(f.read())
        image_part.add_header("Content-Disposition", "attachment", filename=image_path.name)
        msg.attach(image_part)
    with open(video_path, "rb") as f:
        video_part = MIMEBase("application", "octet-stream")
        video_part.set_payload(f.read())
        encoders.encode_base64(video_part)
        video_part.add_header("Content-Disposition", "attachment", filename=video_path.name)
        msg.attach(video_part)
    _smtp_send(msg, to_email, smtp_user, smtp_password)


def detect_people_hog(frame: np.ndarray, hog: cv2.HOGDescriptor) -> List[tuple[int, int, int, int]]:
    h, w = frame.shape[:2]
    scale = min(1.0, 720.0 / float(max(1, w)))
    small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale < 1.0 else frame
    # Use more sensitive HOG params so lying/falling person is less likely to be missed.
    rects, _ = hog.detectMultiScale(small, winStride=(4, 4), padding=(8, 8), scale=1.02)
    inv = 1.0 / scale
    boxes = [(int(x * inv), int(y * inv), int((x + ww) * inv), int((y + hh) * inv)) for (x, y, ww, hh) in rects]
    boxes.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    return boxes


def detect_people_hog_fast(
    frame: np.ndarray,
    hog: cv2.HOGDescriptor,
    max_width: int,
    min_score: float,
) -> List[tuple[int, int, int, int, float]]:
    h, w = frame.shape[:2]
    if max_width > 0 and w > max_width:
        scale = max_width / float(w)
        small = cv2.resize(frame, (max_width, int(h * scale)))
        inv = 1.0 / scale
    else:
        small = frame
        inv = 1.0
    rects, weights = hog.detectMultiScale(small, winStride=(6, 6), padding=(8, 8), scale=1.03)
    boxes: List[tuple[int, int, int, int, float]] = []
    for (x, y, ww, hh), score in zip(rects, weights):
        score_f = float(score)
        if score_f < min_score:
            continue
        x1 = int(x * inv)
        y1 = int(y * inv)
        x2 = int((x + ww) * inv)
        y2 = int((y + hh) * inv)
        boxes.append((x1, y1, x2, y2, score_f))
    boxes.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    return boxes


def filter_boxes_by_motion(
    boxes: List[tuple[int, int, int, int, float]],
    prev_gray: Optional[np.ndarray],
    curr_gray: np.ndarray,
    min_motion_ratio: float,
) -> List[tuple[int, int, int, int, float]]:
    if prev_gray is None or min_motion_ratio <= 0:
        return boxes
    diff = cv2.absdiff(curr_gray, prev_gray)
    _, motion_mask = cv2.threshold(diff, 22, 255, cv2.THRESH_BINARY)
    kept: List[tuple[int, int, int, int, float]] = []
    for x1, y1, x2, y2, score in boxes:
        x1 = max(0, min(x1, curr_gray.shape[1] - 1))
        x2 = max(0, min(x2, curr_gray.shape[1]))
        y1 = max(0, min(y1, curr_gray.shape[0] - 1))
        y2 = max(0, min(y2, curr_gray.shape[0]))
        if x2 <= x1 or y2 <= y1:
            continue
        roi = motion_mask[y1:y2, x1:x2]
        if roi.size == 0:
            continue
        motion_ratio = float(np.count_nonzero(roi)) / float(roi.size)
        if motion_ratio >= min_motion_ratio:
            kept.append((x1, y1, x2, y2, score))
    return kept


def write_mp4(frames: List[np.ndarray], out_path: Path, fps: float) -> None:
    if not frames:
        return
    h, w = frames[0].shape[:2]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for fr in frames:
        writer.write(fr)
    writer.release()


def detect_fall_pose(
    frame: np.ndarray, pose_estimator
) -> tuple[bool, float, float, Optional[tuple[int, int, int, int]], float]:
    """
    Return (has_person, torso_angle_deg, bbox_aspect, bbox_xyxy, pose_confidence).
    torso_angle_deg: 90 ~= upright, 0 ~= horizontal.
    bbox_aspect: width / height over visible landmarks.
    """
    if pose_estimator is None or mp is None:
        return False, 90.0, 0.0, None, 0.0
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = pose_estimator.process(rgb)
    if not result.pose_landmarks:
        return False, 90.0, 0.0, None, 0.0

    landmarks = result.pose_landmarks.landmark
    core_ids = [
        mp.solutions.pose.PoseLandmark.NOSE.value,
        mp.solutions.pose.PoseLandmark.LEFT_SHOULDER.value,
        mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER.value,
        mp.solutions.pose.PoseLandmark.LEFT_ELBOW.value,
        mp.solutions.pose.PoseLandmark.RIGHT_ELBOW.value,
        mp.solutions.pose.PoseLandmark.LEFT_WRIST.value,
        mp.solutions.pose.PoseLandmark.RIGHT_WRIST.value,
        mp.solutions.pose.PoseLandmark.LEFT_HIP.value,
        mp.solutions.pose.PoseLandmark.RIGHT_HIP.value,
        mp.solutions.pose.PoseLandmark.LEFT_KNEE.value,
        mp.solutions.pose.PoseLandmark.RIGHT_KNEE.value,
        mp.solutions.pose.PoseLandmark.LEFT_ANKLE.value,
        mp.solutions.pose.PoseLandmark.RIGHT_ANKLE.value,
    ]
    vis_pts = [landmarks[idx] for idx in core_ids if landmarks[idx].visibility >= 0.55]
    if len(vis_pts) < 6:
        return False, 90.0, 0.0, None, 0.0

    xs = [p.x for p in vis_pts]
    ys = [p.y for p in vis_pts]
    bw = max(1e-6, max(xs) - min(xs))
    bh = max(1e-6, max(ys) - min(ys))
    aspect = float(bw / bh)
    h, w = frame.shape[:2]
    pad = 0.02
    x1 = max(0, int((min(xs) - pad) * w))
    y1 = max(0, int((min(ys) - pad) * h))
    x2 = min(w - 1, int((max(xs) + pad) * w))
    y2 = min(h - 1, int((max(ys) + pad) * h))
    if x2 - x1 < 24 or y2 - y1 < 24:
        return False, 90.0, 0.0, None, 0.0
    pose_bbox = (x1, y1, x2, y2)
    pose_conf = float(np.mean([p.visibility for p in vis_pts]))

    l_sh = landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER.value]
    r_sh = landmarks[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER.value]
    l_hip = landmarks[mp.solutions.pose.PoseLandmark.LEFT_HIP.value]
    r_hip = landmarks[mp.solutions.pose.PoseLandmark.RIGHT_HIP.value]
    if min(l_sh.visibility, r_sh.visibility, l_hip.visibility, r_hip.visibility) < 0.5:
        return True, 90.0, aspect, pose_bbox, pose_conf

    sh_x = (l_sh.x + r_sh.x) * 0.5
    sh_y = (l_sh.y + r_sh.y) * 0.5
    hip_x = (l_hip.x + r_hip.x) * 0.5
    hip_y = (l_hip.y + r_hip.y) * 0.5
    dx = abs(hip_x - sh_x)
    dy = abs(hip_y - sh_y)
    torso_angle = float(np.degrees(np.arctan2(dy, dx + 1e-6)))
    return True, torso_angle, aspect, pose_bbox, pose_conf


def main() -> None:
    parser = argparse.ArgumentParser(description="Fall detection + Gmail alert (image and video)")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--video", type=str, default="")
    parser.add_argument("--max-people", type=int, default=3)
    parser.add_argument("--fall-aspect-threshold", type=float, default=0.95)
    parser.add_argument("--fall-drop-threshold", type=float, default=0.0025)
    parser.add_argument("--consecutive-frames", type=int, default=1)
    parser.add_argument("--cooldown-sec", type=float, default=45.0)
    parser.add_argument("--buffer-sec", type=float, default=3.0)
    parser.add_argument("--after-sec", type=float, default=2.5)
    parser.add_argument("--out-dir", type=str, default="outputs/falls")
    parser.add_argument("--to-email", type=str, default=os.environ.get("ALERT_TO_EMAIL", ""))
    parser.add_argument("--smtp-user", type=str, default=os.environ.get("SMTP_USER", ""))
    parser.add_argument("--smtp-password", type=str, default=os.environ.get("SMTP_APP_PASSWORD", ""))
    parser.add_argument("--no-email", action="store_true")
    parser.add_argument("--test-email", action="store_true")
    parser.add_argument("--detect-every-n-frames", type=int, default=1)
    parser.add_argument("--display-width", type=int, default=960)
    parser.add_argument("--detect-width", type=int, default=768)
    parser.add_argument(
        "--hog-min-score",
        type=float,
        default=0.6,
        help="Nguong diem HOG de loc box nhan nham (tang len de giam false positive).",
    )
    parser.add_argument(
        "--hog-min-motion",
        type=float,
        default=0.03,
        help="Ty le pixel chuyen dong toi thieu trong box HOG de loai bo vat the dung yen.",
    )
    parser.add_argument("--target-process-fps", type=float, default=10.0)
    parser.add_argument(
        "--box-smooth-alpha",
        type=float,
        default=0.65,
        help="Do muot cua khung nguoi (0..1), cao hon thi bam theo khung cu nhieu hon.",
    )
    parser.add_argument("--horizontal-only-threshold", type=float, default=1.15)
    parser.add_argument("--pose-angle-threshold", type=float, default=45.0)
    parser.add_argument("--playback-speed", type=float, default=1.0)
    parser.add_argument(
        "--warning-hold-sec",
        type=float,
        default=2.0,
        help="Giu canh bao do tren man hinh them N giay sau khi co tin hieu nga.",
    )
    parser.add_argument(
        "--send-immediate-image",
        action="store_true",
        help="Gui email anh ngay khi xac nhan te nga, truoc khi clip duoc tao xong.",
    )
    args = parser.parse_args()

    args.to_email = (args.to_email or "").strip()
    args.smtp_user = (args.smtp_user or "").strip()
    args.smtp_password = (args.smtp_password or "").strip()

    if args.test_email:
        if args.no_email or not args.to_email or not args.smtp_user or not args.smtp_password:
            print("Khong the test email: thieu to-email/smtp-user/smtp-password hoac dang --no-email.")
            sys.exit(1)
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        test_img = out_dir / "test_email_image.jpg"
        cv2.imwrite(str(test_img), np.zeros((200, 400, 3), dtype=np.uint8))
        try:
            send_image_email(
                args.to_email,
                "[Fall Detector] Test email",
                "Email test thanh cong.",
                test_img,
                args.smtp_user,
                args.smtp_password,
            )
            print(f"Da gui email test toi {args.to_email}.")
            sys.exit(0)
        except Exception as err:
            print(f"Loi test email: {err}")
            sys.exit(1)

    if args.no_email:
        print("Email OFF (--no-email).")
    elif not args.to_email or not args.smtp_user or not args.smtp_password:
        print("Email OFF (thieu to-email/smtp-user/smtp-password).")
    else:
        print(f"Email ON -> {args.to_email} (from {args.smtp_user}).")
    print(
        f"Config: detect_every={args.detect_every_n_frames}, detect_width={args.detect_width}, "
        f"target_fps={args.target_process_fps}, aspect={args.fall_aspect_threshold}, "
        f"drop={args.fall_drop_threshold}, horizontal_only={args.horizontal_only_threshold}"
    )

    src = args.video.strip() if args.video.strip() else args.camera
    is_video_file = bool(args.video.strip())
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print(f"Khong mo duoc nguon video/camera: {src}")
        sys.exit(1)

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    if fps < 1.0:
        fps = 30.0

    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    pose_estimator = None
    if mp is not None:
        pose_estimator = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        print("Pose detector: ON (MediaPipe)")
    else:
        print("Pose detector: OFF (MediaPipe chua san sang), fallback HOG.")
    ring: Deque[np.ndarray] = deque(maxlen=max(3, int(fps * args.buffer_sec)))
    cy_hist: Deque[float] = deque(maxlen=6)
    frame_idx = 0
    last_fall_hit = False
    send_threads: List[threading.Thread] = []
    source_fps = float(cap.get(cv2.CAP_PROP_FPS) or fps)
    if source_fps < 1.0:
        source_fps = fps
    process_every = max(1, int(round(source_fps / max(1.0, args.target_process_fps))))
    target_frame_interval = (1.0 / source_fps) / max(0.1, args.playback_speed)
    last_frame_wall_time = time.time()
    prev_gray: Optional[np.ndarray] = None
    last_pose_box: Optional[tuple[int, int, int, int]] = None

    consecutive = 0
    last_alert = 0.0
    first_hit_frame: Optional[np.ndarray] = None
    last_boxes: List[tuple[int, int, int, int]] = []
    last_box_source = ""
    last_box_score = 0.0
    last_warning_time = 0.0
    recording = False
    post_target = 0
    post_frames: List[np.ndarray] = []
    pre_frames: List[np.ndarray] = []
    pending: Optional[tuple[Path, Path, str]] = None
    alert_count = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame_idx += 1
        ring.append(frame.copy())
        curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if args.display_width > 0 and frame.shape[1] > args.display_width:
            disp_scale = args.display_width / float(frame.shape[1])
            display = cv2.resize(frame, (args.display_width, int(frame.shape[0] * disp_scale)))
        else:
            display = frame.copy()
        h, _ = frame.shape[:2]
        do_detect = (frame_idx % max(1, args.detect_every_n_frames) == 0) and (frame_idx % process_every == 0)
        if do_detect:
            has_pose, torso_angle, pose_aspect, pose_bbox, pose_conf = detect_fall_pose(frame, pose_estimator)
            boxes = detect_people_hog_fast(frame, hog, args.detect_width, args.hog_min_score)
            boxes = filter_boxes_by_motion(boxes, prev_gray, curr_gray, args.hog_min_motion)
            boxes = boxes[: max(1, int(args.max_people))]
            # Prefer pose bbox for stable person framing; fallback to HOG when pose is unavailable.
            if has_pose and pose_bbox is not None:
                if last_pose_box is None:
                    smooth_box = pose_bbox
                else:
                    a = min(0.95, max(0.0, float(args.box_smooth_alpha)))
                    smooth_box = (
                        int(a * last_pose_box[0] + (1.0 - a) * pose_bbox[0]),
                        int(a * last_pose_box[1] + (1.0 - a) * pose_bbox[1]),
                        int(a * last_pose_box[2] + (1.0 - a) * pose_bbox[2]),
                        int(a * last_pose_box[3] + (1.0 - a) * pose_bbox[3]),
                    )
                last_pose_box = smooth_box
                last_boxes = [smooth_box]
                last_box_source = "POSE"
                last_box_score = pose_conf
            else:
                last_pose_box = None
                last_boxes = [(x1, y1, x2, y2) for (x1, y1, x2, y2, _score) in boxes]
                if boxes:
                    last_box_source = "HOG"
                    # Compress raw HOG score to 0..1 for easier reading.
                    last_box_score = float(1.0 / (1.0 + np.exp(-boxes[0][4])))
                else:
                    last_box_source = ""
                    last_box_score = 0.0
            fall_hit = False
            if has_pose:
                pose_horizontal = torso_angle <= args.pose_angle_threshold
                pose_wide_and_tilted = (pose_aspect >= args.horizontal_only_threshold) and (torso_angle <= 70.0)
                fall_hit = pose_horizontal or pose_wide_and_tilted
                if fall_hit:
                    print(f"Fall signal (pose): angle={torso_angle:.1f}, aspect={pose_aspect:.2f}")
            elif boxes:
                x1, y1, x2, y2, _score = boxes[0]
                bw = max(1, x2 - x1)
                bh = max(1, y2 - y1)
                aspect = bw / float(bh)
                cy = ((y1 + y2) * 0.5) / float(max(1, h))
                cy_hist.append(cy)
                drop = 0.0 if len(cy_hist) < 2 else float(cy_hist[-1] - cy_hist[-2])
                # Trigger if horizontal posture is very clear, or posture+drop indicates a fall.
                fall_hit = (aspect >= args.horizontal_only_threshold) or (
                    aspect >= args.fall_aspect_threshold and drop >= args.fall_drop_threshold
                )
                if fall_hit:
                    print(f"Fall signal (hog): aspect={aspect:.2f}, drop={drop:.4f}")
            else:
                cy_hist.clear()
                fall_hit = False
            last_fall_hit = fall_hit
        else:
            fall_hit = last_fall_hit

        now = time.time()
        if fall_hit:
            last_warning_time = now

        if last_boxes:
            box_color = (0, 0, 255) if fall_hit else (0, 255, 0)
            for x1, y1, x2, y2 in last_boxes:
                if args.display_width > 0 and frame.shape[1] > args.display_width:
                    sx = args.display_width / float(frame.shape[1])
                    sy = sx
                    dx1, dy1 = int(x1 * sx), int(y1 * sy)
                    dx2, dy2 = int(x2 * sx), int(y2 * sy)
                else:
                    dx1, dy1, dx2, dy2 = x1, y1, x2, y2
                cv2.rectangle(display, (dx1, dy1), (dx2, dy2), box_color, 2)
                if last_box_source:
                    label = f"{last_box_source} {last_box_score:.2f}"
                    ly = max(20, dy1 - 10)
                    cv2.putText(display, label, (dx1, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2, cv2.LINE_AA)
        elif fall_hit:
            # If fall is inferred by pose but no HOG box, show a strong full-frame red border.
            cv2.rectangle(display, (6, 6), (display.shape[1] - 6, display.shape[0] - 6), (0, 0, 255), 4)

        if fall_hit:
            if consecutive == 0:
                first_hit_frame = frame.copy()
            consecutive += 1
        else:
            consecutive = 0
            first_hit_frame = None

        confirmed = consecutive >= args.consecutive_frames
        if confirmed and (now - last_alert >= args.cooldown_sec):
            alert_count += 1
            last_alert = now
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            out_dir = Path(args.out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            img_path = out_dir / f"fall_{ts}.jpg"
            vid_path = out_dir / f"fall_{ts}.mp4"
            cv2.imwrite(str(img_path), first_hit_frame if first_hit_frame is not None else frame)
            print(f"ALERT: {stamp}")

            if (
                args.send_immediate_image
                and (not args.no_email)
                and args.to_email
                and args.smtp_user
                and args.smtp_password
            ):

                def _send_img() -> None:
                    try:
                        send_image_email(
                            args.to_email,
                            f"[Fall] Canh bao ngay - {stamp}",
                            f"Phat hien te nga luc: {stamp}",
                            img_path,
                            args.smtp_user,
                            args.smtp_password,
                        )
                        print("Da gui mail canh bao anh.")
                    except Exception as err:
                        print(f"Loi gui mail anh: {err}")

                t = threading.Thread(target=_send_img)
                t.start()
                send_threads.append(t)
            elif args.send_immediate_image:
                print("Bo qua gui email anh (thieu cau hinh hoac --no-email).")

            pre_frames = list(ring)
            post_target = max(1, int(fps * args.after_sec))
            post_frames = [frame.copy()]
            recording = True
            pending = (img_path, vid_path, stamp)

        if recording:
            if len(post_frames) < post_target:
                post_frames.append(frame.copy())
            if len(post_frames) >= post_target:
                recording = False
                if pending is not None:
                    img_path, vid_path, stamp = pending
                    write_mp4(pre_frames + post_frames, vid_path, fps)
                    print(f"Da luu clip: {vid_path}")

                    if not args.no_email and args.to_email and args.smtp_user and args.smtp_password:

                        def _send_video() -> None:
                            try:
                                send_image_video_email(
                                    args.to_email,
                                    f"[Fall] Canh bao te nga - {stamp}",
                                    f"Phat hien te nga luc: {stamp}\n"
                                    "Tai lieu:",
                                    img_path,
                                    vid_path,
                                    args.smtp_user,
                                    args.smtp_password,
                                )
                                print("Da gui mail anh + video.")
                            except Exception as err:
                                print(f"Loi gui mail anh + video: {err}")

                        t = threading.Thread(target=_send_video)
                        t.start()
                        send_threads.append(t)
                    else:
                        print("Bo qua gui email clip (thieu cau hinh hoac --no-email).")
                pending = None
                post_frames = []

        warning_active = (now - last_warning_time) <= max(0.1, args.warning_hold_sec)
        if warning_active:
            cv2.putText(display, "FALL DETECTED", (40, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 255), 4, cv2.LINE_AA)

        cv2.imshow("Fall detection", display)
        if is_video_file and target_frame_interval > 0:
            now_wall = time.time()
            elapsed = now_wall - last_frame_wall_time
            remain = target_frame_interval - elapsed
            if remain > 0:
                time.sleep(remain)
            last_frame_wall_time = time.time()
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        prev_gray = curr_gray

    cap.release()
    cv2.destroyAllWindows()
    if pose_estimator is not None:
        pose_estimator.close()
    # Important for video files: wait mail threads to finish before process exits.
    for t in send_threads:
        t.join(timeout=20.0)
    if is_video_file and alert_count == 0:
        print(
            "Khong co canh bao te nga. Thu video ro hon hoac giam nguong: "
            "--fall-aspect-threshold 0.85 --horizontal-only-threshold 1.0 --fall-drop-threshold 0.0015"
        )


if __name__ == "__main__":
    main()

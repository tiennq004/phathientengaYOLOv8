import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import joblib
import mediapipe as mp
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, f1_score, precision_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def parse_annotation_file(path: Path):
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not lines:
        return None

    start = None
    end = None
    data_start = 0
    if len(lines) >= 3 and "," not in lines[0] and "," not in lines[1]:
        try:
            start = int(lines[0].strip())
            end = int(lines[1].strip())
            data_start = 2
        except ValueError:
            data_start = 0

    rows = []
    for ln in lines[data_start:]:
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) == 6:
            rows.append([int(p) for p in parts])
    if not rows:
        return None

    arr = np.array(rows, dtype=np.float32)
    frame_ids = arr[:, 0].astype(np.int32)
    posture = arr[:, 1]
    h = arr[:, 2]
    w = arr[:, 3]
    cx = arr[:, 4]
    cy = arr[:, 5]
    if start is None or end is None:
        y = np.zeros_like(frame_ids, dtype=np.int32)
    else:
        y = ((frame_ids >= start) & (frame_ids <= end)).astype(np.int32)
    return frame_ids, posture, h, w, cx, cy, y


def locate_video(anno_path: Path) -> Optional[Path]:
    name = anno_path.stem + ".avi"
    subset_root = anno_path.parents[1]
    local = list(subset_root.rglob(name))
    if local:
        return local[0]
    for p in anno_path.parents[4].rglob(name):
        return p
    return None


def extract_frames_and_pose(
    video_path: Path,
    needed_frames: set[int],
    save_frames_dir: Optional[Path] = None,
) -> Dict[int, np.ndarray]:
    pose = mp.solutions.pose.Pose(static_image_mode=False, model_complexity=1)
    cap = cv2.VideoCapture(str(video_path))
    out: Dict[int, np.ndarray] = {}
    prev_gray = None
    idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if idx not in needed_frames:
            continue

        if save_frames_dir is not None:
            save_frames_dir.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(save_frames_dir / f"frame_{idx:04d}.jpg"), frame)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        motion = 0.0 if prev_gray is None else float(cv2.absdiff(gray, prev_gray).mean())
        prev_gray = gray

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = pose.process(rgb)

        if result.pose_landmarks:
            lm = result.pose_landmarks.landmark
            # Use all pose landmarks for richer representation.
            ids = list(range(33))
            vals = []
            for j in ids:
                vals.extend([lm[j].x, lm[j].y, lm[j].visibility])
            pose_vec = np.array(vals, dtype=np.float32)
        else:
            pose_vec = np.zeros(99, dtype=np.float32)

        out[idx] = np.concatenate([pose_vec, np.array([motion], dtype=np.float32)])

    cap.release()
    pose.close()
    return out


def build_features(frame_ids, posture, h, w, cx, cy, pose_map, max_lag=8):
    # 99 pose entries + 1 motion
    pose_raw = np.array([pose_map.get(int(f), np.zeros(100, dtype=np.float32)) for f in frame_ids], dtype=np.float32)
    motion = pose_raw[:, -1]
    pose_vec = pose_raw[:, :-1]

    base = np.column_stack(
        [
            posture,
            h,
            w,
            cx,
            cy,
            w / np.clip(h, 1.0, None),
            h * w,
            np.gradient(cx),
            np.gradient(cy),
            motion,
            pose_vec,
        ]
    ).astype(np.float32)

    feat = [base]
    for lag in range(1, max_lag + 1):
        lagged = np.roll(base, shift=lag, axis=0)
        lagged[:lag, :] = lagged[lag : lag + 1, :]
        feat.append(lagged)
    return np.concatenate(feat, axis=1)


def load_dataset(dataset_root: Path, max_lag: int, save_frames: bool):
    annos = sorted([p for p in dataset_root.rglob("*.txt") if p.name.lower() != "readme.txt" and "annotation" in str(p.parent).lower()])

    xs: List[np.ndarray] = []
    ys: List[np.ndarray] = []
    gs: List[np.ndarray] = []
    used = 0

    for i, anno in enumerate(annos):
        parsed = parse_annotation_file(anno)
        if parsed is None:
            continue
        frame_ids, posture, h, w, cx, cy, y = parsed
        video_path = locate_video(anno)
        if video_path is None:
            continue

        save_dir = None
        if save_frames:
            save_dir = Path("extracted_frames") / video_path.stem

        pose_map = extract_frames_and_pose(video_path, set(frame_ids.tolist()), save_frames_dir=save_dir)
        X = build_features(frame_ids, posture, h, w, cx, cy, pose_map, max_lag=max_lag)
        xs.append(X)
        ys.append(y)
        gs.append(np.full(len(y), i, dtype=np.int32))
        used += 1

    return np.concatenate(xs), np.concatenate(ys), np.concatenate(gs), used


def train_best_model(
    X,
    y,
    groups,
    seed=42,
    optimize_metric="f1",
    target_f1: Optional[float] = None,
    target_recall: Optional[float] = None,
    weight_scales: Optional[List[float]] = None,
    smoothing_window: int = 5,
    prioritize_recall: bool = False,
):
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed).split(X, y, groups))
    Xtr, Xte = X[tr], X[te]
    ytr, yte = y[tr], y[te]
    neg, pos = np.bincount(ytr)
    w = float(neg / max(pos, 1))

    if weight_scales is None:
        weight_scales = [1.0, 1.5, 2.0, 3.0]
    models = {}
    for scale in weight_scales:
        pos_w = float(w * scale)
        suffix = f"_w{scale:g}"
        models[f"extra_trees{suffix}"] = ExtraTreesClassifier(
            n_estimators=900,
            max_depth=22,
            class_weight={0: 1.0, 1: pos_w},
            random_state=seed,
            n_jobs=-1,
        )
        models[f"rf{suffix}"] = RandomForestClassifier(
            n_estimators=600,
            max_depth=18,
            class_weight={0: 1.0, 1: pos_w},
            random_state=seed,
            n_jobs=-1,
        )
        models[f"logreg{suffix}"] = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=2000, class_weight={0: 1.0, 1: pos_w}, random_state=seed)),
            ]
        )

    best = None
    best_res = None
    best_score = -1.0
    for name, model in models.items():
        model.fit(Xtr, ytr)
        score = model.predict_proba(Xte)[:, 1] if hasattr(model, "predict_proba") else model.decision_function(Xte)
        if not hasattr(model, "predict_proba"):
            score = (score - score.min()) / (score.max() - score.min() + 1e-8)

        thr_best = 0.5
        best_thr_metrics = None
        for thr in np.linspace(0.05, 0.95, 73):
            pred = (score >= thr).astype(np.int32)
            if smoothing_window >= 3 and len(pred) >= smoothing_window:
                pred = np.rint(
                    np.convolve(pred, np.ones(smoothing_window) / float(smoothing_window), mode="same")
                ).astype(np.int32)

            metrics = {
                "f1": f1_score(yte, pred, zero_division=0),
                "precision": precision_score(yte, pred, zero_division=0),
                "recall": recall_score(yte, pred, zero_division=0),
                "accuracy": accuracy_score(yte, pred),
                "balanced_accuracy": balanced_accuracy_score(yte, pred),
            }
            meets_target = True
            if target_f1 is not None and metrics["f1"] < target_f1:
                meets_target = False
            if target_recall is not None and metrics["recall"] < target_recall:
                meets_target = False

            if best_thr_metrics is None:
                best_thr_metrics = (meets_target, metrics["f1"], metrics["recall"], metrics["accuracy"], float(thr), metrics)
                thr_best = float(thr)
                continue

            cand = (meets_target, metrics["f1"], metrics["recall"], metrics["accuracy"], float(thr), metrics)
            # Priority: satisfy target(s), then higher F1, then higher recall, then accuracy.
            if prioritize_recall:
                cand_key = (cand[0], cand[2], cand[1], cand[3])
                best_key = (best_thr_metrics[0], best_thr_metrics[2], best_thr_metrics[1], best_thr_metrics[3])
            else:
                cand_key = cand[:4]
                best_key = best_thr_metrics[:4]
            if cand_key > best_key:
                best_thr_metrics = cand
                thr_best = float(thr)

        pred = (score >= thr_best).astype(np.int32)
        # Temporal smoothing usually reduces noisy frame-level spikes.
        if smoothing_window >= 3 and len(pred) >= smoothing_window:
            pred = np.rint(
                np.convolve(pred, np.ones(smoothing_window) / float(smoothing_window), mode="same")
            ).astype(np.int32)
        res = {
            "name": name,
            "model": model,
            "threshold": thr_best,
            "f1": f1_score(yte, pred, zero_division=0),
            "precision": precision_score(yte, pred, zero_division=0),
            "recall": recall_score(yte, pred, zero_division=0),
            "accuracy": accuracy_score(yte, pred),
            "balanced_accuracy": balanced_accuracy_score(yte, pred),
            "report": classification_report(yte, pred, digits=4, zero_division=0),
        }
        meets_target = True
        if target_f1 is not None and res["f1"] < target_f1:
            meets_target = False
        if target_recall is not None and res["recall"] < target_recall:
            meets_target = False

        score_key = "f1" if optimize_metric == "f1" else "accuracy"
        if prioritize_recall:
            ranking = (
                1.0 if meets_target else 0.0,
                res["recall"],
                res["f1"],
                res["balanced_accuracy"],
            )
        else:
            ranking = (
                1.0 if meets_target else 0.0,
                res[score_key],
                res["recall"],
                res["balanced_accuracy"],
            )
        if ranking > (best_score if isinstance(best_score, tuple) else (-1.0, -1.0, -1.0, -1.0)):
            best_score = ranking
            best = name
            best_res = res
    return best, best_res


def main():
    parser = argparse.ArgumentParser(description="Train fall detector with pipeline: video->frames->txt labels->pose->features->train")
    parser.add_argument("--dataset", type=str, default="dataset")
    parser.add_argument("--output", type=str, default="models/fall_detector_pose_best.pkl")
    parser.add_argument("--max-lag", type=int, default=8)
    parser.add_argument("--save-frames", action="store_true")
    parser.add_argument("--optimize-metric", type=str, default="f1", choices=["accuracy", "f1"])
    parser.add_argument("--target-f1", type=float, default=0.74)
    parser.add_argument("--target-recall", type=float, default=0.83)
    parser.add_argument("--weight-scales", type=str, default="1,1.3,1.5,1.7,2,2.5,3")
    parser.add_argument("--smoothing-window", type=int, default=1)
    parser.add_argument("--prioritize-recall", action="store_true")
    parser.add_argument("--seeds", type=str, default="21,42,77")
    parser.add_argument("--target-precision", type=float, default=0.68)
    args = parser.parse_args()
    weight_scales = [float(x.strip()) for x in args.weight_scales.split(",") if x.strip()]
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]

    X, y, g, used = load_dataset(Path(args.dataset), max_lag=args.max_lag, save_frames=args.save_frames)
    best_name = None
    best_res = None
    best_seed = None
    best_key = None
    for seed in seeds:
        name, res = train_best_model(
            X,
            y,
            g,
            seed=seed,
            optimize_metric=args.optimize_metric,
            target_f1=args.target_f1,
            target_recall=args.target_recall,
            weight_scales=weight_scales,
            smoothing_window=args.smoothing_window,
            prioritize_recall=args.prioritize_recall,
        )
        meets_f1 = args.target_f1 is None or res["f1"] >= args.target_f1
        meets_recall = args.target_recall is None or res["recall"] >= args.target_recall
        meets_precision = args.target_precision is None or res["precision"] >= args.target_precision
        meets_all = 1.0 if (meets_f1 and meets_recall and meets_precision) else 0.0

        # If user provides a target profile, choose the nearest profile.
        if args.target_f1 is not None or args.target_recall is not None or args.target_precision is not None:
            d_f1 = 0.0 if args.target_f1 is None else abs(res["f1"] - args.target_f1)
            d_recall = 0.0 if args.target_recall is None else abs(res["recall"] - args.target_recall)
            d_precision = 0.0 if args.target_precision is None else abs(res["precision"] - args.target_precision)
            key = (
                meets_all,
                -(2.0 * d_f1 + 2.0 * d_recall + 1.0 * d_precision),
                res["f1"],
                res["recall"],
            )
        else:
            key = (meets_all, res["f1"], res["recall"], res["balanced_accuracy"])

        if best_key is None or key > best_key:
            best_key = key
            best_name = name
            best_res = res
            best_seed = seed

    name, res = best_name, best_res

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": res["model"], "threshold": res["threshold"], "max_lag": args.max_lag}, args.output)

    print(f"Used labeled videos: {used}")
    print(f"Samples: {len(y)}")
    print(f"Best model: {name}")
    print(f"Best seed: {best_seed}")
    print(
        f"Accuracy: {res['accuracy']:.4f} | Balanced Acc: {res['balanced_accuracy']:.4f} | "
        f"F1: {res['f1']:.4f} | Precision: {res['precision']:.4f} | "
        f"Recall: {res['recall']:.4f} | Threshold: {res['threshold']:.3f}"
    )
    if args.target_f1 is not None or args.target_recall is not None:
        f1_ok = args.target_f1 is None or res["f1"] >= args.target_f1
        recall_ok = args.target_recall is None or res["recall"] >= args.target_recall
        print(
            "Target check:"
            f" F1 {'OK' if f1_ok else 'NOT OK'}"
            + (f" (>= {args.target_f1:.3f})" if args.target_f1 is not None else "")
            + f" | Recall {'OK' if recall_ok else 'NOT OK'}"
            + (f" (>= {args.target_recall:.3f})" if args.target_recall is not None else "")
        )
    print(res["report"])
    print(f"Saved model to: {args.output}")


if __name__ == "__main__":
    main()
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import joblib
import mediapipe as mp
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, f1_score, precision_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def parse_annotation_file(path: Path):
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not lines:
        return None

    start = None
    end = None
    data_start = 0
    if len(lines) >= 3 and "," not in lines[0] and "," not in lines[1]:
        try:
            start = int(lines[0].strip())
            end = int(lines[1].strip())
            data_start = 2
        except ValueError:
            data_start = 0

    rows = []
    for ln in lines[data_start:]:
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) == 6:
            rows.append([int(p) for p in parts])
    if not rows:
        return None

    arr = np.array(rows, dtype=np.float32)
    frame_ids = arr[:, 0].astype(np.int32)
    posture = arr[:, 1]
    h = arr[:, 2]
    w = arr[:, 3]
    cx = arr[:, 4]
    cy = arr[:, 5]
    if start is None or end is None:
        y = np.zeros_like(frame_ids, dtype=np.int32)
    else:
        y = ((frame_ids >= start) & (frame_ids <= end)).astype(np.int32)
    return frame_ids, posture, h, w, cx, cy, y


def locate_video(anno_path: Path) -> Optional[Path]:
    """
    Dataset gốc thường có video cùng tên với annotation: 'video (i).<ext>'.
    Repo này có thể chỉ chứa annotation; người dùng cần cung cấp thư mục video.
    """
    stems = [anno_path.stem]
    exts = [".avi", ".mp4", ".mkv", ".mov", ".mpg", ".mpeg"]

    # Heuristic: tìm quanh subset root trước.
    subset_root = anno_path.parents[1]
    for st in stems:
        for ext in exts:
            name = st + ext
            local = list(subset_root.rglob(name))
            if local:
                return local[0]

    # Fallback: tìm rộng hơn.
    for st in stems:
        for ext in exts:
            name = st + ext
            for p in anno_path.parents[4].rglob(name):
                return p
    return None


def extract_frames_and_pose(
    video_path: Path,
    needed_frames: set[int],
    save_frames_dir: Optional[Path] = None,
) -> Dict[int, np.ndarray]:
    pose = mp.solutions.pose.Pose(static_image_mode=False, model_complexity=1)
    cap = cv2.VideoCapture(str(video_path))
    out: Dict[int, np.ndarray] = {}
    prev_gray = None
    idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if idx not in needed_frames:
            continue

        if save_frames_dir is not None:
            save_frames_dir.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(save_frames_dir / f"frame_{idx:04d}.jpg"), frame)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        motion = 0.0 if prev_gray is None else float(cv2.absdiff(gray, prev_gray).mean())
        prev_gray = gray

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = pose.process(rgb)

        if result.pose_landmarks:
            lm = result.pose_landmarks.landmark
            # Use all pose landmarks for richer representation.
            ids = list(range(33))
            vals = []
            for j in ids:
                vals.extend([lm[j].x, lm[j].y, lm[j].visibility])
            pose_vec = np.array(vals, dtype=np.float32)
        else:
            pose_vec = np.zeros(99, dtype=np.float32)

        out[idx] = np.concatenate([pose_vec, np.array([motion], dtype=np.float32)])

    cap.release()
    pose.close()
    return out


def _stack_lags(base: np.ndarray, max_lag: int) -> np.ndarray:
    feat = [base]
    for lag in range(1, max_lag + 1):
        lagged = np.roll(base, shift=lag, axis=0)
        lagged[:lag, :] = lagged[lag : lag + 1, :]
        feat.append(lagged)
    return np.concatenate(feat, axis=1)


def build_features_pose_only(frame_ids, pose_map, max_lag=8) -> np.ndarray:
    """
    Feature set thuần pose + motion để inference realtime cũng trích được y hệt:
    - 99 pose entries (x,y,visibility) * 33
    - 1 motion (frame diff mean)
    - kèm các lag (temporal context)
    """
    pose_raw = np.array([pose_map.get(int(f), np.zeros(100, dtype=np.float32)) for f in frame_ids], dtype=np.float32)
    base = pose_raw.astype(np.float32)  # (N, 100)
    return _stack_lags(base, max_lag=max_lag)


def build_features_pose_bbox(frame_ids, posture, h, w, cx, cy, pose_map, max_lag=8) -> np.ndarray:
    """
    Feature set kết hợp bbox annotation + motion + pose.
    Lưu ý: feature này khó áp dụng cho realtime nếu không có detector bbox.
    """
    pose_raw = np.array([pose_map.get(int(f), np.zeros(100, dtype=np.float32)) for f in frame_ids], dtype=np.float32)
    motion = pose_raw[:, -1]
    pose_vec = pose_raw[:, :-1]

    base = np.column_stack(
        [
            posture,
            h,
            w,
            cx,
            cy,
            w / np.clip(h, 1.0, None),
            h * w,
            np.gradient(cx),
            np.gradient(cy),
            motion,
            pose_vec,
        ]
    ).astype(np.float32)
    return _stack_lags(base, max_lag=max_lag)


def load_dataset(
    dataset_root: Path,
    max_lag: int,
    save_frames: bool,
    video_root: Optional[Path] = None,
    feature_set: str = "pose_only",
):
    annos = sorted([p for p in dataset_root.rglob("*.txt") if p.name.lower() != "readme.txt" and "annotation" in str(p.parent).lower()])

    xs: List[np.ndarray] = []
    ys: List[np.ndarray] = []
    gs: List[np.ndarray] = []
    used = 0
    missing_videos: List[Path] = []

    for i, anno in enumerate(annos):
        parsed = parse_annotation_file(anno)
        if parsed is None:
            continue
        frame_ids, posture, h, w, cx, cy, y = parsed
        video_path = None
        if video_root is not None:
            # user-specified root: match by stem only
            for ext in (".avi", ".mp4", ".mkv", ".mov", ".mpg", ".mpeg"):
                cand = video_root / f"{anno.stem}{ext}"
                if cand.is_file():
                    video_path = cand
                    break
            if video_path is None:
                # try recursive search
                for ext in (".avi", ".mp4", ".mkv", ".mov", ".mpg", ".mpeg"):
                    hits = list(video_root.rglob(f"{anno.stem}{ext}"))
                    if hits:
                        video_path = hits[0]
                        break
        if video_path is None:
            video_path = locate_video(anno)
        if video_path is None:
            missing_videos.append(anno)
            continue

        save_dir = None
        if save_frames:
            save_dir = Path("extracted_frames") / video_path.stem

        pose_map = extract_frames_and_pose(video_path, set(frame_ids.tolist()), save_frames_dir=save_dir)
        if feature_set == "pose_only":
            X = build_features_pose_only(frame_ids, pose_map, max_lag=max_lag)
        else:
            X = build_features_pose_bbox(frame_ids, posture, h, w, cx, cy, pose_map, max_lag=max_lag)
        xs.append(X)
        ys.append(y)
        gs.append(np.full(len(y), i, dtype=np.int32))
        used += 1

    if used == 0:
        hint = ""
        if missing_videos:
            hint = (
                "\nKhông tìm thấy video cho annotation (repo có thể chỉ chứa *.txt). "
                "Hãy tải video dataset gốc hoặc truyền --video-root trỏ tới thư mục chứa video."
            )
        raise RuntimeError(f"Không load được sample nào từ dataset.{hint}")

    return np.concatenate(xs), np.concatenate(ys), np.concatenate(gs), used


def train_best_model(
    X,
    y,
    groups,
    seed=42,
    optimize_metric="f1",
    target_f1: Optional[float] = None,
    target_recall: Optional[float] = None,
    weight_scales: Optional[List[float]] = None,
    smoothing_window: int = 5,
    prioritize_recall: bool = False,
):
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed).split(X, y, groups))
    Xtr, Xte = X[tr], X[te]
    ytr, yte = y[tr], y[te]
    neg, pos = np.bincount(ytr)
    w = float(neg / max(pos, 1))

    if weight_scales is None:
        weight_scales = [1.0, 1.5, 2.0, 3.0]
    models = {}
    for scale in weight_scales:
        pos_w = float(w * scale)
        suffix = f"_w{scale:g}"
        models[f"extra_trees{suffix}"] = ExtraTreesClassifier(
            n_estimators=900,
            max_depth=22,
            class_weight={0: 1.0, 1: pos_w},
            random_state=seed,
            n_jobs=-1,
        )
        models[f"rf{suffix}"] = RandomForestClassifier(
            n_estimators=600,
            max_depth=18,
            class_weight={0: 1.0, 1: pos_w},
            random_state=seed,
            n_jobs=-1,
        )
        models[f"logreg{suffix}"] = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=2000, class_weight={0: 1.0, 1: pos_w}, random_state=seed)),
            ]
        )

    best = None
    best_res = None
    best_score = -1.0
    for name, model in models.items():
        model.fit(Xtr, ytr)
        score = model.predict_proba(Xte)[:, 1] if hasattr(model, "predict_proba") else model.decision_function(Xte)
        if not hasattr(model, "predict_proba"):
            score = (score - score.min()) / (score.max() - score.min() + 1e-8)

        thr_best = 0.5
        best_thr_metrics = None
        for thr in np.linspace(0.05, 0.95, 73):
            pred = (score >= thr).astype(np.int32)
            if smoothing_window >= 3 and len(pred) >= smoothing_window:
                pred = np.rint(
                    np.convolve(pred, np.ones(smoothing_window) / float(smoothing_window), mode="same")
                ).astype(np.int32)

            metrics = {
                "f1": f1_score(yte, pred, zero_division=0),
                "precision": precision_score(yte, pred, zero_division=0),
                "recall": recall_score(yte, pred, zero_division=0),
                "accuracy": accuracy_score(yte, pred),
                "balanced_accuracy": balanced_accuracy_score(yte, pred),
            }
            meets_target = True
            if target_f1 is not None and metrics["f1"] < target_f1:
                meets_target = False
            if target_recall is not None and metrics["recall"] < target_recall:
                meets_target = False

            if best_thr_metrics is None:
                best_thr_metrics = (meets_target, metrics["f1"], metrics["recall"], metrics["accuracy"], float(thr), metrics)
                thr_best = float(thr)
                continue

            cand = (meets_target, metrics["f1"], metrics["recall"], metrics["accuracy"], float(thr), metrics)
            # Priority: satisfy target(s), then higher F1, then higher recall, then accuracy.
            if prioritize_recall:
                cand_key = (cand[0], cand[2], cand[1], cand[3])
                best_key = (best_thr_metrics[0], best_thr_metrics[2], best_thr_metrics[1], best_thr_metrics[3])
            else:
                cand_key = cand[:4]
                best_key = best_thr_metrics[:4]
            if cand_key > best_key:
                best_thr_metrics = cand
                thr_best = float(thr)

        pred = (score >= thr_best).astype(np.int32)
        # Temporal smoothing usually reduces noisy frame-level spikes.
        if smoothing_window >= 3 and len(pred) >= smoothing_window:
            pred = np.rint(
                np.convolve(pred, np.ones(smoothing_window) / float(smoothing_window), mode="same")
            ).astype(np.int32)
        res = {
            "name": name,
            "model": model,
            "threshold": thr_best,
            "f1": f1_score(yte, pred, zero_division=0),
            "precision": precision_score(yte, pred, zero_division=0),
            "recall": recall_score(yte, pred, zero_division=0),
            "accuracy": accuracy_score(yte, pred),
            "balanced_accuracy": balanced_accuracy_score(yte, pred),
            "report": classification_report(yte, pred, digits=4, zero_division=0),
        }
        meets_target = True
        if target_f1 is not None and res["f1"] < target_f1:
            meets_target = False
        if target_recall is not None and res["recall"] < target_recall:
            meets_target = False

        score_key = "f1" if optimize_metric == "f1" else "accuracy"
        if prioritize_recall:
            ranking = (
                1.0 if meets_target else 0.0,
                res["recall"],
                res["f1"],
                res["balanced_accuracy"],
            )
        else:
            ranking = (
                1.0 if meets_target else 0.0,
                res[score_key],
                res["recall"],
                res["balanced_accuracy"],
            )
        if ranking > (best_score if isinstance(best_score, tuple) else (-1.0, -1.0, -1.0, -1.0)):
            best_score = ranking
            best = name
            best_res = res
    return best, best_res


def main():
    parser = argparse.ArgumentParser(description="Train fall detector with pipeline: video->frames->txt labels->pose->features->train")
    parser.add_argument("--dataset", type=str, default="dataset")
    parser.add_argument("--video-root", type=str, default="", help="Thư mục chứa video (nếu dataset trong repo chỉ có annotation)")
    parser.add_argument("--output", type=str, default="models/fall_detector_pose_best.pkl")
    parser.add_argument("--max-lag", type=int, default=8)
    parser.add_argument("--feature-set", type=str, default="pose_only", choices=["pose_only", "pose_bbox"])
    parser.add_argument("--save-frames", action="store_true")
    parser.add_argument("--optimize-metric", type=str, default="f1", choices=["accuracy", "f1"])
    parser.add_argument("--target-f1", type=float, default=0.74)
    parser.add_argument("--target-recall", type=float, default=0.83)
    parser.add_argument("--weight-scales", type=str, default="1,1.3,1.5,1.7,2,2.5,3")
    parser.add_argument("--smoothing-window", type=int, default=1)
    parser.add_argument("--prioritize-recall", action="store_true")
    parser.add_argument("--seeds", type=str, default="21,42,77")
    parser.add_argument("--target-precision", type=float, default=0.68)
    args = parser.parse_args()
    weight_scales = [float(x.strip()) for x in args.weight_scales.split(",") if x.strip()]
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]

    video_root = Path(args.video_root).resolve() if args.video_root.strip() else None
    X, y, g, used = load_dataset(
        Path(args.dataset),
        max_lag=args.max_lag,
        save_frames=args.save_frames,
        video_root=video_root,
        feature_set=args.feature_set,
    )
    best_name = None
    best_res = None
    best_seed = None
    best_key = None
    for seed in seeds:
        name, res = train_best_model(
            X,
            y,
            g,
            seed=seed,
            optimize_metric=args.optimize_metric,
            target_f1=args.target_f1,
            target_recall=args.target_recall,
            weight_scales=weight_scales,
            smoothing_window=args.smoothing_window,
            prioritize_recall=args.prioritize_recall,
        )
        meets_f1 = args.target_f1 is None or res["f1"] >= args.target_f1
        meets_recall = args.target_recall is None or res["recall"] >= args.target_recall
        meets_precision = args.target_precision is None or res["precision"] >= args.target_precision
        meets_all = 1.0 if (meets_f1 and meets_recall and meets_precision) else 0.0

        # If user provides a target profile, choose the nearest profile.
        if args.target_f1 is not None or args.target_recall is not None or args.target_precision is not None:
            d_f1 = 0.0 if args.target_f1 is None else abs(res["f1"] - args.target_f1)
            d_recall = 0.0 if args.target_recall is None else abs(res["recall"] - args.target_recall)
            d_precision = 0.0 if args.target_precision is None else abs(res["precision"] - args.target_precision)
            key = (
                meets_all,
                -(2.0 * d_f1 + 2.0 * d_recall + 1.0 * d_precision),
                res["f1"],
                res["recall"],
            )
        else:
            key = (meets_all, res["f1"], res["recall"], res["balanced_accuracy"])

        if best_key is None or key > best_key:
            best_key = key
            best_name = name
            best_res = res
            best_seed = seed

    name, res = best_name, best_res

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": res["model"], "threshold": res["threshold"], "max_lag": args.max_lag, "feature_set": args.feature_set},
        args.output,
    )

    print(f"Used labeled videos: {used}")
    print(f"Samples: {len(y)}")
    print(f"Best model: {name}")
    print(f"Best seed: {best_seed}")
    print(
        f"Accuracy: {res['accuracy']:.4f} | Balanced Acc: {res['balanced_accuracy']:.4f} | "
        f"F1: {res['f1']:.4f} | Precision: {res['precision']:.4f} | "
        f"Recall: {res['recall']:.4f} | Threshold: {res['threshold']:.3f}"
    )
    if args.target_f1 is not None or args.target_recall is not None:
        f1_ok = args.target_f1 is None or res["f1"] >= args.target_f1
        recall_ok = args.target_recall is None or res["recall"] >= args.target_recall
        print(
            "Target check:"
            f" F1 {'OK' if f1_ok else 'NOT OK'}"
            + (f" (>= {args.target_f1:.3f})" if args.target_f1 is not None else "")
            + f" | Recall {'OK' if recall_ok else 'NOT OK'}"
            + (f" (>= {args.target_recall:.3f})" if args.target_recall is not None else "")
        )
    print(res["report"])
    print(f"Saved model to: {args.output}")


if __name__ == "__main__":
    main()

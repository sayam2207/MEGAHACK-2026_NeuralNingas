"""
drowsiness.py
-------------
Real-time drowsiness detection using laptop camera.
Uses MediaPipe FaceMesh to compute Eye Aspect Ratio (EAR).
Fires callbacks when drowsiness is detected or cleared.

Requirements:
    pip install opencv-python mediapipe
"""

import threading
import time
import platform
from typing import Callable, Optional, Any

import cv2  # type: ignore[import]
import mediapipe as mp  # type: ignore[import]


# ============================================================
# EYE LANDMARK INDICES (MediaPipe FaceMesh 468 landmarks)
# ============================================================
# Left eye
LEFT_EYE = [362, 385, 387, 263, 373, 380]
# Right eye
RIGHT_EYE = [33, 160, 158, 133, 153, 144]
# Mouth (for yawn detection)
MOUTH_TOP = 13
MOUTH_BOTTOM = 14
MOUTH_LEFT = 78
MOUTH_RIGHT = 308


# ============================================================
# EAR CALCULATION
# ============================================================
def _distance(p1: tuple, p2: tuple) -> float:
    """Euclidean distance between two points."""
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


def _ear(landmarks: Any, eye_indices: list, w: int, h: int) -> float:
    """Compute Eye Aspect Ratio for one eye."""
    pts = [(landmarks[i].x * w, landmarks[i].y * h) for i in eye_indices]
    # Vertical distances
    v1 = _distance(pts[1], pts[5])
    v2 = _distance(pts[2], pts[4])
    # Horizontal distance
    h1 = _distance(pts[0], pts[3])
    if h1 == 0:
        return 0.0
    return (v1 + v2) / (2.0 * h1)


def _mar(landmarks: Any, w: int, h: int) -> float:
    """Compute Mouth Aspect Ratio (for yawn detection)."""
    top = (landmarks[MOUTH_TOP].x * w, landmarks[MOUTH_TOP].y * h)
    bottom = (landmarks[MOUTH_BOTTOM].x * w, landmarks[MOUTH_BOTTOM].y * h)
    left = (landmarks[MOUTH_LEFT].x * w, landmarks[MOUTH_LEFT].y * h)
    right = (landmarks[MOUTH_RIGHT].x * w, landmarks[MOUTH_RIGHT].y * h)
    vertical = _distance(top, bottom)
    horizontal = _distance(left, right)
    if horizontal == 0:
        return 0.0
    return vertical / horizontal


# ============================================================
# DROWSINESS DETECTOR CLASS
# ============================================================
class DrowsinessDetector:
    """
    Real-time drowsiness detection using webcam + MediaPipe FaceMesh.

    Monitors Eye Aspect Ratio (EAR) and Mouth Aspect Ratio (MAR).
    Fires on_drowsy callback when eyes closed for too long.
    Fires on_yawn callback when yawning detected.
    """

    # Thresholds
    EAR_THRESHOLD = 0.25       # below this = eyes closed
    EAR_CONSEC_FRAMES = 15     # consecutive frames → drowsy (~0.5s at 30fps)
    MAR_THRESHOLD = 0.65       # above this = yawning
    YAWN_CONSEC_FRAMES = 10
    NO_FACE_FRAMES = 60        # ~2 sec of no face = drowsy (head dropped)

    def __init__(self) -> None:
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_drowsy: Optional[Callable] = None
        self._on_alert: Optional[Callable] = None
        self._on_yawn: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

        # State
        self._ear_counter = 0
        self._yawn_counter = 0
        self._no_face_counter = 0
        self._is_drowsy = False
        self._is_yawning = False
        self._current_ear = 0.0
        self._current_mar = 0.0
        self._drowsy_events = 0

        # Latest frame for display
        self._latest_frame: Optional[Any] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_drowsy(self) -> bool:
        return self._is_drowsy

    @property
    def current_ear(self) -> float:
        return self._current_ear

    @property
    def current_mar(self) -> float:
        return self._current_mar

    @property
    def drowsy_events(self) -> int:
        return self._drowsy_events

    def start(self, on_drowsy: Optional[Callable] = None,
              on_alert: Optional[Callable] = None,
              on_yawn: Optional[Callable] = None,
              on_error: Optional[Callable] = None) -> None:
        """Start drowsiness detection in a background thread."""
        if self._running:
            return

        self._on_drowsy = on_drowsy
        self._on_alert = on_alert
        self._on_yawn = on_yawn
        self._on_error = on_error
        self._running = True
        self._thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._thread.start()  # type: ignore[union-attr]

    def stop(self) -> None:
        """Stop drowsiness detection."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)  # type: ignore[union-attr]
            self._thread = None

    def get_frame(self) -> Optional[Any]:
        """Return the latest annotated camera frame (for display)."""
        return self._latest_frame

    def _report_error(self, msg: str) -> None:
        """Report an error via callback and print."""
        print(f"[DROWSINESS] {msg}")
        if self._on_error:
            self._on_error(msg)  # type: ignore[misc]

    def _open_camera(self) -> Optional[cv2.VideoCapture]:
        """Try to open a camera with multiple backends and indices."""
        import numpy as np  # type: ignore[import]
        backends: list[tuple[str, int]] = []
        if platform.system() == "Windows":
            backends = [
                ("DSHOW", cv2.CAP_DSHOW),
                ("MSMF", cv2.CAP_MSMF),
                ("DEFAULT", cv2.CAP_ANY),
            ]
        else:
            backends = [("DEFAULT", cv2.CAP_ANY)]

        for bname, backend in backends:
            for cam_idx in (0, 1):
                print(f"[DROWSINESS] Trying camera {cam_idx} with {bname}...")
                test_cap = cv2.VideoCapture(cam_idx, backend)
                if test_cap.isOpened():
                    ret, frame = test_cap.read()
                    if ret and frame is not None:
                        brightness = float(np.mean(frame))
                        print(f"[DROWSINESS]   Frame OK, brightness={brightness:.1f}/255")
                        if brightness > 10:
                            print(f"[DROWSINESS] ✓ Camera {cam_idx} opened with {bname}")
                            return test_cap
                        else:
                            print(f"[DROWSINESS]   Frame is BLACK — trying extended warmup...")
                            # Some cameras need many frames before producing real images
                            got_real_frame = False
                            for warmup in range(200):  # try up to ~10 seconds
                                ret2, frame2 = test_cap.read()
                                if ret2 and frame2 is not None:
                                    brightness = float(np.mean(frame2))
                                    if brightness > 10:
                                        print(f"[DROWSINESS] ✓ Camera activated after "
                                              f"{warmup+1} warmup frames! "
                                              f"brightness={brightness:.1f}")
                                        return test_cap
                                time.sleep(0.05)
                                if warmup % 40 == 39:
                                    print(f"[DROWSINESS]   Still warming up... "
                                          f"({warmup+1}/200 frames)")
                            print(f"[DROWSINESS]   ✗ Camera stayed black after 200 frames")
                            test_cap.release()
                    else:
                        test_cap.release()
                else:
                    test_cap.release()

        return None

    def _detection_loop(self) -> None:
        """Main detection loop running in background thread."""
        import numpy as np  # type: ignore[import]

        # Initialize FaceMesh
        try:
            face_mesh = mp.solutions.face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.3,
                min_tracking_confidence=0.3,
            )
        except Exception as e:
            self._report_error(f"FaceMesh init failed: {e}")
            self._running = False
            return

        # Open camera (includes warmup for black frames)
        cap = self._open_camera()
        if cap is None:
            self._report_error(
                "Cannot open camera! Tried all backends and indices.\n"
                "Camera may be blocked, covered, or used by another app.\n"
                "Check: Windows Settings → Privacy → Camera → Allow apps"
            )
            self._running = False
            return

        # Set camera resolution (lower for performance)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # Extra warmup: ensure we get non-black frames
        print("[DROWSINESS] Final warmup — waiting for bright frames...")
        bright_count = 0
        for i in range(60):  # up to ~3 more seconds
            ret, frame = cap.read()
            if ret and frame is not None:
                brightness = float(np.mean(frame))
                if brightness > 10:
                    bright_count += 1  # type: ignore[operator]
                    if bright_count >= 5:
                        print(f"[DROWSINESS] ✓ Camera producing real frames! "
                              f"(brightness={brightness:.1f})")
                        break
            time.sleep(0.05)
        else:
            print("[DROWSINESS] ⚠ Camera may still be dark — continuing anyway")

        print("[DROWSINESS] Camera opened. Detection started.")

        frame_count = 0
        fail_count = 0
        max_consecutive_fails = 30  # give up after 30 consecutive failed reads

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    fail_count += 1
                    if fail_count >= max_consecutive_fails:
                        self._report_error(
                            f"Camera stopped providing frames after {frame_count} "
                            f"successful frames. Camera may be disconnected."
                        )
                        break
                    time.sleep(0.01)
                    continue

                fail_count = 0  # reset on success
                frame_count += 1

                # Log progress periodically
                if frame_count == 1:
                    print(f"[DROWSINESS] First frame captured! ({frame.shape[1]}x{frame.shape[0]})")
                elif frame_count % 100 == 0:
                    print(f"[DROWSINESS] Processed {frame_count} frames. EAR={self._current_ear:.2f}")

                h, w = frame.shape[:2]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb)  # type: ignore[union-attr]

                if results.multi_face_landmarks:
                    self._no_face_counter = 0  # reset no-face counter
                    landmarks = results.multi_face_landmarks[0].landmark

                    # Compute EAR for both eyes
                    left_ear = _ear(landmarks, LEFT_EYE, w, h)
                    right_ear = _ear(landmarks, RIGHT_EYE, w, h)
                    avg_ear = (left_ear + right_ear) / 2.0
                    self._current_ear = avg_ear

                    # Debug: log EAR every 30 frames so user can see values
                    if frame_count % 30 == 0:
                        status = "CLOSED" if avg_ear < self.EAR_THRESHOLD else "OPEN"
                        print(f"[DROWSINESS] EAR={avg_ear:.3f} ({status}) "
                              f"counter={self._ear_counter}/{self.EAR_CONSEC_FRAMES}")

                    # Compute MAR
                    mar_val = _mar(landmarks, w, h)
                    self._current_mar = mar_val

                    # --- Drowsiness check ---
                    if avg_ear < self.EAR_THRESHOLD:
                        self._ear_counter += 1
                        if self._ear_counter >= self.EAR_CONSEC_FRAMES and not self._is_drowsy:
                            self._is_drowsy = True
                            self._drowsy_events += 1
                            if self._on_drowsy:
                                try:
                                    self._on_drowsy()  # type: ignore[misc]
                                except Exception:
                                    pass
                    else:
                        if self._is_drowsy and self._ear_counter < self.EAR_CONSEC_FRAMES // 2:
                            self._is_drowsy = False
                            if self._on_alert:
                                try:
                                    self._on_alert()  # type: ignore[misc]
                                except Exception:
                                    pass
                        self._ear_counter = max(0, self._ear_counter - 1)

                    # --- Yawn check ---
                    if mar_val > self.MAR_THRESHOLD:
                        self._yawn_counter += 1
                        if self._yawn_counter >= self.YAWN_CONSEC_FRAMES and not self._is_yawning:
                            self._is_yawning = True
                            if self._on_yawn:
                                try:
                                    self._on_yawn()  # type: ignore[misc]
                                except Exception:
                                    pass
                    else:
                        self._yawn_counter = max(0, self._yawn_counter - 1)
                        self._is_yawning = False

                    # --- Annotate frame ---
                    color = (0, 0, 255) if self._is_drowsy else (0, 255, 0)
                    cv2.putText(frame, f"EAR: {avg_ear:.2f}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    cv2.putText(frame, f"MAR: {mar_val:.2f}", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2)

                    if self._is_drowsy:
                        cv2.putText(frame, "!! DROWSY !!", (w // 2 - 100, h // 2),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

                    if self._is_yawning:
                        cv2.putText(frame, "* YAWNING *", (10, 90),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

                    # Draw eye contours
                    for eye_indices in [LEFT_EYE, RIGHT_EYE]:
                        pts = [(int(landmarks[i].x * w), int(landmarks[i].y * h))
                               for i in eye_indices]
                        for i in range(len(pts)):
                            cv2.line(frame, pts[i], pts[(i + 1) % len(pts)], color, 1)

                else:
                    # No face detected — could mean head dropped (sleeping)
                    self._no_face_counter += 1
                    if frame_count % 30 == 0:
                        print(f"[DROWSINESS] No face detected! "
                              f"no_face_counter={self._no_face_counter}/{self.NO_FACE_FRAMES}")

                    if (self._no_face_counter >= self.NO_FACE_FRAMES
                            and not self._is_drowsy):
                        # Head likely dropped — treat as drowsy
                        self._is_drowsy = True
                        self._drowsy_events += 1
                        print(f"[DROWSINESS] NO FACE for {self._no_face_counter} frames "
                              f"— triggering DROWSY alert!")
                        if self._on_drowsy:
                            try:
                                self._on_drowsy()  # type: ignore[misc]
                            except Exception:
                                pass

                    cv2.putText(frame, "No face detected", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)
                    self._current_ear = 0.0
                    self._current_mar = 0.0

                self._latest_frame = frame
                time.sleep(0.033)  # ~30 FPS

        except Exception as e:
            self._report_error(f"Detection error after {frame_count} frames: {e}")
            import traceback
            traceback.print_exc()
        finally:
            cap.release()
            face_mesh.close()
            self._running = False
            print(f"[DROWSINESS] Detection stopped. Total frames processed: {frame_count}")

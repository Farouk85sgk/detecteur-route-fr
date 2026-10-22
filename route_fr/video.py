"""Sources vidéo lues dans un thread : on ne garde que l'image la plus récente pour une latence minimale."""

import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np


class VideoStream:
    """Webcam (indice), fichier vidéo, flux réseau (rtsp://, http://...) ou capture d'écran ("ecran").

    Pour un fichier, `realtime=True` respecte la cadence de la vidéo (les images non traitées à temps sont
    sautées, comme en direct) ; `realtime=False` traite toutes les images.
    """

    def __init__(self, source, width=None, height=None, realtime=True, region=None):
        self.source = str(source)
        self.realtime = realtime
        self.frame, self.frame_id, self.ended = None, 0, False
        self.lock = threading.Condition()
        self.is_screen = self.source.lower() in ("ecran", "écran", "screen")
        self.is_file = not self.is_screen and Path(self.source).is_file()
        if self.is_screen:
            import mss  # pip install mss

            self.sct = mss.mss()
            mon = self.sct.monitors[1]
            if region:
                x, y, w, h = region
                mon = {"left": x, "top": y, "width": w, "height": h}
            self.monitor = mon
            self.fps = 30.0
        else:
            src = int(self.source) if self.source.isdigit() else self.source
            if isinstance(src, int) and os.name == "nt":  # Windows : DirectShow ouvre les webcams plus vite
                self.cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
            else:
                self.cap = cv2.VideoCapture(src)
            if not self.cap.isOpened():
                raise RuntimeError(f"Impossible d'ouvrir la source vidéo : {self.source}")
            if isinstance(src, int):
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if width and height:
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
            if not 1 <= self.fps <= 240:
                self.fps = 30.0
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _grab(self):
        if self.is_screen:
            return True, np.ascontiguousarray(np.array(self.sct.grab(self.monitor))[..., :3])
        return self.cap.read()

    def _run(self):
        if self.is_screen:  # mss doit être utilisé dans le thread qui l'a créé
            import mss

            self.sct = mss.mss()
        t0, n = time.perf_counter(), 0
        while not self.ended:
            if self.is_file and not self.realtime:
                with self.lock:  # attendre que l'image précédente ait été lue
                    while self.frame is not None and not self.ended:
                        self.lock.wait(0.05)
            ok, frame = self._grab()
            if not ok:
                if self.is_file:
                    self.ended = True
                    break
                time.sleep(0.2)  # flux réseau interrompu : on réessaie
                continue
            with self.lock:
                self.frame = frame
                self.frame_id += 1
                self.lock.notify_all()
            n += 1
            if self.is_file and self.realtime:  # cadence de la vidéo d'origine
                delay = t0 + n / self.fps - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
        with self.lock:
            self.lock.notify_all()

    def read(self, timeout=2.0):
        """Image la plus récente non encore lue : (indice, image) ; (None, None) en fin de vidéo."""
        with self.lock:
            last = getattr(self, "_last_id", 0)
            end = time.perf_counter() + timeout
            while self.frame_id == last and not self.ended:
                if not self.lock.wait(max(0.0, end - time.perf_counter())):
                    break
            if self.frame is None or (self.frame_id == last and self.ended):
                return None, None
            self._last_id = self.frame_id
            frame = self.frame
            if self.is_file and not self.realtime:
                self.frame = None
                self.lock.notify_all()
            return self.frame_id, frame

    def release(self):
        self.ended = True
        self.thread.join(timeout=1.0)
        if not self.is_screen:
            self.cap.release()

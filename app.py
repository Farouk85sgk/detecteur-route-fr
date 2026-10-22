"""Détection en temps réel des panneaux et marquages au sol du code de la route français (YOLOv5).

Exemples :
    python app.py                                  # webcam n°0
    python app.py --source 1                       # autre caméra (USB, caméra embarquée...)
    python app.py --source trajet.mp4              # vidéo (lue à sa cadence réelle, comme en direct)
    python app.py --source http://192.168.1.20:8080/video   # téléphone (appli « IP Webcam ») ou caméra IP
    python app.py --source ecran                   # capture de l'écran (ex. vidéo de conduite sur YouTube)
    python app.py --source trajet.mp4 --enregistrer resultat.mp4 --sans-affichage

Touches : Q/Échap quitter, Espace pause, S capture, R enregistrer, M marquages, P panneau latéral, +/- seuil.
"""

import argparse
import csv
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2

from route_fr.classes import CLASSES
from route_fr.detector import Detector
from route_fr.hud import Hud
from route_fr.tracker import Stabilizer
from route_fr.video import VideoStream

HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "weights"
DEFAULT_WEIGHTS = next((p for p in (WEIGHTS / "route_fr_yolov5n.onnx", WEIGHTS / "route_fr_yolov5n.pt") if p.exists()), WEIGHTS / "route_fr_yolov5n.pt")
DEFAULT_CLASSIFIER = next((p for p in (WEIGHTS / "panneaux_cls.onnx", WEIGHTS / "panneaux_cls.pt") if p.exists()), None)


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="0", help="webcam (0, 1...), fichier vidéo, URL rtsp/http, ou « ecran »")
    ap.add_argument("--poids", default=str(DEFAULT_WEIGHTS), help="modèle YOLOv5 (.pt, .onnx, dossier OpenVINO, .engine...)")
    ap.add_argument("--classifieur", default=str(DEFAULT_CLASSIFIER or ""), help="classifieur de panneaux (second étage)")
    ap.add_argument("--sans-classifieur", action="store_true", help="n'utiliser que le détecteur")
    ap.add_argument("--taille", type=int, nargs="+", default=[640], help="taille d'inférence (plus petit = plus rapide) ; H L pour un modèle exporté à taille fixe")
    ap.add_argument("--conf", type=float, default=0.35, help="seuil de confiance")
    ap.add_argument("--iou", type=float, default=0.45, help="seuil IoU de la suppression des doublons")
    ap.add_argument("--appareil", default="", help="cpu, 0 (1er GPU NVIDIA), mps (Mac)...")
    ap.add_argument("--demi", action="store_true", help="demi-précision FP16 (GPU)")
    ap.add_argument("--min-hits", type=int, default=2, help="détections nécessaires avant d'afficher un objet")
    ap.add_argument("--largeur-affichage", type=int, default=1280, help="largeur de la vidéo affichée")
    ap.add_argument("--largeur-camera", type=int, default=1280)
    ap.add_argument("--hauteur-camera", type=int, default=720)
    ap.add_argument("--region", type=int, nargs=4, metavar=("X", "Y", "L", "H"), help="zone de l'écran à capturer")
    ap.add_argument("--toutes-images", action="store_true", help="vidéo : traiter toutes les images (pas de saut)")
    ap.add_argument("--sans-marquages", action="store_true", help="masquer les marquages au sol")
    ap.add_argument("--sans-panneau", action="store_true", help="masquer le panneau latéral")
    ap.add_argument("--voix", action="store_true", help="annonces vocales (pip install pyttsx3)")
    ap.add_argument("--enregistrer", default="", help="enregistrer la vidéo annotée dans ce fichier .mp4")
    ap.add_argument("--sans-affichage", action="store_true", help="pas de fenêtre (serveur, test)")
    ap.add_argument("--journal", default="", help="journal CSV des panneaux et marquages rencontrés (débriefing)")
    return ap.parse_args()


class Voice:
    """Annonces vocales hors ligne, dans un thread pour ne pas ralentir la détection."""

    def __init__(self):
        self.q, self.last = queue.Queue(), {}
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        import pyttsx3

        engine = pyttsx3.init()
        for v in engine.getProperty("voices"):
            if "fr" in (str(v.id) + str(getattr(v, "languages", ""))).lower():
                engine.setProperty("voice", v.id)
                break
        engine.setProperty("rate", 175)
        while True:
            engine.say(self.q.get())
            engine.runAndWait()

    def say(self, key, text, cooldown=10.0):
        now = time.time()
        if now - self.last.get(key, 0.0) > cooldown and self.q.qsize() < 2:
            self.last[key] = now
            self.q.put(text)


def main():
    a = parse_args()
    classifier = None if a.sans_classifieur or not a.classifieur else a.classifieur
    print(f"Modèle : {a.poids}" + (f" + classifieur {classifier}" if classifier else ""))
    det = Detector(a.poids, a.taille, a.conf, a.iou, a.appareil, a.demi, classifier=classifier)
    stream = VideoStream(a.source, a.largeur_camera, a.hauteur_camera, realtime=not a.toutes_images, region=a.region)
    hud = Hud(show_panel=not a.sans_panneau, show_markings=not a.sans_marquages)
    stab = Stabilizer(lambda c: CLASSES[c].categorie == "marquage", min_hits=a.min_hits)
    voice = Voice() if a.voix else None
    journal = None
    if a.journal:
        new_file = not Path(a.journal).exists()
        journal = open(a.journal, "a", newline="", encoding="utf-8-sig")
        log = csv.writer(journal, delimiter=";")
        if new_file:
            log.writerow(["date_heure", "secondes", "code", "nom", "categorie", "confiance", "explication"])
    window = "Detecteur route FR - YOLOv5"
    if not a.sans_affichage:
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    writer, record_path = None, a.enregistrer
    recording = bool(record_path)
    fps, infer_ms, t_last, paused, n_frames, t_start, out = 0.0, 0.0, time.perf_counter(), False, 0, time.perf_counter(), None
    try:
        while True:
            if not paused or out is None:
                _, frame = stream.read()
                if frame is None:
                    break
                t0 = time.perf_counter()
                dets = det(frame)
                infer_ms = 0.8 * infer_ms + 0.2 * (time.perf_counter() - t0) * 1000 if infer_ms else (time.perf_counter() - t0) * 1000
                tracks, new = stab.update(dets, 640 / max(frame.shape[:2]))
                hud.update_speed(tracks, stab.scale)
                for t in new:
                    c = CLASSES[t.cls]
                    hud.on_new(t.cls)
                    if voice and c.voix:
                        voice.say(t.cls, c.voix)
                    if journal:
                        log.writerow([f"{datetime.now():%Y-%m-%d %H:%M:%S}", f"{time.perf_counter() - t_start:.1f}", c.code, c.nom, c.categorie, f"{t.conf:.2f}", c.explication])
                        journal.flush()
                    if a.sans_affichage:
                        print(f"[{time.perf_counter() - t_start:7.1f} s] {c.code:<24} {c.nom} ({t.conf:.0%})")
                scale = min(1.0, a.largeur_affichage / frame.shape[1])
                view = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else frame
                now = time.perf_counter()
                fps = 0.9 * fps + 0.1 / max(now - t_last, 1e-6) if fps else 1 / max(now - t_last, 1e-6)
                t_last = now
                n_frames += 1
                out = hud.compose(view, tracks, scale, fps, infer_ms, det.conf, recording)
                if recording:
                    if writer is None:
                        record_path = record_path or f"enregistrement_{datetime.now():%Y%m%d_%H%M%S}.mp4"
                        writer = cv2.VideoWriter(record_path, cv2.VideoWriter_fourcc(*"mp4v"), stream.fps if stream.is_file else max(5, round(fps)), (out.shape[1], out.shape[0]))
                        print(f"Enregistrement : {record_path}")
                    writer.write(out)
            if a.sans_affichage:
                continue
            cv2.imshow(window, out)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" "):
                paused = not paused
            elif key == ord("s"):
                name = f"capture_{datetime.now():%Y%m%d_%H%M%S}.jpg"
                cv2.imwrite(name, out)
                print(f"Capture : {name}")
            elif key == ord("r"):
                recording = not recording
                if not recording and writer is not None:
                    writer.release()
                    writer, record_path = None, ""
            elif key == ord("m"):
                hud.show_markings = not hud.show_markings
            elif key == ord("p"):
                hud.show_panel = not hud.show_panel
            elif key in (ord("+"), ord("=")):
                det.conf = min(0.95, det.conf + 0.05)
            elif key in (ord("-"), ord("_")):
                det.conf = max(0.05, det.conf - 0.05)
    finally:
        stream.release()
        if writer is not None:
            writer.release()
        if journal:
            journal.close()
        cv2.destroyAllWindows()
        dt = time.perf_counter() - t_start
        if n_frames:
            print(f"{n_frames} images traitées en {dt:.1f} s ({n_frames / dt:.1f} img/s), inférence moyenne {infer_ms:.0f} ms")


if __name__ == "__main__":
    main()

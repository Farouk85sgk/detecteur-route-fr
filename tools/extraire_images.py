"""Extrait des images d'une ou plusieurs vidéos (caméra embarquée, téléphone) pour les annoter.

    python tools/extraire_images.py mes_videos/*.mp4 --sortie mes_images --intervalle 1.0
"""

import argparse
from pathlib import Path

import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--sortie", default="mes_images")
    ap.add_argument("--intervalle", type=float, default=1.0, help="secondes entre deux images extraites")
    ap.add_argument("--largeur", type=int, default=1280, help="largeur maximale des images enregistrées")
    a = ap.parse_args()
    out = Path(a.sortie)
    out.mkdir(parents=True, exist_ok=True)
    total = 0
    for v in a.videos:
        cap = cv2.VideoCapture(v)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, round(fps * a.intervalle))
        i = 0
        while True:
            ok = cap.grab()
            if not ok:
                break
            if i % step == 0:
                _, frame = cap.retrieve()
                if frame.shape[1] > a.largeur:
                    s = a.largeur / frame.shape[1]
                    frame = cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
                cv2.imwrite(str(out / f"{Path(v).stem}_{i:06d}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
                total += 1
            i += 1
        cap.release()
    print(f"{total} images enregistrées dans {out}")


if __name__ == "__main__":
    main()

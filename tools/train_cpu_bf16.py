"""Lance l'entraînement YOLOv5 en précision mixte bfloat16 sur processeur (Intel AVX-512/AMX : ~2,4x plus rapide).

YOLOv5 n'active l'autocast que sur GPU ; ce lanceur l'active sur CPU sans modifier le code de YOLOv5.
Les pertes restent calculées en float32. Mêmes arguments que yolov5/train.py, par exemple :

    python tools/train_cpu_bf16.py --data data/route_fr.yaml --weights yolov5/yolov5n.pt --img 416 --epochs 20

Avec --classifieur en premier argument, lance yolov5/classify/train.py (classifieur de panneaux) :

    python tools/train_cpu_bf16.py --classifieur --model yolov5n-cls.pt --data datasets/panneaux_cls --img 64
"""

import sys
from pathlib import Path

import torch

YOLO = Path(__file__).resolve().parents[1] / "yolov5"
sys.path.insert(0, str(YOLO))

CLASSIFIER = len(sys.argv) > 1 and sys.argv[1] == "--classifieur"
if CLASSIFIER:
    sys.argv.pop(1)
    from classify import train  # noqa: E402

    _ce = torch.nn.CrossEntropyLoss.forward
    torch.nn.CrossEntropyLoss.forward = lambda self, x, y: _ce(self, x.float(), y)
else:
    import train  # noqa: E402
    from utils.loss import ComputeLoss  # noqa: E402

    _loss_call = ComputeLoss.__call__

    def _loss_fp32(self, p, targets):
        with torch.autocast("cpu", enabled=False):
            return _loss_call(self, [x.float() for x in p], targets)

    ComputeLoss.__call__ = _loss_fp32

train.smart_amp_autocast = lambda enabled=True, device="cpu": torch.autocast("cpu", dtype=torch.bfloat16)

if __name__ == "__main__":
    opt = train.parse_opt()
    opt.device = "cpu"
    train.main(opt)

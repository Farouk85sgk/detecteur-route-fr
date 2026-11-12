"""Lance l'entraînement YOLOv5 en précision mixte bfloat16 sur processeur (Intel AVX-512/AMX : ~2,4x plus rapide).

YOLOv5 n'active l'autocast que sur GPU ; ce lanceur l'active sur CPU sans modifier le code de YOLOv5.
Les pertes restent calculées en float32. Mêmes arguments que yolov5/train.py, par exemple :

    python tools/train_cpu_bf16.py --data data/route_fr.yaml --weights weights/route_fr_yolov5n.pt --hyp data/hyp_route_fr.yaml --img 416 --epochs 12

Zones d'entraînement. Les deux dernières classes du jeu de données (« _ignorer » et « _reel », voir route_fr/classes.py)
ne sont pas des objets à détecter mais des zones qui modifient la perte de présence d'objet (objectness) :
- « _ignorer » : zone douteuse (objet non identifié, panneau trop petit...). Rien n'y est compté, ni pour ni contre ;
- « _reel » : zone d'une vraie photo où seuls les panneaux sont annotés. Le réseau y est corrigé s'il voit un panneau
  là où il n'y en a pas, mais pas s'il y voit un marquage au sol (les vrais marquages de ces photos ne sont pas
  annotés : les traiter comme du fond lui apprendrait à ne plus les voir).
Sans ces classes dans les étiquettes, la perte est exactement celle de YOLOv5.

Avec --classifieur en premier argument, lance yolov5/classify/train.py (classifieur de panneaux) :

    python tools/train_cpu_bf16.py --classifieur --model yolov5n-cls.pt --data datasets/panneaux_cls --img 64
"""

import sys
from pathlib import Path

import torch
import torch.nn.functional as F

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
    from ultralytics.utils.metrics import bbox_iou  # noqa: E402

    def _cellules(z, n, centre):
        """Indices de cellules (premier, dernier) couverts par des intervalles normalisés z = (milieu, taille)."""
        a, b = (z[:, 0] - z[:, 1] / 2) * n, (z[:, 0] + z[:, 1] / 2) * n
        if centre:  # cellules dont le centre est dans l'intervalle
            return (a - 0.5).ceil().clamp(0, n - 1).long(), (b - 0.5).floor().clamp(0, n - 1).long()
        return a.floor().clamp(0, n - 1).long(), b.floor().clamp(0, n - 1).long()  # cellules touchées

    def _loss_zones(self, p, targets):
        """Perte de YOLOv5 (utils/loss.py) en float32, avec les zones « _ignorer » et « _reel »."""
        p = [x.float() for x in p]
        with torch.autocast("cpu", enabled=False):
            k_ign, k_reel = self.nc - 2, self.nc - 1
            z_ign, z_reel = targets[targets[:, 1] == k_ign], targets[targets[:, 1] == k_reel]
            targets = targets[targets[:, 1] < k_ign]
            lcls, lbox, lobj = (torch.zeros(1, device=self.device) for _ in range(3))
            tcls, tbox, indices, anchors = self.build_targets(p, targets)
            for i, pi in enumerate(p):
                b, a, gj, gi = indices[i]
                bs, na, ny, nx = pi.shape[:4]
                tobj = torch.zeros((bs, na, ny, nx), dtype=pi.dtype, device=self.device)
                etat = torch.zeros((bs, ny, nx), dtype=torch.uint8, device=self.device)  # 0 normal, 1 « _reel », 2 « _ignorer »
                for valeur, z in ((1, z_reel), (2, z_ign)):
                    if len(z):
                        x1, x2 = _cellules(z[:, [2, 4]], nx, valeur == 1)
                        y1, y2 = _cellules(z[:, [3, 5]], ny, valeur == 1)
                        for j in range(len(z)):
                            etat[int(z[j, 0]), y1[j] : y2[j] + 1, x1[j] : x2[j] + 1] = valeur
                poids = (etat != 2).to(pi.dtype)[:, None].repeat(1, na, 1, 1)
                reel = (etat == 1)[:, None].repeat(1, na, 1, 1)
                if n := b.shape[0]:
                    pxy, pwh, _, pcls = pi[b, a, gj, gi].split((2, 2, 1, self.nc), 1)
                    pxy = pxy.sigmoid() * 2 - 0.5
                    pwh = (pwh.sigmoid() * 2) ** 2 * anchors[i]
                    iou = bbox_iou(torch.cat((pxy, pwh), 1), tbox[i], CIoU=True).squeeze(-1)
                    lbox += (1.0 - iou).mean()
                    iou = iou.detach().clamp(0).type(tobj.dtype)
                    if self.gr < 1:
                        iou = (1.0 - self.gr) + self.gr * iou
                    tobj[b, a, gj, gi] = iou
                    poids[b, a, gj, gi] = 1.0  # un objet annoté compte toujours
                    reel[b, a, gj, gi] = False
                    t = torch.full_like(pcls, self.cn, device=self.device)
                    t[range(n), tcls[i]] = self.cp
                    lcls += self.BCEcls(pcls, t)
                obj = pi[..., 4]
                perte = F.binary_cross_entropy_with_logits(obj, tobj, pos_weight=self.BCEobj.pos_weight, reduction="none")
                if reel.any():  # « pas de panneau ici » : pénalise la confiance « objet x panneau », pas les marquages
                    conjointe = -torch.log1p(-(obj.sigmoid() * pi[..., 5].sigmoid()).clamp(max=1 - 1e-6))
                    perte = torch.where(reel, conjointe, perte)
                obji = (perte * poids).sum() / poids.sum().clamp(min=1)
                lobj += obji * self.balance[i]
                if self.autobalance:
                    self.balance[i] = self.balance[i] * 0.9999 + 0.0001 / obji.detach().item()
            if self.autobalance:
                self.balance = [x / self.balance[self.ssi] for x in self.balance]
            lbox *= self.hyp["box"]
            lobj *= self.hyp["obj"]
            lcls *= self.hyp["cls"]
            return (lbox + lobj + lcls) * p[0].shape[0], torch.cat((lbox, lobj, lcls)).detach()

    _loss_call = ComputeLoss.__call__

    def _loss(self, p, targets):
        if ZONES and self.hyp["fl_gamma"] == 0:
            return _loss_zones(self, p, targets)
        with torch.autocast("cpu", enabled=False):
            return _loss_call(self, [x.float() for x in p], targets)

    ZONES = False  # activées plus bas si le jeu de données se termine par les deux classes techniques
    ComputeLoss.__call__ = _loss

train.smart_amp_autocast = lambda enabled=True, device="cpu": torch.autocast("cpu", dtype=torch.bfloat16)

if __name__ == "__main__":
    opt = train.parse_opt()
    opt.device = "cpu"
    if not CLASSIFIER:
        import yaml

        data = opt.data
        if opt.resume:  # reprise d'un entraînement interrompu : le jeu de données est celui noté dans le dossier de l'entraînement
            dernier = Path(opt.resume if isinstance(opt.resume, str) else train.get_latest_run())
            if (dernier.parent.parent / "opt.yaml").is_file():
                data = yaml.safe_load(open(dernier.parent.parent / "opt.yaml", errors="ignore"))["data"]
        noms = yaml.safe_load(open(data, errors="ignore"))["names"]
        noms = list(noms.values()) if isinstance(noms, dict) else list(noms)
        ZONES = noms[-2:] == ["_ignorer", "_reel"]
        print(f"Zones d'entraînement (_ignorer, _reel) : {'actives' if ZONES else 'absentes de ce jeu de données'}")
    train.main(opt)

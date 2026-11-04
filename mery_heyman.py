#!/usr/bin/env python3
"""Analyse Méry–Heyman de la ligne de poussée d'une voûte maçonnée en arc de cercle.

Hypothèses de Heyman :
  - résistance à la traction nulle ;
  - résistance à la compression infinie ;
  - glissement impossible.

La méthode de Méry consiste à tracer la funiculaire des charges (polygone de
poussée) à l'intérieur du corps de la voûte. D'après le théorème de sécurité de
Heyman, la voûte est stable si et seulement s'il existe une ligne de poussée
entièrement contenue dans l'épaisseur de la maçonnerie. Le script détermine
les bornes de poussée horizontale admissibles à la clé (H_min, H_max), les
articulations correspondantes et, optionnellement, l'épaisseur minimale.

Géométrie : voûte en berceau (arc circulaire), définie par son ouverture
(portée) et sa flèche. Le calcul est mené par tranche unitaire de un mètre
longitudinal, sous poids propre uniquement, avec des joints radiaux
(stéréotomie polaire, solution de Milankovitch).

Exemples :
    python mery_heyman.py --span 6 --rise 3 --thickness 0.6
    python mery_heyman.py --span 6 --rise 3 --thickness 0.6 --plot voute.png
    python mery_heyman.py --span 6 --rise 3 --thickness 0.6 --min-thickness
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Vault:
    span: float
    rise: float
    thickness: float
    gamma: float = 22.0
    n: int = 200


@dataclass(frozen=True)
class Geometry:
    R: float
    alpha: float
    r_in: float
    r_out: float
    n: int
    dtheta: float


@dataclass(frozen=True)
class Voussoir:
    w: float
    x: float
    y: float


class VaultAnalysis:
    def __init__(self, vault: Vault):
        if vault.span <= 0 or vault.rise <= 0:
            raise ValueError("ouverture et flèche doivent être positives")
        if vault.thickness <= 0:
            raise ValueError("l'épaisseur doit être positive")
        if vault.n < 8:
            raise ValueError("au moins 8 voussoirs sont nécessaires")
        self.vault = vault
        L, f = vault.span, vault.rise
        R = (f * f + (L / 2.0) ** 2) / (2.0 * f)
        alpha = math.asin(min(1.0, (L / 2.0) / R))
        self.geo = Geometry(
            R=R,
            alpha=alpha,
            r_in=R - vault.thickness / 2.0,
            r_out=R + vault.thickness / 2.0,
            n=vault.n,
            dtheta=alpha / vault.n,
        )
        self.voussoirs = self._build_voussoirs()
        self._W = [0.0]
        self._Sx = [0.0]
        for vs in self.voussoirs:
            self._W.append(self._W[-1] + vs.w)
            self._Sx.append(self._Sx[-1] + vs.x * vs.w)

    def _build_voussoirs(self) -> list[Voussoir]:
        g = self.geo
        v = []
        for i in range(g.n):
            dth = g.dtheta
            area = 0.5 * (g.r_out ** 2 - g.r_in ** 2) * dth
            r_c = (
                (2.0 / 3.0)
                * (g.r_out ** 3 - g.r_in ** 3)
                / (g.r_out ** 2 - g.r_in ** 2)
                * (math.sin(dth / 2.0) / (dth / 2.0))
            )
            thm = (i + 0.5) * g.dtheta
            v.append(
                Voussoir(
                    w=self.vault.gamma * area,
                    x=r_c * math.sin(thm),
                    y=r_c * math.cos(thm),
                )
            )
        return v

    def total_weight(self) -> float:
        return self._W[-1] * 2.0

    def theta(self, joint: int) -> float:
        return joint * self.geo.dtheta

    def thrust_offset(self, H: float, e_crown: float, joint: int) -> float:
        """Excentricité (m, depuis la fibre moyenne, positif vers l'extrados)
        de la résultante au joint `joint` (0 = clé, n = naissance).

        Corps libre : voussoirs 0..joint-1 (de la clé au joint), soumis à la
        poussée horizontale H appliquée à la clé en (0, R + e_crown) et aux
        poids propres. Le point de poussée est l'intersection de la résultante
        avec le plan radial du joint.
        """
        g = self.geo
        th = self.theta(joint)
        qx = g.R * math.sin(th)
        qy = g.R * math.cos(th)
        W = self._W[joint]
        m = -(g.R + e_crown - qy) * H + (qx * W - self._Sx[joint])
        denom = W * math.sin(th) + H * math.cos(th)
        if abs(denom) < 1e-12:
            return math.inf
        return -m / denom

    def crown_interval(self, H: float) -> tuple[float, float]:
        """Intervalle d'excentricités de clé admissibles pour la poussée H.

        L'excentricité au joint j dépend linéairement de e_crown :
            d(j) = d0(j) + e_crown * H / (W_j sin(theta_j) + H cos(theta_j))
        où W_j est le poids des voussoirs situés entre la clé et le joint.
        Chaque joint contraint e_crown à un intervalle ; la voûte admet une
        ligne de poussée pour H si l'intersection de tous ces intervalles
        (bornée à +/- t/2) est non vide. L'intersection peut être vide :
        la borne inférieure dépasse alors la borne supérieure.
        """
        t2 = self.vault.thickness / 2.0
        g = self.geo
        lo, hi = -t2, t2
        for j in range(g.n + 1):
            th = self.theta(j)
            k = H / (self._W[j] * math.sin(th) + H * math.cos(th))
            if k <= 0.0:
                return 1.0, -1.0
            d0 = self.thrust_offset(H, 0.0, j)
            a = (-t2 - d0) / k
            b = (t2 - d0) / k
            lo = max(lo, min(a, b))
            hi = min(hi, max(a, b))
        return lo, hi

    def slack(self, H: float) -> float:
        lo, hi = self.crown_interval(H)
        return hi - lo

    def is_feasible(self, H: float) -> bool:
        return self.slack(H) >= 0.0

    def _grid(self, n_pts: int = 400) -> list[float]:
        W = self.total_weight()
        lo, hi = 1e-4 * W, 1e3 * W
        return [lo * (hi / lo) ** (k / (n_pts - 1.0)) for k in range(n_pts)]

    def _best_thrust(self) -> tuple[float, float]:
        """Poussée de marge maximale et marge correspondante
        (grille logarithmique + section dorée)."""
        pts = self._grid()
        values = [self.slack(p) for p in pts]
        k = max(range(len(pts)), key=values.__getitem__)
        a = pts[k - 1] if k > 0 else 0.0
        b = pts[k + 1] if k + 1 < len(pts) else pts[-1] * 10.0
        invphi = (math.sqrt(5.0) - 1.0) / 2.0
        c, d = b - invphi * (b - a), a + invphi * (b - a)
        fc, fd = self.slack(c), self.slack(d)
        for _ in range(100):
            if fc > fd:
                b, d, fd = d, c, fc
                c = b - invphi * (b - a)
                fc = self.slack(c)
            else:
                a, c, fc = c, d, fd
                d = a + invphi * (b - a)
                fd = self.slack(d)
        H, s = (c, fc) if fc > fd else (d, fd)
        return H, s

    def is_stable(self) -> bool:
        return self._best_thrust()[1] >= 0.0

    def thrust_bounds(self) -> tuple[float, float, float, float]:
        """Bornes H_min / H_max de la poussée à la clé et excentricités de
        clé des lignes de poussée extrémales correspondantes."""
        H0, s0 = self._best_thrust()
        if s0 < 0.0:
            raise ValueError(
                "aucune ligne de poussée contenue dans l'épaisseur : "
                "voûte instable sous poids propre (augmenter l'épaisseur)"
            )

        def edge(h_in: float, h_out: float) -> float:
            while self.is_feasible(h_out):
                h_in = h_out
                h_out *= 2.0
            for _ in range(80):
                mid = 0.5 * (h_in + h_out)
                if self.is_feasible(mid):
                    h_in = mid
                else:
                    h_out = mid
            return h_in

        H_min = edge(H0, max(H0 / 2.0, 1e-12))
        H_max = edge(H0, H0 * 2.0)
        e_min = sum(self.crown_interval(H_min)) / 2.0
        e_max = sum(self.crown_interval(H_max)) / 2.0
        return H_min, H_max, e_min, e_max

    def hinges(self, H: float, e_crown: float) -> list[tuple[float, str]]:
        """Points où la ligne de poussée touche la limite de la maçonnerie
        (maxima locaux d'excentricité), sous forme (angle en degrés, face)."""
        half = self.vault.thickness / 2.0
        tol = half * (1.0 - 1e-4)
        ds = [abs(self.thrust_offset(H, e_crown, j)) for j in range(self.geo.n + 1)]
        out = []
        for j in range(self.geo.n + 1):
            left = ds[j - 1] if j > 0 else -math.inf
            right = ds[j + 1] if j + 1 <= self.geo.n else -math.inf
            if ds[j] >= left and ds[j] >= right and ds[j] > tol:
                face = "extrados" if self.thrust_offset(H, e_crown, j) > 0 else "intrados"
                out.append((math.degrees(self.theta(j)), face))
        return out

    def min_thickness(self, t_lo: float, t_hi: float) -> Vault:
        """Épaisseur minimale de stabilité par dichotomie."""
        for _ in range(40):
            t = 0.5 * (t_lo + t_hi)
            trial = Vault(self.vault.span, self.vault.rise, t,
                          self.vault.gamma, self.vault.n)
            if VaultAnalysis(trial).is_stable():
                t_hi = t
            else:
                t_lo = t
        return Vault(self.vault.span, self.vault.rise, t_hi,
                     self.vault.gamma, self.vault.n)

    def report(self) -> str:
        g = self.geo
        v = self.vault
        H_min, H_max, e_min, e_max = self.thrust_bounds()
        W = self.total_weight()
        lines = [
            "=== Analyse Méry–Heyman : voûte en berceau ===",
            f"Ouverture (portée)  : {v.span:.3f} m",
            f"Flèche              : {v.rise:.3f} m",
            f"Rayon moyen         : {g.R:.3f} m",
            f"Demi-angle au centre: {math.degrees(g.alpha):.3f} deg"
            + ("  (plein cintre)" if abs(g.alpha - math.pi / 2) < 1e-9 else ""),
            f"Épaisseur           : {v.thickness:.3f} m",
            f"Poids volumique     : {v.gamma:.2f} kN/m3",
            f"Voussoirs (1/2 voûte): {g.n}",
            f"Poids propre (par m): {W:.2f} kN/m",
            "",
            "Hypothèses de Heyman : traction nulle, compression infinie,",
            "glissement impossible (calcul par tranche de 1 m).",
            "",
            "--- Bornes de poussée à la clé ---",
            f"H_min = {H_min:.3f} kN/m  (excentricité de clé : {e_min:+.3f} m)",
            f"H_max = {H_max:.3f} kN/m  (excentricité de clé : {e_max:+.3f} m)",
            f"Rapport H_max/H_min = {H_max / H_min:.2f}",
        ]
        for label, H, ec in (("H_min", H_min, e_min),
                             ("H_max", H_max, e_max)):
            hg = self.hinges(H, ec)
            if hg:
                desc = ", ".join(f"{ang:.1f} deg ({face})" for ang, face in hg)
            else:
                desc = "aucune (ligne strictement intérieure)"
            lines.append(f"Contacts à la limite pour {label} : {desc}")
        return "\n".join(lines)

    def plot(self, path: str, H_min: float, e_min: float,
             H_max: float, e_max: float) -> None:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            raise SystemExit("matplotlib requis pour --plot (pip install matplotlib)")
        g = self.geo
        fig, ax = plt.subplots(figsize=(8, 6))
        for r, style, label in ((g.r_in, "-", "intrados"),
                               (g.R, ":", None),
                               (g.r_out, "-", "extrados")):
            th = [g.alpha * i / 400.0 for i in range(401)]
            xs = [r * math.sin(t) for t in th]
            ys = [r * math.cos(t) for t in th]
            ax.plot([-x for x in xs] + xs, ys + ys,
                    style, color="k" if label else "gray",
                    lw=1.0, label=label)
        for H, ec, color, name in ((H_min, e_min, "tab:red", "H_min"),
                                   (H_max, e_max, "tab:blue", "H_max")):
            xs, ys = [], []
            for j in range(g.n + 1):
                th = self.theta(j)
                d = ec if j == 0 else self.thrust_offset(H, ec, j)
                r = g.R + d
                xs.append(r * math.sin(th))
                ys.append(r * math.cos(th))
            ax.plot([-x for x in xs] + xs, ys + ys, color=color, lw=1.4,
                    label=f"ligne de poussée ({name})")
        ax.set_aspect("equal")
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_title("Méry–Heyman : ligne de poussée")
        ax.legend(loc="lower center", fontsize=8)
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        print(f"Figure enregistrée : {path}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Ligne de poussée Méry–Heyman pour une voûte maçonnée en arc de cercle")
    p.add_argument("--span", type=float, required=True, help="ouverture de la voûte (m)")
    p.add_argument("--rise", type=float, required=True, help="flèche de la voûte (m)")
    p.add_argument("--thickness", type=float, required=True, help="épaisseur radiale (m)")
    p.add_argument("--gamma", type=float, default=22.0, help="poids volumique (kN/m3, defaut 22)")
    p.add_argument("--n", type=int, default=200, help="nombre de voussoirs par demi-voûte (defaut 200)")
    p.add_argument("--plot", metavar="PNG", help="tracer les lignes de poussée dans un fichier PNG")
    p.add_argument("--min-thickness", action="store_true",
                   help="calculer aussi l'épaisseur minimale de stabilité")
    args = p.parse_args()

    vault = Vault(args.span, args.rise, args.thickness, args.gamma, args.n)
    analysis = VaultAnalysis(vault)
    print(analysis.report())
    H_min, H_max, e_min, e_max = analysis.thrust_bounds()
    if args.min_thickness:
        t_min = analysis.min_thickness(1e-4 * vault.thickness, 10.0 * vault.thickness)
        print()
        print(f"Épaisseur minimale de stabilité : {t_min.thickness:.4f} m "
              f"(t/R = {t_min.thickness / analysis.geo.R:.4f})")
        print(f"Facteur de sécurité géométrique (t/t_min) : "
              f"{vault.thickness / t_min.thickness:.2f}")
    if args.plot:
        analysis.plot(args.plot, H_min, e_min, H_max, e_max)


if __name__ == "__main__":
    main()

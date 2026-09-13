"""
Méthode de Méry-Heyman pour l'évaluation des voûtes en maçonnerie
==================================================================

Outil de contrôle d'ingénieur inspiré de la philosophie de LimitState:RING,
fondé sur la théorie de Heyman (1960) et la méthode de Méry (1840).

Principes (Heyman) :
  - résistance à la traction nulle (f_t = 0)
  - résistance en compression infinie (f_c = inf)
  - absence de glissement aux joints (T < N tan(phi))

Critère de stabilité (Heyman) :
  une ligne de poussée admissible = entièrement contenue dans l'épaisseur
  de la voûte sur toute sa longueur.

Critère de Méry (plus conservateur) :
  la ligne de poussée doit rester dans le tiers central de chaque section
  (|e| <= t/6) -> aucune traction, pas de fissuration.

Mécanisme de rupture (analyse limite, type RING) :
  lorsque 4 articulations se forment (ligne de poussée touchant l'intrados
  ou l'extrados en 4 points), la voûte devient un mécanisme -> ruine.

Adequacy Factor (AF) :
  AF = charge_rupture / charge_service

Avertissement
------------
Cet outil constitue un contrôle simplifié et NON une validation réglementaire.
Il ne remplace pas LimitState:RING, la méthode MEXE, un modèle EF ou une
évaluation réglementaire. Les résultats dépendent fortement de la géométrie
réelle, de la qualité de la maçonnerie et de l'état observé.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np


# ---------------------------------------------------------------------------
# Données d'entrée du pont étudié
# ---------------------------------------------------------------------------
#
# Géométrie : arc en demi-cercle (portée = 11 m, flèche = 5,5 m => R = 5,5 m)
#
# Épaisseur réelle (brique + meulière), variable selon l'angle :
#   Naissance (0°)   : 2,86 m  (brique 0,36 + meulière 2,50)
#   Rein (45°)        : 1,20 m  (brique 0,20 + meulière 1,00)
#   Clé (90°)         : 0,50 m  (brique 0,20 + meulière 0,30)
#
# L'épaisseur est interpolée entre ces points pour chaque angle.

# --- Géométrie ---
PORTANCE_L = 11.0        # portée (m)
FLECHE_F = 5.5            # flèche (m)
LARGEUR_B = 3.8           # largeur participante (m)

# --- Épaisseur variable (points de calage) ---
# (angle_deg, epaisseur_totale_m)
EP_T = [
    (0.0, 2.86),
    (15.0, 2.30),
    (30.0, 1.80),
    (45.0, 1.20),
    (60.0, 0.90),
    (75.0, 0.65),
    (90.0, 0.50),
]

# --- Poids volumiques (kN/m³) ---
GAMMA_BRIQUE = 18.0
GAMMA_MEULIERE = 22.0
GAMMA_REMBLAI = 21.0      # stabilisé + revêtement / chaussée

# --- Épaisseur de chaussée ---
EPA_CHAUSSEE = 0.40       # m (appliquée au-dessus de l'extrados)

# --- Charge roulante ---
CHARGE_VEHICULE = 120.0   # kN (camion 12 t)

# --- Discrétisation ---
N_DIV = 36                # secteurs de 5° (0° à 180°)


@dataclass
class Section:
    """Représente une section (voussoir) de la voûte discrétisée."""
    i: int
    theta_deg: float
    theta_rad: float
    x: float           # abscisse intrados
    y: float           # ordonnée intrados
    t: float           # épaisseur totale (m)
    ds: float          # longueur d'arc élémentaire (m)
    W_voute: float     # poids propre du voussoir (kN)
    W_remblai: float   # poids remblai/chaussée au-dessus (kN)
    W_total: float     # poids total (kN)


@dataclass
class ResultatSection:
    """Résultats du calcul de la ligne de poussée pour une section."""
    i: int
    theta_deg: float
    V_cumul: float     # effort vertical cumulé depuis la naissance gauche
    N: float           # effort normal
    M: float           # moment
    e: float           # excentricité (m)
    t_sur_6: float     # limite tiers central (m)
    t_sur_2: float      # demi-épaisseur (m)
    etat_mery: str     # OK / CHARNIERE
    etat_heyman: str   # OK / ART_INT / ART_EXT


@dataclass
class ResultatGlobal:
    """Résultats synthétiques du calcul."""
    H: float                      # poussée horizontale (kN)
    poids_total: float           # poids propre total (kN)
    e_max: float                 # excentricité maximale (m)
    t_min_sur_6: float            # t_min/6
    FS_mery: float               # facteur de sécurité (tiers central)
    nb_articulations_heyman: int # nb de points hors épaisseur
    fs_interpretation: str
    sections: list = field(default_factory=list)
    position_critique_deg: float = 0.0
    AF: float = 0.0              # Adequacy Factor


def epaisseur_variable(theta_deg: float) -> float:
    """Interpole l'épaisseur totale de la voûte selon l'angle (°, 0..180)."""
    a = abs(theta_deg) if theta_deg <= 90.0 else 180.0 - theta_deg
    a = max(0.0, min(90.0, a))
    pts = sorted(EP_T, key=lambda p: p[0])
    if a <= pts[0][0]:
        return pts[0][1]
    if a >= pts[-1][0]:
        return pts[-1][1]
    for j in range(len(pts) - 1):
        a0, t0 = pts[j]
        a1, t1 = pts[j + 1]
        if a0 <= a <= a1:
            return t0 + (t1 - t0) * (a - a0) / (a1 - a0)
    return pts[-1][1]


def discretiser(n_div: int = N_DIV) -> list:
    """Construit la liste des sections (voussoirs) de la voûte."""
    L = PORTANCE_L
    R = L / 2.0
    dtheta_deg = 180.0 / n_div
    dtheta_rad = math.radians(dtheta_deg)
    ds = R * dtheta_rad
    sections = []
    for i in range(n_div + 1):
        theta_deg = i * dtheta_deg
        theta_rad = math.radians(theta_deg)
        x = R * math.cos(theta_rad)
        y = R * math.sin(theta_rad)
        t = epaisseur_variable(theta_deg)
        # Poids propre du voussoir (épaisseur x largeur x longueur d'arc x gamma)
        # On prend un gamma moyen pondéré selon la composition brique/meulière.
        # Approximation : la part de meulière augmente vers les naissances.
        gamma = _gamma_moyen(theta_deg)
        W_voute = t * LARGEUR_B * ds * gamma
        # Poids du remblai/chaussée au-dessus de l'extrados.
        # Hauteur de remblai = f - y (distance verticale jusqu'au sommet).
        h_remblai = max(0.0, FLECHE_F - y) + EPA_CHAUSSEE
        W_remblai = h_remblai * LARGEUR_B * ds * GAMMA_REMBLAI
        W_total = W_voute + W_remblai
        sections.append(Section(i, theta_deg, theta_rad, x, y, t, ds,
                                W_voute, W_remblai, W_total))
    return sections


def _gamma_moyen(theta_deg: float) -> float:
    """Gamma moyen pondéré brique/meulière (kN/m³) selon la position."""
    a = abs(theta_deg) if theta_deg <= 90.0 else 180.0 - theta_deg
    a = max(0.0, min(90.0, a))
    # Part de meulière croissante de la clé (0) vers la naissance (1)
    frac_meuliere = a / 90.0
    return GAMMA_BRIQUE * (1.0 - frac_meuliere) + GAMMA_MEULIERE * frac_meuliere


def _positionner_charge(sections: list, theta_camion_deg: float,
                        charge: float) -> list:
    """Ajoute une charge concentrée au voussoir le plus proche de theta_camion."""
    W_eff = [s.W_total for s in sections]
    idx = int(round(theta_camion_deg / (180.0 / N_DIV)))
    idx = max(0, min(len(W_eff) - 1, idx))
    W_eff[idx] += charge
    return W_eff


def calculer_ligne_poussee(sections: list, theta_camion_deg: float = 90.0,
                           charge: float = CHARGE_VEHICULE,
                           fast: bool = False) -> ResultatGlobal:
    """Calcule la ligne de poussée pour une position de camion donnée.

    Formulation funiculaire (free body depuis la naissance droite) :
      M_i  = M_R + V_R*(R - x_i) - H*y_i + Σ_{θ_j<θ_i} W_j*(x_i - x_j)
      V_i  = V_R - Σ_{θ_j<θ_i} W_j
      N_i  = sqrt(H^2 + V_i^2)
      e_i  = M_i / N_i

    V_L, V_R fixés par la statique globale ; H (poussée) et M_R (moment
    redondant à la naissance, voûte hyperstatique) optimisés pour rendre la
    ligne de poussée admissible (minimisation de l'excentricité normalisée
    max|e_i|/(t_i/2)), conformément au théorème statique de Heyman.
    """
    from scipy.optimize import minimize

    L = PORTANCE_L
    f = FLECHE_F
    R = L / 2.0
    W_eff = _positionner_charge(sections, theta_camion_deg, charge)
    poids_total = sum(s.W_total for s in sections)
    n = len(sections)
    x = np.array([s.x for s in sections])
    y = np.array([s.y for s in sections])
    t_arr = np.array([s.t for s in sections])
    W = np.array(W_eff, dtype=float)
    theta_arr = np.array([s.theta_deg for s in sections])

    # Précalcul : sommes cumulées depuis la naissance droite (θ=0).
    # W_cumul[i] = Σ_{j<i} W_j ; Wx_cumul[i] = Σ_{j<i} W_j * x_j
    W_cumul = np.zeros(n)
    Wx_cumul = np.zeros(n)
    cumw = 0.0
    cumwx = 0.0
    for i in range(n):
        W_cumul[i] = cumw
        Wx_cumul[i] = cumwx
        cumw += W[i]
        cumwx += W[i] * x[i]

    # Réactions verticales par statique globale
    G = float(W.sum())
    V_L = float(np.sum(W * (R - x)) / (2.0 * R))
    V_R = G - V_L
    # Termes indépendants de (H, M_R) : V_R*(R - x_i) + M_poids_i
    base_M = V_R * (R - x) + (x * W_cumul - Wx_cumul)
    t_sur_6_arr = t_arr / 6.0
    t_sur_2_arr = t_arr / 2.0

    def e_pour_params(H: float, M_R: float):
        M = M_R + base_M - H * y
        V_i = V_R - W_cumul
        N = np.sqrt(H ** 2 + V_i ** 2)
        with np.errstate(divide="ignore", invalid="ignore"):
            e = np.where(N > 0, M / N, 0.0)
        return M, V_i, N, e

    def calcul_pour_params(H: float, M_R: float) -> list:
        M, V_i, N, e = e_pour_params(H, M_R)
        res = []
        for i in range(n):
            ei = float(e[i])
            t2 = float(t_sur_2_arr[i])
            t6 = float(t_sur_6_arr[i])
            etat_mery = "OK" if abs(ei) <= t6 else "CHARNIERE"
            if ei >= t2:
                etat_heyman = "ART_EXT"
            elif ei <= -t2:
                etat_heyman = "ART_INT"
            else:
                etat_heyman = "OK"
            res.append(ResultatSection(i, float(theta_arr[i]), float(V_i[i]),
                                       float(N[i]), float(M[i]), ei,
                                       t6, t2, etat_mery, etat_heyman))
        return res

    Q = G
    H0 = Q * L ** 2 / (8.0 * f)

    def cout(params) -> float:
        H, M_R = params
        if H <= 0:
            return 1e12
        _, _, _, e = e_pour_params(H, M_R)
        return float(np.max(np.abs(e) / t_sur_2_arr))

    best = None
    best_cost = 1e18
    starts = [(H0, 0.0)] if fast else [
        (H0 * 0.3, -H0 * R * 0.5), (H0 * 0.6, 0.0), (H0, H0 * R * 0.5),
        (H0 * 1.5, 0.0)]
    maxit = 200 if fast else 500
    for Hstart, Mstart in starts:
        opt = minimize(cout, [Hstart, Mstart], method="Nelder-Mead",
                       options={"xatol": 1e-2, "fatol": 1e-4,
                                "maxiter": maxit})
        if opt.fun < best_cost:
            best_cost = opt.fun
            best = opt.x
    H_opt, M_R_opt = best
    res_sections = calcul_pour_params(H_opt, M_R_opt)

    e_max = max(abs(r.e) for r in res_sections)
    t_min = min(s.t for s in sections)
    t_min_sur_6 = t_min / 6.0
    FS_mery = (t_min_sur_6 / e_max) if e_max > 0 else float("inf")

    nb_art = sum(1 for r in res_sections if r.etat_heyman != "OK")

    fs_interp = _interp_fs(FS_mery)

    return ResultatGlobal(
        H=H_opt,
        poids_total=poids_total,
        e_max=e_max,
        t_min_sur_6=t_min_sur_6,
        FS_mery=FS_mery,
        nb_articulations_heyman=nb_art,
        fs_interpretation=fs_interp,
        sections=res_sections,
        position_critique_deg=theta_camion_deg,
        AF=0.0,
    )


def _interp_fs(fs: float) -> str:
    if fs < 1.0:
        return "Instable"
    if fs < 1.2:
        return "Limite"
    if fs < 1.5:
        return "Acceptable"
    if fs < 2.0:
        return "Bon"
    return "Tres bon / robuste"


def recherche_position_critique(sections: list,
                                 charge: float = CHARGE_VEHICULE) -> ResultatGlobal:
    """Fait varier la position du camion (0° à 180°) et retient la position
    la plus défavorable (excentricité maximale)."""
    best = None
    best_e = -1.0
    for k in range(0, N_DIV + 1):
        theta = k * (180.0 / N_DIV)
        res = calculer_ligne_poussee(sections, theta, charge, fast=True)
        if res.e_max > best_e:
            best_e = res.e_max
            best = res
    return best


def calcul_AF(sections: list,
              charge_service: float = CHARGE_VEHICULE) -> tuple:
    """Calcule l'Adequacy Factor par augmentation du multiplicateur de charge
    jusqu'à formation de 4 articulations (mécanisme de rupture, type RING).

    Renvoie (AF, charge_rupture, lambda_mult, position_critique_deg).
    """
    from scipy.optimize import minimize_scalar

    def nb_art_pour_lambda(lam: float) -> tuple:
        charge = lam * charge_service
        # On cherche la position la plus défavorable
        res = recherche_position_critique(sections, charge)
        return res.nb_articulations_heyman, res

    # Recherche dichotomique du lambda où nb_art >= 4
    lam_lo, lam_hi = 1.0, 1.0
    nb, _ = nb_art_pour_lambda(lam_lo)
    if nb >= 4:
        return (1.0, charge_service, 1.0, 0.0)
    # On augmente lam_hi jusqu'à dépasser 4 articulations
    for _ in range(60):
        lam_hi *= 1.5
        nb, _ = nb_art_pour_lambda(lam_hi)
        if nb >= 4:
            break
        if lam_hi > 1e6:
            break
    # Dichotomie
    for _ in range(80):
        lam_mid = 0.5 * (lam_lo + lam_hi)
        nb, _ = nb_art_pour_lambda(lam_mid)
        if nb >= 4:
            lam_hi = lam_mid
        else:
            lam_lo = lam_mid
        if (lam_hi - lam_lo) < 1e-3:
            break
    lam_rupt = lam_hi
    charge_rupture = lam_rupt * charge_service
    AF = charge_rupture / charge_service
    # Position critique à la rupture
    _, res = nb_art_pour_lambda(lam_rupt)
    return AF, charge_rupture, lam_rupt, res.position_critique_deg


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def afficher_resultats(res: ResultatGlobal) -> None:
    print("=" * 78)
    print("  METHODE DE MERY-HEYMAN - EVALUATION DE VOUTE EN MACONNERIE")
    print("=" * 78)
    print(f"  Pont : portée L = {PORTANCE_L} m,  flèche f = {FLECHE_F} m, "
          f"largeur B = {LARGEUR_B} m")
    print(f"  Charge véhicule (service) = {CHARGE_VEHICULE} kN (camion 12 t)")
    print("-" * 78)
    print(f"  Poussée horizontale H (optimisée)   : {res.H:10.1f} kN")
    print(f"  Poids propre + remblai (total)       : {res.poids_total:10.1f} kN")
    print(f"  Excentricité maximale  e_max         : {res.e_max:10.4f} m")
    print(f"  t_min/6 (tiers central mini)         : {res.t_min_sur_6:10.4f} m")
    print(f"  Facteur de sécurité (Méry, tiers) FS : {res.FS_mery:10.2f}  "
          f"-> {res.fs_interpretation}")
    print(f"  Articulations Heyman (hors épaisseur): "
          f"{res.nb_articulations_heyman}")
    print("-" * 78)
    print(f"  Position critique du camion         : "
          f"{res.position_critique_deg:6.1f} °")
    print(f"  Adequacy Factor (AF)                 : {res.AF:10.2f}")
    print("-" * 78)
    print("  Détail par section :")
    hdr = (f"{'i':>3} {'θ°':>6} {'V_cum':>9} {'N':>9} {'M':>10} "
           f"{'e':>9} {'t/6':>7} {'t/2':>7} {'Méry':>10} {'Heyman':>8}")
    print(hdr)
    print("-" * len(hdr))
    for r in res.sections:
        print(f"{r.i:>3} {r.theta_deg:>6.1f} {r.V_cumul:>9.1f} {r.N:>9.1f} "
              f"{r.M:>10.1f} {r.e:>9.4f} {r.t_sur_6:>7.3f} {r.t_sur_2:>7.3f} "
              f"{r.etat_mery:>10} {r.etat_heyman:>8}")
    print("=" * 78)
    print("  Critère Méry   : |e| <= t/6  (tiers central, pas de traction)")
    print("  Critère Heyman : |e| <= t/2  (ligne dans l'épaisseur)")
    print("  Ruine (RING)   : 4 articulations -> mécanisme")
    print("=" * 78)


def main():
    print("Discrétisation de la voûte en", N_DIV, "secteurs de",
          180.0 / N_DIV, "° ...")
    sections = discretiser(N_DIV)

    print("\n[1] Ligne de poussée - camion à la clé (90°)")
    res_cle = calculer_ligne_poussee(sections, 90.0, CHARGE_VEHICULE)
    afficher_resultats(res_cle)

    print("\n[2] Recherche de la position critique du camion")
    res_crit = recherche_position_critique(sections, CHARGE_VEHICULE)
    print(f"  Position critique : {res_crit.position_critique_deg:.1f}°, "
          f"e_max = {res_crit.e_max:.4f} m, "
          f"FS(Méry) = {res_crit.FS_mery:.2f}")

    print("\n[3] Calcul de l'Adequacy Factor (mécanisme 4 articulations)")
    AF, P_rupt, lam, pos = calcul_AF(sections, CHARGE_VEHICULE)
    print(f"  Multiplicateur de rupture λ = {lam:.2f}")
    print(f"  Charge de rupture           = {P_rupt:.1f} kN")
    print(f"  Adequacy Factor AF          = {AF:.2f}  "
          f"(position critique ≈ {pos:.1f}°)")

    res_crit.AF = AF
    print("\n[4] Interprétation AF : ", end="")
    if AF < 1.0:
        print("Ruine")
    elif AF < 1.5:
        print("Limite")
    elif AF < 2.0:
        print("Acceptable")
    elif AF < 3.0:
        print("Bon")
    else:
        print("Très robuste")

    # Export Excel
    try:
        import generer_excel
        print("\n[5] Génération du classeur Excel ...")
        generer_excel.generer(res_cle, res_crit, AF, P_rupt, lam, pos,
                              sections)
        print("  -> voute_mery_heyman.xlsx généré.")
    except Exception as exc:
        print(f"  (export Excel non disponible : {exc})")


if __name__ == "__main__":
    main()

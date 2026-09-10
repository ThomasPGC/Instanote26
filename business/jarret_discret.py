#! /usr/bin/python3
# coding: utf-8

"""Renfort d'épaule (jarret) discrétisé — roadmap moteur, étape 3.

Ce module remplace, **côté backend PyNite uniquement** (`solveur_pynite.py`),
l'approximation historique du renfort d'épaule — 1 barre prismatique de hauteur
d'âme constante `1,66 · h` (fonction `calcport.jarret()`) — par une suite de
`N_DISC_JARRET` sous-barres dont la section décroît linéairement du genou vers
la sortie de jarret.

Le solveur *legacy* (`calcport._SolveurLegacy`) n'est **pas** modifié : il reste
l'oracle de l'ancien modèle. La parité legacy ↔ PyNite n'est donc vérifiée que
dans le mode « ancien modèle » (`n_disc = 1`), où ce module reproduit à
l'identique la topologie 7 nœuds / 6 barres de `calcport.def_noeud_barres`.

Contenu :
  - `caracs_section_jarret(arba, h_ratio)` : caractéristiques (Iy, A, Avz,
    Wpl.y) d'une section de jarret à 3 semelles + congés de raccordement `r`,
    reconstituée par intégration du contour réel (polygone + arcs de congé).
    Recoupée avec PropSection v1.0.4 (cf. `validation/jarrets/`, self-check en
    `__main__`).
  - `sections_jarret(arba, n_disc)` : la liste des `n_disc` sections, hauteur
    d'âme échantillonnée au milieu de chaque tronçon (`2 · h` au genou →
    `1 · h` à la sortie).
  - `construire_topologie(geom, n_disc)` : le descripteur de modèle discrétisé
    (coords, connectivité, cartes sémantiques barre/nœud).
  - `expanser_charges(charges_logiques, topo)` : projette les tableaux de
    charges « logiques » (6 segments / 21 slots nodaux) de `chargement_nv` sur
    le modèle discrétisé.
  - `diagnostic_cisaillement(...)` : diagnostic a posteriori de la déformation
    d'effort tranchant (non bloquant, ne change aucune section).

Unités : cm et daN, comme `calcport`.
"""

import os
from functools import lru_cache
from math import pi, cos, sin

from calcport import IPE, E, def_noeud_barres

# Nombre de sous-barres par renfort d'épaule. 1 = ancien modèle (barre unique,
# section `calcport.jarret()`), utilisé pour la parité legacy ↔ PyNite.
N_DISC_JARRET = int(os.environ.get("N_DISC_JARRET", "6"))

# Loi de hauteur d'âme du jarret : DEUX fois la hauteur de traverse au genou,
# UNE fois à la sortie (le 1,66 historique était une moyenne des deux).
COEFF_H_GENOU = 2.0
COEFF_H_SORTIE = 1.0

# Poids propre acier : daN/cm de barre par cm² de section (idem
# `crea_matrice_force` / `solveur_pynite.DENS_LIN`).
DENS_LIN = 7.85e-3

# ==========================================================================
#  Caractéristiques de section — intégration du contour réel
# ==========================================================================

def _profil(nom):
    """dict des cotes catalogue d'un profil IPE (mm), + Nom."""
    d = IPE.dict_carac(nom)
    if d is None:
        raise ValueError(f"profil inconnu : {nom!r}")
    return d


def _arc(cx, cz, r, a0, a1, n):
    """Points d'un arc de cercle (centre cx,cz ; rayon r) de l'angle a0 à a1."""
    return [(cx + r * cos(a0 + (a1 - a0) * k / n),
             cz + r * sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


def _demi_contour_droit(b, tf, tw, r, H, zi, n_arc, avec_interm=True):
    """Demi-contour DROIT (x ≥ 0) du jarret, du bas vers le haut, en cm.

    Section en I à **3 semelles** : inférieure (dessus à z = tf), intermédiaire
    (centrée à z = `zi`, = semelle inf de la traverse nue), supérieure (dessous
    à z = H − tf), reliées par une âme d'épaisseur `tw`, hauteur totale `H`.
    Congé de rayon `r` à chaque jonction semelle/âme **quand la place le
    permet**, sinon angle vif — cas des tronçons proches de la sortie, où la
    semelle intermédiaire se rapproche de la semelle inférieure. La semelle
    intermédiaire est toujours présente : à la sortie, la section tend vers
    « traverse + semelle de gousset », pas vers la traverse nue.

    `avec_interm=False` : I classique à 2 semelles (uniquement pour le garde-fou
    de non-régression du contour, cf. `__main__`).
    """
    xw = tw / 2.0
    xb = b / 2.0

    p = [(xb, 0.0), (xb, tf), (xw + r, tf)]                     # semelle inférieure
    p += _arc(xw + r, tf + r, r, -pi / 2, -pi, n_arc)           # congé semelle inf → âme

    if avec_interm:
        zi = max(zi, tf + tf / 2.0)          # garde la semelle intermédiaire au-dessus de la semelle inf
        zf = zi - tf / 2.0
        # jonction âme (gousset, soudée) → dessous de la semelle intermédiaire :
        # angle vif, PAS de congé (recoupé PropSection « section paramétrée n°7 » :
        # 6 congés au total, seul le côté « laminé » de la semelle intermédiaire
        # est raccordé).
        p.append((xw, zf))
        p.append((xb, zf))                                      # tip semelle interm. (dessous)
        p.append((xb, zi + tf / 2.0))                           # tip semelle interm. (dessus)
        if (H - tf - r) - (zi + tf / 2.0) >= r:                 # congé dessus semelle interm. → âme (laminé)
            p += [(xw + r, zi + tf / 2.0)] + _arc(xw + r, zi + tf / 2.0 + r, r, -pi / 2, -pi, n_arc)
        else:
            p.append((xw, zi + tf / 2.0))

    p.append((xw, H - tf - r))                                  # congé âme → semelle sup
    p += _arc(xw + r, H - tf - r, r, pi, pi / 2, n_arc)
    p.append((xb, H - tf))
    p.append((xb, H))
    return p


def _moments_polygone(pts):
    """(A, zG, Iy, Iz) d'un polygone fermé donné par ses sommets (x, z), en cm.

    Iy = ∫ (z − zG)² dA  (inertie d'axe fort, z vertical) ;
    Iz = ∫ x² dA         (axe faible ; polygone symétrique en x → xG = 0).
    """
    A2 = 0.0
    Cz = 0.0
    Izz_o = 0.0   # ∫ z² dA autour de z = 0
    Ixx_o = 0.0   # ∫ x² dA autour de x = 0
    n = len(pts)
    for i in range(n):
        x0, z0 = pts[i]
        x1, z1 = pts[(i + 1) % n]
        cross = x0 * z1 - x1 * z0
        A2 += cross
        Cz += (z0 + z1) * cross
        Izz_o += (z0 * z0 + z0 * z1 + z1 * z1) * cross
        Ixx_o += (x0 * x0 + x0 * x1 + x1 * x1) * cross
    A = A2 / 2.0
    if A < 0:                       # oriente le polygone (aire positive)
        A, Cz, Izz_o, Ixx_o = -A, -Cz, -Izz_o, -Ixx_o
    zG = Cz / (6.0 * A)
    Iy = Izz_o / 12.0 - A * zG * zG
    Iz = Ixx_o / 12.0
    return A, zG, Iy, Iz


def _clip_bas(pts, zc):
    """Sous-polygone des points de z ≤ zc (Sutherland–Hodgman, arête horizontale)."""
    out = []
    n = len(pts)
    for i in range(n):
        x0, z0 = pts[i]
        x1, z1 = pts[(i + 1) % n]
        in0, in1 = z0 <= zc, z1 <= zc
        if in0:
            out.append((x0, z0))
        if in0 != in1:
            t = (zc - z0) / (z1 - z0)
            out.append((x0 + t * (x1 - x0), zc))
    return out


def _wpl_y_polygone(pts, A, zG):
    """Module plastique d'axe fort : Wpl,y = S_bas + S_haut, moments statiques
    (en valeur absolue) des deux moitiés autour de l'axe neutre plastique — la
    cote `zc` qui partage l'AIRE en deux. Section asymétrique (3 semelles
    décalées) : l'ANP ≠ le centre de gravité, il faut donc les deux moments,
    pas le double de l'un."""
    zlo = min(z for _, z in pts)
    zhi = max(z for _, z in pts)
    for _ in range(60):
        zc = 0.5 * (zlo + zhi)
        sub = _clip_bas(pts, zc)
        a_bas = _moments_polygone(sub)[0] if len(sub) >= 3 else 0.0
        if a_bas < A / 2.0:
            zlo = zc
        else:
            zhi = zc
    zc = 0.5 * (zlo + zhi)
    a_bas, zg_bas, _, _ = _moments_polygone(_clip_bas(pts, zc))
    a_haut = A - a_bas
    # A·zG = a_bas·zg_bas + a_haut·zg_haut  ->  zg_haut
    zg_haut = (A * zG - a_bas * zg_bas) / a_haut
    return abs(a_bas * (zc - zg_bas)) + abs(a_haut * (zg_haut - zc))


@lru_cache(maxsize=None)
def _caracs_cache(arba, h_ratio_q, n_arc):
    """Cœur de `caracs_section_jarret`, mémoïsé (h_ratio quantifié à 1e-4)."""
    return _caracs_section_jarret_impl(arba, h_ratio_q, n_arc)


def caracs_section_jarret(arba, h_ratio, n_arc=24):
    """Caractéristiques d'un tronçon de renfort d'épaule.

    `arba` : nom du profil IPE de la traverse (ex. "IPE 400").
    `h_ratio` : hauteur totale du tronçon / hauteur de la traverse, dans
        [`COEFF_H_SORTIE`, `COEFF_H_GENOU`] = [1, 2]. La semelle intermédiaire
        est placée à la profondeur `h` sous la fibre supérieure (position de la
        semelle inférieure de la traverse nue).

    Renvoie `{"Iy", "A", "Avz", "Wpl.y"}` en cm / cm² / cm⁴ / cm³ — mêmes clés
    que `calcport.jarret()`. Mémoïsé (appelé des dizaines de fois par
    `optimise_IPE`, pour un jeu de `h_ratio` fixe).
    """
    return dict(_caracs_cache(arba, round(h_ratio, 4), n_arc))


def _caracs_section_jarret_impl(arba, h_ratio, n_arc):
    d = _profil(arba)
    b = d["b"] / 10.0
    tf = d["tf"] / 10.0
    tw = d["tw"] / 10.0
    r = d["r"] / 10.0
    h = d["h"] / 10.0

    H = h_ratio * h
    zi = (h_ratio - 1.0) * h          # cote de la semelle intermédiaire / fibre inf

    demi = _demi_contour_droit(b, tf, tw, r, H, zi, n_arc)
    pts = demi + [(-x, z) for x, z in reversed(demi)]
    A, zG, Iy, _Iz = _moments_polygone(pts)
    wpl = _wpl_y_polygone(pts, A, zG)

    # Aire de cisaillement d'axe fort ≈ âme dégagée (les semelles horizontales,
    # intermédiaire comprise, ne portent pas d'effort tranchant vertical).
    avz = tw * (H - 2.0 * tf)

    return {"Iy": Iy, "A": A, "Avz": avz, "Wpl.y": wpl}


def sections_jarret(arba, n_disc=None):
    """Liste des `n_disc` sections du renfort d'épaule, du genou vers la sortie.

    `h_ratio` échantillonné au **milieu** de chaque tronçon :
        h_ratio_k = COEFF_H_GENOU − (COEFF_H_GENOU − COEFF_H_SORTIE)·(k+0.5)/n
    (k = 0 côté genou). Avec `n_disc = 1`, renvoie la section
    `calcport.jarret(arba)` d'origine (barre prismatique `1,66·h`) — mode
    « ancien modèle », parité legacy.
    """
    if n_disc is None:
        n_disc = N_DISC_JARRET
    if n_disc == 1:
        from calcport import jarret
        return [jarret(arba)]
    span = COEFF_H_GENOU - COEFF_H_SORTIE
    return [caracs_section_jarret(arba, COEFF_H_GENOU - span * (k + 0.5) / n_disc)
            for k in range(n_disc)]


# ==========================================================================
#  self-check : recoupement PropSection (validation/jarrets/*.png)
# ==========================================================================
# PropSection v1.0.4, « Section Paramétrée » n°7 (I à 3 semelles + congés r).
# hr = profondeur de la semelle intermédiaire sous la fibre sup = (h_ratio-1)*h.
# Grandeurs relevées : repère principal (centroïdal) — A, IyG (axe fort), IzG,
# zG mesuré depuis la fibre inférieure.
_REF_PROPSECTION = [
    # (profil, h_ratio,           A,        IyG,        IzG,      zG)
    ("IPE 160", 1.0 + 80. / 160., 30.180,   2269.427,   102.490,  11.278),
    ("IPE 160", 1.0 + 152. / 160., 33.780,  4065.263,   102.565,  15.601),
    ("IPE 300", 1.0 + 150. / 300., 80.839,  21666.833,  905.791,  21.107),
    ("IPE 300", 1.0 + 289. / 300., 90.708,  39244.472,  906.206,  29.457),
    ("IPE 450", 1.0 + 225. / 450., 148.468, 88094.233,  2514.250, 31.758),
]

if __name__ == "__main__":
    print(f"{'profil':>9}{'h_ratio':>9}  {'grandeur':<6}"
          f"{'calcul':>13}{'PropSection':>13}{'écart %':>9}")
    emax = 0.0
    for prof, hr, A_ref, Iy_ref, Iz_ref, zG_ref in _REF_PROPSECTION:
        d = _profil(prof)
        b, tf, tw, r, h = (d[k] / 10.0 for k in ("b", "tf", "tw", "r", "h"))
        demi = _demi_contour_droit(b, tf, tw, r, hr * h, (hr - 1.0) * h, 24)
        pts = demi + [(-x, z) for x, z in reversed(demi)]
        A, zG, Iy, Iz = _moments_polygone(pts)
        for nom, val, ref in (("A", A, A_ref), ("IyG", Iy, Iy_ref),
                              ("IzG", Iz, Iz_ref), ("zG", zG, zG_ref)):
            e = 100.0 * (val - ref) / ref
            emax = max(emax, abs(e))
            print(f"{prof:>9}{hr:>9.4f}  {nom:<6}{val:>13.3f}{ref:>13.3f}{e:>9.3f}")
        print()
    print(f"écart absolu max sur A/IyG/IzG/zG : {emax:.2f} %")

    print("\nGarde-fou intégrateur : contour à 2 semelles, hauteur h, doit "
          "retomber sur l'IPE 300 catalogue (A=53,8 Iy=8356 Wpl.y=628,4) :")
    d = _profil("IPE 300")
    b, tf, tw, r, h = (d[k] / 10.0 for k in ("b", "tf", "tw", "r", "h"))
    demi = _demi_contour_droit(b, tf, tw, r, h, 0.0, 24, avec_interm=False)
    pts = demi + [(-x, z) for x, z in reversed(demi)]
    A, zG, Iy, Iz = _moments_polygone(pts)
    print(f"  A={A:.2f}  Iy={Iy:.0f}  Iz={Iz:.1f}  Wpl.y={_wpl_y_polygone(pts, A, zG):.1f}")

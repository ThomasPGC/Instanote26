#! /usr/bin/python3
# coding: utf-8

"""Renfort d'épaule (jarret) discrétisé — roadmap moteur, étape 3.

Ce module remplace, **côté backend PyNite uniquement** (`solveur_pynite.py`),
l'approximation historique du renfort d'épaule — 1 barre prismatique de hauteur
d'âme constante `1,66 · h` (fonction `calcport.jarret()`) — par une suite de
`N_DISC_JARRET` sous-barres dont la section décroît linéairement de l'épaule vers
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
    d'âme échantillonnée au milieu de chaque tronçon (`2 · h` à l'épaule →
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

# Loi de hauteur d'âme du jarret : DEUX fois la hauteur de traverse à l'épaule,
# UNE fois à la sortie (le 1,66 historique était une moyenne des deux).
COEFF_H_EPAULE = 2.0
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
        [`COEFF_H_SORTIE`, `COEFF_H_EPAULE`] = [1, 2]. La semelle intermédiaire
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
    """Liste des `n_disc` sections du renfort d'épaule, de l'épaule vers la sortie.

    `h_ratio` échantillonné au **milieu** de chaque tronçon :
        h_ratio_k = COEFF_H_EPAULE − (COEFF_H_EPAULE − COEFF_H_SORTIE)·(k+0.5)/n
    (k = 0 côté épaule). Avec `n_disc = 1`, renvoie la section
    `calcport.jarret(arba)` d'origine (barre prismatique `1,66·h`) — mode
    « ancien modèle », parité legacy.
    """
    if n_disc is None:
        n_disc = N_DISC_JARRET
    if n_disc == 1:
        from calcport import jarret
        return [jarret(arba)]
    span = COEFF_H_EPAULE - COEFF_H_SORTIE
    return [caracs_section_jarret(arba, COEFF_H_EPAULE - span * (k + 0.5) / n_disc)
            for k in range(n_disc)]


def _h_ratios(n_disc):
    """h_ratio au milieu de chaque tronçon, de l'épaule vers la sortie."""
    span = COEFF_H_EPAULE - COEFF_H_SORTIE
    return [COEFF_H_EPAULE - span * (k + 0.5) / n_disc for k in range(n_disc)]


def offset_axe_neutre(arba, h_ratio, n_arc=24):
    """Distance (cm, > 0 = vers le bas) entre la fibre moyenne de la **traverse
    nue** et le centre de gravité de la section de jarret à `h_ratio`.

    [PROTOTYPE étape 3] Sert à placer les nœuds du jarret sur son axe neutre
    (théorie des poutres) plutôt que sur la ligne de la traverse.
    """
    d = _profil(arba)
    b, tf, tw, r, h = (d[k] / 10.0 for k in ("b", "tf", "tw", "r", "h"))
    H = h_ratio * h
    demi = _demi_contour_droit(b, tf, tw, r, H, (h_ratio - 1.0) * h, n_arc)
    pts = demi + [(-x, z) for x, z in reversed(demi)]
    _A, zG, _Iy, _Iz = _moments_polygone(pts)
    return (H - h / 2.0) - zG          # fibre moyenne traverse (H − h/2 depuis la fibre inf) − zG


# ==========================================================================
#  Topologie du portique discrétisé
# ==========================================================================

class Topologie:
    """Descripteur géométrique du portique, renfort d'épaule discrétisé en
    `n_disc` tronçons par côté.

    - `coords`  : liste de (X, Y) en cm, `nN` nœuds. Les 7 premiers (N0..N6)
      sont EXACTEMENT ceux de `calcport.def_noeud_barres` (mêmes indices, même
      sens) ; les nœuds intérieurs de jarret sont ajoutés à la fin (N7…).
    - `conn`    : liste de (i, j), `nbar` barres, de gauche à droite :
        poteau G, [n_disc tronçons jarret G], traverse G, traverse D,
        [n_disc tronçons jarret D], poteau D.
    - `roles`   : par barre, `("poteau",)` | `("traverse",)` |
      `("jarret", t)` où `t` = index du tronçon **depuis l'épaule** (0 = épaule).
    - cartes sémantiques : `node_tete_g` (1), `node_tete_d` (5),
      `node_faitage` (3), `node_sortie_jarret_g` (2), `node_sortie_jarret_d` (4)
      — inchangées car N0..N6 gardent leurs indices ; `bars_jarret_g` /
      `bars_jarret_d` (index des barres), `bar_epaule_g` / `bar_epaule_d`.
    """

    __slots__ = ("n_disc", "coords", "conn", "roles", "nN", "nbar",
                 "node_tete_g", "node_tete_d", "node_faitage",
                 "node_sortie_jarret_g", "node_sortie_jarret_d",
                 "bars_jarret_g", "bars_jarret_d", "bar_epaule_g", "bar_epaule_d",
                 "excentre_arba")


def construire_topologie(geom, n_disc=None, arba=None):
    """Construit la `Topologie` du portique pour `n_disc` tronçons de jarret.

    `n_disc = 1` : reproduit à l'identique les 7 nœuds / 6 barres de
    `calcport.def_noeud_barres` (garde-fou de parité legacy).

    `arba` (nom de profil) : [PROTOTYPE étape 3] mode **excentré** — les nœuds
    du jarret (épaule, intérieurs, sortie) sont abaissés sur l'axe neutre
    (centre de gravité) de la section locale ; le nœud d'épaule étant le sommet
    du poteau, celui-ci est physiquement raccourci. Le jarret n'est alors plus
    colinéaire à la traverse. Sans `arba` : jarret sur la ligne de la traverse
    (comportement par défaut de l'étape 3).
    """
    if n_disc is None:
        n_disc = N_DISC_JARRET

    A, B = def_noeud_barres(geom, "IPE 80", "IPE 80")
    base = [(nd.X, nd.Y) for nd in A]          # N0..N6, ordre et indices figés
    N0, N1, N2, N3, N4, N5, N6 = range(7)

    topo = Topologie()
    topo.n_disc = n_disc
    topo.node_tete_g, topo.node_tete_d, topo.node_faitage = N1, N5, N3
    topo.node_sortie_jarret_g, topo.node_sortie_jarret_d = N2, N4

    coords = list(base)
    conn = []
    roles = []

    def _chaine_jarret(na, nb, sens):
        """Ajoute `n_disc` barres de `na` à `nb` (nœuds intérieurs → fin de
        `coords`). `sens = +1` : l'épaule est en `na` ; `sens = -1` : en `nb`."""
        (xa, ya), (xb, yb) = coords[na], coords[nb]
        interm = []
        for k in range(1, n_disc):
            f = k / n_disc
            coords.append((xa + f * (xb - xa), ya + f * (yb - ya)))
            interm.append(len(coords) - 1)
        noeuds = [na] + interm + [nb]
        bars = []
        for m in range(n_disc):
            conn.append((noeuds[m], noeuds[m + 1]))
            bars.append(len(conn) - 1)
            # tronçon depuis l'épaule
            t = m if sens > 0 else (n_disc - 1 - m)
            roles.append(("jarret", t))
        return bars

    conn.append((N0, N1)); roles.append(("poteau",))                  # poteau G
    topo.bars_jarret_g = _chaine_jarret(N1, N2, sens=+1)              # jarret G (épaule = N1)
    conn.append((N2, N3)); roles.append(("traverse",))               # traverse G
    conn.append((N3, N4)); roles.append(("traverse",))               # traverse D
    topo.bars_jarret_d = _chaine_jarret(N4, N5, sens=-1)             # jarret D (épaule = N5)
    conn.append((N5, N6)); roles.append(("poteau",))                 # poteau D

    topo.coords = coords
    topo.conn = conn
    topo.roles = roles
    topo.nN = len(coords)
    topo.nbar = len(conn)
    topo.bar_epaule_g = topo.bars_jarret_g[0]
    topo.bar_epaule_d = topo.bars_jarret_d[-1]
    topo.excentre_arba = None

    if arba is not None and n_disc > 1:
        # --- [PROTOTYPE] abaissement des nœuds du jarret sur l'axe neutre ---
        e = [offset_axe_neutre(arba, hr) for hr in _h_ratios(n_disc)]   # par tronçon (épaule->sortie)
        # offset au nœud p (0 = épaule, n_disc = sortie) : moyenne des tronçons adjacents
        o = [e[0]] + [0.5 * (e[p - 1] + e[p]) for p in range(1, n_disc)] + [e[-1]]

        def _noeuds_chaine(bars):
            return [conn[bars[0]][0]] + [conn[b][1] for b in bars]

        # jarret G : nœuds ordonnés épaule(N1) -> sortie(N2) ; offsets o[0..n_disc]
        for p, nd in enumerate(_noeuds_chaine(topo.bars_jarret_g)):
            x, y = coords[nd]
            coords[nd] = (x, y - o[p])
        # jarret D : nœuds ordonnés sortie(N4) -> épaule(N5) ; offsets inversés
        for p, nd in enumerate(_noeuds_chaine(topo.bars_jarret_d)):
            x, y = coords[nd]
            coords[nd] = (x, y - o[n_disc - p])
        topo.excentre_arba = arba

    return topo


def sections_par_barre(topo, poteau, arba):
    """Liste des dicts de section (mêmes clés que `calcport.jarret()`) barre par
    barre, dans l'ordre de `topo.conn` — même correspondance que
    `calcport.change_sections` : poteau IPE pour les poteaux, traverse IPE pour
    les traverses, `sections_jarret(arba, n_disc)` tronçon par tronçon."""
    secs_jarret = sections_jarret(arba, topo.n_disc)
    dico_pot = IPE.dict_carac(poteau)
    dico_arb = IPE.dict_carac(arba)
    out = []
    for role in topo.roles:
        if role[0] == "poteau":
            out.append(dico_pot)
        elif role[0] == "traverse":
            out.append(dico_arb)
        else:
            out.append(secs_jarret[role[1]])
    return out


def expanser_charges(charges, topo):
    """Projette les cas de charge « logiques » de `chargement_nv` (tableau par
    barre à 6 segments, tableau nodal à 21 slots) sur le modèle discrétisé.

    - Par barre : `[pot_g, jarret_g, trav_g, trav_d, jarret_d, pot_d]` →
      `[pot_g] + [jarret_g]·n_disc + [trav_g, trav_d] + [jarret_d]·n_disc + [pot_d]`
      (les tronçons de jarret sont colinéaires à la pente : même charge
      linéique).
    - Par nœud : les 21 slots N0..N6 sont conservés tels quels (N0..N6 gardent
      leurs indices) ; les nœuds intérieurs de jarret reçoivent une charge
      nodale nulle. Le « surplus fin de jarret » (neige, accumulation, vent de
      rive) reste donc porté par N2 / N4 = `node_sortie_jarret_*`.

    Renvoie une nouvelle liste de cas `(nom, ch_barres, ch_noeuds)`.
    """
    n = topo.n_disc
    out = []
    for nom, ch_bar, ch_noeud in charges:
        pg, jg, tg, td, jd, pd = ch_bar
        bar_exp = [pg] + [jg] * n + [tg, td] + [jd] * n + [pd]
        assert len(bar_exp) == topo.nbar, (len(bar_exp), topo.nbar)
        noeud_exp = list(ch_noeud) + [0.0] * (3 * (topo.nN - 7))
        out.append((nom, bar_exp, noeud_exp))
    return out


# ==========================================================================
#  Diagnostic a posteriori — déformation d'effort tranchant (non bloquant)
# ==========================================================================

_FV_LIM = (235.0 / 3.0 ** 0.5) / 10.0     # daN/mm² (S235, comme solveur_pynite)

# Pondérations ELS / ELU (identiques à optimise_IPE — lecture seule).
_COMBI_DEPL = [(1, 1, 0), (1, 1, .6), (1, 0, 1), (1, 0.5, 1)]
_COMBI_EFF = [(1.35, 1.5, 0, 0), (1.35, 1.5, 0, .9), (1.35, 0, 0, 1.5),
              (1, 0, 0, 1.5), (1.35, 0.75, 0, 1.5), (1, 0, 1, 0)]


def _simpson01(f, n=16):
    """∫₀¹ f(s) ds par Simpson (n pair)."""
    h = 1.0 / n
    s = f(0.0) + f(1.0)
    for k in range(1, n):
        s += (4.0 if k % 2 else 2.0) * f(k * h)
    return s * h / 3.0


def _energies_barre(eff6, L, EI, GAv):
    """(∫M²/EI dx, ∫V²/GAv dx) sur une barre, M/V reconstruits depuis les
    efforts d'about (V linéaire, M parabolique consistant)."""
    V0, VL, M0 = -eff6[1], eff6[4], -eff6[2]
    dV = VL - V0
    intM2 = L * _simpson01(lambda s: (M0 + V0 * L * s + dV * L * s * s / 2.0) ** 2)
    intV2 = L * _simpson01(lambda s: (V0 + dV * s) ** 2)
    return intM2 / EI, intV2 / GAv


def diagnostic_cisaillement(geom, charges, poteau, arba, n_disc=None):
    """Diagnostic **a posteriori** de la déformation d'effort tranchant, sur la
    section retenue par `optimise_IPE`. Ne change AUCUNE section — le solveur
    reste en Euler-Bernoulli (décision figée). Report-only.

    Renvoie un dict à fusionner dans le résultat de `charge_et_sections` :
      - `cis_ecart_fleche_pct` : contribution estimée de l'effort tranchant à la
        flèche/dérive (énergie de cisaillement / énergie de flexion, combinaison
        ELS la plus fléchie) ;
      - `cis_taux_ame_jarret_pct` : taux de cisaillement d'âme max le long du
        renfort d'épaule (tous tronçons), combinaison ELU ;
      - `cis_note` : phrase pour l'encart résultats (écran + PDF).
    """
    if n_disc is None:
        n_disc = N_DISC_JARRET
    from solveur_pynite import SolveurPyNite
    d = SolveurPyNite(geom, charges, n_disc=n_disc).details_efforts(poteau, arba)

    noms, E_, G_ = d["noms"], d["E"], d["G"]
    L = d["longueurs"]
    props = d["props"]                          # (A, Iy, Wpl.y, Avz) par barre
    eff = d["eff"]
    nbar = len(L)
    cp, nei, nacc = noms[0], noms[1], noms[2]
    vents = noms[3:]

    def eff_combi(poids, cas_list):
        """efforts d'about combinés par barre : Σ poids_k · eff[cas_k]
        (les efforts se superposent linéairement)."""
        return [[sum(poids[k] * eff[cas_list[k]][b][c] for k in range(len(poids)))
                 for c in range(6)] for b in range(nbar)]

    # --- ELS : ratio énergie cisaillement / énergie flexion, combi la plus fléchie
    best_ratio, best_Ub = 0.0, -1.0
    for cv in vents:
        for w in _COMBI_DEPL:
            ec = eff_combi(w, [cp, nei, cv])
            Ub = Uv = 0.0
            for b in range(nbar):
                A_, Iy_, _wpl, Avz_ = props[b]
                im2, iv2 = _energies_barre(ec[b], L[b], E_ * Iy_, G_ * Avz_)
                Ub += im2
                Uv += iv2
            if Ub > best_Ub:
                best_Ub, best_ratio = Ub, (Uv / Ub if Ub > 0 else 0.0)
    ecart_fleche_pct = round(best_ratio * 100.0, 1)

    # --- ELU : cisaillement d'âme le long du renfort d'épaule (tous tronçons)
    taux_max, ou = 0.0, None
    for cv in vents:
        for w in _COMBI_EFF:
            ec = eff_combi(w, [cp, nei, nacc, cv])
            for b in d["bars_jarret"]:
                Avz_ = props[b][3]
                for comp in (1, 4):
                    tx = abs(ec[b][comp]) / (Avz_ * _FV_LIM) / 100.0
                    if tx > taux_max:
                        taux_max, ou = tx, b
    taux_ame_pct = round(taux_max * 100.0, 1)

    note = (f"Déformation d'effort tranchant estimée à +{ecart_fleche_pct:.1f} % "
            f"sur la flèche/dérive : non prise en compte dans le dimensionnement "
            f"(hypothèse Euler-Bernoulli). Cisaillement d'âme du renfort d'épaule : "
            f"{taux_ame_pct:.1f} % max.")
    return {"cis_ecart_fleche_pct": ecart_fleche_pct,
            "cis_taux_ame_jarret_pct": taux_ame_pct,
            "cis_note": note}


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

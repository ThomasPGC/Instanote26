# -*- coding: utf-8 -*-
"""Parité legacy <-> PyNite — sous-étape 1.a.

1 portique, CAS CP SEUL, section constante (poteau IPE 160, traverse IPE 140),
RENFORT D'ÉPAULE NEUTRALISÉ (jarret() renvoie la section de traverse nue).
Géométrie = cas-01-compact.

But : vérifier que le solveur PyNite reproduit les 21 déplacements nodaux du
solveur maison de `business/calcport.py`, une fois appliquée la règle de signe
(le vecteur `D_avec_app` du legacy est l'OPPOSÉ du déplacement physique —
défaut connu de `crea_matrice_force`, cf. CLAUDE.md).

Attendu : écart relatif nul à la précision machine.

Rejeu :  python validation/pynite_check/check_1a_sans_jarret.py
Sortie :  0 = OK (< 1e-3 %), 1 = écart.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "business"))

import numpy as np
import calcport as L
from Pynite import FEModel3D

DENS_LIN = 7.85e-3          # daN/cm par cm^2 de section (comme crea_matrice_force)
E = L.E                     # 2 100 000 daN/cm^2
TOL = 1e-3                  # % d'écart relatif accepté

GEOM = {"hpot": 350, "portee": 400, "pente": 0.10,
        "longueur": 2000, "entraxe": 400, "h_acro": 0}
POT, TRAV = "IPE 160", "IPE 140"
COUV, DIVERS = 10.0, 2.0

w_arba = -(COUV + DIVERS + 7) * GEOM["entraxe"] / 10000.0
CAS_CP = ("CP_", [0.0, w_arba, w_arba, w_arba, w_arba, 0.0], [0.0] * 21)


# --- LEGACY : jarret() neutralisé -> pas de renfort d'épaule --------------
_jarret_orig = L.jarret
L.jarret = lambda section, coeff_hauteur=1.66: L.IPE.dict_carac(section)
try:
    A_nodes, B_bars = L.def_noeud_barres(GEOM, POT, TRAV)
    K = L.crea_matrice_rigidite(A_nodes, B_bars)
    F = L.crea_matrice_force(len(A_nodes), B_bars, CAS_CP)
    cap = {}
    L.calcport(A_nodes, B_bars, K, F, CAS_CP, debug_capture=cap)
    D_legacy = np.asarray(cap["D_avec_app"]).flatten()
finally:
    L.jarret = _jarret_orig

coords = [(n.X, n.Y) for n in A_nodes]
sec_of_bar = [(b.Ai.A, b.Aj.A, b.aire, b.I) for b in B_bars]   # I = inertie forte (cm4)


# --- PYNITE : même géométrie / sections / charges / appuis ----------------
m = FEModel3D()
m.add_material("acier", E, 807692.0, 0.3, 0.0)          # G sans effet (cisaillement off en v3)
for i, (X, Y) in enumerate(coords):
    m.add_node(f"N{i}", X, Y, 0.0)
    m.def_support(f"N{i}", False, False, True, True, True, False)   # modèle plan XY
m.def_support("N0", True, True, True, True, True, False)            # bi-articulé
m.def_support("N6", True, True, True, True, True, False)
for k, (ni, nj, aire, Iyf) in enumerate(sec_of_bar):
    m.add_section(f"S{k}", aire, 1.0, Iyf, 1.0)         # PyNite : flexion plan XY = autour de Z -> Iz
    m.add_member(f"M{k}", f"N{ni}", f"N{nj}", "acier", f"S{k}")
    q = CAS_CP[1][k] - aire * DENS_LIN                  # + poids propre, comme le legacy
    m.add_member_dist_load(f"M{k}", "FY", q, q, case="CP")
m.add_load_combo("CP", {"CP": 1.0})
m.analyze_linear(sparse=False, check_stability=False, check_statics=False)

D_pynite = np.zeros(21)
for i in range(len(coords)):
    nd = m.nodes[f"N{i}"]
    D_pynite[3 * i:3 * i + 3] = [nd.DX["CP"], nd.DY["CP"], nd.RZ["CP"]]


# --- COMPARAISON : règle de signe -> D_legacy = -D_pynite ----------------
D_legacy_corr = -D_legacy
labels = [f"N{i}.{d}" for i in range(len(coords)) for d in ("dx", "dy", "rz")]
print(f"{'DDL':<8}{'-legacy':>16}{'PyNite':>16}{'|Δ|':>13}{'rel %':>11}")
rel_max = 0.0
for lab, a, b in zip(labels, D_legacy_corr, D_pynite):
    d = abs(a - b)
    rel = 100 * d / max(abs(a), 1e-9)
    if abs(a) > 1e-7:
        rel_max = max(rel_max, rel)
    print(f"{lab:<8}{a:>16.6e}{b:>16.6e}{d:>13.2e}{rel:>10.4f}%")

print(f"\ntête poteau G  N1.dx : legacy {D_legacy[3]*10:+.4f} mm | PyNite {D_pynite[3]*10:+.4f} mm")
print(f"faîtage        N3.dy : legacy {D_legacy[10]*10:+.4f} mm | PyNite {D_pynite[10]*10:+.4f} mm")
print(f"\nÉcart relatif max (DDL non nuls) : {rel_max:.6f} %")
ok = rel_max < TOL
print("VERDICT :", "OK" if ok else "ÉCART")
sys.exit(0 if ok else 1)

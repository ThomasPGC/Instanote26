# -*- coding: utf-8 -*-
"""Parité legacy <-> PyNite — sous-étape 1.b.

Renfort d'épaule RÉINTRODUIT À L'IDENTIQUE : barres B1/B4 = section `jarret()`
(I reconstitué, âme haute 1,66·h de la traverse), longueur = 10 % de la portée.
Géométrie = cas-01-compact, sections IPE 160 / IPE 140.

Deux cas de charge :
  - CP_        : permanent (charge verticale globale + poids propre)
  - VEN_TEST   : cas PERPENDICULAIRE synthétique (UDL constante sur les 4 barres
                 de toiture) — pré-test de la convention de charge du vent.

Vérifie, pour chaque cas :
  - les 21 déplacements nodaux ;
  - les efforts d'about des 6 barres [Ni,Vi,Mi,Nj,Vj,Mj].

Règle de signe appliquée (cf. CLAUDE.md « Règle de signe legacy <-> PyNite ») :
  1) déplacements : D_legacy = -D_pynite (flip global, défaut crea_matrice_force) ;
  2) efforts d'about :  [Ni,Vi,Mi]_legacy = [-N(0), -V(0), -M(0)]_pynite
                        [Nj,Vj,Mj]_legacy = [+N(L), +V(L), +M(L)]_pynite
     (identité effort d'about <-> effort interne, valable pour TOUT chargement —
      c'est le point de ce script : montrer qu'elle tient aussi en perpendiculaire).

Attendu : écart relatif nul à la précision machine sur les deux cas.

Rejeu :  python validation/pynite_check/check_1b_renfort_epaule.py
Sortie :  0 = OK (< 1e-3 %), 1 = écart.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "business"))

import numpy as np
import calcport as L
from Pynite import FEModel3D

DENS_LIN = 7.85e-3
E = L.E
TOL = 1e-3

GEOM = {"hpot": 350, "portee": 400, "pente": 0.10,
        "longueur": 2000, "entraxe": 400, "h_acro": 0}
POT, TRAV = "IPE 160", "IPE 140"
COUV, DIVERS = 10.0, 2.0

w_arba = -(COUV + DIVERS + 7) * GEOM["entraxe"] / 10000.0
CAS_CP = ("CP_", [0.0, w_arba, w_arba, w_arba, w_arba, 0.0], [0.0] * 21)
CAS_PERP = ("VEN_TEST", [0.0, 0.5, 0.5, 0.5, 0.5, 0.0], [0.0] * 21)


def legacy_solve(cas):
    A, B = L.def_noeud_barres(GEOM, POT, TRAV)
    K = L.crea_matrice_rigidite(A, B)
    F = L.crea_matrice_force(len(A), B, cas)
    cap = {}
    L.calcport(A, B, K, F, cas, debug_capture=cap)
    D = np.asarray(cap["D_avec_app"]).flatten()
    eff = [np.asarray(b.efforts_noeuds).flatten().copy() for b in B]   # [Ni,Vi,Mi,Nj,Vj,Mj]
    coords = [(n.X, n.Y) for n in A]
    conn = [(b.Ai.A, b.Aj.A, b.aire, b.I) for b in B]
    return D, eff, coords, conn


def pynite_solve(coords, conn, cas):
    m = FEModel3D()
    m.add_material("acier", E, 807692.0, 0.3, 0.0)
    for i, (X, Y) in enumerate(coords):
        m.add_node(f"N{i}", X, Y, 0.0)
        m.def_support(f"N{i}", False, False, True, True, True, False)
    m.def_support("N0", True, True, True, True, True, False)
    m.def_support("N6", True, True, True, True, True, False)
    nom = cas[0]
    for k, (ni, nj, aire, Iyf) in enumerate(conn):
        (Xi, Yi), (Xj, Yj) = coords[ni], coords[nj]
        alpha = np.arctan2(Yj - Yi, Xj - Xi)
        m.add_section(f"S{k}", aire, 1.0, Iyf, 1.0)
        m.add_member(f"M{k}", f"N{ni}", f"N{nj}", "acier", f"S{k}")
        w = cas[1][k]
        if nom.startswith("CP"):
            q = w - aire * DENS_LIN
            m.add_member_dist_load(f"M{k}", "FY", q, q, case=nom)           # vertical global
        elif nom.startswith("NEI"):
            q = w * np.cos(alpha)
            m.add_member_dist_load(f"M{k}", "FY", q, q, case=nom)
        elif nom.startswith("VEN"):
            m.add_member_dist_load(f"M{k}", "Fy", w, w, case=nom)           # perpendiculaire (local y)
    for n in range(7):
        for d, idx in (("FX", 0), ("FY", 1), ("MZ", 2)):
            v = cas[2][3 * n + idx]
            if v:
                m.add_node_load(f"N{n}", d, v, case=nom)
    m.add_load_combo(nom, {nom: 1.0})
    m.analyze_linear(sparse=False, check_stability=False, check_statics=False)

    D = np.zeros(21)
    for i in range(len(coords)):
        nd = m.nodes[f"N{i}"]
        D[3 * i:3 * i + 3] = [nd.DX[nom], nd.DY[nom], nd.RZ[nom]]
    eff = []
    for k in range(len(conn)):
        mem = m.members[f"M{k}"]
        Lk = mem.L()
        eff.append(np.array([mem.axial(0, nom), mem.shear("Fy", 0, nom), mem.moment("Mz", 0, nom),
                             mem.axial(Lk, nom), mem.shear("Fy", Lk, nom), mem.moment("Mz", Lk, nom)]))
    return D, eff


worst = 0.0
for cas in (CAS_CP, CAS_PERP):
    Dl, effl, coords, conn = legacy_solve(cas)
    Dp, effp = pynite_solve(coords, conn, cas)

    # règle de signe
    Dp_map = -Dp
    effp_map = [np.array([-e[0], -e[1], -e[2], +e[3], +e[4], +e[5]]) for e in effp]

    rel_d = max((abs(a - b) / max(abs(a), 1e-9)
                 for a, b in zip(Dl, Dp_map) if abs(a) > 1e-7), default=0.0)
    rel_e = 0.0
    for el, ep in zip(effl, effp_map):
        for a, b in zip(el, ep):
            if abs(a) > 1e-6:
                rel_e = max(rel_e, abs(a - b) / abs(a))
    worst = max(worst, rel_d, rel_e)
    print(f"[{cas[0]:<9}] déplacements rel max {rel_d*100:.6f} %  |  "
          f"efforts 6 barres rel max {rel_e*100:.6f} %")

print(f"\nÉcart relatif max global : {worst*100:.6f} %")
ok = worst < TOL
print("VERDICT :", "OK" if ok else "ÉCART")
sys.exit(0 if ok else 1)

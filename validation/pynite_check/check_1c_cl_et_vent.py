# -*- coding: utf-8 -*-
"""Parité legacy <-> PyNite — sous-étape 1.c (conditions aux limites).

Backend « PyNite assembleur » (option A) : `m.Ke()` de PyNite, puis partition /
`scipy.linalg.lu_factor` / `lu_solve` pilotés ici.

Vérifie :
  - le masque de DDL libres, déduit des flags `def_support` : N0/N6 bi-articulés
    (DX, DY bloqués, RZ libre), `DZ/RX/RY` bloqués partout (modèle plan) ->
    17 DDL libres, identiques à la réduction du solveur maison ;
  - pour LES 8 CAS ÉLÉMENTAIRES de cas-03-haut-fin (CP, NEI, NEI_ACCI, 4x vent
    long-pan, vent pignon) : déplacements ET réactions d'appui N0/N6, legacy vs
    assembleur, au signe global près (R_legacy = K·D_legacy - F_legacy porte le
    même flip que D_legacy).

Rappel (cf. CLAUDE.md) : `m.Ke()` est indexée 6 DDL/nœud dans l'ordre
DX,DY,DZ,RX,RY,RZ ; la rotation dans le plan est RZ = indice local 5, PAS 2.

Attendu : écart relatif nul (déplacements et réactions).

Rejeu :  python validation/pynite_check/check_1c_cl_et_vent.py
Sortie :  0 = OK (< 1e-2 %), 1 = écart.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "business"))

import numpy as np
import scipy.linalg as sla
import calcport as L
import chargement_nv as chnv
from Pynite import FEModel3D

DENS_LIN = 7.85e-3
E = L.E
TOL = 1e-2
DOF_NAMES = ["DX", "DY", "DZ", "RX", "RY", "RZ"]
LOC3 = (0, 1, 5)   # dx, dy, rz  (rz = RZ = 5, PAS 2 = DZ hors-plan)

GEOM = {"hpot": 1000, "portee": 800, "pente": 0.10, "longueur": 4000, "entraxe": 500, "h_acro": 100}
LOCA = {"nom_commune": "Brest", "ancien_nom_comm": "", "departement": "29", "altitude": 50, "rugosite": "0"}
CP = {"couv": 20, "divers": 5}

canton = chnv.trouve_canton(LOCA["departement"], LOCA["nom_commune"], LOCA["ancien_nom_comm"])
zones = chnv.trouve_zones_NV(LOCA["departement"], canton)
cpa = -(CP["couv"] + CP["divers"] + 7) * GEOM["entraxe"] / 10000.0
CHARGES = [("CP_", [0, cpa, cpa, cpa, cpa, 0], [0.0] * 21)] \
    + chnv.charge_neige(zones[0], LOCA["altitude"], GEOM) \
    + chnv.charge_vent(zones[1], LOCA["rugosite"], GEOM)
res, _ = L.charge_et_sections(GEOM, LOCA, CP)
POT, ARBA = res["poteau"], res["traverse"]


# --- LEGACY : D + réactions (R = K·D - F aux DDL supprimés), par cas ------
A, B = L.def_noeud_barres(GEOM, POT, ARBA)
K_leg = L.crea_matrice_rigidite(A, B)
COORDS = [(n.X, n.Y) for n in A]
CONN = [(b.Ai.A, b.Aj.A, b.aire, b.I) for b in B]
LEG = {}
for cas in CHARGES:
    F = L.crea_matrice_force(len(A), B, cas)
    cap = {}
    L.calcport(A, B, K_leg, F, cas, debug_capture=cap)
    D = np.asarray(cap["D_avec_app"]).flatten()
    R = K_leg @ D - F.flatten()
    LEG[cas[0]] = (D, R)


# --- BACKEND ASSEMBLEUR --------------------------------------------------
m = FEModel3D()
m.add_material("acier", E, 807692.0, 0.3, 0.0)
for i, (X, Y) in enumerate(COORDS):
    m.add_node(f"N{i}", X, Y, 0.0)
    m.def_support(f"N{i}", False, False, True, True, True, False)   # DZ,RX,RY bloqués (plan)
m.def_support("N0", True, True, True, True, True, False)            # bi-articulé
m.def_support("N6", True, True, True, True, True, False)
for k, (ni, nj, aire, Iyf) in enumerate(CONN):
    m.add_section(f"S{k}", aire, 1.0, Iyf, 1.0)
    m.add_member(f"M{k}", f"N{ni}", f"N{nj}", "acier", f"S{k}")
for cas in CHARGES:
    nom = cas[0]
    for k, (ni, nj, aire, Iyf) in enumerate(CONN):
        (Xi, Yi), (Xj, Yj) = COORDS[ni], COORDS[nj]
        al = np.arctan2(Yj - Yi, Xj - Xi)
        w = cas[1][k]
        if nom.startswith("CP"):
            m.add_member_dist_load(f"M{k}", "FY", w - aire * DENS_LIN, w - aire * DENS_LIN, case=nom)
        elif nom.startswith("NEI"):
            m.add_member_dist_load(f"M{k}", "FY", w * np.cos(al), w * np.cos(al), case=nom)
        elif nom.startswith("VEN"):
            m.add_member_dist_load(f"M{k}", "Fy", w, w, case=nom)
    for nn in range(7):
        for d, idx in (("FX", 0), ("FY", 1), ("MZ", 2)):
            v = cas[2][3 * nn + idx]
            if v:
                m.add_node_load(f"N{nn}", d, v, case=nom)
    m.add_load_combo(nom, {nom: 1.0})
m.analyze_linear(sparse=False, check_stability=False, check_statics=False)   # prime node.ID
combo0 = list(m.load_combos.keys())[0]
nN = len(m.nodes)

free, supp = [], []
for i, nd in enumerate(m.nodes.values()):
    for j, s in enumerate([nd.support_DX, nd.support_DY, nd.support_DZ,
                           nd.support_RX, nd.support_RY, nd.support_RZ]):
        (supp if s else free).append(i * 6 + j)
free = np.array(free)
libres = [f"N{d // 6}.{DOF_NAMES[d % 6]}" for d in free]
print(f"DDL libres : {len(free)}  ->  {libres}")
print("attendu legacy : 17 (rz N0 ; dx,dy,rz N1..N5 ; rz N6)")
mask_ok = (len(free) == 17
           and libres == (["N0.RZ"]
                          + [f"N{i}.{d}" for i in range(1, 6) for d in ("DX", "DY", "RZ")]
                          + ["N6.RZ"]))

K6 = np.array(m.Ke(combo0, False, False, False))
lu = sla.lu_factor(K6[np.ix_(free, free)], check_finite=False)


def to21(d42):
    return np.array([d42[i * 6 + c] for i in range(nN) for c in LOC3])


print(f"\n{'cas':<18}{'depl rel max':>16}{'react rel max':>16}")
worst_d = worst_r = 0.0
for cas in CHARGES:
    nom = cas[0]
    F6 = (m.P(nom) - m.FER(nom)).flatten()
    d6 = np.zeros(nN * 6)
    d6[free] = sla.lu_solve(lu, F6[free], check_finite=False)
    R6 = K6 @ d6 - F6

    d21, R21 = to21(d6), to21(R6)
    Dl, Rl = LEG[nom]

    def relmax(a, b, thr):
        num = np.abs(np.abs(a) - np.abs(b))
        den = np.maximum(np.abs(a), 1e-6)
        mk = np.abs(a) > thr
        return float(np.max(num[mk] / den[mk])) if mk.any() else 0.0

    rd = relmax(Dl, d21, 1e-4)
    rr = relmax(Rl[[0, 1, 18, 19]], R21[[0, 1, 18, 19]], 1e-2)   # réactions dx,dy N0 et N6
    worst_d, worst_r = max(worst_d, rd), max(worst_r, rr)
    print(f"{nom:<18}{rd * 100:>15.6f}%{rr * 100:>15.6f}%")

print(f"\nécart relatif max : déplacements {worst_d * 100:.6f} %  |  réactions {worst_r * 100:.6f} %")
ok = mask_ok and max(worst_d, worst_r) < TOL
print("VERDICT :", "OK" if ok else "ÉCART" if not mask_ok else "ÉCART")
if not mask_ok:
    print("  (masque de DDL libres != réduction legacy)")
sys.exit(0 if ok else 1)

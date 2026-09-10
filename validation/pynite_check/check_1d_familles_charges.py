# -*- coding: utf-8 -*-
"""Parité legacy <-> PyNite — sous-étape 1.d (portage des familles de charges).

Vérifie que les TROIS familles de charges de `chargement_nv` + les charges
PONCTUELLES `cas[2]` produisent, une fois portées dans PyNite, les mêmes
efforts internes que le solveur maison — cas élémentaire par cas élémentaire,
sur les 3 jeux de `validation/` (cas-01/02/03).

Portage (identique à `check_1c` / futur `resoudre_cas`) :
  - "CP_..."  : UDL verticale GLOBALE  q_k = charge_k - A_k * 7,85e-3
                (poids propre ajouté UNIQUEMENT dans le cas CP, comme le legacy) ;
  - "NEI..."  : UDL verticale globale  q_k = charge_k * cos(alpha_k)
                (neige projetée sur la barre, comme calcSij_vert(w*cos alpha)) ;
  - "VEN..."  : UDL PERPENDICULAIRE (repère local y)  q_k = charge_k
                (comme calcSij_perp) ;
  - charges ponctuelles `cas[2]` = [Fx, Fy, Mz] par nœud -> add_node_load(+v).
    Le legacy fait `F -= cas[2]` ; combiné au flip global de `crea_matrice_force`,
    l'équivalent physique PyNite est `+v` (cf. règle de signe 1).

Comparaison : efforts d'about des 6 barres [Ni,Vi,Mi,Nj,Vj,Mj], via la règle
de signe 2 :  [Ni,Vi,Mi]_legacy = [-N(0),-V(0),-M(0)]_pynite
              [Nj,Vj,Mj]_legacy = [+N(L),+V(L),+M(L)]_pynite

Sortie détaillée par FAMILLE (CP / NEI / VEN) et par présence de charges
nodales, pour rendre explicite ce qui est réellement exercé.

Rejeu :  python validation/pynite_check/check_1d_familles_charges.py
Sortie :  0 = OK (< 1e-2 %), 1 = écart.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "business"))

import os as _os
_os.environ.setdefault("MOTEUR_CALCUL", "legacy")   # harnais etape 1 = ancien modele
_os.environ.setdefault("N_DISC_JARRET", "1")        # (le defaut prod est desormais pynite/6)

import numpy as np
import calcport as L
import chargement_nv as chnv
from Pynite import FEModel3D

DENS_LIN = 7.85e-3
E = L.E
TOL = 1e-2   # %

CASES = {
    "cas-01-compact": (
        {"hpot": 350, "portee": 400, "pente": 0.10, "longueur": 2000, "entraxe": 400, "h_acro": 0},
        {"nom_commune": "Blois", "ancien_nom_comm": "", "departement": "41", "altitude": 114, "rugosite": "IIIb"},
        {"couv": 10, "divers": 2}),
    "cas-02-bas-large": (
        {"hpot": 500, "portee": 2200, "pente": 0.03, "longueur": 4000, "entraxe": 800, "h_acro": 100},
        {"nom_commune": "Millau", "ancien_nom_comm": "", "departement": "12", "altitude": 631, "rugosite": "IIIa"},
        {"couv": 50, "divers": 20}),
    "cas-03-haut-fin": (
        {"hpot": 1000, "portee": 800, "pente": 0.10, "longueur": 4000, "entraxe": 500, "h_acro": 100},
        {"nom_commune": "Brest", "ancien_nom_comm": "", "departement": "29", "altitude": 50, "rugosite": "0"},
        {"couv": 20, "divers": 5}),
}


def charges_elem(geom, loca, cp):
    canton = chnv.trouve_canton(loca["departement"], loca["nom_commune"], loca["ancien_nom_comm"])
    zones = chnv.trouve_zones_NV(loca["departement"], canton)
    cpa = -(cp["couv"] + cp["divers"] + 7) * geom["entraxe"] / 10000.0
    return [("CP_", [0, cpa, cpa, cpa, cpa, 0], [0.0] * 21)] \
        + chnv.charge_neige(zones[0], loca["altitude"], geom) \
        + chnv.charge_vent(zones[1], loca["rugosite"], geom)


def famille(nom):
    if nom.startswith("CP"):
        return "CP"
    if nom.startswith("NEI"):
        return "NEI"
    return "VEN"


def legacy_efforts(geom, pot, arba, charges):
    A, B = L.def_noeud_barres(geom, pot, arba)
    K = L.crea_matrice_rigidite(A, B)
    coords = [(n.X, n.Y) for n in A]
    conn = [(b.Ai.A, b.Aj.A, b.aire, b.I) for b in B]
    out = {}
    for cas in charges:
        F = L.crea_matrice_force(len(A), B, cas)
        L.calcport(A, B, K, F, cas)
        out[cas[0]] = [np.asarray(b.efforts_noeuds).flatten().copy() for b in B]
    return coords, conn, out


def pynite_efforts(coords, conn, charges):
    m = FEModel3D()
    m.add_material("acier", E, 807692.0, 0.3, 0.0)
    for i, (X, Y) in enumerate(coords):
        m.add_node(f"N{i}", X, Y, 0.0)
        m.def_support(f"N{i}", False, False, True, True, True, False)
    m.def_support("N0", True, True, True, True, True, False)
    m.def_support("N6", True, True, True, True, True, False)
    for k, (ni, nj, aire, Iyf) in enumerate(conn):
        m.add_section(f"S{k}", aire, 1.0, Iyf, 1.0)
        m.add_member(f"M{k}", f"N{ni}", f"N{nj}", "acier", f"S{k}")
    for cas in charges:
        nom = cas[0]
        for k, (ni, nj, aire, Iyf) in enumerate(conn):
            (Xi, Yi), (Xj, Yj) = coords[ni], coords[nj]
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
    m.analyze_linear(sparse=False, check_stability=False, check_statics=False)

    out = {}
    for cas in charges:
        nom = cas[0]
        rows = []
        for k in range(len(conn)):
            mem = m.members[f"M{k}"]
            Lk = mem.L()
            # règle de signe 2 : legacy [Ni,Vi,Mi]=[-N(0),-V(0),-M(0)] ; [Nj,Vj,Mj]=[+N(L),+V(L),+M(L)]
            rows.append(np.array([
                -mem.axial(0, nom), -mem.shear("Fy", 0, nom), -mem.moment("Mz", 0, nom),
                +mem.axial(Lk, nom), +mem.shear("Fy", Lk, nom), +mem.moment("Mz", Lk, nom)]))
        out[nom] = rows
    return out


COMP = ["Ni", "Vi", "Mi", "Nj", "Vj", "Mj"]
print(f"{'jeu':<17}{'cas élémentaire':<20}{'fam':<5}{'nœuds ?':<9}{'effort rel max':>16}")
print("-" * 67)
worst_global = 0.0
worst_par_fam = {"CP": 0.0, "NEI": 0.0, "VEN": 0.0}
for name, (geom, loca, cp) in CASES.items():
    charges = charges_elem(geom, loca, cp)
    res, _ = L.charge_et_sections(geom, loca, cp)
    pot, arba = res["poteau"], res["traverse"]
    coords, conn, LEG = legacy_efforts(geom, pot, arba, charges)
    PYN = pynite_efforts(coords, conn, charges)

    for cas in charges:
        nom = cas[0]
        fam = famille(nom)
        has_nodal = any(abs(v) > 1e-9 for v in cas[2])
        rel = 0.0
        for el, ep in zip(LEG[nom], PYN[nom]):
            for a, b in zip(el, ep):
                if abs(a) > 1e-3:
                    rel = max(rel, abs(a - b) / abs(a))
        worst_global = max(worst_global, rel)
        worst_par_fam[fam] = max(worst_par_fam[fam], rel)
        print(f"{name:<17}{nom:<20}{fam:<5}{('oui' if has_nodal else 'non'):<9}{rel*100:>15.6f}%")

print("-" * 67)
for fam in ("CP", "NEI", "VEN"):
    print(f"  écart max famille {fam:<4}: {worst_par_fam[fam]*100:.6f} %")
print(f"\nécart relatif max global (efforts d'about) : {worst_global*100:.6f} %")
ok = worst_global < TOL
print("VERDICT :", "OK" if ok else "ÉCART")
sys.exit(0 if ok else 1)

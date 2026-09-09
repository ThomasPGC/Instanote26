# -*- coding: utf-8 -*-
"""Parité legacy <-> PyNite — sous-étape 1.e (taux de travail cas par cas).

Recalcule les 13 taux `tx_*` de `calculer_et_verifier_resultats` à partir des
efforts PyNite, avec LA MÊME FORMULE que le legacy :

    fy = 235.0 ; fv = fy / sqrt(3)
    tx_mom = M / (Wpl * fy/10) / 100          (M en daN.cm, Wpl en cm3)
    tx_cis = V / (Avz * fv/10) / 100          (V en daN,   Avz en cm2)

et les compare AU SIGNE PRÈS (pas en valeur absolue), cas élémentaire par cas
élémentaire, sur les 3 jeux de `validation/`.

Correspondance barre / composante (indices legacy `efforts_noeuds` = [Ni,Vi,Mi,Nj,Vj,Mj]) :

  clé                  barre                       comp.     dénominateur
  tx_mom_pot_g         B0 (N0->N1) poteau          Mj (N1)   Wpl poteau
  tx_mom_renf_g        B1 (N1->N2) RENFORT ÉPAULE  Mi (N1)   Wpl jarret (1,66 h)   <-- critique
  tx_mom_pied_arba_g   B2 (N2->N3) traverse        Mi (N2)   Wpl traverse nue      <-- critique
  tx_mom_fait          B2 (N2->N3) traverse        Mj (N3)   Wpl traverse
  tx_mom_pied_arba_d   B3 (N3->N4) traverse        Mj (N4)   Wpl traverse          <-- critique
  tx_mom_renf_d        B4 (N4->N5) RENFORT ÉPAULE  Mj (N5)   Wpl jarret            <-- critique
  tx_mom_pot_d         B5 (N5->N6) poteau          Mi (N5)   Wpl poteau
  tx_cis_*             idem, Vi/Vj, dénominateur Avz

Règle de signe 2 :  [Ni,Vi,Mi]_legacy = [-N(0),-V(0),-M(0)]_pynite
                    [Nj,Vj,Mj]_legacy = [+N(L),+V(L),+M(L)]_pynite

Rejeu :  python validation/pynite_check/check_1e_taux.py
Sortie :  0 = OK (< 1e-2 %), 1 = écart.
"""
import sys
import pathlib
from math import sqrt

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "business"))

import numpy as np
import calcport as L
import chargement_nv as chnv
from Pynite import FEModel3D

DENS_LIN = 7.85e-3
E = L.E
TOL = 1e-2   # %

FY = 235.0
FV = FY / sqrt(3.0)
FY_LIM = FY / 10.0
FV_LIM = FV / 10.0

CRITIQUES = ("tx_mom_renf_g", "tx_mom_pied_arba_g", "tx_mom_pied_arba_d", "tx_mom_renf_d")

TX_KEYS = ["tx_mom_pot_g", "tx_mom_renf_g", "tx_mom_pied_arba_g", "tx_mom_fait",
           "tx_mom_pied_arba_d", "tx_mom_renf_d", "tx_mom_pot_d",
           "tx_cis_pot_g", "tx_cis_renf_g", "tx_cis_pied_arba_g",
           "tx_cis_pied_arba_d", "tx_cis_renf_d", "tx_cis_pot_d"]

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

# combinaisons ELU du legacy (optimise_IPE) : (G, N, Nacc, W)
COMBI_EFF = [(1.35, 1.5, 0, 0), (1.35, 1.5, 0, .9), (1.35, 0, 0, 1.5),
             (1, 0, 0, 1.5), (1.35, 0.75, 0, 1.5), (1, 0, 1, 0)]


def charges_elem(geom, loca, cp):
    canton = chnv.trouve_canton(loca["departement"], loca["nom_commune"], loca["ancien_nom_comm"])
    zones = chnv.trouve_zones_NV(loca["departement"], canton)
    cpa = -(cp["couv"] + cp["divers"] + 7) * geom["entraxe"] / 10000.0
    return [("CP_", [0, cpa, cpa, cpa, cpa, 0], [0.0] * 21)] \
        + chnv.charge_neige(zones[0], loca["altitude"], geom) \
        + chnv.charge_vent(zones[1], loca["rugosite"], geom)


def legacy_run(geom, pot, arba, charges):
    """Renvoie coords/conn, sections (Wpl, Avz par barre) et les ens_resu legacy par cas."""
    A, B = L.def_noeud_barres(geom, pot, arba)
    K = L.crea_matrice_rigidite(A, B)
    coords = [(n.X, n.Y) for n in A]
    conn = [(b.Ai.A, b.Aj.A, b.aire, b.I) for b in B]
    wpl = [b.Wpl for b in B]        # B1/B4 = Wpl du jarret 1,66 h
    avz = [b.Avz for b in B]
    per_cas = {}
    for cas in charges:
        F = L.crea_matrice_force(len(A), B, cas)
        ens = L.calcport(A, B, K, F, cas)      # dict ens_resu (13 tx_* + 3 déplacements)
        per_cas[cas[0]] = {k: float(ens[k]) for k in TX_KEYS}
    return coords, conn, wpl, avz, per_cas


def pynite_run(coords, conn, charges, wpl, avz):
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

    per_cas = {}
    for cas in charges:
        nom = cas[0]
        # efforts d'about legacy-convention par barre, via règle de signe 2
        Mi, Mj, Vi, Vj = {}, {}, {}, {}
        for k in range(len(conn)):
            mem = m.members[f"M{k}"]
            Lk = mem.L()
            Mi[k] = -mem.moment("Mz", 0, nom)
            Mj[k] = +mem.moment("Mz", Lk, nom)
            Vi[k] = -mem.shear("Fy", 0, nom)
            Vj[k] = +mem.shear("Fy", Lk, nom)

        def txm(M, k):
            return M / (wpl[k] * FY_LIM) / 100.0

        def txv(V, k):
            return V / (avz[k] * FV_LIM) / 100.0

        per_cas[nom] = {
            "tx_mom_pot_g":       txm(Mj[0], 0),
            "tx_mom_renf_g":      txm(Mi[1], 1),
            "tx_mom_pied_arba_g": txm(Mi[2], 2),
            "tx_mom_fait":        txm(Mj[2], 2),
            "tx_mom_pied_arba_d": txm(Mj[3], 3),
            "tx_mom_renf_d":      txm(Mj[4], 4),
            "tx_mom_pot_d":       txm(Mi[5], 5),
            "tx_cis_pot_g":       txv(Vi[0], 0),
            "tx_cis_renf_g":      txv(Vi[1], 1),
            "tx_cis_pied_arba_g": txv(Vi[2], 2),
            "tx_cis_pied_arba_d": txv(Vj[3], 3),
            "tx_cis_renf_d":      txv(Vj[4], 4),
            "tx_cis_pot_d":       txv(Vj[5], 5),
        }
    return per_cas


def rel(a, b):
    return abs(a - b) / max(abs(a), 1e-12)


worst_global = 0.0
worst_critique = 0.0
for name, (geom, loca, cp) in CASES.items():
    charges = charges_elem(geom, loca, cp)
    res, _ = L.charge_et_sections(geom, loca, cp)
    pot, arba = res["poteau"], res["traverse"]
    coords, conn, wpl, avz, LEG = legacy_run(geom, pot, arba, charges)
    PYN = pynite_run(coords, conn, charges, wpl, avz)

    print(f"\n{'='*78}\n {name}   ({pot} / {arba})   Wpl jarret G/D = {wpl[1]:.1f} cm3   "
          f"Wpl traverse = {wpl[2]:.1f} cm3\n{'='*78}")

    # --- 1) parité des 13 tx_* sur tous les cas élémentaires ---
    cas_worst = 0.0
    for cas in charges:
        nom = cas[0]
        r = max(rel(LEG[nom][k], PYN[nom][k]) for k in TX_KEYS
                if abs(LEG[nom][k]) > 1e-4)
        cas_worst = max(cas_worst, r)
    worst_global = max(worst_global, cas_worst)
    print(f"  parité des 13 tx_* : écart relatif max sur {len(charges)} cas élémentaires "
          f"= {cas_worst*100:.6f} %")

    # --- 2) DÉTAIL des moments critiques (renfort d'épaule + pied d'arbalétrier) ---
    print(f"\n  Moments critiques — legacy vs PyNite (au signe près), % de taux :")
    hdr = "  " + f"{'cas élémentaire':<20}" + "".join(f"{c:>21}" for c in CRITIQUES)
    print(hdr)
    for cas in charges:
        nom = cas[0]
        cells = []
        for k in CRITIQUES:
            a, b = LEG[nom][k], PYN[nom][k]
            div = rel(a, b) > TOL / 100 and abs(a) > 1e-4
            worst_critique = max(worst_critique, rel(a, b) if abs(a) > 1e-4 else 0.0)
            mark = " !!DIV" if div else ""
            cells.append(f"{a*100:8.3f}/{b*100:8.3f}{mark}")
        print("  " + f"{nom:<20}" + "".join(f"{c:>21}" for c in cells))

    # --- 3) taux critique GOUVERNANT après COMBI_EFF (bonus : bout-en-bout) ---
    print(f"\n  Taux critique gouvernant après COMBI_EFF (|Σ combi·tx|) :")
    order = [c[0] for c in charges]
    idx_cp = [i for i, n in enumerate(order) if n.startswith("CP")]
    idx_nei = [i for i, n in enumerate(order) if n.startswith("NEI") and "ACCI" not in n]
    idx_acc = [i for i, n in enumerate(order) if "ACCI" in n]
    idx_ven = [i for i, n in enumerate(order) if n.startswith("VEN")]
    for k in CRITIQUES:
        gl = gp = 0.0
        for iv in idx_ven:
            for (cg, cn, ca, cw) in COMBI_EFF:
                sg = sp = 0.0
                for ii in idx_cp:
                    sg += LEG[order[ii]][k] * cg; sp += PYN[order[ii]][k] * cg
                for ii in idx_nei:
                    sg += LEG[order[ii]][k] * cn; sp += PYN[order[ii]][k] * cn
                for ii in idx_acc:
                    sg += LEG[order[ii]][k] * ca; sp += PYN[order[ii]][k] * ca
                sg += LEG[order[iv]][k] * cw; sp += PYN[order[iv]][k] * cw
                gl = max(gl, abs(sg)); gp = max(gp, abs(sp))
        rr = rel(gl, gp)
        worst_critique = max(worst_critique, rr)
        mark = "  !!DIVERGENCE" if rr > TOL / 100 else ""
        print(f"    {k:<22} legacy {gl*100:7.2f} %   PyNite {gp*100:7.2f} %   "
              f"écart {rr*100:.6f} %{mark}")

print(f"\n{'='*78}")
print(f"écart relatif max — 13 tx_* / tous cas élémentaires        : {worst_global*100:.6f} %")
print(f"écart relatif max — moments critiques (élém. + gouvernant) : {worst_critique*100:.6f} %")
ok = max(worst_global, worst_critique) * 100 < TOL      # TOL exprimé en %
print("VERDICT :", "OK" if ok else "ÉCART")
sys.exit(0 if ok else 1)

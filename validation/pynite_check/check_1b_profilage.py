# -*- coding: utf-8 -*-
"""Profilage — sous-étape 1.b (pas de verdict : temps machine-dépendants).

Compare, sur les 3 jeux de `validation/` (cas-01/02/03), le coût d'un appel
complet à `charge_et_sections()` (boucle `optimise_IPE` réelle) selon le
backend de résolution :

  legacy            : solveur maison actuel de business/calcport.py
  PyNite natif      : 1 modèle, 1 combo PyNite par cas élémentaire
                      (add_load_combo, facteur 1), analyze_linear() puis
                      lecture via member.moment()/shear().
  PyNite assembleur : m.Ke() de PyNite, puis partition + scipy.linalg.lu_factor
                      (1x / itération IPE) + lu_solve par cas, RHS des cas
                      non-CP mis en cache entre itérations (seul CP recalculé
                      pour le poids propre).

Le "PyNite natif" n'est mesuré que sur UNE résolution complète (tous les cas
élémentaires) puis extrapolé × nombre d'itérations IPE ; idem "assembleur"
mesuré par itération. Les chiffres de référence sont consignés dans CLAUDE.md
(section « Étape 1.b — profilage »).

Rejeu :  python validation/pynite_check/check_1b_profilage.py
"""
import sys
import pathlib
import time
import statistics

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "business"))

import numpy as np
import scipy.linalg as sla
import calcport as L
import chargement_nv as chnv
from Pynite import FEModel3D

DENS_LIN = 7.85e-3
E = L.E

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


def med(fn, n=60):
    fn(); fn()
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return statistics.median(ts) * 1e3


def charges_elem(geom, loca, cp):
    canton = chnv.trouve_canton(loca["departement"], loca["nom_commune"], loca["ancien_nom_comm"])
    zones = chnv.trouve_zones_NV(loca["departement"], canton)
    cpa = -(cp["couv"] + cp["divers"] + 7) * geom["entraxe"] / 10000.0
    return [("CP_", [0, cpa, cpa, cpa, cpa, 0], [0.0] * 21)] \
        + chnv.charge_neige(zones[0], loca["altitude"], geom) \
        + chnv.charge_vent(zones[1], loca["rugosite"], geom)


def count_iters(geom, charges):
    n = {"c": 0}
    orig = L.change_sections
    def wrap(*a, **k):
        n["c"] += 1
        return orig(*a, **k)
    L.change_sections = wrap
    try:
        L.optimise_IPE(geom, charges)
    finally:
        L.change_sections = orig
    return n["c"]


def build_pynite(coords, conn, charges):
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
    return m


def pynite_natif_resolution(m, charges, nbar):
    """1 analyze_linear + lecture member.*() pour tous les cas élémentaires."""
    m.analyze_linear(sparse=False, check_stability=False, check_statics=False)
    out = {}
    for cas in charges:
        nom = cas[0]
        D = np.zeros(21)
        for i in range(7):
            nd = m.nodes[f"N{i}"]
            D[3 * i:3 * i + 3] = [nd.DX[nom], nd.DY[nom], nd.RZ[nom]]
        eff = []
        for k in range(nbar):
            mm = m.members[f"M{k}"]
            Lk = mm.L()
            eff.append((mm.moment("Mz", 0, nom), mm.moment("Mz", Lk, nom),
                        mm.shear("Fy", 0, nom), mm.shear("Fy", Lk, nom)))
        out[nom] = (D, eff)
    return out


LOC3 = (0, 1, 5)   # DX, DY, RZ (RZ = indice local 5, pas 2)

print(f"{'cas':<17}{'itér IPE':>9}{'legacy':>10}{'natif/résol':>13}{'assemb/itér':>13}"
      f"{'-> natif tot':>14}{'-> assemb tot':>15}")
print("-" * 91)
for name, (geom, loca, cp) in CASES.items():
    charges = charges_elem(geom, loca, cp)
    res, _ = L.charge_et_sections(geom, loca, cp)
    pot, arba = res["poteau"], res["traverse"]
    niter = count_iters(geom, charges)

    A, B = L.def_noeud_barres(geom, pot, arba)
    coords = [(nd.X, nd.Y) for nd in A]
    conn = [(b.Ai.A, b.Aj.A, b.aire, b.I) for b in B]
    nbar = len(B)

    t_legacy = med(lambda: L.charge_et_sections(geom, loca, cp), n=25)

    # --- PyNite natif : 1 résolution de tous les cas élémentaires
    m_nat = build_pynite(coords, conn, charges)
    t_natif = med(lambda: pynite_natif_resolution(build_pynite(coords, conn, charges), charges, nbar), n=25)

    # --- PyNite assembleur : coût d'une itération IPE
    m = build_pynite(coords, conn, charges)
    m.analyze_linear(sparse=False, check_stability=False, check_statics=False)   # prime node.ID
    combo0 = list(m.load_combos.keys())[0]
    free = []
    for i, nd in enumerate(m.nodes.values()):
        for j, s in enumerate([nd.support_DX, nd.support_DY, nd.support_DZ,
                               nd.support_RX, nd.support_RY, nd.support_RZ]):
            if not s:
                free.append(i * 6 + j)
    free = np.array(free)
    noncp = [c for c in m.load_combos if not c.startswith("CP")]
    rhs_cache = {c: (m.P(c) - m.FER(c)).flatten() for c in noncp}
    cpname = [c for c in m.load_combos if c.startswith("CP")][0]

    def assembleur_iteration():
        K = np.array(m.Ke(combo0, False, False, False))
        lu = sla.lu_factor(K[np.ix_(free, free)], check_finite=False)
        rhs_cp = (m.P(cpname) - m.FER(cpname)).flatten()
        d_all = {}
        for c in m.load_combos:
            F = rhs_cp if c == cpname else rhs_cache[c]
            d6 = np.zeros(len(m.nodes) * 6)
            d6[free] = sla.lu_solve(lu, F[free], check_finite=False)
            d_all[c] = np.array([d6[i * 6 + q] for i in range(7) for q in LOC3])
        eff = {}
        for c, d6 in d_all.items():
            eff[c] = [m.members[f"M{k}"].T() for k in range(nbar)]   # transf. locale (coût représentatif)
        return d_all, eff

    t_assemb = med(assembleur_iteration, n=100)

    est_natif = niter * t_natif
    est_assemb = 5.0 + niter * t_assemb   # ~5 ms d'init (RHS des cas non-CP)
    print(f"{name:<17}{niter:>9}{t_legacy:>9.1f}m{t_natif:>12.1f}{t_assemb:>12.2f}"
          f"{est_natif:>13.0f}m{est_assemb:>14.0f}m")

print("\n(temps en ms, médianes ; 'm' = millisecondes. Machine de dev, indicatif.)")
print("Référence figée : CLAUDE.md, section « Étape 1.b — profilage ».")

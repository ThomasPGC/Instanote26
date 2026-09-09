# -*- coding: utf-8 -*-
"""Parité legacy <-> PyNite — sous-étape 1.f (boucle optimise_IPE complète).

Rebranche un `resoudre_cas` PyNite DANS `optimise_IPE` (par monkeypatch de
`calcport.calcport` et `calcport.optimise_IPE`, sans toucher au fichier) et
vérifie que `charge_et_sections()` retient LES MÊMES SECTIONS que le legacy,
sur les 3 jeux de `validation/` + une série de cas aléatoires reproductibles.

La boucle `optimise_IPE` elle-même n'est PAS réécrite : on laisse tourner
celle du legacy (prédim, incréments IPE, COMBI_DEPL/COMBI_EFF, critères), on
lui substitue seulement la résolution d'un cas -> `ens_resu`. Comme les
`ens_resu` PyNite sont identiques au legacy (sous-étapes 1.a–1.e), le chemin
de la boucle et donc les sections retenues doivent être identiques.

Backend : PyNite "natif" (analyze_linear + member.*()) — suffisant pour un
contrôle de justesse ; l'optimisation "assembleur" (Ke réutilisée, scipy)
donne les mêmes nombres (1.c) et ne concerne que la performance.

Rejeu :  python validation/pynite_check/check_1f_optimise.py
Sortie :  0 = toutes sections identiques, 1 = au moins une divergence.
"""
import sys
import pathlib
import random
from math import sqrt, cos, atan

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "business"))

import numpy as np
import calcport as L
import chargement_nv as chnv
from Pynite import FEModel3D

DENS_LIN = 7.85e-3
E = L.E
FY = 235.0
FV = FY / sqrt(3.0)
FY_LIM = FY / 10.0
FV_LIM = FV / 10.0

VALID_CASES = {
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

COMMUNES = [("Orléans", "45"), ("Chartres", "28"), ("Ganges", "34"), ("Toulouse", "31"),
            ("Lille", "59"), ("Nantes", "44"), ("Strasbourg", "67"), ("Grenoble", "38"),
            ("Chambéry", "73"), ("Gap", "05")]
RUGOS = ["0", "II", "IIIa", "IIIb", "IV"]


# ======================================================================
#  resoudre_cas PyNite -> ens_resu (convention legacy, cf. règles de signe)
# ======================================================================
def _build_model(coords, conn, charges):
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
    return m


def _ens_resu(m, nom, conn, wpl, avz):
    Mi, Mj, Vi, Vj = {}, {}, {}, {}
    for k in range(len(conn)):
        mem = m.members[f"M{k}"]
        Lk = mem.L()
        Mi[k] = -mem.moment("Mz", 0, nom); Mj[k] = +mem.moment("Mz", Lk, nom)
        Vi[k] = -mem.shear("Fy", 0, nom);  Vj[k] = +mem.shear("Fy", Lk, nom)
    tm = lambda M, k: M / (wpl[k] * FY_LIM) / 100.0
    tv = lambda V, k: V / (avz[k] * FV_LIM) / 100.0
    return dict(
        # déplacements : convention legacy (opposé du physique) -> -DX/-DY PyNite
        depl_t_p_g=-m.nodes["N1"].DX[nom], depl_t_p_d=-m.nodes["N5"].DX[nom],
        fleche_fait=-m.nodes["N3"].DY[nom],
        tx_mom_pot_g=tm(Mj[0], 0), tx_mom_renf_g=tm(Mi[1], 1), tx_mom_pied_arba_g=tm(Mi[2], 2),
        tx_mom_fait=tm(Mj[2], 2), tx_mom_pied_arba_d=tm(Mj[3], 3), tx_mom_renf_d=tm(Mj[4], 4),
        tx_mom_pot_d=tm(Mi[5], 5),
        tx_cis_pot_g=tv(Vi[0], 0), tx_cis_renf_g=tv(Vi[1], 1), tx_cis_pied_arba_g=tv(Vi[2], 2),
        tx_cis_pied_arba_d=tv(Vj[3], 3), tx_cis_renf_d=tv(Vj[4], 4), tx_cis_pot_d=tv(Vj[5], 5),
    )


_real_calcport = L.calcport
_real_optimise = L.optimise_IPE


def _make_pynite_calcport(charges):
    cache = {}

    def pynite_calcport(A, B, K, F, cas, cas_=None, lim_fy=235, debug_capture=None):
        sig = tuple((round(b.aire, 8), round(b.I, 8), round(b.Wpl, 8), round(b.Avz, 8)) for b in B)
        if sig not in cache:
            coords = [(n.X, n.Y) for n in A]
            conn = [(b.Ai.A, b.Aj.A, b.aire, b.I) for b in B]
            wpl = [b.Wpl for b in B]
            avz = [b.Avz for b in B]
            cache[sig] = (_build_model(coords, conn, charges), conn, wpl, avz)
        m, conn, wpl, avz = cache[sig]
        return _ens_resu(m, cas[0], conn, wpl, avz)

    return pynite_calcport


def _patched_optimise(geom, charges):
    L.calcport = _make_pynite_calcport(charges)
    try:
        return _real_optimise(geom, charges)
    finally:
        L.calcport = _real_calcport


def run_pynite(geom, loca, cp):
    L.optimise_IPE = _patched_optimise
    try:
        return L.charge_et_sections(geom, loca, cp)
    finally:
        L.optimise_IPE = _real_optimise


# ======================================================================
#  comparaison
# ======================================================================
def compare(name, geom, loca, cp):
    res_l, st_l = L.charge_et_sections(geom, loca, cp)
    res_p, st_p = run_pynite(geom, loca, cp)

    err = (str(st_l) != str(st_p))
    line = f"  {name:<26} "
    if "traverse" not in res_l or "traverse" not in res_p:
        same = res_l.get("poteau") == res_p.get("poteau") and str(st_l) == str(st_p)
        print(line + f"[non dimensionné] legacy={res_l.get('poteau')!r} pynite={res_p.get('poteau')!r} "
                     f"-> {'OK' if same else 'DIVERGENCE'}")
        return same

    sec_ok = (res_l["poteau"] == res_p["poteau"] and res_l["traverse"] == res_p["traverse"])
    detail = (f"legacy {res_l['poteau']}/{res_l['traverse']}  "
              f"pynite {res_p['poteau']}/{res_p['traverse']}")
    # champs numériques
    num_notes = []
    for f in ("fleche", "ratio_fleche", "deplacement_gauche", "deplacement_droite",
              "depl_tete_pot", "ratio_depl", "taux_trav", "masse"):
        a, b = float(res_l[f]), float(res_p[f])
        d = abs(a - b)
        tol = 0.15 if f in ("fleche", "deplacement_gauche", "deplacement_droite",
                            "depl_tete_pot") else (1.0 if f.startswith("ratio") else
                            (0.0 if f == "masse" else 0.11))
        if f == "taux_trav":
            tol = 10.01   # multiple de 10 ; ±10 seulement si sur une frontière d'arrondi
        if d > tol:
            num_notes.append(f"{f}: {a} vs {b} (Δ={d:g})")
    verdict = "OK" if (sec_ok and not num_notes and not err) else "DIVERGENCE"
    print(line + f"{detail:<44} {verdict}")
    if num_notes:
        for n in num_notes:
            print(f"      - {n}")
    return sec_ok and not num_notes and not err


print("=" * 78)
print(" 1.f — sections retenues : charge_et_sections() legacy vs PyNite dans optimise_IPE")
print("=" * 78)
all_ok = True

print("\n[3 jeux de validation]")
for name, (geom, loca, cp) in VALID_CASES.items():
    all_ok &= compare(name, geom, loca, cp)

print("\n[cas aléatoires reproductibles — seed 20240601]")
rng = random.Random(20240601)
done = 0
tries = 0
while done < 12 and tries < 60:
    tries += 1
    commune, dep = rng.choice(COMMUNES)
    geom = {"hpot": rng.randrange(300, 1001, 25),
            "portee": rng.randrange(600, 2201, 50),
            "pente": round(rng.uniform(0.05, 0.20), 3),
            "longueur": rng.randrange(2000, 6001, 100),
            "entraxe": rng.randrange(400, 801, 25),
            "h_acro": rng.choice([0, 0, 100, 150])}
    loca = {"nom_commune": commune, "ancien_nom_comm": "", "departement": dep,
            "altitude": rng.randrange(20, 900, 10), "rugosite": rng.choice(RUGOS)}
    cp = {"couv": rng.choice([8, 12, 21, 35, 50]), "divers": rng.choice([2, 3, 5, 10, 15])}
    res_l, st_l = L.charge_et_sections(geom, loca, cp)
    if str(st_l) not in ("OK", "None"):
        continue     # zonage introuvable -> on saute (pas un défaut du solveur)
    done += 1
    tag = f"{commune}/{dep} h{geom['hpot']} p{geom['portee']} pente{geom['pente']} rug{loca['rugosite']}"
    all_ok &= compare(tag, geom, loca, cp)

print("\n" + "=" * 78)
print("VERDICT :", "OK — toutes sections identiques" if all_ok else "DIVERGENCE (voir ci-dessus)")
sys.exit(0 if all_ok else 1)

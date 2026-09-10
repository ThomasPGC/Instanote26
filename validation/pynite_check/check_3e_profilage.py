# -*- coding: utf-8 -*-
"""Étape 3 — sous-étape 3.e : profilage (pas de verdict, temps machine-dépendants).

  1. coût d'un `resoudre(poteau, arba)` : ancien modèle (`n_disc = 1`, 6 barres)
     vs jarret discrétisé (`n_disc = 6`, 16 barres) ;
  2. dense vs creux (`scipy.linalg.lu_factor`/`lu_solve` vs
     `scipy.sparse.linalg.splu`) sur la matrice de rigidité réduite du modèle
     discrétisé (47 × 47) — justifie de rester en **dense**.

Chiffres de référence : `docs/historique/jarret-discretise-etape3.md`.

Rejeu :  python validation/pynite_check/check_3e_profilage.py
"""
import sys
import pathlib
import time
import statistics

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "business"))

import numpy as np
import scipy.linalg as sla
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import chargement_nv as chnv
from solveur_pynite import SolveurPyNite

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


def med(fn, n=200):
    fn(); fn()
    ts = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t)
    return statistics.median(ts) * 1e3


def charges_elem(g, l, c):
    ca = chnv.trouve_canton(l["departement"], l["nom_commune"], l["ancien_nom_comm"])
    z = chnv.trouve_zones_NV(l["departement"], ca)
    cpa = -(c["couv"] + c["divers"] + 7) * g["entraxe"] / 10000.0
    return ([("CP_", [0, cpa, cpa, cpa, cpa, 0], [0.0] * 21)]
            + chnv.charge_neige(z[0], l["altitude"], g)
            + chnv.charge_vent(z[1], l["rugosite"], g))


print("=" * 72)
print(" 3.e — profilage jarret discrétisé (indicatif, machine de dev)")
print("=" * 72)
print(f"\n{'cas':<18}{'resoudre n=1':>14}{'resoudre n=6':>14}{'  ×':>7}")
for name, (g, l, c) in CASES.items():
    ch = charges_elem(g, l, c)
    s1 = SolveurPyNite(g, ch, n_disc=1)
    s6 = SolveurPyNite(g, ch, n_disc=6)
    r1 = med(lambda: s1.resoudre("IPE 400", "IPE 360"))
    r6 = med(lambda: s6.resoudre("IPE 400", "IPE 360"))
    print(f"{name:<18}{r1:>12.3f}m{r6:>13.3f}m{r6 / r1:>6.2f}x")

print("\n--- dense vs creux : LU de la matrice réduite (cas-02, n_disc=6) ---")
g, l, c = CASES["cas-02-bas-large"]
s6 = SolveurPyNite(g, charges_elem(g, l, c), n_disc=6)
s6.resoudre("IPE 600", "IPE 500")
K = np.asarray(s6._m.Ke(s6._cp, False, False, False))[np.ix_(s6._free, s6._free)]
Kc = sp.csc_matrix(K)
b = np.random.default_rng(0).random(K.shape[0])
t_dense = med(lambda: sla.lu_solve(sla.lu_factor(K, check_finite=False), b, check_finite=False), 500)
t_sparse = med(lambda: spla.splu(Kc).solve(b), 500)
print(f"  matrice {K.shape[0]}×{K.shape[0]}  ({100.0 * np.count_nonzero(K) / K.size:.0f} % non nuls)")
print(f"  dense  lu_factor + lu_solve : {t_dense * 1e3:6.1f} µs")
print(f"  creux  splu + solve        : {t_sparse * 1e3:6.1f} µs")
print(f"  -> dense {'plus rapide' if t_dense < t_sparse else 'plus lent'} "
      f"(×{max(t_dense, t_sparse) / min(t_dense, t_sparse):.1f}) : on reste en dense.")

print("\n(médianes, ms sauf µs indiqués. Indicatif — voir le journal étape 3.)")

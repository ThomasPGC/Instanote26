# -*- coding: utf-8 -*-
"""Étape 3 — sous-étape 3.c : `SolveurPyNite(n_disc=1)` == `_SolveurLegacy`.

Le backend PyNite a été généralisé (topologie paramétrée par `n_disc`,
`jarret_discret`). En mode « ancien modèle » (`n_disc = 1`) il DOIT rester
rigoureusement identique au solveur maison — c'est ce qui fait du legacy
l'**oracle figé** de l'ancien modèle (le legacy, lui, n'a pas la variante
discrétisée).

On compare `resoudre(poteau, arba)` clé par clé (3 déplacements + 13 taux) sur
tous les cas élémentaires, pour :
  - les 3 jeux de validation ;
  - une série de couples IPE fixes ;
  - des géométries aléatoires reproductibles.

Rejeu :  python validation/pynite_check/check_3c_non_regression_ancien_modele.py
Sortie :  0 = parité < 1e-6 %, 1 = écart.
"""
import sys
import pathlib
import random

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "business"))

import calcport as L
import chargement_nv as chnv
from solveur_pynite import SolveurPyNite

TOL = 1e-6      # % d'écart relatif accepté

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
            ("Lille", "59"), ("Nantes", "44"), ("Strasbourg", "67"), ("Grenoble", "38")]
RUGOS = ["0", "II", "IIIa", "IIIb", "IV"]
COUPLES = [("IPE 200", "IPE 160"), ("IPE 300", "IPE 240"), ("IPE 400", "IPE 360"),
           ("IPE 500", "IPE 450"), ("IPE 550", "IPE 500"), ("IPE 240", "IPE 240")]


def charges_elem(g, l, c):
    ca = chnv.trouve_canton(l["departement"], l["nom_commune"], l["ancien_nom_comm"])
    z = chnv.trouve_zones_NV(l["departement"], ca)
    cpa = -(c["couv"] + c["divers"] + 7) * g["entraxe"] / 10000.0
    return ([("CP_", [0, cpa, cpa, cpa, cpa, 0], [0.0] * 21)]
            + chnv.charge_neige(z[0], l["altitude"], g)
            + chnv.charge_vent(z[1], l["rugosite"], g))


def compare(tag, g, ch):
    leg = L._SolveurLegacy(g, ch)
    pyn = SolveurPyNite(g, ch, n_disc=1)
    worst = 0.0
    worst_where = ""
    for pot, arb in COUPLES:
        rl = dict((k, dict(v)) for k, v in leg.resoudre(pot, arb))
        rp = dict((k, dict(v)) for k, v in pyn.resoudre(pot, arb))
        for cas in rl:
            for key in rl[cas]:
                a, b = rl[cas][key], rp[cas][key]
                d = abs(a - b) / abs(a) * 100 if abs(a) > 1e-9 else abs(b) * 100
                if d > worst:
                    worst, worst_where = d, f"{pot}/{arb} {cas} {key}"
    flag = "OK " if worst <= TOL else "!! "
    print(f"  {flag}{tag:<40} écart max {worst:.2e} %   {worst_where if worst > TOL else ''}")
    return worst <= TOL


print("=" * 78)
print(" 3.c — SolveurPyNite(n_disc=1) == _SolveurLegacy  (oracle de l'ancien modèle)")
print("=" * 78)
ok = True

print("\n[3 jeux de validation]")
for name, (g, l, c) in VALID_CASES.items():
    ok &= compare(name, g, charges_elem(g, l, c))

print("\n[géométries aléatoires — seed 20260910]")
rng = random.Random(20260910)
done = 0
while done < 15:
    commune, dep = rng.choice(COMMUNES)
    g = {"hpot": rng.randrange(300, 1001, 25), "portee": rng.randrange(600, 2201, 50),
         "pente": round(rng.uniform(0.03, 0.20), 3), "longueur": rng.randrange(2000, 6001, 100),
         "entraxe": rng.randrange(400, 801, 25), "h_acro": rng.choice([0, 0, 100, 150])}
    l = {"nom_commune": commune, "ancien_nom_comm": "", "departement": dep,
         "altitude": rng.randrange(20, 900, 10), "rugosite": rng.choice(RUGOS)}
    c = {"couv": rng.choice([8, 12, 21, 35, 50]), "divers": rng.choice([2, 3, 5, 10, 15])}
    try:
        ch = charges_elem(g, l, c)
    except Exception:
        continue
    done += 1
    ok &= compare(f"{commune}/{dep} h{g['hpot']} p{g['portee']} pente{g['pente']}", g, ch)

print("\n" + "=" * 78)
print("VERDICT :", "OK — parité stricte conservée" if ok else "DIVERGENCE (voir ci-dessus)")
sys.exit(0 if ok else 1)

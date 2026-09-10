# -*- coding: utf-8 -*-
"""Étape 3 — sous-étape 3.f [PROTOTYPE] : jarret excentré sur son axe neutre.

Compare, sur les 3 jeux de validation + quelques géométries aléatoires, le
modèle à jarret **colinéaire** à la traverse (défaut de l'étape 3) au modèle
**excentré** (`JARRET_EXCENTRE=1` : nœuds du jarret abaissés sur le centre de
gravité de la section locale, sommet de poteau raccourci, jarret non
colinéaire). Pas de verdict — outil de décision.

Rejeu :  python validation/pynite_check/check_3f_excentre.py
"""
import sys
import os
import json
import subprocess
import pathlib
import random

REPO = pathlib.Path(__file__).resolve().parents[2]

VALID = {
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
CTICM = {"cas-01-compact": "IPE 160/IPE 140", "cas-02-bas-large": "IPE 600/IPE 500",
         "cas-03-haut-fin": "IPE 600/IPE 500"}
COMMUNES = [("Orléans", "45"), ("Ganges", "34"), ("Toulouse", "31"), ("Lille", "59"),
            ("Nantes", "44"), ("Grenoble", "38")]
RUGOS = ["0", "II", "IIIa", "IIIb", "IV"]

_DUMP = r"""
import sys, json
sys.path.insert(0, r"__BIZ__")
import calcport as L
CASES = __CASES__
out = {}
for name, (g, l, c) in CASES.items():
    res, st = L.charge_et_sections(g, l, c)
    out[name] = {k: (round(float(v), 3) if isinstance(v, (int, float)) else v)
                 for k, v in res.items()} | {"status": str(st)}
print(json.dumps(out, ensure_ascii=False))
""".replace("__BIZ__", str(REPO / "business").replace(chr(92), chr(92) * 2))


def run(cases, excentre):
    env = dict(os.environ, MOTEUR_CALCUL="pynite", N_DISC_JARRET="6",
               PYTHONIOENCODING="utf-8",
               JARRET_EXCENTRE="1" if excentre else "0")
    dump = _DUMP.replace("__CASES__", repr(cases))
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", dump],
                       capture_output=True, text=True, env=env, cwd=str(REPO))
    if p.returncode != 0:
        print(p.stderr[-3000:]); sys.exit(2)
    t = p.stdout
    return json.loads(t[t.index("{"):t.rstrip().rindex("}") + 1])


def ligne(r):
    if "traverse" not in r:
        return f"{r.get('poteau', '?')}"
    return (f"{r['poteau']}/{r['traverse']}  taux {r['taux_trav']:.0f}%  "
            f"flèche {r['fleche']:.1f}  dérive {r['depl_tete_pot']:.1f} (H/{r['ratio_depl']})  "
            f"{r['masse']:.0f} kg")


rng = random.Random(20260911)
rand = {}
while len(rand) < 6:
    commune, dep = rng.choice(COMMUNES)
    g = {"hpot": rng.randrange(350, 1001, 25), "portee": rng.randrange(800, 2201, 50),
         "pente": round(rng.uniform(0.03, 0.18), 3), "longueur": rng.randrange(2000, 5001, 100),
         "entraxe": rng.randrange(400, 801, 25), "h_acro": rng.choice([0, 0, 100])}
    rand[f"rnd h{g['hpot']} p{g['portee']} {commune}"] = (
        g, {"nom_commune": commune, "ancien_nom_comm": "", "departement": dep,
            "altitude": rng.randrange(30, 800, 10), "rugosite": rng.choice(RUGOS)},
        {"couv": rng.choice([12, 21, 35]), "divers": rng.choice([3, 5, 10])})

allcases = {**VALID, **rand}
col = run(allcases, False)
exc = run(allcases, True)

print("=" * 100)
print(" 3.f [PROTOTYPE] jarret colinéaire vs excentré sur l'axe neutre — n_disc=6")
print("=" * 100)
for name in allcases:
    tag = f"  ({CTICM[name]} CTICM)" if name in CTICM else ""
    print(f"\n{name}{tag}")
    print(f"   colinéaire : {ligne(col[name])}")
    print(f"   excentré   : {ligne(exc[name])}")

print("\n" + "=" * 100)
print("Pas de verdict — comparer sections retenues / taux / dérive.")

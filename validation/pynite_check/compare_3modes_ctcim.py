# -*- coding: utf-8 -*-
"""Comparaison des backends sur les 3 jeux de validation — support de la
comparaison croisée CTICM (roadmap moteur, étape 2).

Modes (via MOTEUR_CALCUL, un sous-processus par mode) : `legacy` et `pynite`.
Depuis fix/legacy-sij (étape 4), le bug `Sij` est corrigé des deux côtés et
le mode « pynite parité stricte » a été retiré → les deux colonnes doivent
être identiques. Les chiffres historiques à 3 modes (legacy bugué / pynite
parité / corrigé) sont figés dans `validation/COMPARAISON_CTICM.md` § 1.

Sortie : par cas et par mode — poteau/traverse retenus, `taux_trav` arrondi,
`taux_max` brut recalculé, flèche, masse.

Rejeu :  python validation/pynite_check/compare_3modes_ctcim.py
"""
import sys
import os
import json
import subprocess
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

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

# recalcule taux_max BRUT (avant round(.,1)) en reproduisant la boucle ELU de optimise_IPE
_DUMP = r'''
import sys, json
sys.path.insert(0, r"__BIZ__")
import calcport as L, chargement_nv as chnv

COMBI_EFF = [(1.35,1.5,0,0),(1.35,1.5,0,.9),(1.35,0,0,1.5),(1,0,0,1.5),(1.35,0.75,0,1.5),(1,0,1,0)]

def charges_elem(g, l, c):
    ca = chnv.trouve_canton(l["departement"], l["nom_commune"], l["ancien_nom_comm"])
    z = chnv.trouve_zones_NV(l["departement"], ca)
    cpa = -(c["couv"] + c["divers"] + 7) * g["entraxe"] / 10000.0
    return ([("CP_", [0, cpa, cpa, cpa, cpa, 0], [0.0]*21)]
            + chnv.charge_neige(z[0], l["altitude"], g)
            + chnv.charge_vent(z[1], l["rugosite"], g))

def taux_max_brut(g, l, c, pot, arba):
    charges = charges_elem(g, l, c)
    d = dict(L._make_solveur(g, charges).resoudre(pot, arba))
    order = [x[0] for x in charges]
    tk = [k for k in d[order[0]] if "tx" in k]
    tmax = 0.0
    for cv in order[3:]:
        quat = [d[order[0]], d[order[1]], d[order[2]], d[cv]]
        for cb in COMBI_EFF:
            for k in tk:
                v = sum(quat[i][k] * cb[i] for i in range(4))
                if abs(v) <= 1 and abs(v) > tmax:
                    tmax = abs(v)
    return tmax

out = {}
for name, (g, l, c) in __CASES__.items():
    res, st = L.charge_et_sections(g, l, c)
    row = {"status": str(st)}
    if "traverse" in res:
        row["poteau"] = res["poteau"]
        row["traverse"] = res["traverse"]
        for k in ("fleche", "ratio_fleche", "depl_tete_pot", "ratio_depl", "taux_trav", "masse"):
            row[k] = round(float(res[k]), 4)
        row["taux_max_brut_pct"] = round(taux_max_brut(g, l, c, res["poteau"], res["traverse"]) * 100, 2)
    else:
        row["poteau"] = res.get("poteau")
    out[name] = row
print(json.dumps(out, ensure_ascii=False))
'''
_DUMP = _DUMP.replace("__BIZ__", str(REPO / "business").replace(chr(92), chr(92) * 2))
_DUMP = _DUMP.replace("__CASES__", repr(CASES))


def run(moteur):
    env = dict(os.environ, MOTEUR_CALCUL=moteur, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _DUMP],
                       capture_output=True, text=True, env=env, cwd=str(REPO))
    if p.returncode != 0:
        print(f"[{moteur}] KO:\n{p.stderr[-3000:]}")
        sys.exit(2)
    return json.loads(p.stdout[p.stdout.index("{"):p.stdout.rstrip().rindex("}") + 1])


MODES = ["legacy", "pynite"]
data = {m: run(m) for m in MODES}

for name in CASES:
    print(f"\n{'='*84}\n {name}\n{'='*84}")
    print(f"  {'mode':<16}{'poteau':>10}{'traverse':>10}{'taux_trav':>11}{'taux_max brut':>15}"
          f"{'fleche mm':>11}{'masse kg':>10}")
    for m in MODES:
        r = data[m][name]
        if "traverse" not in r:
            print(f"  {m:<16}{r.get('poteau','?'):>10}")
            continue
        print(f"  {m:<16}{r['poteau']:>10}{r['traverse']:>10}{r['taux_trav']:>10.0f}%"
              f"{r['taux_max_brut_pct']:>14.2f}%{r['fleche']:>11.1f}{r['masse']:>10.0f}")

print(f"\n{'='*84}")
print("À compléter avec les notes CTICM de valid/ (sections retenues + taux ELU gouvernant)")
print("pour obtenir la colonne « écart CTICM » des 3 modes.")

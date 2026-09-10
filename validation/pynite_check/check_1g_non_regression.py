# -*- coding: utf-8 -*-
"""Non-régression endpoint — parité `MOTEUR_CALCUL=legacy` vs `=pynite`,
**mode ancien modèle** (`N_DISC_JARRET=1`).

`charge_et_sections()` doit renvoyer EXACTEMENT le même dict avec les deux
backends (c'est ce que consomment `/htmx/calcul` et `/htmx/calcul-pdf` : le
dict est rendu tel quel dans les templates → dict identique ⇒ HTML/PDF
identiques). Bug `Sij` corrigé des deux côtés (branche fix/legacy-sij).

⚠️ Depuis l'étape 3 (jarret discrétisé), le backend `pynite` utilise par
défaut `N_DISC_JARRET=6` (renfort d'épaule à inertie variable) et n'est donc
**plus** identique au legacy. Ce harnais force `N_DISC_JARRET=1` : il vérifie
que le legacy reste l'oracle exact de l'ancien modèle. La validation du modèle
discrétisé est dans `check_3d_discretise.py`.

Le flag est lu à l'import de `calcport` : on compare via deux sous-processus
(un par valeur du flag) qui dumpent le résultat en JSON.

Cas couverts : 30 géométries/zones/charges aléatoires reproductibles
+ un cas non dimensionnable (`PasDeSolutionIPE`) + un cas de zonage introuvable.

Rejeu :  python validation/pynite_check/check_1g_non_regression.py
Sortie :  0 = dicts identiques partout, 1 = au moins une divergence.
"""
import sys
import os
import json
import subprocess
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

# --- programme exécuté dans chaque sous-processus (dump JSON sur stdout) --------
_DUMP = r"""
import sys, json, random
sys.path.insert(0, r"__BIZ__")
import calcport as L

COMMUNES = [("Orleans","45"),("Chartres","28"),("Ganges","34"),("Toulouse","31"),
            ("Lille","59"),("Nantes","44"),("Strasbourg","67"),("Grenoble","38"),
            ("Chambery","73"),("Gap","05"),("Briancon","05"),("Lyon","69")]
RUGOS = ["0","II","IIIa","IIIb","IV"]

def norm(res, st):
    d = {"status": str(st)}
    for k, v in res.items():
        d[k] = round(float(v), 6) if isinstance(v, (int, float)) else v
    return d

out = {}
# cas explicites : non dimensionnable + zonage introuvable
out["_pas_de_solution"] = norm(*L.charge_et_sections(
    {"hpot":1000,"portee":2200,"pente":0.185,"longueur":6000,"entraxe":800,"h_acro":0},
    {"nom_commune":"Ganges","ancien_nom_comm":"","departement":"34","altitude":120,"rugosite":"0"},
    {"couv":50,"divers":20}))
out["_zonage_ko"] = norm(*L.charge_et_sections(
    {"hpot":400,"portee":1000,"pente":0.1,"longueur":2000,"entraxe":500,"h_acro":0},
    {"nom_commune":"CommuneQuiNexistePas","ancien_nom_comm":"","departement":"99","altitude":100,"rugosite":"II"},
    {"couv":15,"divers":3}))

rng = random.Random(777)
done = tries = 0
while done < 30 and tries < 200:
    tries += 1
    commune, dep = rng.choice(COMMUNES)
    g = {"hpot": rng.randrange(300,1001,25), "portee": rng.randrange(600,2201,50),
         "pente": round(rng.uniform(0.05,0.20),3), "longueur": rng.randrange(2000,6001,100),
         "entraxe": rng.randrange(400,801,25), "h_acro": rng.choice([0,0,100,150])}
    l = {"nom_commune":commune,"ancien_nom_comm":"","departement":dep,
         "altitude": rng.randrange(20,1400,10), "rugosite": rng.choice(RUGOS)}
    c = {"couv": rng.choice([8,12,21,35,50]), "divers": rng.choice([2,3,5,10,15])}
    res, st = L.charge_et_sections(g, l, c)
    if str(st) not in ("OK", "None"):
        continue
    done += 1
    out[f"rnd{done:02d}"] = norm(res, st)

print(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
""".replace("__BIZ__", str(REPO / "business").replace(chr(92), chr(92)*2))


def _run(moteur):
    env = dict(os.environ, MOTEUR_CALCUL=moteur, PYTHONIOENCODING="utf-8",
               N_DISC_JARRET="1")     # parité = ancien modèle uniquement (cf. docstring)
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _DUMP],
                       capture_output=True, text=True, env=env, cwd=str(REPO))
    if p.returncode != 0:
        print(f"[{moteur}] sous-processus KO :\n{p.stderr[-2000:]}")
        sys.exit(2)
    # les bannières PyNite (Statics Check...) partent sur stdout : on isole le JSON
    txt = p.stdout
    start = txt.index("{")
    return json.loads(txt[start:])


leg = _run("legacy")     # solveur maison (bug Sij corrigé)
pyn = _run("pynite")     # backend PyNiteFEA

keys = sorted(set(leg) | set(pyn))
ndiff = 0
for k in keys:
    a, b = leg.get(k), pyn.get(k)
    if a != b:
        ndiff += 1
        print(f"DIVERGENCE [{k}]")
        for kk in sorted(set(a or {}) | set(b or {})):
            if (a or {}).get(kk) != (b or {}).get(kk):
                print(f"    {kk}: legacy={a.get(kk)!r}  pynite={b.get(kk)!r}")

print(f"\n{len(keys)} cas comparés — {ndiff} divergence(s)")
print("VERDICT :", "OK" if ndiff == 0 else "DIVERGENCE")
sys.exit(0 if ndiff == 0 else 1)

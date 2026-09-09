# -*- coding: utf-8 -*-
"""Garde-fou dépendances runtime — `MOTEUR_CALCUL=pynite`.

Après un `charge_et_sections()` complet avec le backend PyNite :
  - `matplotlib` NE DOIT PAS être chargé (`sys.modules`) — il est neutralisé
    par le stub `Pynite.ShearWall` en tête de `business/solveur_pynite.py`
    (PyNiteFEA le tire en dépendance pour ses tracés, qu'on n'utilise pas :
    schémas = SVG `portique.js`, PDF = WeasyPrint) ;
  - `scipy` DOIT l'être — `Pynite/FEModel3D.py` fait `import scipy` au niveau
    module, et `solveur_pynite.py` utilise `scipy.linalg.lu_factor`.

À rejouer lors de **toute montée de version de PyNiteFEA** : si `matplotlib`
réapparaît, le stub ne couvre plus tous les imports au niveau module de
`.venv/.../Pynite/` (voir CLAUDE.md, « Check-list montée de version PyNite »).

Rejeu :  python validation/pynite_check/check_deps_runtime.py
Sortie :  0 = OK, 1 = matplotlib chargé (ou scipy absent).
"""
import sys
import os
import subprocess
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

_PROBE = (
    "import sys; sys.path.insert(0, r'%s'); import calcport as L; "
    "L.charge_et_sections("
    "{'hpot':1000,'portee':800,'pente':0.10,'longueur':4000,'entraxe':500,'h_acro':100},"
    "{'nom_commune':'Brest','ancien_nom_comm':'','departement':'29','altitude':50,'rugosite':'0'},"
    "{'couv':20,'divers':5}); "
    "print('MOTEUR=%%s MATPLOTLIB=%%s SCIPY=%%s' %% "
    "(L.MOTEUR_CALCUL, 'matplotlib' in sys.modules, 'scipy' in sys.modules))"
) % str(REPO / "business")

env = dict(os.environ, MOTEUR_CALCUL="pynite", PYTHONIOENCODING="utf-8")
p = subprocess.run([sys.executable, "-X", "utf8", "-c", _PROBE],
                   capture_output=True, text=True, env=env, cwd=str(REPO))
if p.returncode != 0:
    print("sous-processus KO :\n" + p.stderr[-3000:])
    sys.exit(2)

line = next((l for l in p.stdout.splitlines() if l.startswith("MOTEUR=")), "")
print(line or p.stdout.strip()[-500:])

mpl_loaded = "MATPLOTLIB=True" in line
scipy_loaded = "SCIPY=True" in line
moteur_ok = "MOTEUR=pynite" in line

ok = moteur_ok and not mpl_loaded and scipy_loaded
if not moteur_ok:
    print("  ATTENDU: MOTEUR=pynite (le flag n'a pas été pris ?)")
if mpl_loaded:
    print("  ÉCHEC: matplotlib est chargé → le stub Pynite.ShearWall ne couvre "
          "plus tous les imports au niveau module. Voir CLAUDE.md.")
if not scipy_loaded:
    print("  INATTENDU: scipy absent (PyNite/FEModel3D.py devrait l'importer).")
print("VERDICT :", "OK" if ok else "ÉCHEC")
sys.exit(0 if ok else 1)

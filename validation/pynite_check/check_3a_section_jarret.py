# -*- coding: utf-8 -*-
"""Étape 3 — sous-étape 3.a : fonction de section du jarret discrétisé.

Vérifie `jarret_discret.caracs_section_jarret` (section en I à 3 semelles +
congés `r`, reconstituée par intégration du contour) :

  1. recoupement avec PropSection v1.0.4 (`validation/jarrets/*.png`,
     « section paramétrée » n°7) sur IPE 160 / 300 / 450, hr = 150 % et ~200 % ;
  2. garde-fou : le contour à 2 semelles (hauteur h) retombe sur l'IPE
     catalogue au chiffre près (l'intégrateur est juste) ;
  3. monotonie de la loi dégressive (A, Iy, Wpl.y décroissent du genou vers la
     sortie) ;
  4. `sections_jarret(arba, 1)` == `[calcport.jarret(arba)]` (mode ancien
     modèle, parité legacy).

Rejeu :  python validation/pynite_check/check_3a_section_jarret.py
Sortie :  0 = OK, 1 = écart hors tolérance.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "business"))

import calcport as L
import jarret_discret as J

# tolérances (%) — prédimensionnement pour étude de prix
TOL = {"A": 0.5, "IyG": 1.0, "IzG": 0.5, "zG": 1.5}

ok = True


def _chk(nom, val, ref, tol, ctx):
    global ok
    e = 100.0 * (val - ref) / ref
    flag = "OK " if abs(e) <= tol else "!! "
    if abs(e) > tol:
        ok = False
    print(f"  {flag}{ctx:<22}{nom:<5}{val:>13.3f}{ref:>13.3f}{e:>9.3f} %  (tol {tol})")


print("=" * 78)
print(" 3.a — section du jarret discrétisé : recoupement PropSection + garde-fous")
print("=" * 78)

print("\n[1] caracs_section_jarret vs PropSection (contour réel, 3 semelles + r)")
for prof, hr, A_ref, Iy_ref, Iz_ref, zG_ref in J._REF_PROPSECTION:
    d = J._profil(prof)
    b, tf, tw, r, h = (d[k] / 10.0 for k in ("b", "tf", "tw", "r", "h"))
    demi = J._demi_contour_droit(b, tf, tw, r, hr * h, (hr - 1.0) * h, 24)
    pts = demi + [(-x, z) for x, z in reversed(demi)]
    A, zG, Iy, Iz = J._moments_polygone(pts)
    ctx = f"{prof} x{hr:.3f}"
    _chk("A", A, A_ref, TOL["A"], ctx)
    _chk("IyG", Iy, Iy_ref, TOL["IyG"], ctx)
    _chk("IzG", Iz, Iz_ref, TOL["IzG"], ctx)
    _chk("zG", zG, zG_ref, TOL["zG"], ctx)

print("\n[2] garde-fou intégrateur : contour 2 semelles == IPE catalogue")
for prof in ("IPE 160", "IPE 300", "IPE 450", "IPE 600"):
    d = J._profil(prof)
    b, tf, tw, r, h = (d[k] / 10.0 for k in ("b", "tf", "tw", "r", "h"))
    demi = J._demi_contour_droit(b, tf, tw, r, h, 0.0, 24, avec_interm=False)
    pts = demi + [(-x, z) for x, z in reversed(demi)]
    A, zG, Iy, _Iz = J._moments_polygone(pts)
    wpl = J._wpl_y_polygone(pts, A, zG)
    _chk("A", A, d["A"], 0.3, f"{prof} (cat.)")
    _chk("Iy", Iy, d["Iy"], 0.3, f"{prof} (cat.)")
    _chk("Wpl.y", wpl, d["Wpl.y"], 0.5, f"{prof} (cat.)")

print("\n[3] monotonie de la loi dégressive (genou -> sortie)")
for prof in ("IPE 160", "IPE 240", "IPE 400", "IPE 600"):
    secs = J.sections_jarret(prof, 6)
    mono = all(secs[k + 1][key] < secs[k][key]
               for k in range(len(secs) - 1)
               for key in ("A", "Iy", "Wpl.y"))
    print(f"  {'OK ' if mono else '!! '}{prof:<10} "
          f"A {secs[0]['A']:.1f}->{secs[-1]['A']:.1f}  "
          f"Iy {secs[0]['Iy']:.0f}->{secs[-1]['Iy']:.0f}  "
          f"Wpl.y {secs[0]['Wpl.y']:.0f}->{secs[-1]['Wpl.y']:.0f}")
    ok = ok and mono

print("\n[4] sections_jarret(arba, 1) == [calcport.jarret(arba)]  (parité legacy)")
for prof in ("IPE 140", "IPE 300", "IPE 550"):
    a = J.sections_jarret(prof, 1)
    b = [L.jarret(prof)]
    same = a == b
    print(f"  {'OK ' if same else '!! '}{prof}")
    ok = ok and same

print("\n" + "=" * 78)
print("VERDICT :", "OK" if ok else "ÉCART — voir ci-dessus")
sys.exit(0 if ok else 1)

# -*- coding: utf-8 -*-
"""Étape 3 — sous-étape 3.b : topologie discrétisée + expansion des charges.

Vérifie `jarret_discret.construire_topologie` / `expanser_charges` /
`sections_par_barre` :

  1. `n_disc = 1` reproduit EXACTEMENT `calcport.def_noeud_barres` (coords,
     connectivité, rôles) — garde-fou de parité legacy ;
  2. `n_disc = 6` : comptes de nœuds/barres, N0..N6 préservés, tronçons de
     jarret colinéaires à la traverse, épaule correctement ancrée (N1 à gauche,
     N5 à droite), tronçons numérotés depuis l'épaule ;
  3. `expanser_charges` : identité en `n_disc = 1` ; en `n_disc = 6`, recopie
     de la charge de jarret sur les tronçons + slots nodaux N0..N6 conservés +
     nœuds intérieurs à charge nulle ;
  4. `sections_par_barre` en `n_disc = 1` == correspondance de
     `calcport.change_sections` (poteau / jarret(arba) / traverse) ;
  5. ordre d'insertion des nœuds PyNite == ordre de `topo.coords` (le masque
     des DDL libres du solveur en dépend).

Rejeu :  python validation/pynite_check/check_3b_topologie.py
Sortie :  0 = OK, 1 = écart.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "business"))

import calcport as L
import jarret_discret as J

GEOMS = [
    {"hpot": 350, "portee": 400, "pente": 0.10, "longueur": 2000, "entraxe": 400, "h_acro": 0},
    {"hpot": 500, "portee": 2200, "pente": 0.03, "longueur": 4000, "entraxe": 800, "h_acro": 100},
    {"hpot": 1000, "portee": 800, "pente": 0.10, "longueur": 4000, "entraxe": 500, "h_acro": 100},
    {"hpot": 700, "portee": 1500, "pente": 0.15, "longueur": 3000, "entraxe": 600, "h_acro": 0},
]

ok = True


def _fail(msg):
    global ok
    ok = False
    print("  !! " + msg)


print("=" * 78)
print(" 3.b — topologie discrétisée + expansion des charges")
print("=" * 78)

print("\n[1] n_disc=1 == def_noeud_barres")
for g in GEOMS:
    A, B = L.def_noeud_barres(g, "IPE 200", "IPE 200")
    t = J.construire_topologie(g, 1)
    ref_coords = [(nd.X, nd.Y) for nd in A]
    ref_conn = [(b.Ai.A, b.Aj.A) for b in B]
    if t.coords != ref_coords:
        _fail(f"coords h{g['hpot']} p{g['portee']} : {t.coords} != {ref_coords}")
    if t.conn != ref_conn:
        _fail(f"conn h{g['hpot']} p{g['portee']} : {t.conn} != {ref_conn}")
    want = [("poteau",), ("jarret", 0), ("traverse",), ("traverse",), ("jarret", 0), ("poteau",)]
    if t.roles != want:
        _fail(f"roles : {t.roles}")
print("  OK" if ok else "  (voir ci-dessus)")

print("\n[2] n_disc=6 : géométrie")
for g in GEOMS:
    t = J.construire_topologie(g, 6)
    A, B = L.def_noeud_barres(g, "IPE 200", "IPE 200")
    ref_coords = [(nd.X, nd.Y) for nd in A]
    if t.nN != 17 or t.nbar != 16:
        _fail(f"nN={t.nN} nbar={t.nbar} (attendu 17/16)")
    if t.coords[:7] != ref_coords:
        _fail("N0..N6 non préservés")
    ig, jg = t.conn[t.bar_epaule_g]
    idd, jd = t.conn[t.bar_epaule_d]
    if ig != 1:
        _fail(f"épaule G non ancrée à N1 (barre {t.bar_epaule_g} = {ig}-{jg})")
    if jd != 5:
        _fail(f"épaule D non ancrée à N5 (barre {t.bar_epaule_d} = {idd}-{jd})")
    if [t.roles[b][1] for b in t.bars_jarret_g] != [0, 1, 2, 3, 4, 5]:
        _fail("tronçons jarret G mal numérotés")
    if [t.roles[b][1] for b in t.bars_jarret_d] != [5, 4, 3, 2, 1, 0]:
        _fail("tronçons jarret D mal numérotés")
    # colinéarité
    (x1, y1), (x2, y2) = t.coords[1], t.coords[2]
    for b in t.bars_jarret_g:
        (xa, ya), (xb, yb) = t.coords[t.conn[b][0]], t.coords[t.conn[b][1]]
        if abs((xb - xa) * (y2 - y1) - (yb - ya) * (x2 - x1)) > 1e-6:
            _fail(f"tronçon jarret G {b} non colinéaire à N1-N2")
    (x4, y4), (x5, y5) = t.coords[4], t.coords[5]
    for b in t.bars_jarret_d:
        (xa, ya), (xb, yb) = t.coords[t.conn[b][0]], t.coords[t.conn[b][1]]
        if abs((xb - xa) * (y5 - y4) - (yb - ya) * (x5 - x4)) > 1e-6:
            _fail(f"tronçon jarret D {b} non colinéaire à N4-N5")
print("  OK" if ok else "  (voir ci-dessus)")

print("\n[3] expanser_charges")
CH = [("CP_", [0, -1.2, -1.5, -1.6, -1.2, 0], [float(i) for i in range(21)]),
      ("NEI_", [0, -2.0, -2.1, -2.1, -2.0, 0], [0.0] * 21)]
t1 = J.construire_topologie(GEOMS[0], 1)
if J.expanser_charges(CH, t1) != CH:
    _fail("expanser_charges non identité en n_disc=1")
t6 = J.construire_topologie(GEOMS[0], 6)
e6 = J.expanser_charges(CH, t6)
want_bar = [0, -1.2, -1.2, -1.2, -1.2, -1.2, -1.2, -1.5, -1.6,
            -1.2, -1.2, -1.2, -1.2, -1.2, -1.2, 0]
if e6[0][1] != want_bar:
    _fail(f"expansion barre : {e6[0][1]}")
if len(e6[0][2]) != 3 * t6.nN or e6[0][2][:21] != [float(i) for i in range(21)]:
    _fail("slots nodaux N0..N6 non conservés")
if any(e6[0][2][21:]):
    _fail("nœuds intérieurs de jarret : charge nodale non nulle")
print("  OK" if ok else "  (voir ci-dessus)")

print("\n[4] sections_par_barre en n_disc=1 == change_sections")
t1 = J.construire_topologie(GEOMS[1], 1)
sb = J.sections_par_barre(t1, "IPE 330", "IPE 270")
want = [L.IPE.dict_carac("IPE 330"), L.jarret("IPE 270"), L.IPE.dict_carac("IPE 270"),
        L.IPE.dict_carac("IPE 270"), L.jarret("IPE 270"), L.IPE.dict_carac("IPE 330")]
if sb != want:
    _fail(f"sections_par_barre : {sb}")
print("  OK" if ok else "  (voir ci-dessus)")

print("\n[5] ordre des nœuds PyNite == ordre topo.coords")
try:
    from Pynite import FEModel3D, Analysis
    t6 = J.construire_topologie(GEOMS[2], 6)
    m = FEModel3D()
    m.add_material("acier", L.E, L.E / 2.6, 0.3, 0.0)
    for k, (x, y) in enumerate(t6.coords):
        m.add_node(f"N{k}", x, y, 0.0)
        m.def_support(f"N{k}", False, False, True, True, True, False)
    m.def_support("N0", True, True, True, True, True, False)
    m.def_support("N6", True, True, True, True, True, False)
    for k, (i, j) in enumerate(t6.conn):
        m.add_section(f"S{k}", 1.0, 1.0, 1.0, 1.0)
        m.add_member(f"M{k}", f"N{i}", f"N{j}", "acier", f"S{k}")
    Analysis._prepare_model(m)
    order = list(m.nodes.keys())
    if order != [f"N{k}" for k in range(t6.nN)]:
        _fail(f"ordre nœuds PyNite : {order}")
    free = sum(1 for nd in m.nodes.values()
               for s in (nd.support_DX, nd.support_DY, nd.support_DZ,
                         nd.support_RX, nd.support_RY, nd.support_RZ) if not s)
    # 17 nœuds : 3 DDL utiles chacun (dx,dy,rz) - 2 translations bloquées à N0 et N6
    if free != 17 * 3 - 4:
        _fail(f"DDL libres = {free} (attendu {17 * 3 - 4})")
    print("  OK" if ok else "  (voir ci-dessus)")
except ImportError:
    print("  (PyNite indisponible — sous-test sauté)")

print("\n" + "=" * 78)
print("VERDICT :", "OK" if ok else "ÉCART — voir ci-dessus")
sys.exit(0 if ok else 1)

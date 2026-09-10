# -*- coding: utf-8 -*-
"""Étape 3 — sous-étape 3.d : modèle à jarret discrétisé (n_disc = 6, excentré).

Fait tourner `charge_et_sections()` avec le renfort d'épaule discrétisé et
**excentré sur son axe neutre** (`MOTEUR_CALCUL=pynite`, `N_DISC_JARRET=6`,
`JARRET_EXCENTRE` au défaut = activé) sur les 3 jeux de validation et vérifie :

  1. **non-régression** : le dict résultat est identique aux valeurs de
     référence figées ci-dessous (modèle discrétisé + excentré) ;
  2. **garde de sécurité** : les sections retenues ne descendent PAS sous les
     sections CTICM, et `taux_max` brut ne chute pas de plus de 8 pts sous
     l'ancien modèle (legacy) — sinon le modèle serait dangereusement optimiste
     → ÉCHEC ;
  3. **suivi** (informatif) : écart aux sections CTICM et à l'ancien modèle.

Rejeu :  python validation/pynite_check/check_3d_discretise.py
Sortie :  0 = non-régression + garde OK ; 1 = régression ou garde franchie.
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

# Référence FIGÉE — modèle discrétisé (n_disc = 6) + excentré sur l'axe neutre.
REF_DISCRET = {
    "cas-01-compact": dict(poteau="IPE 160", traverse="IPE 140", fleche=2.8, ratio_fleche=1437,
                           deplacement_gauche=21.2, deplacement_droite=21.4, depl_tete_pot=21.4,
                           ratio_depl=163, taux_trav=40.0, masse=168, taux_max_brut=37.08,
                           cis_ecart_fleche_pct=0.3, cis_taux_ame_jarret_pct=11.0),
    "cas-02-bas-large": dict(poteau="IPE 600", traverse="IPE 550", fleche=64.2, ratio_fleche=342,
                             deplacement_gauche=2.8, deplacement_droite=5.6, depl_tete_pot=5.6,
                             ratio_depl=889, taux_trav=100.0, masse=3786, taux_max_brut=98.26,
                             cis_ecart_fleche_pct=0.8, cis_taux_ame_jarret_pct=23.0),
    "cas-03-haut-fin": dict(poteau="IPE 600", traverse="IPE 500", fleche=2.0, ratio_fleche=3983,
                            deplacement_gauche=59.7, deplacement_droite=59.4, depl_tete_pot=59.7,
                            ratio_depl=167, taux_trav=50.0, masse=3242, taux_max_brut=54.02,
                            cis_ecart_fleche_pct=0.6, cis_taux_ame_jarret_pct=13.5),
}

# Ancien modèle (legacy) — pour le suivi / la garde de sécurité.
REF_LEGACY = {
    "cas-01-compact": dict(poteau="IPE 160", traverse="IPE 140", taux_max_brut=37.84),
    "cas-02-bas-large": dict(poteau="IPE 600", traverse="IPE 600", taux_max_brut=98.84),
    "cas-03-haut-fin": dict(poteau="IPE 600", traverse="IPE 500", taux_max_brut=54.92),
}

CTICM = {"cas-01-compact": ("IPE 160", "IPE 140"),
         "cas-02-bas-large": ("IPE 600", "IPE 500"),
         "cas-03-haut-fin": ("IPE 600", "IPE 500")}

_ORDRE_IPE = ["IPE 80", "IPE 100", "IPE 120", "IPE 140", "IPE 160", "IPE 180", "IPE 200",
              "IPE 220", "IPE 240", "IPE 270", "IPE 300", "IPE 330", "IPE 360", "IPE 400",
              "IPE 450", "IPE 500", "IPE 550", "IPE 600"]

_DUMP = r"""
import sys, json
sys.path.insert(0, r"__BIZ__")
import calcport as L, chargement_nv as chnv
COMBI_EFF = [(1.35,1.5,0,0),(1.35,1.5,0,.9),(1.35,0,0,1.5),(1,0,0,1.5),(1.35,0.75,0,1.5),(1,0,1,0)]
def charges_elem(g,l,c):
    ca=chnv.trouve_canton(l["departement"],l["nom_commune"],l["ancien_nom_comm"])
    z=chnv.trouve_zones_NV(l["departement"],ca)
    cpa=-(c["couv"]+c["divers"]+7)*g["entraxe"]/10000.0
    return [("CP_",[0,cpa,cpa,cpa,cpa,0],[0.0]*21)]+chnv.charge_neige(z[0],l["altitude"],g)+chnv.charge_vent(z[1],l["rugosite"],g)
def tmax_brut(g,l,c,pot,arb):
    ch=charges_elem(g,l,c); d=dict(L._make_solveur(g,ch).resoudre(pot,arb)); order=[x[0] for x in ch]
    tk=[k for k in d[order[0]] if "tx" in k]; tm=0.0
    for cv in order[3:]:
        quat=[d[order[0]],d[order[1]],d[order[2]],d[cv]]
        for cb in COMBI_EFF:
            for k in tk:
                v=sum(quat[i][k]*cb[i] for i in range(4))
                if abs(v)<=1 and abs(v)>tm: tm=abs(v)
    return tm
CASES = __CASES__
out={}
for name,(g,l,c) in CASES.items():
    res,st=L.charge_et_sections(g,l,c)
    row={"status":str(st)}
    for k,v in res.items():
        row[k]=round(float(v),6) if isinstance(v,(int,float)) else v
    if "traverse" in res:
        row["taux_max_brut"]=round(tmax_brut(g,l,c,res["poteau"],res["traverse"])*100,2)
    out[name]=row
print(json.dumps(out,ensure_ascii=False))
""".replace("__BIZ__", str(REPO / "business").replace(chr(92), chr(92) * 2)).replace("__CASES__", repr(CASES))


def run_discret():
    env = dict(os.environ, MOTEUR_CALCUL="pynite", N_DISC_JARRET="6", PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _DUMP],
                       capture_output=True, text=True, env=env, cwd=str(REPO))
    if p.returncode != 0:
        print("sous-processus KO :\n" + p.stderr[-3000:])
        sys.exit(2)
    t = p.stdout
    return json.loads(t[t.index("{"):t.rstrip().rindex("}") + 1])


def plus_leger(a, b):
    return _ORDRE_IPE.index(a) < _ORDRE_IPE.index(b)


print("=" * 84)
print(" 3.d — modèle à jarret discrétisé (n_disc = 6) : non-régression + garde + suivi CTICM")
print("=" * 84)

data = run_discret()
ok = True

for name in CASES:
    r = data[name]
    ref = REF_DISCRET[name]
    leg = REF_LEGACY[name]
    ct = CTICM[name]
    print(f"\n{name}")
    print(f"  retenu     : {r['poteau']} / {r['traverse']}   taux_trav {r['taux_trav']:.0f}%   "
          f"taux_max brut {r['taux_max_brut']:.2f}%   flèche {r['fleche']} mm   dérive {r['depl_tete_pot']} mm   {r['masse']} kg")
    print(f"  legacy     : {leg['poteau']} / {leg['traverse']}   taux_max brut {leg['taux_max_brut']:.2f}%")
    print(f"  CTICM      : {ct[0]} / {ct[1]}")

    # 1. non-régression vs référence figée
    for k, v in ref.items():
        got = r.get(k)
        if isinstance(v, float):
            bad = got is None or abs(got - v) > 0.02
        else:
            bad = got != v
        if bad:
            ok = False
            print(f"  !! RÉGRESSION {k}: {got!r} != réf {v!r}")

    # 2. garde de sécurité : ne pas descendre SOUS les sections CTICM,
    #    ni s'effondrer en taux_max vs l'ancien modèle.
    if plus_leger(r["poteau"], ct[0]) or plus_leger(r["traverse"], ct[1]):
        ok = False
        print(f"  !! GARDE : section retenue SOUS le CTICM "
              f"({r['poteau']}/{r['traverse']} vs {ct[0]}/{ct[1]})")
    chute = leg["taux_max_brut"] - r["taux_max_brut"]
    if chute > 8.0:
        ok = False
        print(f"  !! GARDE : taux_max brut chute de {chute:.1f} pts sous l'ancien "
              f"modèle (trop optimiste)")

    # 3. suivi (informatif)
    if plus_leger(r["poteau"], leg["poteau"]) or plus_leger(r["traverse"], leg["traverse"]):
        print(f"  -> plus léger que l'ancien modèle ({leg['poteau']}/{leg['traverse']}) "
              f"— attendu de l'excentrement (géométrie plus juste)")
    if (r["poteau"], r["traverse"]) == ct:
        print("  -> sections CTICM atteintes")
    else:
        d_arb = _ORDRE_IPE.index(r["traverse"]) - _ORDRE_IPE.index(ct[1])
        d_pot = _ORDRE_IPE.index(r["poteau"]) - _ORDRE_IPE.index(ct[0])
        print(f"  -> écart CTICM : poteau {d_pot:+d} cran(s), arbalétrier {d_arb:+d} cran(s) "
              f"(informatif)")

print("\n" + "=" * 84)
print("VERDICT :", "OK (non-régression + garde)" if ok else "ÉCHEC — voir ci-dessus")
sys.exit(0 if ok else 1)

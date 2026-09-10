#! /usr/bin/python3
# coding: utf-8

"""Backend de résolution structurelle sur PyNiteFEA — option A « assembleur ».

Utilisé par `calcport.optimise_IPE` quand la variable d'environnement
`MOTEUR_CALCUL=pynite`. Résultats identiques au solveur maison
(`calcport._SolveurLegacy`), bug `Sij` compris = **corrigé des deux côtés**
(chaque cas reconstruit ses efforts avec son propre `fer`). Voir CLAUDE.md,
section « Roadmap moteur de calcul », étape 1 (sous-étapes 1.a–1.f, découpage
A→H, branche `fix/legacy-sij`) pour le contexte, les règles de signe et les
parités démontrées.

Principe : PyNite fournit l'assemblage de la matrice de rigidité (`m.Ke`), la
conversion charges → efforts d'encastrement (`m.P`, `m.FER`, `member.fer`) et
le catalogue de sections mutables. `SolveurPyNite` pilote lui-même :
  - la partition selon les DDL libres (CL bi-articulées + modèle plan) ;
  - la factorisation (`scipy.linalg.lu_factor`, une fois par itération IPE) ;
  - la résolution `lu_solve` **par cas élémentaire** (jamais via les
    combinaisons ELU/ELS natives de PyNite) ;
  - la reconstruction des efforts d'about `floc = ke·(T·d) + fer` et des taux
    `tx_*` avec la formule exacte du legacy.

Le modèle PyNite est construit une seule fois (dans `__init__`) et réutilisé
sur toutes les itérations de `optimise_IPE` : par itération on ne paie que la
mutation des 6 sections, `m.Ke()`, la factorisation, `lu_solve` par cas et une
extraction numpy.

⚠️ Dépend de méthodes semi-internes de PyNite (`Ke`, `P`, `FER`, `member.fer`,
`member.ke`, `member.T`). `PyNiteFEA` est épinglé à `==3.0.0` ; toute montée de
version est un projet à part (re-run des scripts `validation/pynite_check/`).

Dépendances runtime effectivement chargées : `numpy`, `scipy`, `PrettyTable`.
`matplotlib` (dépendance de PyNiteFEA, pour ses fonctions de tracé qu'on
n'utilise pas) est **neutralisé** : voir le stub `Pynite.ShearWall` ci-dessous.
"""

import os
import sys as _sys
import types as _types

# --- neutralise l'import de matplotlib au chargement de PyNite -----------------
# `Pynite/__init__.py` fait `from Pynite.ShearWall import ShearWall`, et
# `Pynite/ShearWall.py` (3.0.0) importe `matplotlib.pyplot` au niveau module. On
# n'utilise NI ShearWall NI aucune fonction de tracé de PyNite (schémas SVG et
# PDF générés par ailleurs). On injecte donc un faux module `Pynite.ShearWall`
# avant tout import de PyNite : matplotlib n'est jamais chargé à l'exécution
# (il reste installé comme dépendance de PyNiteFEA, mais dormant). scipy reste
# nécessaire — `Pynite/FEModel3D.py` fait `import scipy` et on s'en sert pour la
# factorisation (`scipy.linalg.lu_factor`).
# ⚠️ À REVÉRIFIER à toute montée de version de PyNiteFEA : cf. CLAUDE.md,
# « Check-list montée de version PyNite », + `validation/pynite_check/
# check_deps_runtime.py`.
if "Pynite.ShearWall" not in _sys.modules:
    _stub = _types.ModuleType("Pynite.ShearWall")
    _stub.ShearWall = type("ShearWall", (), {})   # placeholder inutilisé
    _sys.modules["Pynite.ShearWall"] = _stub

import numpy as np
import scipy.linalg as sla
from Pynite import FEModel3D
from Pynite import Analysis

from calcport import E
import jarret_discret as jd

# Poids propre acier : daN/cm de barre par cm² de section (comme crea_matrice_force).
DENS_LIN = 7.85e-3

# Indices, dans le vecteur d'efforts d'about local 12 de PyNite
# [Nxi,Vyi,Vzi,Mxi,Myi,Mzi, Nxj,Vyj,Vzj,Mxj,Myj,Mzj], des composantes dans le plan.
_IDX6 = np.array([0, 1, 5, 6, 7, 11])

_FY = 235.0                      # S235 (comme calculer_et_verifier_resultats, fy en dur)
_FY_LIM = _FY / 10.0
_FV_LIM = (_FY / 3.0 ** 0.5) / 10.0

# Attributs posés par `SolveurPyNite._build_model` — capturés/restaurés par
# `_ensure_built` quand la géométrie dépend de la traverse (mode excentré).
_ETAT_MODELE = ("_topo", "_conn", "_nbar", "_tx_mom", "_tx_cis", "_m", "_nN",
                "_free", "_rhs", "_rhs_cp_ext", "_rhs_sw", "_fer_ext", "_fer_sw", "_T")


def _tx_points(topo):
    """Correspondance clé de taux -> (barre, extrémité) construite depuis la
    topologie (`jarret_discret.construire_topologie`). "i" = nœud origine de la
    barre, "j" = nœud fin. Efforts d'about legacy [Ni,Vi,Mi,Nj,Vj,Mj] :
    comp. 2 = Mi, 5 = Mj, 1 = Vi, 4 = Vj.

    En `n_disc = 1` reproduit EXACTEMENT les tuples `_TX_MOM`/`_TX_CIS`
    historiques (poteau=0/dernier, épaule=1/4, sortie de jarret=2/3).
    """
    b_trav_g = 1 + topo.n_disc                    # 1re barre de traverse (après poteau + jarret G)
    b_trav_d = b_trav_g + 1
    b_last = topo.nbar - 1
    mom = (
        ("tx_mom_pot_g", 0, "j"),
        ("tx_mom_renf_g", topo.bar_epaule_g, "i"),
        ("tx_mom_pied_arba_g", b_trav_g, "i"),
        ("tx_mom_fait", b_trav_g, "j"),
        ("tx_mom_pied_arba_d", b_trav_d, "j"),
        ("tx_mom_renf_d", topo.bar_epaule_d, "j"),
        ("tx_mom_pot_d", b_last, "i"),
    )
    cis = (
        ("tx_cis_pot_g", 0, "i"),
        ("tx_cis_renf_g", topo.bar_epaule_g, "i"),
        ("tx_cis_pied_arba_g", b_trav_g, "i"),
        ("tx_cis_pied_arba_d", b_trav_d, "j"),
        ("tx_cis_renf_d", topo.bar_epaule_d, "j"),
        ("tx_cis_pot_d", b_last, "j"),
    )
    return mom, cis


class SolveurPyNite:
    """Même interface que `calcport._SolveurLegacy` : `resoudre(poteau, arba)`
    renvoie `[(nom_cas, ens_resu), ...]` pour chaque cas élémentaire de `charges`,
    où `ens_resu` a exactement les clés produites par `calcport.calcport`
    (3 déplacements clés + 13 taux `tx_*`), en convention legacy."""

    def __init__(self, geom, charges, n_disc=1, excentre=None):
        # Chaque cas reconstruit ses efforts d'about avec SON PROPRE `fer`
        # (efforts d'encastrement du cas), et pas avec celui du CP : le bug `Sij`
        # du legacy (cf. CLAUDE.md) n'est PAS reproduit. Le mode « parité stricte »
        # (fer_CP pour tous les cas), scaffold de la bascule, a été retiré à
        # l'étape 4 de fix/legacy-sij une fois le legacy lui-même corrigé.
        #
        # `n_disc` : nombre de tronçons par renfort d'épaule.
        #   1  -> ancien modèle (7 nœuds / 6 barres, section `jarret()`),
        #         parité stricte avec `_SolveurLegacy` ;
        #   >1 -> jarret discrétisé à inertie variable (étape 3). Le legacy n'a
        #         PAS cette variante : parité vérifiée seulement en `n_disc=1`.
        #
        # `excentre` : [PROTOTYPE étape 3] abaisser les nœuds du jarret sur
        #   l'axe neutre (centre de gravité) de sa section. La géométrie dépend
        #   alors de la traverse -> le modèle est (re)construit à chaque
        #   changement de `arba` (mis en cache). `None` -> lit `JARRET_EXCENTRE`.
        self._charges = charges
        self._noms = [c[0] for c in charges]
        self._cp = self._noms[0]                      # le 1er cas est toujours "CP..."
        self._geom = geom
        self._n_disc = n_disc
        if excentre is None:
            excentre = os.environ.get("JARRET_EXCENTRE") == "1"
        self._excentre = bool(excentre) and n_disc > 1
        self._cache_build = {}                        # arba -> état de modèle (mode excentré)
        self._arba_courant = None

        if not self._excentre:
            self._build_model(jd.construire_topologie(geom, n_disc))

    def _ensure_built(self, arba):
        """Mode excentré : (re)construit le modèle pour la traverse `arba`
        (géométrie du jarret = axe neutre, donc dépendante de la section)."""
        if not self._excentre or arba == self._arba_courant:
            return
        etat = self._cache_build.get(arba)
        if etat is None:
            self._build_model(jd.construire_topologie(self._geom, self._n_disc, arba=arba))
            etat = {a: getattr(self, a) for a in _ETAT_MODELE}
            self._cache_build[arba] = etat
        else:
            for a, v in etat.items():
                setattr(self, a, v)
        self._arba_courant = arba

    def _build_model(self, topo):
        self._topo = topo
        self._conn = list(topo.conn)
        self._nbar = topo.nbar
        self._tx_mom, self._tx_cis = _tx_points(topo)
        coords = topo.coords
        alpha = [np.arctan2(coords[j][1] - coords[i][1], coords[j][0] - coords[i][0])
                 for (i, j) in self._conn]

        # charges « logiques » (6 segments / 21 slots nodaux) -> modèle discrétisé
        charges_exp = jd.expanser_charges(self._charges, topo)

        # --- modèle PyNite (3D bridé en plan XY : DZ/RX/RY bloqués partout ;
        #     N0/N6 bi-articulés)
        m = FEModel3D()
        m.add_material("acier", E, E / 2.6, 0.3, 0.0)   # G sans effet (Euler-Bernoulli)
        for k, (x, y) in enumerate(coords):
            m.add_node(f"N{k}", x, y, 0.0)
            m.def_support(f"N{k}", False, False, True, True, True, False)
        m.def_support("N0", True, True, True, True, True, False)
        m.def_support("N6", True, True, True, True, True, False)
        for k, (i, j) in enumerate(self._conn):
            m.add_section(f"S{k}", 1.0, 1.0, 1.0, 1.0)
            m.add_member(f"M{k}", f"N{i}", f"N{j}", "acier", f"S{k}")

        # --- charges élémentaires : 1 « case » PyNite + 1 combo trivial par cas.
        #     CP = charge permanente EXTERNE seule ; le poids propre est traité
        #     par décomposition linéaire (cases unitaires __SWk ci-dessous).
        for nom, ch_bar, ch_noeud in charges_exp:
            for k in range(self._nbar):
                w = ch_bar[k]
                if nom.startswith("CP"):
                    m.add_member_dist_load(f"M{k}", "FY", w, w, case=nom)
                elif nom.startswith("NEI"):
                    q = w * np.cos(alpha[k])            # neige projetée (calcSij_vert(w·cos α))
                    m.add_member_dist_load(f"M{k}", "FY", q, q, case=nom)
                elif nom.startswith("VEN"):
                    m.add_member_dist_load(f"M{k}", "Fy", w, w, case=nom)   # perpendiculaire (local y)
            for nn in range(topo.nN):
                fx, fy, mz = ch_noeud[3 * nn], ch_noeud[3 * nn + 1], ch_noeud[3 * nn + 2]
                if fx:
                    m.add_node_load(f"N{nn}", "FX", fx, case=nom)
                if fy:
                    m.add_node_load(f"N{nn}", "FY", fy, case=nom)
                if mz:
                    m.add_node_load(f"N{nn}", "MZ", mz, case=nom)
            m.add_load_combo(nom, {nom: 1.0})

        # --- poids propre : 1 case unitaire par barre (UDL vertical -1)
        for k in range(self._nbar):
            m.add_member_dist_load(f"M{k}", "FY", -1.0, -1.0, case=f"__SW{k}")
            m.add_load_combo(f"__SW{k}", {f"__SW{k}": 1.0})

        # Prépare le modèle (numérotation des DDL `node.ID`, `member.active`,
        # sous-membres) sans résoudre : ~1 ms au lieu de ~20 ms pour un
        # `analyze_linear` complet dont on n'a besoin de rien d'autre.
        Analysis._prepare_model(m)
        self._m = m
        self._nN = len(m.nodes)

        # --- masque des DDL libres (déduit des flags def_support)
        #     n_disc=1 -> 17 ; n_disc=6 -> 47
        free = []
        for idx, nd in enumerate(m.nodes.values()):
            flags = (nd.support_DX, nd.support_DY, nd.support_DZ,
                     nd.support_RX, nd.support_RY, nd.support_RZ)
            for q, s in enumerate(flags):
                if not s:
                    free.append(idx * 6 + q)
        self._free = np.array(free)

        # --- caches invariants entre itérations IPE (les charges ne changent pas ;
        #     seules les sections changent)
        def _rhs(nom):
            return (np.asarray(m.P(nom)) - np.asarray(m.FER(nom))).reshape(-1)[self._free]

        self._rhs = {nom: _rhs(nom) for nom in self._noms if not nom.startswith("CP")}
        self._rhs_cp_ext = _rhs(self._cp)
        self._rhs_sw = [_rhs(f"__SW{k}") for k in range(self._nbar)]

        # FER local (12 composantes) par barre, par cas élémentaire :
        #  - `_fer_ext[nom]`  : efforts d'encastrement des charges EXTERNES du cas
        #    `nom` (sans poids propre). Chaque cas utilise LE SIEN pour reconstruire
        #    ses efforts d'about (le bug `Sij` du legacy n'est pas reproduit).
        #  - `_fer_sw`        : idem pour un poids propre unitaire par barre
        #    (le cas CP y ajoute Σ A_k·dens·_fer_sw[k]).
        self._fer_ext = {nom: [np.asarray(m.members[f"M{k}"].fer(nom)).reshape(-1)
                               for k in range(self._nbar)]
                         for nom in self._noms}
        self._fer_sw = [np.asarray(m.members[f"M{k}"].fer(f"__SW{k}")).reshape(-1)
                        for k in range(self._nbar)]
        self._T = [np.asarray(m.members[f"M{k}"].T()) for k in range(self._nbar)]

    # ------------------------------------------------------------------
    def _props(self, poteau, arba):
        """(A, Iy_fort, Wpl.y, Avz) par barre — MÊME source que change_sections :
        poteau IPE pour les poteaux, traverse IPE pour les traverses,
        `jarret_discret.sections_jarret(arba, n_disc)` tronçon par tronçon
        (= `jarret(arba)` quand n_disc=1)."""
        return [(r["A"], r["Iy"], r["Wpl.y"], r["Avz"])
                for r in jd.sections_par_barre(self._topo, poteau, arba)]

    def _solve_all(self, poteau, arba):
        """Cœur commun : résout tous les cas élémentaires pour (poteau, arba) et
        renvoie `(props, longueurs, {nom: [eff6 par barre]}, {nom: df})`, `eff6`
        = [Ni,Vi,Mi,Nj,Vj,Mj] en convention legacy (efforts d'about), `df` =
        vecteur déplacement complet (6 DDL/nœud, convention PyNite = physique)."""
        self._ensure_built(arba)             # no-op sauf mode excentré (géométrie ~ arba)
        m = self._m
        nbar = self._nbar
        props = self._props(poteau, arba)
        aire = [p[0] for p in props]

        for k, (a, iy, _w, _v) in enumerate(props):
            sec = m.sections[f"S{k}"]
            sec.A = a
            sec.Iz = iy
        ke = [np.asarray(m.members[f"M{k}"].ke()) for k in range(nbar)]

        K = np.asarray(m.Ke(self._cp, False, False, False))
        lu = sla.lu_factor(K[np.ix_(self._free, self._free)], check_finite=False)

        rhs_cp = self._rhs_cp_ext.copy()
        for k in range(nbar):
            rhs_cp = rhs_cp + (aire[k] * DENS_LIN) * self._rhs_sw[k]
        fer_cp = [self._fer_ext[self._cp][k] + (aire[k] * DENS_LIN) * self._fer_sw[k]
                  for k in range(nbar)]

        eff_par_cas = {}
        df_par_cas = {}
        for nom in self._noms:
            rhs = rhs_cp if nom == self._cp else self._rhs[nom]
            d1 = sla.lu_solve(lu, rhs, check_finite=False)
            df = np.zeros(self._nN * 6)
            df[self._free] = d1
            fer = fer_cp if nom == self._cp else self._fer_ext[nom]
            eff = []
            for k in range(nbar):
                i, j = self._conn[k]
                dm = np.concatenate([df[i * 6:i * 6 + 6], df[j * 6:j * 6 + 6]])
                floc = ke[k] @ (self._T[k] @ dm) + fer[k]
                eff.append(-floc[_IDX6])
            eff_par_cas[nom] = eff
            df_par_cas[nom] = df

        longueurs = [float(np.hypot(self._topo.coords[j][0] - self._topo.coords[i][0],
                                    self._topo.coords[j][1] - self._topo.coords[i][1]))
                     for (i, j) in self._conn]
        return props, longueurs, eff_par_cas, df_par_cas

    def details_efforts(self, poteau, arba):
        """Efforts d'about bruts + géométrie/section par barre, pour le
        diagnostic a posteriori d'effort tranchant (`jarret_discret.
        diagnostic_cisaillement`). Ne participe PAS au dimensionnement."""
        props, longueurs, eff_par_cas, _df = self._solve_all(poteau, arba)
        t = self._topo
        return {
            "noms": list(self._noms),
            "E": E, "G": E / 2.6,
            "roles": list(t.roles),
            "bars_jarret": list(t.bars_jarret_g) + list(t.bars_jarret_d),
            "longueurs": longueurs,
            "props": props,                       # (A, Iy, Wpl.y, Avz) par barre
            "eff": eff_par_cas,                   # {nom: [ [Ni,Vi,Mi,Nj,Vj,Mj], ... ]}
        }

    def resoudre(self, poteau, arba):
        """[(nom_cas, ens_resu), ...] — même sortie que `_SolveurLegacy`
        (3 déplacements clés + 13 taux `tx_*`, convention legacy)."""
        props, _long, eff_par_cas, df_par_cas = self._solve_all(poteau, arba)
        wpl = [p[2] for p in props]
        avz = [p[3] for p in props]
        t = self._topo

        resultats = []
        for nom in self._noms:
            eff = eff_par_cas[nom]
            df = df_par_cas[nom]
            ens = {
                # déplacements en convention legacy (opposé du physique, cf. règle 1)
                "depl_t_p_g": -df[t.node_tete_g * 6 + 0],
                "depl_t_p_d": -df[t.node_tete_d * 6 + 0],
                "fleche_fait": -df[t.node_faitage * 6 + 1],
            }
            for cle, b, bout in self._tx_mom:
                mom = eff[b][2] if bout == "i" else eff[b][5]
                ens[cle] = mom / (wpl[b] * _FY_LIM) / 100.0
            for cle, b, bout in self._tx_cis:
                cis = eff[b][1] if bout == "i" else eff[b][4]
                ens[cle] = cis / (avz[b] * _FV_LIM) / 100.0
            resultats.append((nom, ens))
        return resultats

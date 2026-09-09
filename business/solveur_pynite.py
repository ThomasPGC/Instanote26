#! /usr/bin/python3
# coding: utf-8

"""Backend de résolution structurelle sur PyNiteFEA — option A « assembleur ».

Utilisé par `calcport.optimise_IPE` quand la variable d'environnement
`MOTEUR_CALCUL=pynite` (parité stricte avec le legacy) ou
`MOTEUR_CALCUL=pynite_corrige` (mode de comparaison : `Sij`/`fer` propre à
chaque cas, bug latent du legacy corrigé — pas pour la prod). Voir CLAUDE.md,
section « Roadmap moteur de calcul », étape 1 (sous-étapes 1.a–1.f + découpage
A→H) pour le contexte, les règles de signe et les parités démontrées.

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
"""

import numpy as np
import scipy.linalg as sla
from Pynite import FEModel3D
from Pynite import Analysis

from calcport import E, IPE, jarret, def_noeud_barres

# Poids propre acier : daN/cm de barre par cm² de section (comme crea_matrice_force).
DENS_LIN = 7.85e-3

# Indices, dans le vecteur d'efforts d'about local 12 de PyNite
# [Nxi,Vyi,Vzi,Mxi,Myi,Mzi, Nxj,Vyj,Vzj,Mxj,Myj,Mzj], des composantes dans le plan.
_IDX6 = np.array([0, 1, 5, 6, 7, 11])

# Correspondance clé de taux -> (barre, extrémité) — identique au legacy
# calculer_et_verifier_resultats (efforts_noeuds = [Ni,Vi,Mi,Nj,Vj,Mj], comp. 2=Mi,
# 5=Mj, 1=Vi, 4=Vj). "i" = nœud origine de la barre, "j" = nœud fin.
_TX_MOM = (
    ("tx_mom_pot_g", 0, "j"), ("tx_mom_renf_g", 1, "i"), ("tx_mom_pied_arba_g", 2, "i"),
    ("tx_mom_fait", 2, "j"), ("tx_mom_pied_arba_d", 3, "j"), ("tx_mom_renf_d", 4, "j"),
    ("tx_mom_pot_d", 5, "i"),
)
_TX_CIS = (
    ("tx_cis_pot_g", 0, "i"), ("tx_cis_renf_g", 1, "i"), ("tx_cis_pied_arba_g", 2, "i"),
    ("tx_cis_pied_arba_d", 3, "j"), ("tx_cis_renf_d", 4, "j"), ("tx_cis_pot_d", 5, "j"),
)

_FY = 235.0                      # S235 (comme calculer_et_verifier_resultats, fy en dur)
_FY_LIM = _FY / 10.0
_FV_LIM = (_FY / 3.0 ** 0.5) / 10.0


class SolveurPyNite:
    """Même interface que `calcport._SolveurLegacy` : `resoudre(poteau, arba)`
    renvoie `[(nom_cas, ens_resu), ...]` pour chaque cas élémentaire de `charges`,
    où `ens_resu` a exactement les clés produites par `calcport.calcport`
    (3 déplacements clés + 13 taux `tx_*`), en convention legacy."""

    def __init__(self, geom, charges, sij_corrige=False):
        # sij_corrige : mode de COMPARAISON uniquement (MOTEUR_CALCUL=pynite_corrige).
        # False (défaut) -> parité stricte avec le legacy : `fer_CP` réutilisé pour
        #   la reconstruction des efforts de TOUS les cas (bug latent reproduit).
        # True  -> chaque cas utilise son PROPRE `fer` (physique correcte, ELU juste).
        # Ne pas activer en prod tant que la comparaison CTICM (étape 2) n'a pas
        # statué. Voir CLAUDE.md, encart « bug latent du legacy ».
        self._sij_corrige = sij_corrige
        self._charges = charges
        self._noms = [c[0] for c in charges]
        self._cp = self._noms[0]                      # le 1er cas est toujours "CP..."

        # --- géométrie : réutilise def_noeud_barres pour les coordonnées et la
        #     connectivité (sections bidon, on jette les objets Beam)
        noeuds, barres = def_noeud_barres(geom, "IPE 80", "IPE 80")
        coords = [(n.X, n.Y) for n in noeuds]
        self._conn = [(b.Ai.A, b.Aj.A) for b in barres]
        alpha = [np.arctan2(coords[j][1] - coords[i][1], coords[j][0] - coords[i][0])
                 for (i, j) in self._conn]

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
        for nom, ch_bar, ch_noeud in charges:
            for k in range(6):
                w = ch_bar[k]
                if nom.startswith("CP"):
                    m.add_member_dist_load(f"M{k}", "FY", w, w, case=nom)
                elif nom.startswith("NEI"):
                    q = w * np.cos(alpha[k])            # neige projetée (calcSij_vert(w·cos α))
                    m.add_member_dist_load(f"M{k}", "FY", q, q, case=nom)
                elif nom.startswith("VEN"):
                    m.add_member_dist_load(f"M{k}", "Fy", w, w, case=nom)   # perpendiculaire (local y)
            for nn in range(7):
                fx, fy, mz = ch_noeud[3 * nn], ch_noeud[3 * nn + 1], ch_noeud[3 * nn + 2]
                if fx:
                    m.add_node_load(f"N{nn}", "FX", fx, case=nom)
                if fy:
                    m.add_node_load(f"N{nn}", "FY", fy, case=nom)
                if mz:
                    m.add_node_load(f"N{nn}", "MZ", mz, case=nom)
            m.add_load_combo(nom, {nom: 1.0})

        # --- poids propre : 6 cases unitaires (UDL vertical -1 sur une barre chacun)
        for k in range(6):
            m.add_member_dist_load(f"M{k}", "FY", -1.0, -1.0, case=f"__SW{k}")
            m.add_load_combo(f"__SW{k}", {f"__SW{k}": 1.0})

        # Prépare le modèle (numérotation des DDL `node.ID`, `member.active`,
        # sous-membres) sans résoudre : ~1 ms au lieu de ~20 ms pour un
        # `analyze_linear` complet dont on n'a besoin de rien d'autre.
        Analysis._prepare_model(m)
        self._m = m
        self._nN = len(m.nodes)

        # --- masque des DDL libres (déduit des flags def_support) -> 17
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
        self._rhs_sw = [_rhs(f"__SW{k}") for k in range(6)]

        # FER local (12 composantes) par barre :
        #  - `_fer_ext[nom]`  : efforts d'encastrement des charges EXTERNES du cas `nom`
        #    (sans poids propre) — sert au mode `sij_corrige`.
        #  - `_fer_cp_ext`    : idem pour le cas CP (raccourci).
        #  - `_fer_sw`        : idem pour un poids propre unitaire par barre.
        # En parité stricte, `resoudre` reconstruit les efforts de TOUS les cas
        # avec le FER du seul cas CP (bug latent du legacy reproduit — voir
        # CLAUDE.md). En mode `sij_corrige`, chaque cas utilise `_fer_ext[nom]`.
        self._fer_ext = {nom: [np.asarray(m.members[f"M{k}"].fer(nom)).reshape(-1) for k in range(6)]
                         for nom in self._noms}
        self._fer_cp_ext = self._fer_ext[self._cp]
        self._fer_sw = [np.asarray(m.members[f"M{k}"].fer(f"__SW{k}")).reshape(-1) for k in range(6)]
        self._T = [np.asarray(m.members[f"M{k}"].T()) for k in range(6)]

    # ------------------------------------------------------------------
    def _props(self, poteau, arba):
        """(A, Iy_fort, Wpl.y, Avz) par barre — MÊME source que change_sections :
        poteau IPE pour B0/B5, traverse IPE pour B2/B3, jarret(arba) pour B1/B4."""
        dp, da, dj = IPE.dict_carac(poteau), IPE.dict_carac(arba), jarret(arba)
        return [(r["A"], r["Iy"], r["Wpl.y"], r["Avz"]) for r in (dp, dj, da, da, dj, dp)]

    def resoudre(self, poteau, arba):
        m = self._m
        props = self._props(poteau, arba)
        aire = [p[0] for p in props]
        wpl = [p[2] for p in props]
        avz = [p[3] for p in props]

        # mutation des 6 sections en place -> m.Ke() et member.ke() la reflètent
        for k, (a, iy, _w, _v) in enumerate(props):
            sec = m.sections[f"S{k}"]
            sec.A = a
            sec.Iz = iy                     # PyNite : flexion plan XY = autour de Z
        ke = [np.asarray(m.members[f"M{k}"].ke()) for k in range(6)]

        # assemblage (PyNite) + partition + factorisation (ici)
        K = np.asarray(m.Ke(self._cp, False, False, False))
        lu = sla.lu_factor(K[np.ix_(self._free, self._free)], check_finite=False)

        # RHS du cas CP = charge externe + poids propre (Σ A_k · dens · SW_unit_k)
        rhs_cp = self._rhs_cp_ext.copy()
        for k in range(6):
            rhs_cp = rhs_cp + (aire[k] * DENS_LIN) * self._rhs_sw[k]

        # FER local du cas CP (externe + poids propre).
        fer_cp = [self._fer_cp_ext[k] + (aire[k] * DENS_LIN) * self._fer_sw[k] for k in range(6)]

        resultats = []
        for nom in self._noms:
            rhs = rhs_cp if nom == self._cp else self._rhs[nom]
            d1 = sla.lu_solve(lu, rhs, check_finite=False)
            df = np.zeros(self._nN * 6)
            df[self._free] = d1

            # FER utilisé pour reconstruire les efforts d'about de CE cas :
            #  - parité stricte   -> fer_cp pour tous les cas (bug legacy) ;
            #  - sij_corrige      -> fer propre au cas (CP garde son poids propre).
            if nom == self._cp:
                fer = fer_cp
            elif self._sij_corrige:
                fer = self._fer_ext[nom]
            else:
                fer = fer_cp

            # efforts d'about par barre, convention legacy [Ni,Vi,Mi,Nj,Vj,Mj]
            #   floc = ke · (T · d_barre) + fer
            #   [Ni,Vi,Mi,Nj,Vj,Mj]_legacy = -floc[[0,1,5,6,7,11]]     (checkpoint D-ter)
            eff = []
            for k in range(6):
                i, j = self._conn[k]
                dm = np.concatenate([df[i * 6:i * 6 + 6], df[j * 6:j * 6 + 6]])
                floc = ke[k] @ (self._T[k] @ dm) + fer[k]
                eff.append(-floc[_IDX6])          # [Ni,Vi,Mi,Nj,Vj,Mj]

            ens = {
                # déplacements en convention legacy (opposé du physique, cf. règle 1)
                "depl_t_p_g": -df[1 * 6 + 0],     # N1 DX
                "depl_t_p_d": -df[5 * 6 + 0],     # N5 DX
                "fleche_fait": -df[3 * 6 + 1],    # N3 DY
            }
            for cle, b, bout in _TX_MOM:
                mom = eff[b][2] if bout == "i" else eff[b][5]
                ens[cle] = mom / (wpl[b] * _FY_LIM) / 100.0
            for cle, b, bout in _TX_CIS:
                cis = eff[b][1] if bout == "i" else eff[b][4]
                ens[cle] = cis / (avz[b] * _FV_LIM) / 100.0
            resultats.append((nom, ens))
        return resultats

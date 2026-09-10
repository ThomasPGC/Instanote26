# Historique — bascule moteur legacy → PyNite (étape 1)

> Journal détaillé de l'étape 1 (sous-étapes 1.a→1.g, découpage code A→H, bug `Sij`,
> règle de signe, profilage, jeux de validation). Conservé mot pour mot.
> Décisions durables + roadmap étapes 2→8 : `docs/moteur-de-calcul.md`.

### Étape 1 — Bascule vers PyNite
- Branche `refactor/pynite`. Backend = **option A « PyNite assembleur »**
  (PyNite fournit `Ke` + sections + charges→`FER` ; `resoudre_cas` pilote
  partition + factorisation scipy + solve). Interface `charge_et_sections()`
  inchangée. Détails et justification plus bas.

#### Sous-étapes 1.a → 1.g — état d'avancement

Reprendre ici après une pause. Chaque sous-étape = un diff relu et validé
avant la suivante. Scripts de parité : `validation/pynite_check/`.

| # | Objet | État |
|---|---|---|
| **1.a** | Modèle PyNite jetable, 1 portique, cas CP seul, section constante, **sans renfort d'épaule** ; comparer `D` nœud par nœud au legacy. | ✅ **fait** — 21 DDL identiques (précision machine) après règle de signe. `check_1a_sans_jarret.py`. |
| **1.b** | Renfort d'épaule **à l'identique** (`jarret()` 1,66·h, 10 % portée) ; comparer 21 DDL + efforts d'about des 6 barres. + **profilage** (bloquant) et **règle de signe**. | ✅ **fait** — écart nul (CP + cas perpendiculaire). Profilage → décision backend = option A. `check_1b_renfort_epaule.py`, `check_1b_profilage.py`. |
| **1.c** | Reproduire les **CL bi-articulées** N0/N6 + blocage des DDL hors-plan (PyNite est 3D) ; réactions et `D` identiques. | ✅ **fait** — 17 DDL libres = réduction legacy ; `D` **et** réactions à 0,000 % sur les 8 cas élémentaires de cas-03 (dont vent). `check_1c_cl_et_vent.py`. |
| **1.d** | Porter les **3 familles de charges** (CP + poids propre uniquement en CP ; neige projetée ; vent perpendiculaire) **et** les charges ponctuelles `cas[2]`, avec la même convention de signe ; efforts de barre identiques cas par cas. | ✅ **fait** — efforts d'about des 6 barres identiques (0,000 %) sur **les 22 cas élémentaires** des 3 jeux, familles CP/NEI/VEN et charges nodales incluses. `check_1d_familles_charges.py`. |
| **1.e** | Extraire Mi/Mj, Vi/Vj, déplacements → recalculer les `tx_*` avec la **même formule** `M/(Wpl·fy)`, γM0=1 ; taux identiques cas par cas. | ✅ **fait** — les 13 `tx_*` identiques **au signe près** (0,000 %) sur les 22 cas élémentaires ; moments critiques du renfort d'épaule vérifiés en détail + gouvernant post-`COMBI_EFF`. `check_1e_taux.py`. |
| **1.f** | Rebrancher `resoudre_cas` (PyNite) dans `optimise_IPE` ; exécuter les **3 jeux de validation** + cas aléatoires ; **sections retenues identiques**. | ✅ **fait** — 3 jeux + 12 cas aléatoires reproductibles (seed 20240601) : **sections retenues identiques** partout (dont un `PasDeSolutionIPE` concordant), aucun écart sur `fleche`/`ratio_*`/`taux_trav`/`masse`. `check_1f_optimise.py`. |
| **1.g** | Nettoyage : retirer le code legacy **seulement après accord explicite**, ou le garder sous `MOTEUR_CALCUL=legacy`. | 🔸 **partiel** — `_SolveurLegacy` **gardé** en secours (`MOTEUR_CALCUL=legacy`, résultats identiques à `pynite`). Retiré : le mode « pynite parité stricte » (scaffold, cf. branche `fix/legacy-sij` étape 4). Retrait complet du legacy : réévaluer à l'**étape 3** (jarret discrétisé — le legacy ne pourra pas représenter cette géométrie). |

#### Bascule dans le code — découpage A→H (état)

Décisions : solveur PyNite isolé dans `business/solveur_pynite.py` ; aiguillage
par la **variable d'environnement `MOTEUR_CALCUL`** (`legacy` par défaut,
`pynite` opt-in) — pas de constante module ; défaut prod `legacy` jusqu'à ce
que la validation croisée CTICM (étape 2) ait statué ; legacy gardé en
secours (pas de retrait à l'étape 1.g).

| Ét. | Objet | État |
|---|---|---|
| **A** | Extraire le bloc de résolution de `optimise_IPE` → `_SolveurLegacy` + `_make_solveur(MOTEUR_CALCUL)`. | ✅ — `charge_et_sections()` byte-identique au pré-refactor (3 jeux + 12 aléatoires, dict complet). |
| **B** | `business/solveur_pynite.py` + micro-tests (mutation `Section.A/.Iz` reflétée par `m.Ke()` ; `Analysis._prepare_model` suffit pour `node.ID`/`member.active`). | ✅ |
| **C** | Poids propre par décomposition linéaire (6 cases unitaires `__SWk`) : `rhs_cp = rhs_ext + Σ A_k·dens·rhs_sw_unit_k`. | ✅ — écart nul vs RHS CP legacy. |
| **D** | Efforts d'about `floc = ke·(T·d) + fer_CP` → `[Ni,Vi,Mi,Nj,Vj,Mj]_legacy = −floc[[0,1,5,6,7,11]]`. | ✅ — 0,000 % vs `efforts_noeuds` legacy (checkpoint D-ter). |
| **E** | Câblage `MOTEUR_CALCUL` + `SolveurPyNite`. | ✅ — `charge_et_sections()` **byte-identique** legacy vs pynite (3 jeux + 12 aléatoires) ; 6 scripts `check_1*` OK sous `MOTEUR_CALCUL=pynite`. |
| **F** | Profilage. | ✅ — `_prepare_model` au lieu d'`analyze_linear` en `__init__` → **×1,27 / ×1,61 / ×1,10** (cas-01 / 02 / 03), tous < 120 ms. |
| **G** | Non-régression endpoint. | ✅ — `check_1g_non_regression.py` : 32 cas (30 aléa. + `PasDeSolutionIPE` + zonage KO), dict identique. `POST /htmx/calcul` → HTML même SHA256 ; `/htmx/calcul-pdf` → PDF valide des 2 côtés. |
| **H** | Doc `CLAUDE.md`. | ✅ (ce bloc). |

> **⚠️ Bug latent du legacy — `Sij` figé sur le cas CP.** En cours de
> correction sur la branche `fix/legacy-sij` (voir « Correction » ci-dessous).
>
> **Mécanisme.** `crea_matrice_force` a un effet de bord : elle (ré)écrit
> `barre.Sij` (efforts d'encastrement) sur toutes les barres. `calculer_et_
> verifier_resultats` ([calcport.py:321](business/calcport.py#L321),
> [:332](business/calcport.py#L332)) reconstruit ensuite
> `efforts_noeuds = −barre.Sij + k_barre·d_rot`. Or dans le `optimise_IPE`
> d'origine / `_SolveurLegacy.resoudre`, le **seul** `crea_matrice_force`
> rappelé dans la boucle des tailles IPE était celui du **CP**. Résultat :
> pour les 8 cas élémentaires d'**une même résolution**, `calculer_et_verifier_
> resultats` lit toujours `Sij_CP`. Les efforts internes (donc les 13 `tx_*`,
> donc l'ELU) de NEI et VENT combinent `Sij_CP` + déplacements du cas courant
> → **physiquement incohérents**. Le *solve* (déplacements) n'est **pas**
> touché — l'ELS (flèche/dérive) reste juste. Cas le plus net : `NEI_ACCI`
> zone A1 (`ch_bar_acci = 0` → `Sij` correct = 0) reçoit quand même
> `Sij_CP ≠ 0`. Trace (cas-03, B2 traverse) : `Sij` lu pour **tous** les cas
> = `[40,17 ; 401,70 ; 21530,6]` (CP) ; `Sij` correct du vent =
> `[0 ; 310,5 ; 16641,7]`.
>
> **Indépendant du bug de signe global** (`D_avec_app = −déplacement
> physique`). Vérifié : le bug de signe vient de `crea_matrice_force` qui
> assemble `F = +Σ barre.Fij` au lieu de `−Σ` (l'équivalent-nodal correct) —
> `calcport(A,B,K,−F,…)` rend `D` physique. Corriger l'entrelacement de `Sij`
> laisse `D_avec_app` toujours négatif. Deux défauts orthogonaux qui
> coexistent ; **on ne corrige QUE le bug `Sij`** (le bug de signe est
> globalement cohérent et neutralisé par les `abs()` de `optimise_IPE`).
>
> **Ampleur** (`compare_3modes_ctcim.py`, `taux_max` brut avant `round(.,1)`) :
>
> | cas | legacy d'origine (bug) | corrigé | Δ | section retenue |
> |---|---|---|---|---|
> | cas-01-compact | 37,98 % | 37,84 % | −0,14 pt | inchangée |
> | cas-02-bas-large | 99,33 % | 98,84 % | −0,49 pt | inchangée (IPE 600/600) |
> | cas-03-haut-fin | 56,07 % | 54,92 % | −1,15 pt | inchangée (`taux_trav` **affiché** passe 60→50, Δ franchit l'arrondi 0,55) |
>
> → Le bug `Sij` déplace `taux_max` de **< 1,2 point** et **ne change aucune
> section retenue** sur ces 3 cas + ~50 aléatoires. Il **n'explique pas** une
> part significative de l'écart CTICM — chercher ailleurs (jarret `1,66·h`
> constant, zones vent F/G/J, hors-périmètre flambement/déversement).
>
> **Correction — branche `fix/legacy-sij`** (départ : commit `020c1cb` sur
> `refactor/pynite`). Plan en 4 étapes, **toutes faites** :
> 1. ✅ Référence « avant » = `020c1cb`.
> 2. ✅ `_SolveurLegacy.resoudre` : `crea_matrice_force` rappelé **dans la
>    boucle pour chaque cas** juste avant `calcport` (`self.F` supprimé).
>    Perf `charge_et_sections()` (dev, médianes) : cas-01 31,6→35,5 ms
>    (+12 %) · cas-02 15,6→18,1 ms (+16 %) · cas-03 104,0→126,2 ms (+21 %)
>    — surcoût ∝ nombre d'itérations IPE.
> 3. ✅ Validation locale (3 jeux) + `check_1g` adapté (parité `legacy` vs
>    `pynite`) + **comparaison CTICM** → `validation/COMPARAISON_CTICM.md` :
>    l'écart CTICM croît avec le taux ELU (−1,3 / +4,2 / +10,1 pt sur
>    cas-01/03/02), élément gouvernant identique Instanote ↔ CTICM. Le bug
>    `Sij` (0,1–1,2 pt) **n'explique pas** cet écart. Sections CTICM (user) :
>    cas-01 et cas-03 **identiques** à Instanote ; cas-02 poteaux IPE 600
>    identiques mais **arbalétriers CTICM = IPE 500** (2 crans sous Instanote)
>    → l'influence du jarret devient prépondérante → à traiter à l'**étape 3**
>    (jarret discrétisé).
> 4. ✅ Retrait du mode « pynite parité stricte » (scaffold obsolète). Les
>    deux backends (`legacy`, `pynite`) donnent des résultats identiques, bug
>    `Sij` corrigé des deux côtés. Défaut code = `legacy` ; Railway =
>    `MOTEUR_CALCUL=pynite`. `pynite_corrige` conservé comme **alias** de
>    `pynite`. **Non poussé / non déployé** — attente de la validation locale
>    manuelle du user, puis push + déploiement.

Variable d'env **`MOTEUR_CALCUL`** : absente/`legacy` → solveur maison
(méthode des déplacements) ; `pynite` (alias : `pynite_corrige`) →
`business/solveur_pynite.py`. Résultats **identiques**. Sur Railway :
`MOTEUR_CALCUL=pynite`. En local : `MOTEUR_CALCUL=pynite python ...`.

#### Audit réalisé (session 1) — synthèse

- **Méthode actuelle** : méthode des déplacements maison (raideur directe),
  1er ordre linéaire, élément poutre-poteau 2D **Euler-Bernoulli** (3 DDL/nœud).
  Modèle figé : **7 nœuds / 6 barres**, portique bipente symétrique, 1 poteau
  par côté, pieds **articulés**. `E = 2 100 000 daN/cm²`, unités cm/daN.
- **Renfort d'épaule** : barres B1 et B4 (`N1→N2`, `N4→N5`), section `jarret()`
  = I reconstitué `b`/`tf`/`tw` de la traverse mais âme haute `1,66·h`,
  **prismatique**, sur 10 % de portée. Résistance vérifiée au genou
  (`tx_mom_renf_*`, Wpl du I `1,66·h`) et en bout (`tx_mom_pied_arba_*`, Wpl
  traverse nue). Suspecté n°1 de l'écart croissant avec CTICM (hauteur `1,66h`
  < `≈2h` réel au genou + renfort constant au lieu de dégressif → outil
  sur-dimensionne). À contre-sens : l'absence de flambement/déversement rend
  l'outil moins conservatif → l'écart net est une résultante, à décomposer en
  étape 2.
- **Résistance** : `taux = M / (Wpl · fy)` (γM0 = 1) + `V / (Avz · fy/√3)`,
  superposés APRÈS résolution avec `COMBI_EFF` ; ELS via `COMBI_DEPL` contre
  `hpot/150` (tête) et `portée/200` (flèche). Pas de N/M, pas d'instabilités.
- **Point de couture retenu** : une fonction interne unique
  `resoudre_cas(geom, sections, cas) -> ens_resu` (mêmes clés :
  `depl_t_p_g/d`, `fleche_fait`, `tx_mom_*`, `tx_cis_*`).
  `optimise_IPE`, `charge_et_sections`, `chargement_nv`, catalogue IPE,
  combinaisons : **inchangés**. Flag `MOTEUR = "legacy" | "pynite"` pour faire
  tourner les deux en parallèle (étape 2).
- **Piège signe** : `calcport()` renvoie `D_avec_app` et
  `barre.efforts_noeuds` avec un **signe globalement inversé** vs axes
  physiques (cf. commentaire « les signes sont mauvais » dans
  `crea_matrice_force`). Invisible en aval car `calculer_et_verifier_resultats`
  est auto-cohérent et `optimise_IPE` prend des `abs()` partout. Le backend
  PyNite utilise les signes physiques → `resoudre_cas` doit extraire
  **déplacements ET efforts de PyNite** (jamais mélanger), en gardant une
  convention unique entre les cas CP/NEI/VENT.

#### Étape 1.a — validée

- `PyNiteFEA==3.0.0` ajouté à `requirements.txt`.
- Comparaison legacy vs PyNite sur 1 portique, cas CP seul, section constante,
  **sans renfort d'épaule** (géométrie cas-01-compact) : après correction du
  signe global, **les 21 DDL coïncident à la précision machine** (écart
  relatif 0,000 %, résidus ~1e-15). Parité Euler-Bernoulli confirmée sans
  bricolage (pas besoin de forcer `G`).
- Conventions d'effort d'extrémité : voir « Règle de signe » ci-dessous.

#### Étape 1.b — validée

Renfort d'épaule **réintroduit à l'identique** (`jarret()` 1,66·h, 10 % de
portée, barres B1/B4). Legacy vs PyNite (1 modèle, résolution **par cas
élémentaire**, sans combinaison ELU/ELS PyNite), sur cas-01-compact, avec
le **cas CP** *et* un **cas perpendiculaire synthétique** :
- 21 DDL : écart relatif 0,000 %, résidu ~1e-16 ;
- efforts d'extrémité des 6 barres (N, V, M aux 2 nœuds) : écart ~1e-10.
La règle de signe ci-dessous tient **à l'identique pour la charge
perpendiculaire** → c'est une convention, pas une correction propre à la
gravité (donc robuste quand le vent entrera en 1.d).

#### Règle de signe legacy ↔ PyNite (à appliquer telle quelle en 1.c–1.f)

Le backend PyNite adopte **les conventions PyNite partout** ; on ne
reproduit jamais les signes du legacy. Deux écarts, de natures différentes :

1. **Défaut de signe global du legacy** (commentaire « les signes sont
   mauvais » dans `crea_matrice_force`) : le vecteur `D_avec_app` de
   `calcport()` est l'**opposé** du déplacement physique. Invisible en aval
   car tout consommateur ré-emploie ce même vecteur, ou prend `abs()`.
   → `resoudre_cas` pose `depl_t_p_g = −DX(N1)`, `depl_t_p_d = −DX(N5)`,
     `fleche_fait = −DY(N3)` (PyNite) — le « − » appliqué **une seule fois**,
     à l'extraction des déplacements.

2. **Effort d'about (« barre → nœud ») vs effort interne N(x)/V(x)/M(x)** :
   `efforts_noeuds` du legacy sont des efforts d'about ; PyNite
   `axial/shear/moment(x)` sont les diagrammes internes. Identité de
   statique, vraie pour **tout** chargement (gravité, vent perpendiculaire,
   charges nodales) :

   | legacy `efforts_noeuds[b]` | PyNite |
   |---|---|
   | `[Nᵢ, Vᵢ, Mᵢ]` (nœud origine `i`) | `[ −N(0), −V(0), −M(0) ]` |
   | `[Nⱼ, Vⱼ, Mⱼ]` (nœud fin `j`)     | `[ +N(L), +V(L), +M(L) ]` |

   Le « − » côté `i` n'est **pas** lié à l'orientation de la charge : c'est
   « effort interne à la coupure `i` = −(effort que la barre exerce sur le
   nœud `i`) ». Côté `j`, la normale sortante de la coupure pointe déjà
   selon +x local → pas de changement de signe. Vérifié bit à bit sur
   gravité **et** perpendiculaire (étape 1.b).

3. **Invariance pour `optimise_IPE`** : chaque clé `tx_*` cible **un seul**
   about de barre → le map applique un ±1 **fixe par clé, identique pour
   tous les cas élémentaires**. Donc `Σ_cas (combi · tx)` puis `abs()` (déjà
   fait par `optimise_IPE`), et les tests `abs()` sur les déplacements, sont
   **prouvablement invariants** au map. Le map ne sert qu'à la comparaison
   **cas par cas** de l'étape 1.e.

`resoudre_cas` extrait donc **déplacements ET efforts de PyNite** (jamais un
mélange legacy/PyNite), applique (1) aux déplacements et (2) aux efforts.

#### Étape 1.b — profilage (⚠ point bloquant, à trancher avant 1.c)

Machine de dev, médianes sur 25–200 exécutions. Legacy =
`charge_et_sections()` actuel complet (boucle `optimise_IPE` réelle).

| Cas | itér. IPE | **legacy** | PyNite natif¹ | PyNite assembleur² |
|---|---|---|---|---|
| cas-01-compact | 13 | **32 ms** | ~420 ms (×13) | ~38 ms (×1,2) |
| cas-02-bas-large | 12 | **16 ms** | ~295 ms (×18) | ~32 ms (×2,0) |
| cas-03-haut-fin | 74 | **106 ms** | ~2400 ms (×22) | ~195 ms (×1,8) |

¹ **PyNite natif** = 1 modèle, 1 combo PyNite par cas élémentaire
  (`add_load_combo`, facteur 1), `analyze_linear()` puis lecture via
  `member.moment()/shear()`. Coût mesuré par résolution :
  `analyze_linear` **≈ 21 ms** + extraction **≈ 10 ms**, × nb d'itérations
  IPE. `sparse=False` ≈ `sparse=True` (21 DDL : la conversion CSR coûte plus
  qu'elle ne rapporte). Le coût **n'est pas** dans l'algèbre (assemblage
  `Ke` 0,5 ms, `spsolve` < 0,1 ms) mais dans l'orchestration Python de
  `analyze_linear` (`_calc_reactions`, `_store_displacements`,
  partition/renumber) et dans `member.*()` qui reconstruit les diagrammes.

² **PyNite assembleur** = PyNite fournit l'assemblage `Ke`, la conversion
  charges → `FER`/`P`, le catalogue de sections ; on pilote soi-même
  partition + `scipy.linalg.lu_factor` (1×/itération) + `lu_solve` par cas,
  **RHS des cas non-CP mis en cache** entre itérations (seul CP recalculé,
  pour le poids propre), efforts d'about par transformation locale.
  Mesuré : **≈ 2,3–2,6 ms/itération**. Contourne `analyze()`.

**Conclusion** : « PyNite natif » dégrade l'endpoint HTMX `/htmx/calcul`
d'un facteur **13–22** (jusqu'à 2,4 s) → **inacceptable en prod**.
« PyNite assembleur » tient (**×1,2–2**, < 200 ms) mais s'appuie sur des
méthodes internes de PyNite (`Ke`, `FER`, `P`) et ré-implémente
partition/solve/récupération.

**Décision (user) — option A retenue : PyNite assembleur.** PyNite fournit
l'assemblage `Ke`, le catalogue de sections et la conversion charges →
`FER`/`P` ; `resoudre_cas` pilote lui-même la partition (CL), la
factorisation (`scipy.linalg.lu_factor`, 1×/itération IPE) et le `lu_solve`
par cas élémentaire, RHS des cas non-CP mis en cache entre itérations.
Motifs : perf ×1,2–2 (B rejeté à ×13–22) ; on garde le bénéfice structurel
qui justifie la bascule (assemblage `Ke` + sections + charges→efforts
réutilisables tels quels pour le jarret discrétisé de l'étape 3 et le
portique asymétrique de l'étape 6, là où C obligerait à réécrire
l'assemblage maison à chaque nouvelle géométrie) ; argument externe (se
prévaloir de PyNiteFEA, lib EF établie, comme caution technique).

> ⚠️ **Politique de version PyNite** (risque accepté de l'option A —
> dépendance à des méthodes semi-internes `Ke` / `FER` / `P`) : PyNite est
> **piqué à `==3.0.0`** dans `requirements.txt`. Toute montée de version est
> un **projet à part entière**, pas une mise à jour de routine : re-run
> complet des tests de non-régression contre `validation/` (sorties
> identiques au chiffre près) **avant** merge. Ne jamais bumper PyNite dans
> un `pip install --upgrade` groupé.
>
> **Check-list « montée de version PyNite »** (dans l'ordre) :
> 1. **Stub `matplotlib`** — `business/solveur_pynite.py` injecte un faux
>    `sys.modules['Pynite.ShearWall']` **avant** `from Pynite import …`, parce
>    que `Pynite/__init__.py` fait `from Pynite.ShearWall import ShearWall` et
>    que `Pynite/ShearWall.py` (3.0.0) importe `matplotlib.pyplot` **au niveau
>    module**. On n'utilise ni `ShearWall` ni aucune fonction de tracé PyNite.
>    À la montée de version, vérifier :
>    - `grep -rn "^import matplotlib\|^from matplotlib" .venv/Lib/site-packages/Pynite/`
>      (imports matplotlib **non indentés** = au niveau module). Si un autre
>      module que `ShearWall` en a un (ex. `Rendering`, `Visualization`,
>      `__init__` lui-même), **ajouter le stub correspondant** ;
>    - que `Pynite/__init__.py` importe toujours `ShearWall` par ce chemin
>      exact (sinon adapter la clé du stub, ou le retirer s'il est devenu
>      inutile) ;
>    - que `from Pynite import FEModel3D` + `Analysis` fonctionnent **avec** le
>      stub en place (le faux `ShearWall` ne doit rien casser).
> 2. **Rejouer `validation/pynite_check/check_deps_runtime.py`** : assert que
>    `matplotlib` n'est **pas** dans `sys.modules` après un
>    `charge_et_sections()` en mode `pynite`, et que `scipy` l'est (attendu :
>    `Pynite/FEModel3D.py` fait `import scipy` au niveau module + on utilise
>    `scipy.linalg`). Si `matplotlib` réapparaît → le stub ne couvre plus tout
>    (retour au point 1).
> 3. **Rejouer tous les `check_1*`** (`MOTEUR_CALCUL=legacy` **et** `=pynite`)
>    → exit `0`, dict `charge_et_sections()` identique entre les deux backends.
> 4. Vérifier que les méthodes semi-internes utilisées existent toujours avec
>    la même signature : `m.Ke(combo, log, check_stability, sparse)`,
>    `m.P(combo)`, `m.FER(combo)`, `member.fer(combo)`, `member.ke()`,
>    `member.T()`, `Analysis._prepare_model(m)`. (`solveur_pynite.py` les
>    liste en tête.)
> 5. Re-profiler (`check_1b_profilage.py`) et comparer aux chiffres d'ici.

Alternatives écartées : **(B) PyNite natif** (`analyze()` + combos) — le
plus propre mais ×13–22 ; **(C) solveur maison allégé** + PyNite seulement
comme oracle hors ligne — perf ×1 mais assemblage maison à maintenir pour
chaque géométrie future.

**Observation annexe** (hors périmètre étape 1, touche la logique
d'optimisation) : `optimise_IPE` fait **74 itérations** sur cas-03
(recherche gloutonne : +1 taille à la fois, reset traverse à poteau−4 à
chaque bump de poteau). Une recherche plus fine diviserait le temps par
3–5 pour **tous** les backends.

#### Étape 1.c — validée (CL bi-articulées + blocage hors-plan)

Backend assembleur (option A) : `m.Ke()` de PyNite, puis partition /
`scipy.linalg.lu_factor` / `lu_solve` pilotés dans `resoudre_cas`.
- Masque de DDL libres déduit des flags `def_support` : N0/N6 → `{RZ}`
  seul (DX, DY bloqués = rotule) ; N1–N5 → `{DX, DY, RZ}` ; `DZ, RX, RY`
  bloqués partout (modèle plan). Total **17 DDL libres**, identiques à la
  réduction du legacy (`rz N0 ; dx,dy,rz N1..N5 ; rz N6`).
- Sur cas-03-haut-fin (asymétrique, avec vent), **les 8 cas élémentaires**
  (CP, NEI, NEI_ACCI, 4× VEN long-pan, VEN pignon) : déplacements **0,000 %**
  d'écart, **réactions d'appui 0,000 %** (au signe global près, règle 1 —
  `R_legacy = K·D_legacy − F_legacy` porte le même flip).
- **Gotcha réutilisable (1.d–1.f)** : `m.Ke()` est indexée 6 DDL/nœud dans
  l'ordre `DX, DY, DZ, RX, RY, RZ`, nœuds en ordre d'`ID` (= ordre
  d'insertion). La rotation dans le plan est **RZ = indice local 5**, pas 2
  (2 = `DZ`, hors-plan, toujours nul). Extraire un vecteur « 3 DDL/nœud »
  façon legacy = prendre les indices locaux **(0, 1, 5)**.
- Le contrôle « ΣF appliqué + Σréactions » n'est **pas** un bon test
  d'équilibre quand des charges réparties perpendiculaires agissent sur des
  barres inclinées (`Σ FER` ≠ résultante appliquée) — se fier à l'égalité
  des réactions avec le legacy.

**Scripts de parité versionnés** : `validation/pynite_check/` — un script
autonome et figé par sous-étape (`check_1a_sans_jarret.py`,
`check_1b_renfort_epaule.py`, `check_1b_profilage.py`,
`check_1c_cl_et_vent.py`, `check_1d_familles_charges.py`,
`check_1e_taux.py`, `check_1f_optimise.py`, `check_1g_non_regression.py`),
rejouables (sortie `0`/`1`). À relancer lors de toute montée de version de
PyNite ou refactor du moteur. Voir le `README.md` du dossier.

#### Étape 1.d — validée (portage des familles de charges)

Portage des charges de `chargement_nv` dans PyNite (identique dans
`check_1c` / `check_1d` / futur `resoudre_cas`) :
- **CP** : UDL verticale **globale** `q_k = charge_k − A_k·7,85e-3`
  (poids propre ajouté **uniquement** dans le cas CP, comme le legacy) ;
- **NEI** : UDL verticale globale `q_k = charge_k·cos(α_k)` (neige projetée,
  comme `calcSij_vert(w·cos α)`) ;
- **VEN** : UDL **perpendiculaire** (repère local y) `q_k = charge_k` (comme
  `calcSij_perp`) ;
- **charges ponctuelles `cas[2]`** = `[Fx, Fy, Mz]` par nœud →
  `add_node_load(+v)`. Le legacy fait `F −= cas[2]` ; combiné au flip global
  de `crea_matrice_force`, l'équivalent physique PyNite est `+v` (règle de
  signe 1).

Vérifié : efforts d'about des 6 barres `[Ni,Vi,Mi,Nj,Vj,Mj]` identiques au
legacy (**0,000 %**, règle de signe 2) sur **les 22 cas élémentaires** des 3
jeux `validation/` (cas-01/02/03) — familles CP / NEI / VEN, avec charges
nodales (moments d'acrotère `VEN_G_D`, points de charge neige aux nœuds 2/5,
accumulation) exercées et validées.

#### Étape 1.e — validée (taux de travail cas par cas)

Les 13 `tx_*` de `calculer_et_verifier_resultats` recalculés depuis les
efforts PyNite avec la **formule legacy exacte** (`M/(Wpl·fy/10)/100`,
`fy = 235`, γM0 implicite = 1 ; `Wpl`/`Avz` lus sur le catalogue — B1/B4 =
`Wpl` du jarret 1,66·h). Comparaison **au signe près** (pas `abs()`) :
- les 13 `tx_*` identiques au legacy à **0,000 %** sur les 22 cas
  élémentaires des 3 jeux ;
- **moments critiques du renfort d'épaule** (`tx_mom_renf_g/d`,
  `tx_mom_pied_arba_g/d`) : détaillés cas élémentaire par cas élémentaire —
  aucun écart. Ex. cas-03 / `VEN_G_D_pos_neg` :
  `tx_mom_pied_arba_d = 36,103 %` (legacy) = `36,103 %` (PyNite) ;
- **taux critique gouvernant après `COMBI_EFF`** (bonus bout-en-bout,
  `|Σ combi·tx|` sur les 6 combos ELU × cas de vent) : identique aussi —
  cas-01 `pied_arba_d` 36,18 % ; cas-02 `renf_g/d` 50,77 % ; cas-03
  `pied_arba_d` 54,92 %.
- **Observation métier** (parité OK, c'est du legacy fidèlement reproduit) :
  dans les cas pilotés par le vent, `tx_mom_pied_arba_*` (arbalétrier juste
  après le jarret, `Wpl` traverse nue) est nettement > `tx_mom_renf_*`
  (genou, sur le `Wpl` élargi 1,66·h). Le point qui « mord » dans la zone
  d'épaule est donc l'arbalétrier **en sortie de jarret**, pas le genou —
  cohérent avec l'hypothèse d'audit (le renfort constant 1,66·h sur-résiste
  au genou et reporte la demande sur la traverse courante).

#### Étape 1.f — validée (boucle `optimise_IPE` complète)

`check_1f_optimise.py` : **monkeypatch** de `calcport.calcport` (résolution
d'un cas → `ens_resu`) et `calcport.optimise_IPE` (installe le `resoudre_cas`
PyNite pour la liste de charges courante), **sans toucher au fichier**. La
boucle `optimise_IPE` du legacy tourne inchangée (prédim, incréments IPE,
`COMBI_DEPL`/`COMBI_EFF`, critères) ; seule la résolution est PyNite. Le
`ens_resu` PyNite est renvoyé **en convention legacy** (déplacements =
`−DX/−DY` PyNite ; 13 `tx_*` via règle de signe 2) → drop-in exact.
- 3 jeux `validation/` : sections retenues identiques.
- **12 cas aléatoires reproductibles** (seed 20240601 ; communes ×10, `hpot`
  300–1000, `portee` 600–2200, pente 0,05–0,20, `h_acro` 0/100/150,
  rugosité 0–IV, couv/divers variés) : **sections retenues identiques**
  partout, dont un cas `PasDeSolutionIPE` concordant. Aucun écart sur
  `fleche` / `ratio_fleche` / `ratio_depl` / `taux_trav` / `masse`.
- Backend du check = PyNite "natif" (`analyze_linear` + `member.*()`),
  suffisant pour la justesse ; le backend "assembleur" (perf) donne les
  mêmes nombres (1.c).

#### Jeux de validation (étape 2) — entrées `charge_et_sections`

Retrouvés depuis les PDF **Instanote26** de `validation/` (les PDF `… CTICM.pdf`
sont la **référence externe** de comparaison, pas des entrées). Longueurs en
cm, `pente` = ratio, `couv`/`divers` en daN/m². Sorties = algo actuel, à figer.

| Cas | geom | localisation | cp | Algo actuel |
|---|---|---|---|---|
| cas-01-compact | hpot 350, portee 400, pente 0.10, longueur 2000, entraxe 400, h_acro 0 | Blois / dept 41 / alt 114 / IIIb | couv 10, divers 2 | poteau **IPE 160**, traverse **IPE 140**, taux **40,0 %**, flèche faîtage 2,8 mm (L/1404), dérive H/160, masse 168 kg |
| cas-02-bas-large | hpot 500, portee 2200, pente 0.03, longueur 4000, entraxe 800, h_acro 100 | Millau / dept 12 / alt 631 / IIIa | couv 50, divers 20 | poteau **IPE 600**, traverse **IPE 600**, taux **100,0 %**, flèche faîtage 57,4 mm (L/383), dérive H/1057, masse 4174 kg |
| cas-03-haut-fin | hpot 1000, portee 800, pente 0.10, longueur 4000, entraxe 500, h_acro 100 | Brest / dept 29 / alt 50 / cat. 0 | couv 20, divers 5 | poteau **IPE 600**, traverse **IPE 500**, taux **60,0 %**, flèche faîtage 2,0 mm (L/4044), dérive **H/161** (pilotée par la dérive), masse 3242 kg |

`ancien_nom_comm` = `""` pour les trois. Reconstruction vérifiée : rejeu de
ces entrées dans `charge_et_sections` → sorties identiques aux PDF au chiffre
près.

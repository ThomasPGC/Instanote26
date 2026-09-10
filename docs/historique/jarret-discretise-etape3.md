# Historique — jarret discrétisé (étape 3 de la roadmap moteur)

> Journal détaillé de l'étape 3 : renfort d'épaule modélisé en suite de barres
> à inertie variable (au lieu d'une barre prismatique `1,66·h`). Conservé mot
> pour mot. Décisions durables + roadmap : `docs/moteur-de-calcul.md`.
> Correspondance legacy ↔ PyNite : `docs/reference-legacy-vs-pynite.md` (§4, §5.11).

Branche : `feat/jarret-discretise-etape3` (depuis `master`).
Étape 2 (validation croisée CTICM) : **confirmée validée par le user** avant démarrage.

## 1. Décisions actées (questions préalables au user)

| Sujet | Décision |
|---|---|
| **Loi de section** | Âme dégressive **linéaire de `2·h` (épaule) à `1·h` (sortie)**. Le `1,66` historique était une moyenne des deux. Échantillonnage au **milieu** de chaque tronçon : `h_ratio_k = 2 − (k+0.5)/n`. |
| **Fonction de section** | Ad hoc, **I à 3 semelles** (sup + intermédiaire = semelle inf de la traverse nue + inf de gousset) **+ congés de raccordement `r`**. La semelle intermédiaire a peu d'effet en flexion mais est modélisée pour le réalisme (aire, cisaillement). |
| **« Arrondi omis » du legacy** | = les congés de raccordement `r` (colonne `IPE.csv`), ignorés par `jarret()`. Réintégrés. |
| **Effort tranchant** | **Diagnostic post-optimisation, non bloquant.** Le solveur reste Euler-Bernoulli (décision figée). Pas d'interaction M+V. |
| **Backend legacy** | Figé = oracle de l'ancien modèle. Discrétisation **uniquement dans PyNite**. `_SolveurLegacy`, `def_noeud_barres`, `jarret()`, `change_sections`, `calculer_et_verifier_resultats` non touchés. |
| **Bascule `MOTEUR_CALCUL` défaut `legacy → pynite`** | Dernière étape, conditionnée à la validation complète (tous `check_3*` verts + validation manuelle user + re-comparaison CTICM). Pendant le développement, défaut = `legacy`. |
| **Nombre de tronçons** | `N_DISC_JARRET = 6` (constante module, surchargée par variable d'env). |

## 2. Architecture

Tout le neuf dans `business/jarret_discret.py` (le métier historique de
`calcport.py` reste gelé) :

- **`caracs_section_jarret(arba, h_ratio)`** → `{Iy, A, Avz, "Wpl.y"}` d'un
  tronçon. Contour réel du I à 3 semelles + congés `r` construit en polygone
  (arcs de congé discrétisés, `n_arc=24`), intégré par les formules de moments
  de polygone ; `Wpl.y` par découpe à l'axe neutre plastique (bissection sur
  l'aire). `Avz = tw·(H − 2·tf)` (âme dégagée ; les semelles horizontales ne
  portent pas d'effort tranchant vertical). Mémoïsé (`lru_cache`).
- **`sections_jarret(arba, n_disc)`** → liste des `n_disc` sections. `n_disc=1`
  renvoie `calcport.jarret(arba)` (parité legacy).
- **`construire_topologie(geom, n_disc)`** → `Topologie` : `coords`, `conn`,
  `roles` par barre, cartes sémantiques (`node_tete_g/_d`, `node_faitage`,
  `node_sortie_jarret_g/_d`, `bars_jarret_g/_d`, `bar_epaule_g/_d`). `n_disc=1`
  reproduit `def_noeud_barres` (7 nœuds / 6 barres, mêmes indices). `n_disc>1` :
  `n_disc−1` nœuds intérieurs par jarret ajoutés **en fin** (N7…) → N0..N6
  gardent leurs indices.
- **`sections_par_barre(topo, poteau, arba)`** → sections barre par barre (même
  correspondance que `change_sections`).
- **`expanser_charges(charges, topo)`** → projette les tableaux « logiques » de
  `chargement_nv` (6 segments par barre / 21 slots nodaux) sur le modèle
  discrétisé : la charge de jarret recopiée sur les tronçons colinéaires ; les
  21 slots N0..N6 conservés tels quels (le « surplus fin de jarret » —
  `ch_noeud_jar`, accumulation acrotère, réactions vent de rive — reste porté
  par N2/N4) ; nœuds intérieurs à charge nodale nulle.
- **`diagnostic_cisaillement(...)`** → cf. §5.

`business/solveur_pynite.py` : `SolveurPyNite.__init__(geom, charges, n_disc=1)`.
Toute la construction du modèle et `resoudre()` dé-câblées des `range(6)`/`range(7)`.
`_solve_all()` factorise le cœur (résolution de tous les cas → efforts d'about +
déplacements) ; `resoudre()` et `details_efforts()` s'en servent.
`_tx_points(topo)` construit la correspondance clé de taux → (barre, extrémité)
depuis la topologie ; en `n_disc=1` = exactement les tuples `_TX_MOM`/`_TX_CIS`
historiques.

`business/calcport.py` : `_make_solveur` passe `n_disc=jarret_discret.N_DISC_JARRET`
au backend pynite. `charge_et_sections` appelle `diagnostic_cisaillement` après
`optimise_IPE`, en `try/except` (jamais bloquant), seulement en mode pynite +
`N_DISC_JARRET>1`. **`MOTEUR_CALCUL` défaut inchangé (`legacy`)** — la bascule
sera un commit final séparé. Rien d'autre touché dans `calcport.py`.

`chargement_nv.py` : **non touché** (l'expanseur de charges est la couture ;
l'étape 4 y reviendra pour les charges réparties trapézoïdales).

## 3. Fonction de section — recoupement PropSection

Références : `validation/jarrets/*.png` (PropSection v1.0.4, « Section
Paramétrée » n°7 = I à 3 semelles + congés `r`), fournies par le user.
`hr` (paramètre PropSection) = profondeur de la semelle intermédiaire sous la
fibre supérieure = `(h_ratio − 1)·h`. Grandeurs relevées dans le repère
principal (centroïdal).

| profil | h_ratio | A (cm²) | Iy,G (cm⁴, axe fort) | Iz,G (cm⁴) | zG (cm) |
|---|---|---|---|---|---|
| IPE 160 | 1,500 | 30,180 | 2 269,427 | 102,490 | 11,278 |
| IPE 160 | 1,950 | 33,780 | 4 065,263 | 102,565 | 15,601 |
| IPE 300 | 1,500 | 80,839 | 21 666,833 | 905,791 | 21,107 |
| IPE 300 | 1,963 | 90,708 | 39 244,472 | 906,206 | 29,457 |
| IPE 450 | 1,500 | 148,468 | 88 094,233 | 2 514,250 | 31,758 |

**Écart calcul ↔ PropSection** (après calage du modèle de congés) :

| grandeur | écart max |
|---|---|
| A | **0,15 %** |
| Iy,G | **0,45 %** |
| Iz,G | **0,06 %** |
| zG | **0,66 %** |

Calage : la « section n°7 » de PropSection a **6 congés** (2 par semelle). Un
modèle à 8 congés (2 de chaque côté de la semelle intermédiaire) surestimait A
de ~1 % de façon systématique ; en ne raccordant que le **côté laminé** de la
semelle intermédiaire (dessus) et en laissant un angle vif côté gousset soudé
(dessous), A retombe à −0,15 %. Cohérent physiquement : la semelle
intermédiaire est la semelle inférieure du profil laminé (congé laminé conservé
au-dessus), le gousset est soudé dessous.

**Garde-fou intégrateur** : le contour à **2 semelles** (hauteur `h`, sans
semelle intermédiaire) retombe sur l'IPE catalogue au chiffre près sur
IPE 160/300/450/600 (A, Iy, Wpl.y : écart < 0,05 %). L'intégrateur polygone +
congés est donc juste ; l'écart de 0,15–0,66 % sur les sections à 3 semelles
vient d'un détail de modélisation des congés, sans effet sur le
prédimensionnement.

Loi dégressive `2·h → 1·h`, `n_disc=6` : A, Iy, Wpl.y strictement décroissants
de l'épaule vers la sortie (vérifié IPE 160/240/400/600). Le dernier tronçon
(`h_ratio ≈ 1,083`) tend vers « traverse + semelle de gousset », pas vers la
traverse nue — c'est voulu (le gousset a sa propre semelle inférieure sur toute
sa longueur).

## 4. Résultats sur les 3 jeux de validation

`legacy` (jarret `1,66·h`) vs `pynite discrétisé` (`N_DISC_JARRET=6`,
loi `2h→1h`) — `compare_3modes_ctcim.py` :

| cas | mode | poteau / traverse | taux_trav | taux_max brut | flèche | dérive | masse |
|---|---|---|---|---|---|---|---|
| cas-01-compact | legacy | IPE 160 / IPE 140 | 40 % | 37,84 % | 2,8 | 21,8 | 168 |
| | **discrétisé** | IPE 160 / IPE 140 | 40 % | **37,77 %** | 2,9 | 22,2 | 168 |
| cas-02-bas-large | legacy | IPE 600 / IPE 600 | 100 % | 98,84 % | 57,4 | 4,7 | 4174 |
| | **discrétisé** | IPE 600 / IPE 600 | 100 % | **98,18 %** | 58,1 | 4,9 | 4174 |
| cas-03-haut-fin | legacy | IPE 600 / IPE 500 | 50 % | 54,92 % | 2,0 | 61,9 | 3242 |
| | **discrétisé** | IPE 600 / IPE 500 | 50 % | **54,85 %** | 2,0 | 62,9 | 3242 |

**Aucune section retenue ne change.** `taux_max` bouge de −0,07 / −0,66 /
−0,07 point. Flèche/dérive +1 à +2 % (le jarret discrétisé est un peu plus
souple : la loi `2h→1h` passe la majeure partie de sa longueur sous `1,66·h`).
`pynite ancien` (`N_DISC_JARRET=1`) est identique au legacy au chiffre près.

Détail des taux à l'épaule vs sortie (cas-02, section retenue) : `tx_mom_renf`
50,8 % (legacy) → 39,5 % (discrétisé) — le tronçon d'épaule `h_ratio≈1,92` a un
`Wpl` bien supérieur au `1,66·h` constant ; `tx_mom_pied_arba` reste < 40 %.

### Écart CTICM — cas-02 « bas et large » : NON résorbé par la discrétisation

CTICM dimensionne l'arbalétrier à **IPE 500** là où Instanote exige **IPE 600**
(2 crans). La discrétisation du jarret **ne change rien** à ce constat, et c'est
attendu : le point gouvernant de cas-02 est le **moment de poteau** en tête
(`tx_mom_pot ≈ 98 %`), pas le jarret. Test à sections forcées :

| section | tx_mom_pot (ELU gouvernant) | verdict |
|---|---|---|
| IPE 600 / IPE 500 | **103,1 %** | rejeté |
| IPE 600 / IPE 550 | 100,9 % | rejeté |
| IPE 600 / IPE 600 | 98,2 % | retenu |

Un arbalétrier plus raide (IPE 600) soulage le moment de poteau (moins de
rotation à l'épaule) → Instanote a besoin d'IPE 600 pour passer la vérification
du **poteau**, pas de l'arbalétrier (dont tous les taux sont < 55 %). L'écart
de ~10 points sur le moment de poteau vs CTICM (déjà relevé dans
`validation/COMPARAISON_CTICM.md` §2) n'est donc **pas** porté par le renfort
d'épaule. Pistes restantes : traitement des zones de vent de rive F/G/J
(**étape 4**), et modélisation du jeu de la liaison poteau/traverse (le jarret
ne raidit ici que l'arbalétrier, pas la tête de poteau — cf. étape 7, longueur
de jarret variable). Le user a acté ce résultat comme **non bloquant**.

## 5. Diagnostic a posteriori — effort tranchant

`jarret_discret.diagnostic_cisaillement(geom, charges, poteau, arba)` — appelé
par `charge_et_sections` après `optimise_IPE`, en `try/except`, **ne change
aucune section**. Méthode énergétique (Castigliano) : sur les efforts d'about
combinés (les efforts se superposent linéairement), reconstruction de `V(x)`
(linéaire) et `M(x)` (parabole consistante) barre par barre, puis
`Σ ∫V²/(G·Avz) dx / Σ ∫M²/(E·Iy) dx` pour la combinaison ELS la plus fléchie
(`G = E/2,6`). Cisaillement d'âme de jarret : `|V_about| / (Avz · fy/√3/10)`
max sur **tous** les tronçons, combinaison ELU.

| cas | contribution effort tranchant à la flèche | cisaillement d'âme jarret (max) |
|---|---|---|
| cas-01-compact | **+0,3 %** | 11,4 % |
| cas-02-bas-large | **+0,9 %** | 20,6 % |
| cas-03-haut-fin | **+0,6 %** | 14,5 % |

→ La déformation d'effort tranchant pèse **moins de 1 %** sur la flèche/dérive
des portiques IPE : l'hypothèse Euler-Bernoulli du solveur est bien justifiée,
un passage à Timoshenko ne changerait rien de sensible. Clés ajoutées au dict
résultat : `cis_ecart_fleche_pct`, `cis_taux_ame_jarret_pct`, `cis_note`
(phrase pour l'encart résultats écran + PDF).

## 6. Dense vs creux — on reste en dense

`check_3e_profilage.py`, matrice réduite du modèle discrétisé (**47 × 47**,
18 % de non-nuls) :

| méthode | temps |
|---|---|
| dense (`scipy.linalg.lu_factor` + `lu_solve`) | **17 µs** |
| creux (`scipy.sparse.linalg.splu` + `solve`) | 31 µs |

En dessous de ~quelques centaines de DDL, l'analyse symbolique + la
construction CSC de `splu` coûtent plus qu'elles ne rapportent. **Aucun
changement de code** : `m.Ke(..., sparse=False)` + LU dense scipy conservés.

## 7. Profilage — coût de la discrétisation

`check_3e_profilage.py`, `resoudre(poteau, arba)` (médianes, machine de dev) :

| cas | `n_disc = 1` (6 barres) | `n_disc = 6` (16 barres) | × |
|---|---|---|---|
| cas-01-compact | 0,96 ms | 2,61 ms | 2,7 |
| cas-02-bas-large | 0,92 ms | 2,51 ms | 2,7 |
| cas-03-haut-fin | 0,97 ms | 2,66 ms | 2,7 |

Le modèle discrétisé multiplie par ~2,7 le coût d'une résolution (plus de
barres → plus de `member.ke()`/`T()`, LU 47×47 vs 17×17). Sur un
`charge_et_sections` complet (10–40 itérations IPE), l'écran de calcul passe
d'environ 30–120 ms à 80–280 ms — acceptable pour l'usage web. La fonction de
section est mémoïsée (~60 calculs de contour uniques par calcul). Pistes
d'optimisation si besoin plus tard : `n_arc` du contour, cache des `member.ke()`
des barres dont la section ne change pas d'une itération à l'autre.

## 8. Tests (`validation/pynite_check/`)

| script | rôle | verdict |
|---|---|---|
| `check_3a_section_jarret.py` | section 3 semelles + `r` vs PropSection (IPE 160/300/450) ; garde-fou intégrateur ; monotonie ; `sections_jarret(_,1)==[jarret()]` | **0** |
| `check_3b_topologie.py` | topologie + expanseur : `n_disc=1` == `def_noeud_barres` ; `n_disc=6` sain ; ordre nœuds PyNite | **0** |
| `check_3c_non_regression_ancien_modele.py` | `SolveurPyNite(n_disc=1)` == `_SolveurLegacy` (< 1e-6 %) sur 3 jeux + 15 aléatoires | **0** |
| `check_3d_discretise.py` | non-régression du modèle discrétisé (référence figée) + garde de sécurité + suivi CTICM | **0** |
| `check_3e_profilage.py` | profilage n=1 vs n=6, dense vs creux | (pas de verdict) |
| `check_1a…1g` + `check_deps_runtime` | rejoués — inchangés. `check_1g` **épinglé à `N_DISC_JARRET=1`** (parité = ancien modèle) | **0** |

## 9. Reste à faire pour clôturer l'étape

1. Doc : `docs/moteur-de-calcul.md`, `docs/reference-legacy-vs-pynite.md`,
   `CLAUDE.md`, `validation/COMPARAISON_CTICM.md` — **fait dans ce commit**.
2. Validation manuelle du user (calcul réel, encart cisaillement, export PDF).
3. **Commit final séparé** : bascule `MOTEUR_CALCUL` défaut `legacy → pynite`
   dans `calcport.py` + `CLAUDE.md`, après feu vert du user.
4. Déploiement Railway : `MOTEUR_CALCUL=pynite` déjà prévu ; `N_DISC_JARRET`
   laissé au défaut (6).

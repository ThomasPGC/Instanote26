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

## 4. Jarret excentré sur son axe neutre (sous-étape 3.f — **par défaut**)

Le jarret discrétisé **colinéaire** à la traverse (loi `2h→1h`) ne changeait
**aucune section retenue** sur les 3 jeux (`taux_max` : −0,07 / −0,66 / −0,07 pt,
flèche/dérive +1 à +2 %). Le `1,66·h` prismatique ne faussait donc pas le
dimensionnement — mais la modélisation restait grossière : les barres du jarret
étaient portées par la fibre moyenne de la **traverse nue**, alors que leur
section (âme jusqu'à `2h`) a son centre de gravité nettement plus bas.

**Correction (demande du user) :** chaque nœud du jarret (épaule, intérieurs,
sortie) est abaissé sur la **ligne des centres de gravité** des sections
successives des tronçons (axe neutre de flexion, théorie des poutres). Le nœud
d'épaule étant le sommet du poteau, celui-ci est **physiquement raccourci** ;
le jarret n'est plus colinéaire à la traverse. `offset_axe_neutre(arba,
h_ratio) = (H − h/2) − zG`. Offset au nœud interne `p` = moyenne des deux
tronçons adjacents ; à l'épaule = tronçon le plus profond ; en sortie ≈ tronçon
`h_ratio≈1,08` (petit résidu : le gousset a encore sa semelle inférieure).

Ordre de grandeur de l'abaissement du sommet de poteau : ~0,047·hpot pour
cas-01 (IPE 140, ~6,5 cm) ; ~0,28·h_traverse pour cas-02 (IPE 600, ~28 cm).

`legacy` vs `pynite colinéaire` (`JARRET_EXCENTRE=0`) vs **`pynite excentré`
(défaut)** — `check_3f_excentre.py` :

| cas | mode | poteau / traverse | taux_trav | taux_max brut | flèche | dérive | masse |
|---|---|---|---|---|---|---|---|
| cas-01-compact | legacy | IPE 160 / IPE 140 | 40 % | 37,84 % | 2,8 | 21,8 (H/160) | 168 |
| | colinéaire | IPE 160 / IPE 140 | 40 % | 37,77 % | 2,9 | 22,2 (H/157) | 168 |
| | **excentré** | IPE 160 / IPE 140 | 40 % | **37,08 %** | 2,8 | **21,4 (H/163)** | 168 |
| cas-02-bas-large | legacy | IPE 600 / IPE 600 | 100 % | 98,84 % | 57,4 | 4,7 | 4174 |
| | colinéaire | IPE 600 / IPE 600 | 100 % | 98,18 % | 58,1 | 4,9 | 4174 |
| | **excentré** | IPE 600 / **IPE 550** | 100 % | **98,26 %** | 64,2 | 5,6 | **3786** |
| cas-03-haut-fin | legacy | IPE 600 / IPE 500 | 50 % | 54,92 % | 2,0 | 61,9 (H/161) | 3242 |
| | colinéaire | IPE 600 / IPE 500 | 50 % | 54,85 % | 2,0 | 62,9 (H/158) | 3242 |
| | **excentré** | IPE 600 / IPE 500 | 50 % | **54,02 %** | 2,0 | **59,7 (H/167)** | 3242 |

- **cas-02 : IPE 600/600 → IPE 600/550** (−388 kg). Un cran vers l'IPE 500 de
  CTICM. À sections forcées, `tx_mom_pot` gouvernant : 103,1 % (colinéaire) →
  **100,3 %** (excentré) à IPE 600/500 — l'excentrement gagne 2,8 pts, il en
  fallait ~3,1 → toujours rejeté d'un cheveu.
- **cas-01, cas-03 : sections inchangées**, dérive améliorée (poteau plus
  court = plus raide) — marge regagnée sur le critère H/150 qui gouverne ces
  deux cas.
- Série aléatoire (6 géométries) : 5 inchangées, 1 gagne un cran d'arbalétrier.
  Aucun cas ne bascule en échec, aucune section sous le CTICM.

**Coût architecture.** La géométrie dépend maintenant de la **traverse** (pas du
poteau) → `SolveurPyNite` reconstruit son modèle (et les caches de forces `FER`,
`_T`, RHS) **à chaque changement de `arba`** (~10 fois par `optimise_IPE`), mis
en cache. Surcoût mesuré : +~0,2 ms en régime établi, +~10-20 ms sur un
`charge_et_sections` complet. La matrice de rigidité, elle, était déjà
réassemblée + refactorisée à chaque itération (les sections changent). Effets
secondaires (décalage du `FER` des charges réparties dû au léger changement de
longueur/angle des barres ; charges nodales de rive de `chargement_nv` qui
gardent l'angle de toiture nominal) : quelques dixièmes de pour-cent, négligeables
à ce niveau — à revoir éventuellement à l'étape 4.

### Écart CTICM — cas-02 « bas et large » : réduit à 1 cran, pas résorbé

Le point gouvernant de cas-02 reste le **moment de poteau** en tête
(`tx_mom_pot`), pas le jarret. L'excentrement le fait passer de 103,1 % à
100,3 % (IPE 600/500) — il manque ~0,3 point. Les taux d'arbalétrier sont tous
< 55 %. L'écart résiduel (~10 → ~0,3 pt de marge sur le poteau) pointe vers le
traitement des **zones de vent de rive** (**étape 4**) et la modélisation fine
de la liaison poteau/traverse (le jarret ne raidit que l'arbalétrier —
**étape 7**, longueur de jarret variable). **Non bloquant** (acté par le user).

Flag : `JARRET_EXCENTRE` (défaut activé pour `N_DISC_JARRET>1` ;
`JARRET_EXCENTRE=0` → jarret colinéaire, pour comparaison / debug).

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
| cas-01-compact | **+0,3 %** | 11,0 % |
| cas-02-bas-large | **+0,8 %** | 23,0 % |
| cas-03-haut-fin | **+0,6 %** | 13,5 % |

(valeurs du modèle excentré ; en colinéaire : +0,3 / +0,9 / +0,6 % et
11,4 / 20,6 / 14,5 %.)

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
| `check_3d_discretise.py` | non-régression du modèle discrétisé **+ excentré** (référence figée) + garde (pas sous CTICM, taux_max ne s'effondre pas) | **0** |
| `check_3e_profilage.py` | profilage n=1 vs n=6, dense vs creux | (pas de verdict) |
| `check_3f_excentre.py` | comparaison colinéaire vs excentré (3 jeux + aléatoires) | (pas de verdict) |
| `check_1a…1g` + `check_deps_runtime` | rejoués — inchangés. `check_1g` **épinglé à `N_DISC_JARRET=1`** (parité = ancien modèle) | **0** |

## 9. Reste à faire pour clôturer l'étape

1. Doc : `docs/moteur-de-calcul.md`, `docs/reference-legacy-vs-pynite.md`,
   `CLAUDE.md`, `validation/COMPARAISON_CTICM.md` — **fait**.
2. **Validation manuelle du user en local** (`MOTEUR_CALCUL=pynite` dans `.env`) :
   calcul réel, encart cisaillement, export PDF, `/compte`.
3. Si OK → push. **Commit de bascille séparé** : `MOTEUR_CALCUL` défaut
   `legacy → pynite` dans `calcport.py` + `CLAUDE.md`.
4. Railway : poser `MOTEUR_CALCUL=pynite` s'il n'y est pas déjà ; `N_DISC_JARRET`
   et `JARRET_EXCENTRE` laissés au défaut (6 / activé).

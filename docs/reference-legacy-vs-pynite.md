# Référence — correspondance moteur « legacy » ↔ PyNite

> Document de référence, en lecture seule. Il explique, étape de calcul par étape
> de calcul, ce que faisait le moteur historique (`business/calcport.py`, dit
> *legacy*) et ce qui le remplace depuis la bascule de l'**étape 1** de la
> roadmap moteur (`business/solveur_pynite.py`, backend *PyNite*).
>
> Contexte de la bascule : `docs/moteur-de-calcul.md` (décisions, roadmap) et
> `docs/historique/bascule-pynite-etape1.md` (journal détaillé, sous-étapes
> 1.a→1.g, parités mesurées).
>
> **Périmètre.** On ne décrit ici que **ce qui a changé** : la résolution
> structurelle (efforts, déplacements, taux de travail) et le modèle mécanique
> sous-jacent. Le calcul des charges de neige et de vent (`chargement_nv.py`),
> la boucle de choix des profils IPE (`optimise_IPE`) et l'orchestration
> (`charge_et_sections`) sont **inchangés** et ne sont pas détaillés.
>
> **Public visé.** Quelqu'un qui connaît la résistance des matériaux (RDM) et
> découvre les codes de calcul par éléments finis. Le vocabulaire éléments finis
> et les noms de fonctions PyNite sont explicités au fil de l'eau ; un glossaire
> est donné plus bas.

---

## 1. Mise en contexte — de quoi on parle

### 1.1 Ce que fait cette partie du moteur

À géométrie et chargement donnés, on veut connaître, pour **un couple de
profils** (IPE du poteau, IPE de la traverse) :

- les **déplacements** de quelques points clés (tête des poteaux, faîtage) —
  pour vérifier les critères de service (flèche, dérive) ;
- les **efforts internes** (moment fléchissant, effort tranchant) aux
  sections sensibles — pour vérifier la résistance ;
- les **taux de travail** qui en découlent (effort sollicitant / effort
  résistant).

La boucle `optimise_IPE` appelle cette résolution des dizaines de fois, en
faisant grossir les profils jusqu'à ce que tous les critères passent.

### 1.2 La méthode « legacy » : la méthode des déplacements, écrite à la main

Le moteur historique applique la **méthode des déplacements** (aussi appelée
méthode de la raideur, ou méthode directe de rigidité) : la même méthode
matricielle qui est à la base de tous les codes de portiques. En résumé :

1. on découpe la structure en **barres** reliées par des **nœuds** ;
2. chaque barre a une **matrice de rigidité** \(k\) qui relie les
   déplacements de ses deux extrémités aux efforts à ces extrémités ;
3. on **assemble** ces matrices dans une grande matrice de rigidité globale
   \(K\) ;
4. on écrit l'équilibre \(K \cdot d = F\), où \(d\) est le vecteur de tous
   les déplacements nodaux inconnus et \(F\) le vecteur des forces nodales ;
5. on **bloque** les déplacements empêchés par les appuis, on **résout** le
   système linéaire, puis on **remonte** aux efforts dans chaque barre.

Dans `calcport.py`, tout cela est codé explicitement : les classes `Node` et
`Beam`, les matrices \(3\times3\) tapées terme à terme dans
`Beam.calc_kl_ij()`, l'assemblage dans `crea_matrice_rigidite()`, le blocage
des appuis par suppression de lignes/colonnes dans `calcport()`, la résolution
par `numpy.linalg.solve`.

> **« Élément fini »** est ici un synonyme d'« élément de barre » : une poutre
> droite à deux nœuds. La méthode des déplacements *est* la méthode des
> éléments finis appliquée aux poutres. Le legacy et PyNite font donc la
> **même physique** ; ils diffèrent seulement par *qui écrit les matrices*.

### 1.3 PyNite : la même méthode, fournie par une bibliothèque

[PyNite](https://github.com/JWock82/PyNite) (paquet `PyNiteFEA`, épinglé en
version `3.0.0`) est une bibliothèque Python de calcul de structures par
éléments finis (poutres et coques 3D). Elle sait faire, de manière générique
et testée, exactement les cinq points ci-dessus.

On garde **la même interface** (`resoudre(poteau, arba)` renvoie le même
dictionnaire de résultats) et **la même boucle** `optimise_IPE`. Seule la
« couche 3 » ci-dessous est remplacée.

### 1.4 Les quatre couches du calcul, et où se situe la bascule

| Couche | Rôle | Code | Touché ? |
|---|---|---|---|
| **1. Données & zonage** | géométrie + commune → zones neige/vent → liste de **cas de charge élémentaires** (1 permanent « CP », 2 neige, N vent) | `charge_et_sections`, `chargement_nv.py` | **non** — mêmes cas donnés aux deux backends |
| **2. Choix des profils** | prédimensionnement, boucle qui fait grossir les IPE, combinaisons ELS/ELU, critères flèche `L/200` · dérive `h/150` · taux ≤ 100 % | `optimise_IPE` | **non**, sauf le bloc « résoudre tous les cas », désormais **délégué** |
| **3. Résolution structurelle** | pour un couple de profils : monter le modèle, résoudre chaque cas, en tirer 3 déplacements + 13 taux | `_SolveurLegacy` **↔** `SolveurPyNite` | **OUI — couche remplacée** |
| **4. Modèle mécanique** | 7 nœuds / 6 barres, pieds articulés, élément poutre Euler-Bernoulli 1er ordre | classes `Node`/`Beam` **↔** `FEModel3D` de PyNite | **OUI** |

L'aiguillage se fait par la variable d'environnement **`MOTEUR_CALCUL`**
(`legacy` par défaut dans le code, `pynite` sur Railway) — fonction
`_make_solveur()` dans `calcport.py`. Les deux backends renvoient des
**résultats identiques** (parité à 0,000 % consignée dans le journal, bug
`Sij` corrigé des deux côtés — voir §7 et §8).

### 1.5 L'idée à retenir

Le legacy **écrit lui-même** toutes les matrices et résout tout à la main.
PyNite, dans l'option retenue (dite **« assembleur »**, cf.
`docs/historique/bascule-pynite-etape1.md`), **fournit les briques**
(matrices de barre, matrice globale, conversion des charges en forces
nodales, catalogue de sections modifiables) et **`SolveurPyNite` garde le
pilotage** : c'est lui qui applique les conditions d'appui, factorise la
matrice une seule fois par couple de profils, résout cas par cas, et
reconstruit efforts et taux avec **les formules exactes du legacy**. On
bénéficie d'une bibliothèque éléments finis établie sans dépendre de sa
boucle de résolution complète (qui serait 13 à 22 fois trop lente ici — voir
le profilage dans le journal).

---

## 2. Glossaire — termes, acronymes, noms de fonctions

### Vocabulaire général

| Terme | Signification |
|---|---|
| **DDL** (angl. *DOF*) | **degré de liberté** : une composante de déplacement possible d'un nœud. Ici, dans le plan : translation X, translation Y, rotation. 3 DDL par nœud × 7 nœuds = 21 DDL. |
| **Nœud** | point de connexion entre barres, où l'on écrit l'équilibre et où vivent les DDL. |
| **Barre / membre** (angl. *member*) | poutre droite à deux nœuds. Legacy : classe `Beam`. PyNite : *member*. |
| **Repère local / global** | *local* = attaché à la barre (axe x le long de la barre) ; *global* = repère du portique (X horizontal, Y vertical). Le passage de l'un à l'autre est une rotation. |
| **Matrice de rigidité** | matrice \(k\) telle que `efforts = k · déplacements`. *Élémentaire* pour une barre (repère local), *globale* après assemblage de toutes les barres. |
| **Assemblage** | opération qui range les matrices élémentaires de toutes les barres dans la matrice globale \(K\), en additionnant les contributions des barres qui partagent un nœud. |
| **Second membre** (angl. **RHS**, *right-hand side*) | le vecteur \(F\) du système \(K \cdot d = F\), c.-à-d. **le vecteur des forces nodales**. « RHS » ne désigne ici *que* le membre de droite d'une équation — aucun rapport avec un profil creux. |
| **UDL** (*uniformly distributed load*) | **charge uniformément répartie** le long d'une barre (daN/cm). |
| **Efforts d'encastrement** / **FER** (*fixed-end reactions*) | efforts et moments qui apparaîtraient aux deux extrémités d'une barre **si elles étaient parfaitement encastrées**, sous la charge répartie de la barre. Formules fermées classiques : réaction \(qL/2\), moment \(qL^2/12\). C'est **exactement** ce que le legacy appelle `Sij` / `Sji`. On s'en sert pour transformer une charge « sur la barre » en forces équivalentes « aux nœuds ». |
| **Efforts d'about** (angl. *member end forces*) | les efforts (N, V, M) aux **deux extrémités** d'une barre, une fois la structure résolue. Terme maison : « about » = extrémité de barre. |
| **Factorisation LU** | on écrit une matrice \(A\) comme produit \(L \cdot U\) (triangulaire inférieure × supérieure). Coûteux une fois, mais permet ensuite de résoudre \(A x = b\) pour **plusieurs** seconds membres \(b\) très vite. Utilisé pour résoudre tous les cas de charge d'un même couple de profils sans refaire l'élimination de Gauss à chaque fois. |
| **Euler-Bernoulli** (EB) | théorie de poutre où les sections restent planes **et perpendiculaires** à la fibre moyenne : la déformation due à l'effort tranchant est négligée dans la raideur. Opposé : Timoshenko (cisaillement pris en compte). Le legacy et PyNite (tel que configuré ici) sont tous deux en Euler-Bernoulli. |
| **1er ordre / linéaire** | équilibre écrit sur la géométrie **non déformée**, pas d'effet P-Δ, matériau élastique. |

### Objets et fonctions — legacy (`calcport.py`)

| Nom | Rôle |
|---|---|
| `Node`, `Beam` | classes nœud et barre. |
| `Beam.calc_R()` | matrice de rotation \(R\) (\(3\times3\)) repère local → global de la barre. |
| `Beam.calc_kl_ij()` | matrices de rigidité élémentaires en repère local : blocs `kij`, `kji` (diagonaux) et `lij`, `lji` (couplage entre les 2 nœuds). |
| `Beam.calc_KL_ij()` | passe ces blocs en repère global : \(K = R^{\mathsf T} k\, R\). |
| `Beam.calcSij_vert(q)` / `calcSij_perp(q)` | efforts d'encastrement `Sij`/`Sji` de la barre sous charge verticale (gravité) ou perpendiculaire (vent). |
| `Beam.eff()` | passe `Sij`/`Sji` en global : `Fij = Rᵀ·Sij`. |
| `jarret(section, 1.66)` | caractéristiques (I, A, Avz, Wpl) du **renfort d'épaule** : section en I reconstituée, âme de hauteur `1,66 × h` de la traverse, prismatique. |
| `def_noeud_barres(geom, …)` | construit les 7 nœuds et 6 barres du portique. |
| `change_sections(barres, poteau, arba)` | ré-affecte les profils aux 6 barres (poteau → B0/B5, traverse → B2/B3, `jarret(traverse)` → B1/B4). |
| `crea_matrice_rigidite(A, B)` | **assemblage** de la matrice globale \(K\) (21×21). |
| `crea_matrice_force(nb, B, cas)` | construit le **second membre** \(F\) d'un cas : appelle `calcSij_*` + `eff()` sur chaque barre, somme aux nœuds, retranche les charges ponctuelles `cas[2]`. |
| `calcport(A, B, K, F, cas)` | applique les appuis (supprime les lignes/colonnes bloquées), résout `K·d = F` (`numpy.linalg.solve`), ré-insère les zéros, appelle le post-traitement. |
| `calculer_et_verifier_resultats(B, D)` | efforts d'about de chaque barre `efforts_noeuds = −Sij + k_barre·(R·d)` ; en déduit les 3 déplacements clés et les 13 taux `tx_*`. |
| `_SolveurLegacy.resoudre(poteau, arba)` | enchaîne `change_sections` → `crea_matrice_rigidite` → (pour chaque cas) `crea_matrice_force` → `calcport`. Renvoie `[(nom_cas, ens_resu), …]`. |

### Objets et fonctions — PyNite (`solveur_pynite.py`)

| Nom | Rôle | Équivalent legacy |
|---|---|---|
| `FEModel3D()` | le modèle de structure (nœuds, barres, matériaux, sections, charges). | l'ensemble `A`, `B` |
| `m.add_material(nom, E, G, nu, rho)` | définit un matériau. Ici `("acier", E, E/2.6, 0.3, 0.0)` : **G et ρ sont inertes** (pas de cisaillement en EB, poids propre traité à part). | constante `E` |
| `m.add_node(nom, x, y, z)` | ajoute un nœud (modèle 3D, on travaille dans le plan z = 0). | `Node(x, y, num)` |
| `m.def_support(nom, DX, DY, DZ, RX, RY, RZ)` | bloque des DDL du nœud (`True` = bloqué). Pieds N0/N6 : translations bloquées, rotation libre = **rotule**. Partout : DZ, RX, RY bloqués → modèle **plan**. | suppression de lignes/colonnes dans `calcport` |
| `m.add_section(nom, A, Iy, Iz, J)` | section de barre. La flexion **dans le plan XY** se fait autour de l'axe Z → c'est **`Iz`** qui porte l'inertie forte de l'IPE (`Iy` et `J` restent à 1, inutilisés en plan). Les sections sont **modifiées en place** à chaque itération (`sec.A = …`, `sec.Iz = …`). | `Beam.aire`, `Beam.I` |
| `m.add_member(nom, ni, nj, mat, sec)` | ajoute une barre entre deux nœuds. | `Beam(nOr, nExtr, section)` |
| `m.add_member_dist_load(barre, dir, w1, w2, case=…)` | charge répartie sur une barre. `dir="FY"` = repère **global** (gravité, neige projetée) ; `dir="Fy"` = repère **local** (vent, perpendiculaire à la barre). `w1 = w2` → charge **uniforme** (UDL). `case` = étiquette du cas de charge. | `calcSij_vert` / `calcSij_perp` |
| `m.add_node_load(nœud, dir, P, case=…)` | charge ponctuelle sur un nœud (`"FX"`, `"FY"`, `"MZ"`). | terme `cas[2]` |
| `m.add_load_combo(nom, {case: 1.0})` | combinaison triviale « ce cas seul, facteur 1 » : on résout **cas par cas**, jamais via les combinaisons pondérées de PyNite (les pondérations ELS/ELU sont faites dans `optimise_IPE`). | — |
| `Analysis._prepare_model(m)` | **prépare** le modèle : numérote les DDL (`node.ID`), marque les barres actives, découpe les sous-barres — **sans résoudre**. ~1 ms, au lieu de ~20 ms pour une analyse complète dont on n'a besoin de rien d'autre. | — |
| `m.Ke(combo, False, False, False)` | **assemble et renvoie la matrice de rigidité globale** \(K\) (21×21). `Ke` : *K* = rigidité, *e* = *elastic* (par opposition à une matrice géométrique). | `crea_matrice_rigidite` |
| `m.P(combo)` | vecteur global des **charges ponctuelles** nodales (angl. *point loads*). | part « `− cas[2]` » de `F` |
| `m.FER(combo)` | vecteur global des **efforts d'encastrement** (*fixed-end reactions*) de toutes les charges réparties, ramenés aux nœuds. | part « `Σ Fij` » de `F` |
| `member.fer(combo)` | les 12 efforts d'encastrement d'**une** barre, repère local. | `Sij` / `Sji` |
| `member.ke()` | matrice de rigidité **élémentaire** d'une barre (12×12, repère local). Reflète immédiatement `sec.A` / `sec.Iz`. | blocs `kij/kji/lij/lji` |
| `member.T()` | matrice de **transformation** local ↔ global (12×12). | `R` (en 3×3) |
| `scipy.linalg.lu_factor(K_libre)` | **factorise** la sous-matrice réduite aux DDL libres. Fait **une fois par couple de profils**. | (le legacy refait `solve` à chaque cas) |
| `scipy.linalg.lu_solve(lu, rhs)` | résout `K_libre · d = rhs` pour un second membre donné. Fait **une fois par cas de charge**. | `numpy.linalg.solve` |
| `m.analyze_linear(...)`, `member.moment(x)`, `member.shear(x)` | résolution **complète** intégrée + lecture des **diagrammes internes** le long de la barre. **Non utilisés en production** (trop lents) ; servent seulement d'oracle dans les scripts de validation `validation/pynite_check/`. | — |

---

## 3. Le modèle : 7 nœuds, 6 barres

Portique bipente symétrique, pieds articulés (rotules), construit par
`def_noeud_barres()` — **identique** pour les deux backends (PyNite importe
cette fonction du legacy pour les coordonnées et la connectivité).

```
                         N3  (faîtage, portée/2 ; h_faît)
                         /\
                    B2  /  \  B3          B1, B4 = renforts d'épaule (jarrets),
              N2 ______/    \______ N4    sur 10 % de la portée en projection
               /                    \     horizontale ; section jarret(traverse)
          B1  /                      \  B4    (âme 1,66·h, prismatique)
       N1 ___/                        \___ N5     N1, N5 = têtes de poteau
          |                              |
      B0  |                              |  B5    B0, B5 = poteaux (IPE poteau)
          |                              |        B2, B3 = traverses (IPE traverse)
       N0 o                              o N6     N0, N6 = pieds articulés
      (0,0)                        (portée,0)
```

| Barre | Nœuds | Rôle | Section |
|---|---|---|---|
| B0 | N0 → N1 | poteau gauche | IPE poteau |
| B1 | N1 → N2 | renfort d'épaule gauche | `jarret(traverse)` |
| B2 | N2 → N3 | traverse gauche | IPE traverse |
| B3 | N3 → N4 | traverse droite | IPE traverse |
| B4 | N4 → N5 | renfort d'épaule droit | `jarret(traverse)` |
| B5 | N5 → N6 | poteau droit | IPE poteau |

**Comptage des DDL.** 7 nœuds × 3 DDL = **21**. Les pieds N0 et N6 bloquent
translation X et translation Y (rotule), les autres nœuds sont libres :
21 − 4 = **17 DDL libres**. Le legacy obtient ce 17 en supprimant 4
lignes/colonnes de \(K\) ; `SolveurPyNite` l'obtient en construisant un
**masque** des DDL non bloqués (`self._free`) et en extrayant
`K[free, free]`. Forme différente, même système réduit (démontré à la
sous-étape 1.c du journal).

Points où sont évalués les taux de travail (mapping barre / extrémité,
**identique** entre `calculer_et_verifier_resultats` et les tables
`_TX_MOM` / `_TX_CIS` de `solveur_pynite.py`) :

| Clé | Point | Barre / extrémité |
|---|---|---|
| `tx_mom_pot_g` / `_d` | tête de poteau | B0 fin / B5 origine |
| `tx_mom_renf_g` / `_d` | entrée du renfort d'épaule (angle du portique) | B1 origine / B4 fin |
| `tx_mom_pied_arba_g` / `_d` | arbalétrier **en sortie de jarret** | B2 origine / B3 fin |
| `tx_mom_fait` | faîtage | B2 fin (= N3) |
| `tx_cis_*` | mêmes points, effort tranchant | idem |

---

## 4. L'élément poutre (Euler-Bernoulli)

- **Legacy.** Élément de poutre plan à 2 nœuds, **3 DDL par nœud**
  (translation x, translation y, rotation). Matrice de rigidité de flexion
  bâtie sur les termes classiques de la poutre Euler-Bernoulli :
  rigidité axiale \(EA/L\), rigidité de flexion en \(12EI/L^3\),
  \(6EI/L^2\), \(4EI/L\), \(2EI/L\) (voir `Beam.calc_kl_ij()`). Aucune
  contribution d'effort tranchant : c'est de l'Euler-Bernoulli pur.

- **PyNite.** Élément *frame* (poutre) 3D à 2 nœuds, **6 DDL par nœud**. On
  bride le hors-plan en bloquant partout DZ, RX, RY : il ne reste que les
  3 DDL utiles (x, y, rotation autour de Z). Comme on **ne fournit pas**
  d'aire de cisaillement à `add_section`, PyNite 3.0 n'ajoute **aucun terme
  de Timoshenko** : l'élément est lui aussi en Euler-Bernoulli.

- **Pourquoi les deux coïncident sans réglage.** Même théorie de poutre,
  même hypothèse (cisaillement négligé), même module \(E = 2\,100\,000\)
  daN/cm², mêmes unités (cm, daN). Le module de cisaillement \(G\) passé à
  PyNite (`E/2.6`) n'a **aucun effet** puisqu'aucun terme ne l'utilise. La
  parité des 21 déplacements a été vérifiée « à la précision machine » dès la
  sous-étape 1.a (journal), d'abord sans renfort d'épaule puis avec.

- **Diagnostic Timoshenko a posteriori (étape 3).** Le solveur **reste
  Euler-Bernoulli**. `jarret_discret.diagnostic_cisaillement` estime, **après**
  le choix des sections et sans jamais le modifier, la contribution de la
  déformation d'effort tranchant à la flèche par bilan d'énergie
  (\(\sum\!\int V^2/(G A_{vz})\,\mathrm dx \big/ \sum\!\int M^2/(E I)\,\mathrm dx\)).
  Mesure : **+0,3 à +0,9 %** sur les 3 jeux de validation → l'hypothèse EB est
  bien justifiée pour des portiques IPE. Clés ajoutées au dict résultat :
  `cis_ecart_fleche_pct`, `cis_taux_ame_jarret_pct`, `cis_note`.

- **Attention à un piège d'indexation** (utile si l'on relit le code
  PyNite) : dans les vecteurs à 6 DDL/nœud de PyNite, l'ordre est
  `DX, DY, DZ, RX, RY, RZ`. La **rotation dans le plan est RZ, à l'indice
  local 5** — pas l'indice 2 (qui est DZ, hors-plan, toujours nul).
  Extraire un vecteur « façon legacy » (3 DDL/nœud) = prendre les indices
  locaux `(0, 1, 5)`.

---

## 5. Correspondance étape par étape

Pour chaque étape : rôle → méthode legacy (formule clé) → méthode PyNite
(fonctions nommées) → pourquoi c'est équivalent, ou quelle différence de
forme subsiste.

### 5.1 Raideur d'une barre (repère local)

- **Rôle.** Relier les 6 efforts d'about d'une barre à ses 6 déplacements
  d'about : `f_local = k · d_local`.
- **Legacy.** `Beam.calc_kl_ij()` : construction manuelle des blocs
  \(3\times3\) `kij`, `kji`, `lij`, `lji`, avec les termes \(EA/L\),
  \(12EI/L^3\), \(6EI/L^2\), \(4EI/L\), \(2EI/L\). L'inertie \(I\) et l'aire
  \(A\) viennent du catalogue IPE, ou de `jarret()` pour B1/B4.
- **PyNite.** `member.ke()` renvoie la matrice élémentaire \(12\times12\).
  Les sections sont **mutées en place** au début de chaque `resoudre()`
  (`sec.A`, `sec.Iz`), et `member.ke()` en tient compte immédiatement.
- **Équivalence.** Mêmes formules de poutre EB, mêmes \(E\), \(A\), \(I\).
  Différence de forme uniquement : blocs \(3\times3\) explicites (legacy) vs
  matrice \(12\times12\) dont on n'exploite que les lignes/colonnes du plan.

### 5.2 Passage repère local → repère global

- **Rôle.** Les barres sont inclinées (poteaux verticaux, traverses en
  pente) ; il faut exprimer toutes les raideurs dans le repère commun du
  portique avant de les additionner.
- **Legacy.** `Beam.calc_R()` construit la rotation \(R\) (\(3\times3\),
  \(\cos\alpha\), \(\sin\alpha\)) ; `calc_KL_ij()` applique
  \(K = R^{\mathsf T} k\, R\).
- **PyNite.** `member.T()` (matrice de transformation \(12\times12\)) ;
  `SolveurPyNite` l'applique explicitement quand il reconstruit les efforts
  d'about (`floc = ke · (T · d_barre) + fer`, §5.8).
- **Équivalence.** Même opération. Correspondance de vocabulaire :
  `R` (legacy) ↔ `T` (PyNite).

### 5.3 Assemblage de la matrice de rigidité globale

- **Rôle.** Ranger les raideurs de toutes les barres dans une matrice
  \(K\) de taille 21×21, en additionnant les contributions des barres qui se
  rejoignent sur un même nœud.
- **Legacy.** `crea_matrice_rigidite(A, B)` : double boucle sur les nœuds,
  somme des blocs diagonaux `Kij/Kji`, placement des blocs de couplage
  `Lij/Lji` d'après la connectivité.
- **PyNite.** `m.Ke(combo, False, False, False)`. (Les trois `False` :
  pas de log, pas de vérification de stabilité, pas de format creux — on
  veut une matrice dense de 21×21, la conversion en creux coûterait plus
  qu'elle ne rapporte à cette taille.)
- **Équivalence.** Résultat identique (réactions et déplacements à 0,000 %
  sur tous les cas, sous-étape 1.c).

### 5.4 Conditions d'appui (pieds articulés + modèle plan)

- **Rôle.** Empêcher les déplacements bloqués par les appuis, et fixer le
  hors-plan.
- **Legacy.** Dans `calcport()` : suppression des lignes/colonnes 0 et 1
  (translations de N0) et 18, 19 (translations de N6) de \(K\) et \(F\).
  On résout sur les 17 DDL restants, puis on **ré-insère des zéros** aux
  positions supprimées.
- **PyNite.** `def_support()` par nœud : N0 et N6 → translations bloquées,
  rotation libre (rotule) ; tous les nœuds → DZ, RX, RY bloqués (plan).
  `SolveurPyNite` déduit des drapeaux un **masque** `self._free` des 17 DDL
  libres et travaille sur `K[free, free]`.
- **Équivalence.** Le sous-espace des 17 DDL libres est le même
  (`rz` de N0 ; `dx, dy, rz` de N1…N5 ; `rz` de N6). Vérifié en 1.c
  (déplacements **et** réactions identiques).

### 5.5 Charges réparties → forces nodales équivalentes (efforts d'encastrement)

- **Rôle.** Une charge « sur la barre » (poids de couverture, neige, vent)
  ne peut pas entrer directement dans \(K \cdot d = F\), qui ne connaît que
  des forces **aux nœuds**. On la remplace par le système de forces nodales
  qui produit le même effet : les **efforts d'encastrement** de la barre
  bi-encastrée (réaction \(qL/2\), moment \(qL^2/12\)), changés de signe.
- **Legacy.** `Beam.calcSij_vert(q)` (charge dans le repère global : gravité,
  neige) et `Beam.calcSij_perp(q)` (charge perpendiculaire à la barre :
  vent) remplissent `Sij` / `Sji`. `crea_matrice_force()` choisit la
  fonction selon la famille du cas (`"CP"`, `"NEI"`, `"VEN"` dans le nom),
  appelle `eff()` (`Fij = Rᵀ·Sij`), somme aux nœuds, puis retranche les
  charges ponctuelles `cas[2]`.
- **PyNite.** `m.add_member_dist_load()` pose les charges réparties
  (direction `"FY"` globale pour CP et neige, `"Fy"` locale pour le vent),
  `m.add_node_load()` pose les charges ponctuelles. Ensuite :
  - `member.fer(combo)` = les efforts d'encastrement locaux d'une barre
    (l'équivalent exact de `Sij`/`Sji`) ;
  - `m.FER(combo)` = leur assemblage global ; `m.P(combo)` = les charges
    ponctuelles assemblées ;
  - le **second membre** (RHS) d'un cas = `m.P(combo) − m.FER(combo)`,
    restreint aux 17 DDL libres.
- **Correspondance de vocabulaire.** `Sij` / `Sji` (legacy) ↔ **FER**
  (*fixed-end reactions*, PyNite). Même hypothèse : poutre EB bi-encastrée
  sous charge uniforme.
- **Convention de signe des charges ponctuelles.** Le legacy fait
  `F −= cas[2]` ; combiné à son défaut de signe global (§7), l'équivalent
  physique correct côté PyNite est `add_node_load(+v)`. Voir §6, règle 1.
- **⚠ C'est l'étape concernée par le bug `Sij`.** Voir §8.

### 5.6 Poids propre de l'acier

- **Rôle.** Ajouter le poids des profils eux-mêmes, **uniquement dans le cas
  permanent** « CP ».
- **Legacy.** Dans `crea_matrice_force()`, pour le cas CP seulement :
  `calcSij_vert(q − A · 7,85·10⁻³)` — le poids linéique
  (\(7{,}85\cdot10^{-3}\) daN/cm par cm² de section) est fondu dans la
  charge répartie.
- **PyNite.** Décomposition linéaire : 6 « cas unitaires » `__SW0…__SW5`
  (une charge répartie verticale de −1 sur une seule barre chacun). Le RHS
  et les efforts d'encastrement du cas CP sont recomposés par
  `rhs_cp = rhs_externe + Σ Aₖ · dens · rhs_unitₖ` (idem pour le FER local).
- **Pourquoi ce détour.** La charge de poids propre dépend de l'aire \(Aₖ\),
  qui **change à chaque itération** de profils ; alors que les cas unitaires,
  eux, ne changent jamais. On les calcule **une fois** (dans `__init__`),
  puis chaque itération ne fait qu'une combinaison linéaire — beaucoup moins
  cher que tout recalculer.
- **Statut.** Reformulé (hybride), résultat numérique identique : écart nul
  vs le RHS du cas CP legacy (sous-étape C du découpage).

### 5.7 Résolution du système linéaire

- **Rôle.** Résoudre \(K \cdot d = F\) pour obtenir les déplacements
  nodaux, cela pour **chaque cas de charge** d'un même couple de profils.
- **Legacy.** `numpy.linalg.solve(K_sans_app, F_sans_app)` — une élimination
  de Gauss complète **à chaque cas et à chaque itération de profils**.
- **PyNite (assembleur).** `scipy.linalg.lu_factor(K[free, free])` **une
  seule fois par couple de profils**, puis `scipy.linalg.lu_solve(lu, rhs)`
  **une fois par cas de charge**. Les seconds membres des cas autres que CP
  sont même mis en cache d'une itération à l'autre (les charges ne changent
  pas, seules les sections changent).
- **Équivalence — pourquoi c'est exact.** La matrice \(K\) ne dépend **que
  des sections**, pas du cas de charge. Factoriser \(K\) une fois puis
  résoudre pour plusieurs seconds membres donne rigoureusement la même
  solution que refaire l'élimination à chaque fois — c'est seulement plus
  rapide. C'est le cœur du gain de performance qui a rendu la bascule
  acceptable en production.

### 5.8 Efforts d'about (remontée aux efforts de barre)

- **Rôle.** Une fois les déplacements connus, calculer N, V, M aux deux
  extrémités de chaque barre.
- **Legacy.** `calculer_et_verifier_resultats()` :
  `efforts_noeuds = −Sij + k_barre · (R · d)`, où `k_barre` est la matrice
  \(6\times6\) recomposée des blocs `kij/lji/lij/kji`. Vecteur résultat par
  barre : `[Nᵢ, Vᵢ, Mᵢ, Nⱼ, Vⱼ, Mⱼ]`.
- **PyNite (assembleur).** Par barre :
  `floc = ke · (T · d_barre) + fer`, puis
  `efforts_about_legacy = −floc[[0, 1, 5, 6, 7, 11]]`
  (les indices 0,1,5,6,7,11 = les composantes du plan : N, V, M à chaque
  extrémité ; le signe « − » global reproduit la convention du legacy).
- **Équivalence.** Identité algébrique — mêmes matrices, même vecteur de
  déplacement, écart 0,000 % (« checkpoint D » du journal).
- **⚠ Ne pas confondre** ce « − » **uniforme** (efforts d'about, convention
  legacy) avec la **règle de signe 2** du §6, qui relie les efforts d'about
  du legacy aux **diagrammes internes** `member.moment(x)` de PyNite — et
  qui, elle, a un signe différent selon l'extrémité. La règle 2 ne concerne
  que le chemin « natif » utilisé dans les scripts de validation, pas le
  backend de production.

### 5.9 Déplacements clés

- **Rôle.** Extraire les 3 déplacements servant aux critères de service :
  tête de poteau gauche, tête de poteau droite, flèche au faîtage.
- **Legacy.** `depl_t_p_g = D_avec_app[3]` (translation X de N1),
  `depl_t_p_d = D_avec_app[15]` (translation X de N5),
  `fleche_fait = D_avec_app[10]` (translation Y de N3) — **avec le signe
  global inversé** propre au legacy (§7).
- **PyNite.** `−df[N1.DX]`, `−df[N5.DX]`, `−df[N3.DY]`. Le « − » (règle de
  signe 1, §6) est appliqué **une seule fois**, ici, pour restituer la même
  valeur signée que le legacy.
- **Équivalence.** Identique après application de la règle de signe 1.

### 5.10 Taux de travail

- **Rôle.** Convertir les efforts en taux sans dimension (sollicitant /
  résistant), pour les 7 points de moment et 6 points d'effort tranchant.
- **Legacy.** Pour chaque point :
  \[
    \text{tx}_\text{moment} = \frac{M}{W_{pl}\, f_y},\qquad
    \text{tx}_\text{tranchant} = \frac{V}{A_{vz}\, (f_y/\sqrt3)}
  \]
  avec \(f_y = 235\) MPa **en dur** et \(\gamma_{M0} = 1\) implicite
  (formules `M/(Wpl·fy/10)/100` etc. après conversions d'unités). \(W_{pl}\)
  et \(A_{vz}\) viennent du catalogue IPE — ou de `jarret()` pour B1/B4.
- **PyNite.** Tables `_TX_MOM` / `_TX_CIS` dans `solveur_pynite.py` :
  **exactement les mêmes formules**, mêmes constantes (`_FY = 235.0`), même
  catalogue, même usage de `jarret()` pour les renforts d'épaule.
- **Statut.** **Conservé tel quel** — le code du taux a été recopié à
  l'identique dans le backend PyNite (parité des 13 `tx_*` « au signe près »,
  0,000 %, sous-étape 1.e).
- **Ce que le taux ne contient pas** (choix durable, cf.
  `docs/moteur-de-calcul.md`) : ni interaction M+N ou M+V, ni flambement, ni
  déversement, ni classification de section. C'est du prédimensionnement pour
  étude de prix, pas une vérification réglementaire complète.

### 5.11 Renfort d'épaule (`jarret`) — DIFFÈRE entre les deux backends depuis l'étape 3

- **Rôle.** Modéliser le gousset triangulaire sous la traverse au droit du
  poteau.
- **Legacy (figé — oracle de l'ancien modèle).** `jarret(traverse, 1.66)` :
  section en I reconstituée avec les semelles de la traverse mais une âme de
  hauteur \(1{,}66\times h\), **prismatique** (constante), sur des barres B1/B4
  longues de 10 % de la portée. **Inchangé.**
- **PyNite (étape 3).** Renfort **discrétisé** en `N_DISC_JARRET` (défaut 6)
  tronçons à inertie variable, âme dégressive **linéaire de \(2h\) à l'épaule à
  \(h\) en sortie**. Section de chaque tronçon reconstituée en **I à 3 semelles
  + congés de raccordement \(r\)** (`jarret_discret.caracs_section_jarret`, par
  intégration du contour réel — recoupée PropSection v1.0.4). Topologie
  paramétrée par `jarret_discret.construire_topologie` : `N_DISC_JARRET=1`
  reproduit exactement les 7 nœuds / 6 barres de `def_noeud_barres`,
  `N_DISC_JARRET>1` insère `n−1` nœuds intérieurs par jarret (numérotés N7…,
  N0..N6 gardent leurs indices).
- **Excentrement (`JARRET_EXCENTRE`, défaut activé).** Les nœuds du jarret sont
  abaissés sur la **ligne des centres de gravité** des sections des tronçons
  (axe neutre de flexion) : `offset = (H - h/2) - z_G`. Le nœud d'épaule étant
  le sommet du poteau, le **poteau modélisé est raccourci** (~0,05·hpot pour un
  cas compact, ~0,28·h_traverse pour un cas bas et large) ; le jarret n'est
  plus colinéaire à la traverse. La géométrie dépend alors de la **traverse** →
  `SolveurPyNite` reconstruit son modèle (et les caches `FER` / `_T` / RHS) à
  chaque changement de `arba`, mis en cache. Effet principal recherché : bras
  de levier du poteau plus court → moment de tête plus faible.
- **Statut.** **Parité legacy ↔ PyNite garantie seulement en
  `N_DISC_JARRET=1`** (harnais `check_1g`, `check_3c`). En `N_DISC_JARRET=6`
  (défaut prod), les deux backends modélisent le jarret différemment — le
  legacy n'est plus qu'un oracle de l'ancien modèle. Détail :
  `docs/historique/jarret-discretise-etape3.md`.

---

## 6. Les deux règles de signe

Le backend PyNite adopte **les conventions PyNite partout** et ne reproduit
jamais les signes internes du legacy. Deux ajustements, de natures
différentes, suffisent :

### Règle 1 — défaut de signe global du legacy (sur les déplacements)

Le vecteur de déplacements `D_avec_app` renvoyé par `calcport()` est
l'**opposé** du déplacement physique. Origine : dans `crea_matrice_force()`,
le second membre est assemblé en `F = +Σ Fij` au lieu de `−Σ Fij`
(l'équivalent nodal correct). Le commentaire « les signes sont mauvais » dans
le code le signale. C'est **invisible en aval** parce que tout consommateur
réutilise ce même vecteur, ou prend une valeur absolue.

→ `SolveurPyNite` calcule le déplacement **physique** et applique un « − »
**une seule fois**, à l'extraction : `depl_t_p_g = −DX(N1)`,
`depl_t_p_d = −DX(N5)`, `fleche_fait = −DY(N3)`. La valeur signée rendue est
alors identique à celle du legacy.

### Règle 2 — efforts d'about vs diagrammes internes

Cette règle **ne concerne que le chemin « natif »** (résolution PyNite
complète + lecture de `member.moment(x)` / `shear(x)`), utilisé dans les
scripts de validation `validation/pynite_check/` — **pas** le backend de
production, qui reconstruit les efforts d'about directement (§5.8).

Les `efforts_noeuds` du legacy sont des **efforts d'about** (« ce que la
barre exerce sur le nœud ») ; les fonctions `axial/shear/moment(x)` de PyNite
donnent les **diagrammes d'efforts internes** \(N(x), V(x), M(x)\). Le lien
statique, valable pour **tout** chargement :

| Effort d'about legacy | Diagramme interne PyNite |
|---|---|
| \([N_i, V_i, M_i]\) au nœud origine \(i\) | \([-N(0),\; -V(0),\; -M(0)]\) |
| \([N_j, V_j, M_j]\) au nœud fin \(j\) | \([+N(L),\; +V(L),\; +M(L)]\) |

Le « − » du côté \(i\) n'est **pas** lié au sens de la charge : c'est
simplement « effort interne à la coupure \(i\) = − (effort que la barre
exerce sur le nœud \(i\)) ». Côté \(j\), la normale sortante de la coupure
pointe déjà selon \(+x\) local → pas de changement de signe.

### Pourquoi le choix de section reste insensible à ces signes

Chaque clé `tx_*` cible **un seul** about de barre : la correspondance
applique donc un \(\pm1\) **fixe pour cette clé**, le même pour tous les cas
élémentaires. Or `optimise_IPE` combine ensuite les cas
(\(\sum_\text{cas} \text{combi}\cdot\text{tx}\)) puis prend une **valeur
absolue**, et teste les déplacements également en valeur absolue. Un facteur
\(\pm1\) constant par clé passe à travers ces opérations sans rien changer.
Les règles de signe ne servent donc qu'à la **comparaison cas par cas** de la
validation (sous-étape 1.e), pas au résultat final.

---

## 7. Le bug `Sij` du legacy — corrigé des deux côtés

> Détail complet et chiffres : `docs/historique/bascule-pynite-etape1.md`
> (encart « Bug latent du legacy — `Sij` figé sur le cas CP »).

**Mécanisme.** `crea_matrice_force()` a un **effet de bord** : elle réécrit
`barre.Sij` (les efforts d'encastrement, §5.5) sur **toutes** les barres.
Ensuite, `calculer_et_verifier_resultats()` reconstruit les efforts d'about
avec `efforts_noeuds = −barre.Sij + k_barre·(R·d)` (§5.8). Or, dans la boucle
d'origine de `optimise_IPE`, `crea_matrice_force()` n'était rappelée **que
pour le cas permanent CP**. Résultat : pour les cas de neige et de vent d'une
même résolution, le post-traitement lisait encore le `Sij` du **CP** — un
mélange incohérent (déplacements du bon cas, efforts d'encastrement du
mauvais). Cas le plus net : le cas de neige accidentelle en zone sans neige
(`Sij` correct = 0) recevait quand même le `Sij` non nul du CP.

**Ce qui n'était pas touché.** Le *solve* (les déplacements) restait juste —
donc l'ELS (flèche, dérive) était correct. Seuls les efforts internes, donc
les 13 `tx_*`, donc l'ELU, étaient faussés.

**Ampleur.** `taux_max` décalé de **moins de 1,2 point** sur les 3 jeux de
validation + ~50 cas aléatoires. **Aucune section retenue changée.** (Un
`taux_trav` *affiché* peut basculer par l'arrondi — cas-03 : 60 → 50.)

**Correction (branche `fix/legacy-sij`).** `_SolveurLegacy.resoudre()`
rappelle désormais `crea_matrice_force()` **pour chaque cas**, juste avant
`calcport()`. Le backend PyNite, lui, n'a **jamais** reproduit le bug :
chaque cas reconstruit ses efforts avec **son propre** `fer`
(`self._fer_ext[nom]`), pas celui du CP. Un ancien mode « parité stricte »
(qui forçait `fer_CP` partout côté PyNite pour coller au legacy bogué) a été
retiré une fois le legacy corrigé. **Les deux backends sont donc alignés sur
le comportement correct.**

**Ce que le bug `Sij` n'explique pas.** L'écart avec la référence externe
CTICM (§9, point 3) est d'un autre ordre de grandeur et a d'autres causes.

---

## 8. Écarts connus, non imputables à la bascule

1. **Le défaut de signe global du legacy est toujours là** (règle 1, §6).
   Il n'est **pas** corrigé, volontairement : il est cohérent d'un bout à
   l'autre du legacy et neutralisé par les valeurs absolues de
   `optimise_IPE`. Le backend PyNite calcule le déplacement physique puis
   applique un « − » cosmétique pour rendre **la même valeur signée** que le
   legacy. Conséquence pratique : toute lecture future d'un `depl_*` **sans
   valeur absolue** héritera de ce signe « à la mode legacy » (opposé du
   déplacement physique réel), quel que soit le backend.

2. **`_SolveurLegacy` (corrigé) ≠ legacy d'origine.** À cause de la
   correction du bug `Sij` (§7), les taux bruts diffèrent de la toute
   première version du moteur de **moins de 1,2 point** (aucune section
   changée, mais un `taux_trav` affiché peut franchir un arrondi). Si l'on
   compare un ancien calcul de production aux résultats actuels, cet
   écart-là vient de la **correction `Sij`**, pas de PyNite.

3. **Écart avec la référence externe CTICM.** Il **croît avec le taux de
   travail ELU** (jusqu'à ≈ +10 points sur le cas-02 « bas et large », où les
   arbalétriers retenus par CTICM sont deux crans plus légers que ceux
   d'Instanote). Il n'est expliqué **ni** par le bug `Sij` (0,1–1,2 pt) **ni**
   par la bascule (parité legacy ↔ PyNite à 0,000 %). Causes pressenties, à
   traiter dans les étapes suivantes de la roadmap : renfort d'épaule à
   \(1{,}66\times h\) **constant** au lieu d'un gousset réel dégressif
   (**étape 3**), traitement des zones de vent de rive F/G/J (**étape 4**),
   et le fait — assumé — que le moteur ne vérifie ni le flambement ni le
   déversement. Voir `validation/COMPARAISON_CTICM.md`.

**À ce jour**, d'après le journal de la bascule : parité legacy ↔ PyNite à
**0,000 %** sur les 3 jeux de validation + 12 cas aléatoires (déplacements,
13 taux, sections retenues, flèche, ratios, masse). Ces chiffres proviennent
du journal (`docs/historique/bascule-pynite-etape1.md`), non d'une
ré-exécution faite pour rédiger ce document.

---

## 9. Vérifier la parité soi-même

Scripts figés, un par sous-étape, dans `validation/pynite_check/`
(`check_1a_*` … `check_1g_*`, `check_deps_runtime.py`) — voir le `README.md`
du dossier. Chacun sort `0` (parité OK) ou `1` (écart).

```bash
# backend maison (défaut)
python validation/pynite_check/check_1f_optimise.py

# backend PyNite
MOTEUR_CALCUL=pynite python validation/pynite_check/check_1g_non_regression.py
```

À rejouer systématiquement lors de **toute montée de version de PyNite**
(épinglé à `==3.0.0`) ou de tout remaniement du moteur — check-list dans
`docs/moteur-de-calcul.md`.

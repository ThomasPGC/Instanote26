# Moteur de calcul — décisions durables & roadmap

> Extrait de `CLAUDE.md`. Positionnement produit, décisions figées, aiguillage
> `MOTEUR_CALCUL`, roadmap étapes 2→8, check-list montée de version PyNite.
> Journal détaillé de l'étape 1 (déjà faite) : `docs/historique/bascule-pynite-etape1.md`.

## Roadmap moteur de calcul (session post-infrastructure)

Contexte : l'infrastructure SaaS (auth, PDF, profil, migrations Alembic) est
en place. Prochaine phase : fiabiliser et enrichir le cœur de calcul avant
d'ouvrir Stripe. Objectif : rigueur et validation à chaque étape, ne pas
enchaîner sans avoir validé l'étape précédente.

#### Positionnement produit du moteur — choix DURABLE, ne pas « corriger »

Instanote26 fait du **prédimensionnement pour étude de prix**, pas de la
vérification réglementaire complète aux Eurocodes. Sont **volontairement et
durablement hors périmètre** du moteur (ce ne sont **pas des oublis** — ne
pas les « ajouter » dans une session future sans validation explicite du
user) :
- **flambement** (poteaux, arbalétriers) et **déversement** (semelle
  comprimée) : les bracons anti-dévers / anti-flambement réels sont non
  significatifs à l'échelle d'un chiffrage ;
- classification de section EC3 (classes 1/2/3/4), interactions M+N et M+V,
  imperfections, analyse au 2ᵉ ordre / P-Δ.
À rappeler explicitement à l'utilisateur, à trois endroits (cf. « Sur
l'horizon » et « Mentions légales + disclaimer ») : **conditions générales**
(à rédiger), **encart visible dans les résultats de calcul** (écran + PDF),
et **acceptation à l'inscription**.

#### Vocabulaire (à respecter partout : code, commentaires, docs, réponses)

- On dit **renfort d'épaule** — jamais « renfort de genou ». Anglais :
  **haunch**, jamais « knee ». La barre s'appelle historiquement `jarret()` /
  « Jarret » dans le code (`business/calcport.py`) — terme charpente correct,
  conservé tel quel.

#### Décisions figées à la session 1 d'audit (verrouillées pour étapes 1 et 2)

- **Pieds de poteau bi-articulés** — encastrement hors périmètre (cf. « Sur
  l'horizon » §4 : piste offre premium / ponts roulants).
- **Résolution Euler-Bernoulli** (déformation d'effort tranchant négligée
  dans la raideur). PyNite v3 : `add_section` sans aires de cisaillement =
  pas de terme Timoshenko, donc parité directe. **Étape 3 : maintenu.** Un
  diagnostic a posteriori (`jarret_discret.diagnostic_cisaillement`, non
  bloquant) mesure la contribution de l'effort tranchant à la flèche : **< 1 %**
  sur les 3 jeux de validation → Timoshenko dans la raideur non justifié.
- **Renfort d'épaule** — **étape 3 faite** : côté backend **PyNite** le renfort
  est discrétisé en `N_DISC_JARRET = 6` tronçons à inertie variable, âme
  dégressive **linéaire de `2·h` (épaule) à `1·h` (sortie)** (le `1,66` était une
  moyenne), section reconstituée en **I à 3 semelles + congés `r`**
  (`jarret_discret.caracs_section_jarret`, recoupée PropSection à < 0,5 % sur
  Iy). Longueur inchangée (10 % de la portée). Les nœuds du jarret sont
  **excentrés sur l'axe neutre** (ligne des centres de gravité des sections des
  tronçons) : le sommet de poteau descend, le poteau modélisé est raccourci, le
  jarret n'est plus colinéaire à la traverse (`JARRET_EXCENTRE`, défaut activé).
  Le **solveur legacy** garde la barre prismatique `1,66·h` (`jarret()`) et
  devient l'**oracle de l'ancien modèle** : parité legacy ↔ pynite vérifiée
  seulement en `N_DISC_JARRET=1`. Détail :
  `docs/historique/jarret-discretise-etape3.md`.
- **S235 seul** (`fy = 235` en dur ; noter que le paramètre `lim_fy` de
  `calcport()` est mort — non propagé à `calculer_et_verifier_resultats`, à
  traiter à l'étape 8 avec S275/S355).
- **Combinaisons `COMBI_DEPL` / `COMBI_EFF` inchangées** (facteurs actuels).
  Si une erreur/oubli EC0 manifeste est repéré pendant l'implémentation :
  **le signaler au user avant** toute correction.

### État d'avancement (résumé)

- **Étape 1 — bascule PyNite : faite et validée** (sous-étapes 1.a→1.g, découpage
  code A→H, bug `Sij` du legacy corrigé des deux côtés). Détail complet :
  `docs/historique/bascule-pynite-etape1.md`.
- **Étape 2 — validation croisée CTICM : validée** (par le user).
  `validation/COMPARAISON_CTICM.md`.
- **Étape 3 — jarret discrétisé : faite** (branche `feat/jarret-discretise-etape3`).
  Section 3 semelles + `r` recoupée PropSection ; topologie paramétrée par
  `N_DISC_JARRET` ; **nœuds du jarret excentrés sur l'axe neutre** (poteau
  raccourci) ; solveur legacy figé = oracle de l'ancien modèle ; diagnostic
  cisaillement a posteriori non bloquant. Résultat sur les 3 jeux :
  **cas-02 « bas et large » IPE 600/600 → IPE 600/550** (−388 kg, 1 cran de
  l'IPE 500 de CTICM ; le résiduel est porté par le moment de poteau → étape 4) ;
  cas-01/03 sections inchangées, marge de dérive regagnée. Détail :
  `docs/historique/jarret-discretise-etape3.md`. **`MOTEUR_CALCUL` défaut basculé
  sur `pynite`** (validation locale du user faite).
- **Étape 4 — audit des charges (vent) : prochaine.**

Variables d'env :
- **`MOTEUR_CALCUL`** : `pynite` (**défaut depuis l'étape 3**) →
  `business/solveur_pynite.py`, renfort d'épaule **discrétisé + excentré** ;
  `legacy` → solveur maison, renfort d'épaule `1,66·h` prismatique (oracle de
  l'ancien modèle). Alias `pynite_corrige`. **Résultats identiques seulement en
  `N_DISC_JARRET=1`.**
- **`N_DISC_JARRET`** : nombre de tronçons par renfort d'épaule (défaut **6**).
  `1` = ancien modèle (barre unique `jarret()`), utilisé par les harnais de
  parité (`check_1g`, `check_3c`).
- **`JARRET_EXCENTRE`** : `0` = jarret colinéaire à la traverse ; sinon (défaut)
  excentré sur l'axe neutre (seulement si `N_DISC_JARRET>1`).

## Montée de version PyNite (piqué à `==3.0.0`)

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

## Roadmap — étapes 2 à 8

### Étape 2 — Validation croisée (JALON BLOQUANT)
- Choisir 2 ou 3 modèles de portique représentatifs (dont un cas limite)
- Calculer chaque modèle avec : l'ancien algo, PyNite, et un logiciel externe
  de référence (CTICM)
- Définir AVANT de comparer les seuils d'écart acceptables (%) sur : flèche,
  moment fléchissant, effort normal, section retenue
- Ne pas passer à l'étape 3 tant que cette validation n'est pas actée

### Étape 3 — Jarrets en suite de petites barres — ✅ FAITE

`docs/historique/jarret-discretise-etape3.md`. Résumé :
- Renfort d'épaule discrétisé en `N_DISC_JARRET = 6` tronçons (backend PyNite
  seulement — legacy figé = oracle de l'ancien modèle) ; module
  `business/jarret_discret.py`.
- Loi d'âme **linéaire `2·h → 1·h`** ; section reconstituée **I à 3 semelles
  + congés `r`** par intégration du contour, recoupée PropSection v1.0.4
  (`validation/jarrets/`) à < 0,15 % sur A, < 0,5 % sur Iy.
- **« Arrondi omis »** du legacy = les congés `r` → réintégrés.
- **Nœuds du jarret excentrés sur l'axe neutre** (ligne des centres de gravité
  des sections des tronçons) — `JARRET_EXCENTRE`, défaut activé. Poteau modélisé
  raccourci ; géométrie dépendante de la traverse → modèle reconstruit par
  `arba` (caché).
- Diagnostic a posteriori d'**effort tranchant** non bloquant
  (`diagnostic_cisaillement`) : < 1 % sur la flèche → Euler-Bernoulli confirmé.
- **Dense conservé** (LU 47×47 : dense ~1,8× plus rapide que `splu`).
- Résultat : **cas-02 « bas et large » IPE 600/600 → IPE 600/550** grâce à
  l'excentrement (−388 kg) ; cas-01/03 sections inchangées, marge de dérive
  regagnée. Écart CTICM cas-02 réduit à 1 cran ; le résiduel (`tx_mom_pot`
  100,3 % à IPE 600/500) est porté par le **moment de poteau** → étape 4
  (vent de rive) / étape 7 (longueur de jarret).
- **`MOTEUR_CALCUL` défaut = `pynite`** (basculé après validation locale du user).

### Étape 4 — Audit des charges, en particulier celles de vent
- Revue exhaustive des configurations de vent (zones, catégories de terrain,
  coefficients de forme selon géométrie, faces au vent/sous le vent)
- Cas de test dédiés par configuration
- **Affiner la répartition des charges N/V** (aujourd'hui : pression `qpz`
  constante par barre + « surplus » des zones de rive F/G/J et de l'accumulation
  neige d'acrotère injectés en **charges ponctuelles aux nœuds** N1/N2/N3/…
  via `repart_charge_surpl` / `ch_noeud_accu_*` — cf. `chargement_nv.py`).
  Piste : utiliser les charges **réparties trapézoïdales / partielles**
  natives de PyNite (`add_member_dist_load` avec `x1`/`x2` et `w1 ≠ w2`) pour
  représenter directement le champ de pression variable le long de la barre,
  au lieu de l'approximation « uniforme + corrections nodales ».
- Simplifications actuelles à statuer : `μ2` neige (0,8 constant ≤ 30°),
  pas de neige asymétrique / demi-charge / glissante ; paire nodale neige
  `40·entraxe` d'origine non documentée dans le code ; zones vent F/G/H/I/J
  réduites à ~4 valeurs par barre.

### Étape 5 — Modèle d'appentis
- Reprendre l'ancien modèle back-office si dispo (portique à un seul arbalétrier)
  et le remettre au propre avec le nouveau moteur PyNite, sinon le créer

### Étape 6 — Portique bipente asymétrique
- Support de 2 poteaux distincts + 2 arbalétriers distincts
- Revoir l'algorithme d'optimisation : l'espace de recherche passe de
  2 variables discrètes (1 poteau, 1 arba) à un espace plus large
  (2 poteaux, 2 arbas, + longueurs de jarret cf étape suivante)

### Étape 7 — Optimisation de la longueur des jarrets
- Rendre la longueur de jarret variable en interne (non exposée utilisateur)
- Adapter l'optimisateur pour jouer sur ce paramètre en plus du choix IPE
  (ex : rallonger de quelques cm peut faire redescendre d'une section)

### Étape 8 — Option nuance d'acier en fin de calcul + renommage des forfaits

Contexte : les tests de validation croisée (étape 2) montrent que l'écart
entre le moteur interne et les logiciels de référence croît avec le taux
de travail ELU du portique (zone de marge faible). Pour les cas proches
de la limite de résistance, proposer une nuance d'acier supérieure
(S275/S355) permet de gagner une ou plusieurs sections IPE sans toucher
à l'ELS (le module d'élasticité E est identique entre nuances : seule fy
change, donc seules les vérifications de résistance sont affectées, pas
les déplacements).

Fonctionnalité :
- En fin de calcul, si le dimensionnement est piloté par une vérification
  de résistance (pas de déplacement), proposer à l'utilisateur les
  sections obtenues en S275 et S355 en plus du S235 par défaut
- Recalculer la classification de section (classe 1/2/3/4) pour chaque
  nuance, ne pas se contenter d'appliquer un facteur sur le taux de travail
- L'utilisateur choisit la nuance qui lui convient

Prérequis (à traiter AVANT d'implémenter cette fonctionnalité) :
Les forfaits d'abonnement actuels s'appellent S235/S275/S355 (grades
EN 10025). Une option de nuance d'acier sur le calcul dans le même
vocabulaire créerait une confusion forte entre "palier d'abonnement" et
"matériau de la structure". Renommer les forfaits AVANT d'introduire
cette fonctionnalité (impact : base de données - champ plan par défaut
"S235", UI, et éventuellement Stripe si déjà intégré à ce moment-là).

Cette étape se place après la validation croisée et l'audit des charges
de vent — c'est un ajout produit à part entière, pas une correction de
justesse.

Règle de méthode : chaque étape = une session dédiée, validée et
commitée avant de passer à la suivante. Pas de mélange d'étapes dans une
même session.

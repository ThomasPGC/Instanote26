# validation/pynite_check — parité legacy ↔ PyNite (roadmap moteur, étape 1)

Scripts de vérification de la bascule du solveur structurel de
`business/calcport.py` vers **PyNiteFEA** (branche `refactor/pynite`,
option A « PyNite assembleur » — voir `CLAUDE.md`, section
« Roadmap moteur de calcul »).

Chaque script est **autonome et figé** : il est la trace de ce qui a
réellement été comparé à une sous-étape donnée. On ne factorise pas de
code commun entre eux, pour qu'un `git log` de ce dossier dise exactement
ce qui a été testé, quand.

## Scripts

| Fichier | Sous-étape | Ce qui est vérifié |
|---|---|---|
| `check_1a_sans_jarret.py` | 1.a | 1 portique, cas CP seul, section constante, **sans renfort d'épaule** : les 21 DDL legacy vs PyNite. |
| `check_1b_renfort_epaule.py` | 1.b | Renfort d'épaule réintroduit à l'identique (`jarret()` 1,66·h) : 21 DDL + efforts d'about des 6 barres, sur cas CP **et** un cas perpendiculaire synthétique (pré-test de la convention vent). Applique et vérifie la **règle de signe**. |
| `check_1b_profilage.py` | 1.b | Profilage : `charge_et_sections()` legacy vs backend « PyNite natif » (`analyze()` + 1 combo/cas) vs backend « PyNite assembleur » (`Ke` + factorisation scipy + RHS en cache). Sur les 3 jeux de `validation/`. |
| `check_1c_cl_et_vent.py` | 1.c | Backend assembleur : masque de DDL libres (CL bi-articulées + blocage hors-plan) = réduction legacy ; déplacements **et** réactions d'appui identiques sur les 8 cas élémentaires de cas-03 (dont les cas de vent). |

## Rejouer

Depuis la racine du dépôt, venv actif (`PyNiteFEA` installé) :

```
python validation/pynite_check/check_1a_sans_jarret.py
python validation/pynite_check/check_1b_renfort_epaule.py
python validation/pynite_check/check_1b_profilage.py
python validation/pynite_check/check_1c_cl_et_vent.py
```

Chaque script de parité (`check_1a`, `check_1b_renfort_epaule`,
`check_1c`) affiche un verdict et sort avec le code `0` (OK) ou `1`
(écart au-delà de la tolérance). `check_1b_profilage.py` n'a pas de
verdict — il imprime des temps (machine-dépendants).

## Quand les rejouer

- **Montée de version de PyNite** (rappel : `PyNiteFEA` est piqué à
  `==3.0.0` — toute montée est un projet à part) : rejouer les 3 scripts
  de parité, exiger le code de sortie `0`, comparer les temps de
  `check_1b_profilage.py` à ceux consignés dans `CLAUDE.md`.
- Refactor du moteur (`business/calcport.py`) : idem.

Convention de signe legacy ↔ PyNite : voir `CLAUDE.md`, section
« Règle de signe legacy ↔ PyNite ».

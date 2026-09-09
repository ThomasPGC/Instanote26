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
| `check_1d_familles_charges.py` | 1.d | Efforts d'about des 6 barres identiques legacy vs PyNite sur les 22 cas élémentaires des 3 jeux — familles CP / NEI / VEN + charges nodales. |
| `check_1e_taux.py` | 1.e | Les 13 `tx_*` recalculés depuis les efforts PyNite (formule legacy exacte), comparés **au signe près** cas par cas ; détail des moments critiques du renfort d'épaule + gouvernant post-`COMBI_EFF`. |
| `check_1f_optimise.py` | 1.f | Boucle `optimise_IPE` complète (monkeypatch d'un `resoudre_cas` PyNite) : sections retenues identiques sur 3 jeux + 12 cas aléatoires reproductibles. |
| `check_1g_non_regression.py` | G | `charge_et_sections()` dict identique `MOTEUR_CALCUL=legacy` vs `pynite_corrige` (2 sous-processus), 32 cas dont `PasDeSolutionIPE` et zonage introuvable. **Depuis fix/legacy-sij : cible = legacy corrigé vs pynite_corrige** (avant : legacy bugué vs pynite parité stricte). |
| `compare_3modes_ctcim.py` | étape 2 CTICM | Rejoue cas-01/02/03 dans les 3 modes (`legacy`, `pynite` parité stricte, `pynite_corrige`) : poteau/traverse, `taux_trav`, `taux_max` brut, flèche, masse. Sert à isoler la contribution du bug Sij avant la comparaison CTICM. Pas de verdict. |

## Rejouer

Depuis la racine du dépôt, venv actif (`PyNiteFEA` installé) :

```
for s in 1a_sans_jarret 1b_renfort_epaule 1b_profilage 1c_cl_et_vent \
         1d_familles_charges 1e_taux 1f_optimise 1g_non_regression; do
    python validation/pynite_check/check_$s.py
done
```

`check_1a`..`check_1f` acceptent aussi `MOTEUR_CALCUL=pynite` (ils
appellent `charge_et_sections` en interne). `check_1g` pilote les deux
backends lui-même.

Tous les scripts sauf `check_1b_profilage.py` affichent un verdict et
sortent avec le code `0` (OK) ou `1` (écart au-delà de la tolérance).
`check_1b_profilage.py` n'a pas de verdict — il imprime des temps
(machine-dépendants).

## Quand les rejouer

- **Montée de version de PyNite** (rappel : `PyNiteFEA` est piqué à
  `==3.0.0` — toute montée est un projet à part) : rejouer tous les
  scripts de parité, exiger le code de sortie `0`, comparer les temps de
  `check_1b_profilage.py` à ceux consignés dans `CLAUDE.md`.
- Refactor du moteur (`business/calcport.py`, `business/solveur_pynite.py`) :
  idem.

Convention de signe legacy ↔ PyNite : voir `CLAUDE.md`, section
« Règle de signe legacy ↔ PyNite ».

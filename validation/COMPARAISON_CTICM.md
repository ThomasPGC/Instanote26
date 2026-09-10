# Comparaison Instanote26 ↔ CTICM (PORTAL+) — 3 jeux de validation

Roadmap moteur de calcul, **étape 2** (jalon bloquant). Objectif immédiat :
mesurer la contribution du **bug `Sij`** (cf. `CLAUDE.md`, encart) dans l'écart
avec CTICM, avant de décider de le corriger en prod.

Sources CTICM : `validation/cas-*/synthese*.pdf` (PORTAL+ vv 11.3399,
« VII — Synthèse des vérifications du portique »). Les taux CTICM sont des
**taux d'utilisation** (0–1). Entrées Instanote : cf. `CLAUDE.md`, « Jeux de
validation (étape 2) ».

**Sections IPE retenues par CTICM** (confirmées par le user, pas dans les
synthèses PORTAL+) :

| cas | poteaux | arbalétriers | vs Instanote |
|---|---|---|---|
| cas-01-compact | IPE 160 | IPE 140 | **identiques** |
| cas-03-haut-fin | IPE 600 | IPE 500 | **identiques** |
| cas-02-bas-large | IPE 600 | **IPE 500** | poteaux identiques ; **arbalétriers 2 crans sous Instanote** (IPE 500 vs IPE 600) |

→ Sur cas-02, CTICM dimensionne l'arbalétrier à IPE 500 là où Instanote exige
IPE 600.

**MISE À JOUR — étape 3 faite (jarret discrétisé) :** la discrétisation du
renfort d'épaule (6 tronçons, âme dégressive `2h→1h`, section 3 semelles + `r`
recoupée PropSection) **ne résorbe pas** cet écart. Sur les 3 jeux, **aucune
section retenue ne change** ; `taux_max` bouge de −0,07 / −0,66 / −0,07 point.
Le point gouvernant de cas-02 est le **moment de poteau** (`tx_mom_pot ≈ 98 %`,
cf. §2), pas le jarret : à sections forcées, IPE 600/500 donne
`tx_mom_pot = 103 %` (rejeté), IPE 600/600 = 98,2 % (retenu) — un arbalétrier
plus raide **soulage le poteau**. L'écart de ~10 pts sur le moment de poteau
n'est donc **pas** porté par le renfort d'épaule → pistes : zones de vent de
rive F/G/J (**étape 4**), modélisation du jeu poteau/traverse (**étape 7**,
longueur de jarret). Détail : `docs/historique/jarret-discretise-etape3.md`.

## 1. Les 3 modes Instanote

`compare_3modes_ctcim.py` — `taux_max` **brut** (avant `round(., 1)` qui donne
le `taux_trav` affiché) :

| cas | legacy (bug `Sij`) | pynite parité stricte | **corrigé** (legacy fix + pynite_corrige) | **jarret discrétisé** (étape 3, `N_DISC_JARRET=6`) |
|---|---|---|---|---|
| cas-01-compact  | 37,98 % | 37,98 % | **37,84 %** | 37,77 % |
| cas-02-bas-large | 99,33 % | 99,33 % | **98,84 %** | 98,18 % |
| cas-03-haut-fin | 56,07 % | 56,07 % | **54,92 %** | 54,85 % |

Colonne « jarret discrétisé » : rejeu `compare_3modes_ctcim.py` après l'étape 3.
Sections retenues **inchangées** (IPE 160/140 · 600/600 · 600/500), flèche/dérive
+1 à +2 %.

Sections retenues **identiques dans les 3 modes** : IPE 160/140 · IPE 600/600 ·
IPE 600/500. `fleche` et `derive` identiques dans les 3 modes (l'ELS n'est pas
touché par le bug `Sij`). Seul `taux_trav` **affiché** de cas-03 change
(60 → 50 %, l'écart de 1,15 pt franchit la frontière d'arrondi 0,55).

**→ Le bug `Sij` déplace `taux_max` de −0,14 / −0,49 / −1,15 point.**

## 2. Comparaison au CTICM — résistance de **section** (Tableau 22, comparable)

PORTAL+ Tableau 22 = résistance de section **sans instabilité** (N, V, M, MN,
MV, MNV) — c'est le périmètre d'Instanote26. Tableau 23 (by, bz, LT, bMN…)
inclut **flambement + déversement**, hors périmètre Instanote (choix assumé) →
non comparable, donné pour contexte au § 4.

| cas | Instanote **corrigé** (max `tx_*` section, post-`COMBI_EFF`) | CTICM Tab. 22 (max section) | **écart** (Insta − CTICM) | élément gouvernant |
|---|---|---|---|---|
| cas-01-compact  | **37,84 %** (`tx_mom_pot_d`) | **39,1 %** (Poteau 2, MNV) | **−1,3 pt** | poteau — **accord** |
| cas-03-haut-fin | **54,92 %** (`tx_mom_pied_arba_d`) | **50,7 %** (Arbalétrier 2) | **+4,2 pt** | arbalétrier (sortie de jarret) — **accord** |
| cas-02-bas-large | **98,84 %** (`tx_mom_pot_g/d`) | **88,7 %** (Poteau 2, M) | **+10,1 pt** | poteau — **accord** |

### Ce que ça dit

1. **L'élément gouvernant est le même** entre Instanote et CTICM sur les 3 cas :
   poteau pour cas-01 et cas-02, arbalétrier (bout de jarret) pour cas-03. Le
   pattern « concentré sur l'arbalétrier » **n'est pas universel** — il dépend
   de la géométrie (cas-03 = poteau haut, vent dominant → arbalétrier ;
   cas-01/02 compacts ou bas-larges → poteau).
2. **L'écart croît avec le taux ELU** : −1,3 pt à ~38 %, +4,2 pt à ~52 %,
   +10,1 pt à ~89–99 %. Instanote devient **plus conservatif** que CTICM à
   mesure que la charge monte (et très légèrement moins conservatif à faible
   charge).
3. **Le bug `Sij` n'explique pas cet écart** : il ne pèse que 0,1–1,2 point,
   alors que l'écart CTICM va jusqu'à ~10 points sur cas-02.

### Détail Instanote — taux `tx_*` gouvernants (mode corrigé)

- **cas-01** : `tx_mom_pot_d` 37,84 % · `tx_mom_pied_arba_d` 36,18 % ·
  `tx_mom_renf_d` 27,62 %
- **cas-02** : `tx_mom_pot_g/d` 98,84 % · `tx_mom_fait` 53,50 % ·
  `tx_mom_renf_g/d` 50,77 % · `tx_mom_pied_arba_g/d` 39,87 %
- **cas-03** : `tx_mom_pied_arba_d` 54,92 % · `tx_mom_pied_arba_g` 47,90 % ·
  `tx_mom_pot_d` 43,12 %

## 3. Comparaison au CTICM — ELS (déplacements)

| cas | dérive tête poteau — Instanote | — CTICM | flèche faîtage — Instanote | — CTICM |
|---|---|---|---|---|
| cas-01-compact  | 21,8 mm (H/160) | 23,2 mm (H/151) | 2,8 mm (L/1404) | ≈ 0 mm |
| cas-02-bas-large | 4,7 mm (H/1057) | 7,9 mm (H/635) | 57,4 mm (L/383) | 59,3 mm (L1/354) |
| cas-03-haut-fin | 61,9 mm (H/161) | 59,3 mm (H/169) | 2,0 mm (L/4044) | 1,1 / 3,5 mm |

- Dérive : accord ~5–6 % sur cas-01 et cas-03 (les deux cas où la dérive
  **gouverne**, proche de H/150). Sur cas-02 la dérive Instanote est ~40 %
  plus faible que CTICM (4,7 vs 7,9 mm) — mais elle est très loin de la limite
  (H/1057) donc sans effet sur le dimensionnement.
- Flèche faîtage : accord ~3 % sur cas-02 (le seul cas où elle est
  significative). Négligeable ailleurs.

## 4. Contexte — résistance des **éléments** CTICM (Tableau 23, hors périmètre)

Pour mémoire, avec flambement + déversement (ce qu'Instanote ne fait **pas**,
choix assumé) :

| cas | CTICM max Tab. 23 | localisation |
|---|---|---|
| cas-01 | 0,434 | Poteau 2, `bMN2` (interaction M-N + flambement) |
| cas-02 | 0,946 | Poteau 2, `bMN1` |
| cas-03 | 0,585 | Poteau 2, `bMN1` |

L'instabilité fait passer le taux gouvernant CTICM au-dessus du taux de
section (ex. cas-02 : 0,887 → 0,946). Instanote ne verra jamais cette marche.

## 5. Conclusion

- **Le bug `Sij` est un défaut réel mais mineur** : −0,14 à −1,15 point sur
  `taux_max`, **aucune section retenue changée** sur ces 3 cas + ~50 aléatoires.
  → **Corrigé** (branche `fix/legacy-sij`, dans le legacy comme dans PyNite),
  coût perf +12–21 %. Sain de le prendre (ELU physiquement cohérent), même si
  l'impact sur le résultat livré est quasi nul.
- **Il n'explique PAS l'écart avec CTICM** (jusqu'à ~10 points sur cas-02).
  L'écart **croît avec le taux ELU** (confirmé sur les 3 cas) et pointe vers
  la modélisation du **jarret `1,66·h` constant** : sur cas-02, CTICM
  dimensionne l'arbalétrier 2 crans plus bas (IPE 500 vs IPE 600). C'est
  l'objet de l'**étape 3** de la roadmap moteur (jarret discrétisé). Autres
  pistes secondaires : calcul du moment (charges N/V, appuis, offsets
  d'assemblage) — étape 4.
- **Déploiement** : après validation locale manuelle du user, `MOTEUR_CALCUL=
  pynite` sur Railway.

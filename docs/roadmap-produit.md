# Roadmap produit — décisions à trancher

> Extrait de `CLAUDE.md`. Pas de code pour l'instant : décisions produit en attente.

## Sur l'horizon (décisions produit à trancher — pas de code pour l'instant)

### 1. Statut « email non vérifié » et accès aux calculs
- **État actuel (à re-confirmer en code au moment de la session concernée)** :
  les routes `/calcul` et l'export PDF n'ont **aucune protection d'accès** — ni
  connexion, ni vérification d'email requises.
- **Décision produit** : ce sujet ne doit **pas** être traité isolément mais
  **conjointement avec la stratégie de paliers S235/S275/S355** (point 2) : ce
  sont trois marches d'un même parcours
  `visiteur → inscrit non vérifié → inscrit vérifié → payant`.
- **Piste retenue** : garder une **démo de calcul accessible sans inscription et
  sans friction** (effet « waouh » immédiat), mais **fortement limitée
  fonctionnellement** — ex. charges permanentes (couverture, diverses) forcées à
  zéro ou quasi nulles, résultats non exportables en PDF, etc. (détails à
  définir).
- Le statut **« compte créé mais email non vérifié »** doit trouver sa place
  dans ce parcours : accès identique à la démo ? accès intermédiaire ? — à
  trancher.

### 2. Stratégie de paliers S235 / S275 / S355
- Toujours prévue, dans l'ordre convenu depuis le début du projet :
  **d'abord le marketing** (quelles fonctionnalités / limites par palier),
  **puis l'implémentation technique**.
- Le champ `plan` existe déjà sur `User` (défaut `"S235"`), prêt pour
  l'intégration Stripe future.
- **Session dédiée à prévoir**, qui doit **englober le point 1 ci-dessus**.

### 3. Email administrateur à changer un jour
- Le compte de test utilise une **adresse personnelle « de dépannage »**
  (`tomajeu@gmail.com`), pas destinée à rester en usage en production réelle.
- **Pas de fonctionnalité de changement d'email** aujourd'hui : le champ email
  est en lecture seule sur `/compte` (choix de sécurité, standard fastapi-users).
- **Au vrai lancement commercial**, deux options — à trancher selon le besoin
  réel à ce moment-là, probablement à rattacher à la session « back office
  admin » :
  - supprimer ce compte de test et en recréer un avec la vraie adresse
    professionnelle ; ou
  - développer un **changement d'email** (formulaire + confirmation par email
    envoyée sur la **nouvelle** adresse, pour éviter le vol de compte).

### 4. Pied de poteau encastré — offre premium éventuelle
- Le moteur ne calcule que des portiques à **pieds articulés** (choix figé,
  cf. « Roadmap moteur de calcul »). L'encastrement de pied n'est pas au
  programme : à l'échelle d'une étude de prix, le surcoût de fondation
  (massifs, ancrages) dépasse en général l'économie de métal permise par
  l'encastrement.
- **Piste commerciale future** : proposer le pied encastré comme **option
  d'un palier payant supérieur**, et/ou le rendre nécessaire le jour où on
  voudrait prendre en compte des **ponts roulants** (efforts horizontaux de
  chariot, qui changent la donne sur la dérive et rendent l'encastrement
  souvent incontournable).
- Rien à coder tant que ce n'est pas tranché ; noté ici pour ne pas
  redécouvrir la question à chaque passage sur le moteur.

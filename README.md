# Outil Méry-Heyman — Évaluation de voûte en maçonnerie

Outil de **contrôle d'ingénieur** pour l'évaluation de la capacité portante
d'un **pont voûté en maçonnerie**, fondé sur la **méthode de Méry-Heyman**
et inspiré de la philosophie de **LimitState:RING**.

> ⚠️ Cet outil constitue un contrôle simplifié et **non une validation
> réglementaire**. Il ne remplace pas LimitState:RING, la méthode MEXE, un
> modèle éléments finis ou une évaluation réglementaire. Les résultats
> dépendent fortement de la géométrie réelle, de la qualité de la maçonnerie
> et de l'état observé.

## Contexte théorique

La **théorie de Heyman** (1960) repose sur trois hypothèses :

1. **Résistance à la traction nulle** (`f_t = 0`) — un joint s'ouvre dès
   qu'une traction apparaît (fissuration acceptée).
2. **Résistance en compression infinie** (`f_c = ∞`) — l'écrasement n'est
   quasi jamais dimensionnant dans les ponts anciens.
3. **Absence de glissement** aux joints (`T < N tan φ`).

**Critère de stabilité (Heyman)** : si une **ligne de poussée** admissible
peut être tracée **entièrement dans l'épaisseur** de la voûte, un état
d'équilibre est possible et l'ouvrage est stable (théorème statique).

**Critère de Méry** (plus conservateur) : la ligne de poussée doit rester
dans le **tiers central** (`|e| ≤ t/6`) — aucune traction, pas de
fissuration.

**Mécanisme de rupture** (analyse limite, type RING) : lorsque **4
articulations** se forment (ligne de poussée touchant l'intrados ou
l'extrados en 4 points), la voûte devient un mécanisme → ruine.

**Adequacy Factor (AF)** : `AF = charge_rupture / charge_service`.

## Données du pont étudié (par défaut, modifiables)

| Paramètre | Valeur |
|---|---|
| Portée L | 11 m |
| Flèche f | 5,5 m |
| Largeur participante B | 3,8 m |
| Épaisseur clé (brique + meulière) | 0,50 m |
| Épaisseur rein 45° | 1,20 m |
| Épaisseur naissance | 2,86 m |
| γ brique | 18 kN/m³ |
| γ meulière | 22 kN/m³ |
| γ remblai/chaussée | 21 kN/m³ |
| Charge véhicule (camion 12 t) | 120 kN |
| Discrétisation | 36 secteurs de 5° |

L'épaisseur est **variable** (interpolée entre naissance, rein et clé) et
les **poids propres** (voûte + remblai + chaussée) sont calculés pour
chaque voussoir, conformément à la géométrie réelle (brique + meulière).

## Fichiers livrés

- **`mery_heyman.py`** — script Python autonome : discrétisation, calcul
  de la ligne de poussée (optimisation de la poussée H et du moment
  redondant à la naissance), recherche de la position critique du camion,
  calcul de l'Adequacy Factor par mécanisme à 4 articulations, affichage
  détaillé et export Excel.
- **`generer_excel.py`** — génère `voute_mery_heyman.xlsx` (formules
  vivantes : θ, x, y, t, poids, V cumul, M, N, e, t/6, t/2, états Méry et
  Heyman, synthèse) et le **module VBA** `MeryHeyman.bas`.
- **`voute_mery_heyman.xlsx`** — classeur Excel prêt à l'emploi (3
  feuilles : `Parametres`, `Calcul`, `Resultats`).
- **`MeryHeyman.bas`** — module VBA reproduisant le calcul complet
  (lignes de poussée, optimisation de H, position critique, Adequacy
  Factor), à importer dans Excel.

## Utilisation Python

```bash
pip install openpyxl numpy scipy
python3 mery_heyman.py
```

Sortie : ligne de poussée détaillée par section, position critique du
camion, Adequacy Factor, et génération du classeur Excel.

## Utilisation Excel (formules)

1. Ouvrir `voute_mery_heyman.xlsx`.
2. Ajuster les paramètres dans la feuille **Parametres** (portée, épaisseurs,
   charges, position/multiplicateur du camion).
3. La feuille **Calcul** recalcule automatiquement la ligne de poussée.
4. La feuille **Resultats** donne les valeurs de synthèse issues du calcul
   Python (H, e_max, FS Méry, AF).

> La cellule **H** (poussée horizontale, feuille `Calcul!U1`) est ajustable
> et peut être optimisée avec le **Solver Excel** (minimiser `e_max` en
> faisant varier H) pour reproduire la recherche de ligne de poussée.

## Utilisation Excel (VBA, équivalent RING)

1. Ouvrir un classeur Excel (ou `voute_mery_heyman.xlsx`).
2. `Alt+F11` → éditeur VBA → **Fichier > Importer un fichier** →
   sélectionner `MeryHeyman.bas`.
3. `Alt+F8` → exécuter **`RunMeryHeyman`**.
4. Une feuille `Resultats_VBA` est créée avec H, e_max, FS (Méry),
   articulations, position critique et **Adequacy Factor**.

Le module VBA reproduit le calcul Python : optimisation de H par balayage,
recherche de la position critique du camion (0° à 180°), calcul de l'AF
par dichotomie sur le multiplicateur de charge jusqu'à formation de 4
articulations.

## Interprétation des résultats

**Facteur de sécurité (Méry, tiers central)**

| FS | État |
|---|---|
| < 1 | Instable |
| 1,0–1,2 | Limite |
| 1,2–1,5 | Acceptable |
| 1,5–2 | Bon |
| > 2 | Très bon / robuste |

> Un FS Méry < 1 n'implique pas l'instabilité au sens de Heyman : il
> indique seulement que la ligne de poussée sort du tiers central
> (fissuration possible), tout en restant dans l'épaisseur (stable au sens
> Heyman).

**Adequacy Factor (RING)**

| AF | État |
|---|---|
| < 1 | Ruine |
| 1,0 | Limite |
| 1,5 | Acceptable |
| 2 | Bon |
| > 3 | Très robuste |

## Limites

La méthode Méry-Heyman représente bien : l'équilibre global, le mécanisme
de rupture, le comportement des joints, la stabilité générale. Elle
représente mal : l'écrasement local de la pierre, la dégradation des
mortiers, l'altération des matériaux, les effets tridimensionnels et les
tassements de fondations complexes.

Avant toute conclusion sur la capacité portante de l'ouvrage, il faut
valider la géométrie exacte, l'épaisseur réelle de la voûte, la qualité de
la meulière et des joints, et l'état observé (fissures, déformations,
infiltrations).

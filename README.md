# miumiu

Dépôt d'études d'ouvrages d'art.

## Méry–Heyman : ligne de poussée d'une voûte maçonnée

`mery_heyman.py` calcule la ligne de poussée d'une voûte en berceau (arc
circulaire, plein cintre ou surbaissé) sous poids propre, par la méthode
graphique de Méry et les hypothèses de Heyman :

- résistance à la traction nulle ;
- résistance à la compression infinie ;
- glissement impossible.

Le calcul est mené par tranche de un mètre longitudinal, avec des joints
radiaux (stéréotomie polaire). Le théorème de sécurité de Heyman garantit
que la voûte est stable dès qu'il existe une ligne de poussée entièrement
contenue dans l'épaisseur de la maçonnerie. Le script détermine :

- les bornes de poussée horizontale à la clé `H_min` / `H_max` ;
- les excentricités de clé et les points de contact (articulations
  potentielles) des lignes extrémales ;
- l'épaisseur minimale de stabilité et le facteur de sécurité géométrique ;
- une figure des lignes de poussée (option `--plot`, nécessite matplotlib).

### Utilisation

```bash
python3 mery_heyman.py --span 6 --rise 3 --thickness 0.6            # plein cintre
python3 mery_heyman.py --span 8 --rise 2 --thickness 0.5 --min-thickness
python3 mery_heyman.py --span 6 --rise 3 --thickness 0.6 --plot voute.png
```

Paramètres : `--span` ouverture (m), `--rise` flèche (m), `--thickness`
épaisseur radiale (m), `--gamma` poids volumique (kN/m³, défaut 22),
`--n` nombre de voussoirs par demi-voûte (défaut 200).

### Validation

Le module reproduit la solution de Milankovitch (1907) pour l'arcade
semi-circulaire sous poids propre : épaisseur minimale `t/R = 0.10748`
avec articulation d'intrados à 54.484° de la clé.

```bash
python3 -m unittest test_mery_heyman
```

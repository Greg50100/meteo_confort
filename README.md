# Météo & Confort pour Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![Validate](https://github.com/Greg50100/meteo_confort/actions/workflows/validate.yml/badge.svg)](https://github.com/Greg50100/meteo_confort/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/Greg50100/meteo_confort)](https://github.com/Greg50100/meteo_confort/releases)

Intégration personnalisée qui calcule, à partir de vos capteurs existants, des
grandeurs **météorologiques dérivées** (point de rosée, humidex, refroidissement
éolien, pression au niveau de la mer…) et des indicateurs de **confort
intérieur** (PMV/PPD ISO 7730, risque de moisissure, conseil d'aération…).

> [!WARNING]
> Projet en cours de développement (versions 0.x) : les noms d'entités et les
> options peuvent encore changer d'une version à l'autre.

Tout est calculé localement (`iot_class: calculated`), sans dépendance externe,
et recalculé à chaque changement d'état d'un capteur source.

## Installation

### HACS (dépôt personnalisé)

[![Ouvrir dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Greg50100&repository=meteo_confort&category=integration)

Ou manuellement :
1. HACS → ⋮ → *Dépôts personnalisés* → `https://github.com/Greg50100/meteo_confort`, catégorie **Intégration**.
2. Installez **Météo & Confort**, puis redémarrez Home Assistant.

### Manuelle
Copiez `custom_components/meteo_confort` dans le dossier `config/custom_components/`
de Home Assistant, puis redémarrez.

Version minimale : **Home Assistant 2024.12**.

## Configuration

*Paramètres → Appareils et services → Ajouter une intégration → Météo & Confort*,
puis choisissez le type de profil. Créez autant de profils que nécessaire (une
station extérieure, une entrée par pièce…). Tout reste modifiable ensuite via
**Configurer**.

| Profil | Obligatoire | Facultatif |
|---|---|---|
| **Extérieur** | température, humidité | pression, vitesse du vent |
| **Intérieur** | température, humidité | CO₂, température radiante (globe), température et humidité extérieures |

Les unités des capteurs sources (°F, inHg, mph, m/s…) sont converties
automatiquement. Les entités qui dépendent d'un capteur facultatif ne sont
créées que si ce capteur est renseigné.

### Paramètres

| Paramètre | Défaut | Rôle |
|---|---|---|
| Altitude | altitude de HA | réduction de la pression, pression standard |
| Type de pression | absolue | indiquez « relative » si votre station affiche déjà la pression au niveau de la mer |
| Plage de température | 20–24 °C | niveau et score de confort, aération par rafraîchissement |
| Plage d'humidité | 40–60 % | niveau et score de confort, aération par asséchement |
| Seuil CO₂ | 1000 ppm | aération recommandée |
| met / clo / vitesse d'air | 1,2 / 0,8 / 0,1 m/s | calcul PMV/PPD |
| fRsi | 0,7 | estimation de la température des parois froides |
| Seuil moisissure | 80 % | alerte moisissure (critère ISO 13788) |
| Durée de la moyenne moisissure | 24 h | période sur laquelle l'humidité est moyennée (0 = valeur instantanée) |

## Entités

### Communes aux deux profils
| Entité | Méthode |
|---|---|
| Point de rosée, point de givre | Magnus (Alduchov & Eskridge 1996) |
| Température humide | Stull (2011) |
| Indice de chaleur | NOAA / Rothfusz avec corrections ; égal à la température de l'air sous 26,7 °C, où l'indice n'est pas défini |
| Humidex | Environnement Canada ; égal à la température de l'air sous 20 °C, et jamais inférieur à celle-ci (air sec) |
| Humidité absolue (g/m³), enthalpie (kJ/kg) | thermodynamique de l'air humide |
| Ressenti de l'humidité | classes selon le point de rosée |
| *Désactivées par défaut :* pression de vapeur, rapport de mélange, humidité spécifique, densité de l'air, indice de Thom | |

### Profil extérieur
| Entité | Méthode |
|---|---|
| Température ressentie | refroidissement éolien si froid, indice de chaleur si chaud (style NWS) |
| Refroidissement éolien + risque de gelure | formule JAG/TI 2001, seuils Environnement Canada |
| Température apparente | Steadman / Bureau of Meteorology australien |
| Pression au niveau de la mer *ou* à la station | formule hypsométrique |
| Base des nuages | Espy : 125 m × (T − Td) |
| Force du vent | échelle de Beaufort |
| Risque de chaleur | catégories NOAA |
| Risque de gel, risque de brouillard (binaires) | T ≤ 0 °C ou T ≤ 3 °C avec Td ≤ 0 °C ; écart T − Td ≤ 1,5 °C et vent faible |

### Profil intérieur
| Entité | Méthode |
|---|---|
| Niveau de confort | combinaison des plages de température et d'humidité |
| Score de confort (0–100 %) | pénalités : 12 pts/°C hors plage, 1,5 pt/% HR hors plage, CO₂ au-delà de 800 ppm (max 40 pts) |
| PMV, PPD, sensation thermique | ISO 7730, échelle ASHRAE à 7 niveaux |
| Qualité de l'air (CO₂) | < 600 / 800 / 1000 / 1500 ppm |
| Température et humidité des parois froides | T_paroi = T_ext + fRsi × (T_int − T_ext) |
| Humidité moyenne (moisissure) | moyenne pondérée dans le temps de l'humidité à la paroi (ou de l'air sans capteur extérieur) sur la durée choisie. L'historique est conservé entre deux redémarrages. |
| Risque de moisissure, alerte moisissure | calculés sur cette moyenne, pour qu'une douche ou une cuisson ne déclenche pas l'alerte. L'alerte expose `mean_humidity`, `window_hours` et `coverage_hours` (historique déjà disponible). |
| Condensation sur les parois (binaire) | T_paroi ≤ point de rosée intérieur |
| Aération recommandée (binaire) | CO₂ au-dessus du seuil, **ou** air trop humide et air extérieur plus sec d'au moins 1 g/m³, **ou** trop chaud et extérieur plus frais d'au moins 2 °C. L'attribut `reasons` indique la cause (`co2`, `humidity`, `cooling`). |

### Hystérésis des alertes

Pour éviter qu'une alerte clignote quand une mesure oscille autour de son seuil,
chaque capteur binaire s'active au seuil mais ne se désactive qu'une fois la
valeur revenue au-delà d'une marge :

| Alerte | S'active | Se désactive |
|---|---|---|
| Moisissure | humidité moyenne ≥ seuil | < seuil − 5 points |
| Condensation | T_paroi ≤ point de rosée | T_paroi > point de rosée + 0,5 °C |
| Aération (CO₂) | CO₂ ≥ seuil | < seuil − 100 ppm |
| Aération (humidité) | HR > maximum et air extérieur plus sec d'au moins 1 g/m³ | HR ≤ maximum − 3 points, ou écart < 0,5 g/m³ |
| Aération (rafraîchissement) | T > maximum et extérieur plus frais d'au moins 2 °C | T ≤ maximum − 0,5 °C, ou écart < 1 °C |
| Gel | T ≤ 0 °C, ou T ≤ 3 °C avec Td ≤ 0 °C | mêmes seuils relevés de 1 °C |
| Brouillard | écart T − Td ≤ 1,5 °C et vent < 15 km/h | écart > 2 °C ou vent ≥ 18 km/h |

Le calculateur hors ligne, lui, affiche les valeurs instantanées : il n'a ni
historique ni état précédent.

## Exemple d'automatisation

```yaml
automation:
  - alias: "Prévenir quand il faut aérer le salon"
    triggers:
      - trigger: state
        entity_id: binary_sensor.salon_aeration_recommandee
        to: "on"
        for: "00:10:00"
    actions:
      - action: notify.mobile_app_telephone
        data:
          title: "Salon"
          message: >
            Aérez maintenant ({{ state_attr('binary_sensor.salon_aeration_recommandee', 'reasons') | join(', ') }}).
```

## Calculateur hors ligne

`tools/calculateur.py` est une petite application de bureau qui réutilise le
moteur de calcul et les traductions françaises de l'intégration, sans Home
Assistant ni connexion : vous saisissez les mesures à la main et tous les
résultats se mettent à jour en direct. Elle ne demande que Python 3.10 ou plus
récent, avec tkinter (inclus dans l'installateur Windows de python.org).

```bash
python tools/calculateur.py
```

- Choisissez le profil **Extérieur** ou **Intérieur**, puis remplissez l'onglet
  *Mesures* (température et humidité obligatoires, le reste facultatif).
- L'onglet *Paramètres* reprend les réglages de l'intégration (plages de
  confort, met/clo, fRsi, altitude…).
- Les virgules décimales sont acceptées (`21,5`). **Copier les résultats** met
  le tableau dans le presse-papiers.
- L'onglet **Diagramme psychrométrique** (de −10 à 45 °C, jusqu'à 30 g/kg) trace
  la courbe de saturation, les courbes d'humidité relative, les droites
  d'enthalpie et la zone de confort définie dans les paramètres intérieurs. Il y
  place vos mesures : le point intérieur ou extérieur, le point de rosée et, si
  la température extérieure est renseignée, la paroi froide à la même humidité.
  Si la paroi passe à gauche de la courbe de saturation, il y a condensation. Au
  survol, la souris donne la température, l'humidité relative, le rapport de
  mélange, l'enthalpie et le point de rosée. Le diagramme suit la pression
  mesurée ou l'altitude.

## Développement

Le moteur de calcul (`calculations.py`) ne dépend pas de Home Assistant et est
couvert par des tests unitaires validés sur des valeurs de référence (tables
NOAA et Environnement Canada, exemple de l'annexe D d'ISO 7730…) :

```bash
python -m pytest tests
```

## Licence

[MIT](LICENSE)

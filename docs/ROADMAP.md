# Feuille de route

Où en est le projet après le nettoyage d'architecture et la confrontation aux données NIST,
et ce qu'il reste à faire. Les documents de référence restent en anglais
([ARCHITECTURE](ARCHITECTURE.md), [NIST_MAPPING](NIST_MAPPING.md),
[NIST_FINDINGS](NIST_FINDINGS.md)) ; cette feuille de route est un document de travail.

## Ce qui est fait

**Setup** — `.gitignore` nettoyé, Docker, CI front, et surtout le pin `scikit-learn==1.6.1`
sans lequel le `.joblib` commité ne se charge pas.

**Architecture en couches** (PR #2, #3, #4) — `src/` est passé de neuf modules à plat à trois
couches explicites :

```
physics/   le modèle physique        simulator · thermo_lab · thermodynamic_viz
fdd/       la méthode, partagée      features · ml_models · inference · visualization
studies/   les études                synthetic/ (generator · scenarios · taxonomy)
outputs/<étude>/   models/<étude>/
```

Règle : `studies/` → `fdd/` → `physics/`. Zéro violation aujourd'hui, et cinq tests la
verrouillent (`test_engine_has_no_synthetic_study_api`, etc.).

**42 tests passent.** L'équivalence de comportement a été vérifiée à chaque étape du refactor
en comparant les sorties avant/après octet pour octet.

**Confrontation aux essais NIST** — deux notebooks dans `EDA/`, résultats dans
`docs/NIST_FINDINGS.md`.

## Le reste en suspens

- [ ] `git mv outputs/ml_graphs outputs/synthetic/ml_graphs` — 13 PNG sont restés à l'ancien
      emplacement alors que `scripts/generate_ml_graphs.py:24` écrit désormais sous
      `outputs/synthetic/`. Au prochain run, deux dossiers dont un périmé.

## Ce que les données NIST ont appris

Détail et méthode dans [NIST_FINDINGS](NIST_FINDINGS.md). Trois choses comptent ici.

**1. Le protocole de validation change tout.** Sur 5386 essais réels, six classes, même
modèle :

| Validation | Accuracy |
|---|---|
| CV aléatoire (mélange les machines) | **0,95** |
| Leave-one-machine-out (honnête) | **0,60** |

Un split aléatoire mesure l'installation autant que le défaut. C'est le même problème que
d'entraîner et tester depuis le même simulateur — mais ici il est **mesuré**.

**2. Le design en résidus est validé, et c'est le meilleur argument du projet.** Les résidus
font passer le transfert entre machines de **0,333 à 0,602**, pour 1,7 point perdu en CV
aléatoire. La méthode Li & Braun que nomme `src/fdd/features.py` tient sur des mesures réelles.

Corollaire : **ajouter les grandeurs brutes aux résidus dégrade le transfert** (0,602 → 0,562),
parce que les valeurs absolues laissent le modèle ré-identifier la machine.

**3. Trois erreurs de physique dans `simulator.py`**, trouvées en comparant les signes des
signatures mesurées et simulées (accord 12/16) :

| Défaut | Problème |
|---|---|
| Surcharge | **non modélisée** — seul `refrigerant_charge < 1.0` a une branche, toutes les pentes sont nulles |
| Obstruction condenseur | `subcooling` **inversé** — devrait monter, le simulateur le fait descendre |
| Débit évaporateur | `superheat` et `T_discharge` **inversés** — terme `+ 8.0 * (1.0 - fan_evap_ratio)` |

**4. La limite de température de refoulement n'est jamais appliquée.** `simulator.py` déclare
`self.T_discharge_max = 130.0` et ne s'en sert pas :

| Conditions | `T_discharge` produit |
|---|---|
| −5 °C / 50 °C | **200 °C** |
| −10 °C / 55 °C | **319 °C** |

Ces points sont **dans** les plages d'entraînement (`T_source` descend à −10, `T_sink` monte à
55), donc une partie des 5000 échantillons contient des cycles physiquement impossibles —
319 °C au refoulement d'un R-410A n'existe pas. À corriger avant toute reprise du dataset.

## Les décisions qui t'appartiennent

**A. Comment annoncer la performance.** C'est le point le plus urgent, et le seul qu'un jury
démontera en une question. Le 99,8 % actuel mesure la séparabilité des signatures dans le
modèle physique, pas une détection sur machine réelle. Proposition :

> Signatures de défauts séparables à 99,8 % en validation croisée sur données simulées.
> Méthode par résidus confrontée aux essais NIST : le transfert entre deux machines réelles
> passe de 0,33 à 0,60 grâce aux résidus, contre 0,95 en validation aléatoire — laquelle
> surestime largement.

Moins spectaculaire, et défendable.

**B. Faut-il basculer sur les données réelles ?** Les 5386 essais NIST suffisent à réentraîner.
Mais ça change le sujet : mode **froid**, machine **air/air**, taxonomie NIST. Le cadrage
A7/W40 disparaît, et avec lui la distinction encrassement / ventilateur. Le simulateur ne
serait pas jeté — il deviendrait le **modèle de référence sain**, son vrai rôle dans la méthode
Li & Braun. Décision de fond, pas de refactor.

**C. `FEATURE_COLUMNS` en résidus seuls ?** Il mélange aujourd'hui 19 grandeurs absolues et 5
résidus. La mesure dit que ce mélange nuit au transfert.

**D. Les deux défauts fantômes.** `REFRIGERANT_OVERCHARGE` et `COMPRESSOR_VALVE_LEAK` ont une
`FaultType` et une branche d'injection, mais ne sont jamais générés. Les produire ou les
retirer — NIST couvre les deux, donc les produire est défendable.

## Chantiers suivants

**Nettoyage du cœur** — une PR par idée :

- [ ] Corriger les trois erreurs de `simulator.py` ci-dessus, puis re-mesurer la concordance
- [ ] `compression_ratio` et `pressure_ratio` sont **le même nombre** (vérifié à la précision
      machine). Le modèle a 23 entrées indépendantes, pas 24 — et `test_feature_count` fige 24
- [ ] Unifier `FAULT_PARAM_MAP` / `SCENARIOS`
- [ ] Trancher les deux défauts fantômes (décision D)

**Découper `api/app.py`** — 582 lignes, la couture est nette : 4 routes d'inférence
(`/health` `/predict` `/simulate` `/live`) contre 17 routes `/api/*` qui servent le dashboard.

**Creuser le modèle de référence** — le baseline actuel des notebooks est un simple
plus-proche-voisin sain. Un vrai modèle ajusté sur les essais sans défaut, comme NIST en
construit, devrait faire mieux : **0,602 est un plancher, pas un plafond.**

**Front et ménage** — `web/src/` (routing, moins de widgets), puis Streamlit et les modules de
visualisation en `legacy/`. En dernier : le démo clone-and-run ne doit jamais casser.

## Règles de travail

1. Une PR = une idée, commit par commit.
2. `pytest` vert avant et après chaque PR — 42 aujourd'hui.
3. Rien qui casse le clone-and-run.
4. Le pin `scikit-learn==1.6.1` est **porteur** : le `.joblib` commité ne se charge qu'avec
   cette version. La changer impose de réentraîner via `main_analysis.py`.
5. `dashboard.py` et `scripts/` ne sont couverts par aucun test — les vérifier à la main
   (`python -c "import dashboard"`) après tout déplacement.

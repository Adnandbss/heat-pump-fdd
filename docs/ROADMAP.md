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

**70 tests** passent (dont les gardes d'étanchéité P0). L'équivalence de comportement a été
vérifiée à chaque étape du refactor en comparant les sorties avant/après octet pour octet.

**Confrontation aux essais NIST** — quatre notebooks dans `EDA/` (descriptif, modèle,
référence, calibration), résultats dans `docs/NIST_FINDINGS.md`.

**Quatre défauts de physique corrigés** — surcharge non modélisée, sous-refroidissement inversé
sur l'encrassement condenseur, surchauffe et refoulement inversés sur le ventilateur
d'évaporateur, plafond de refoulement jamais appliqué. L'accord des sens de variation avec les
essais mesurés passe de **12/16 à 20/22**, et l'accuracy simulée de 99,8 % à 99,6 % — baisse
attendue, le modèle n'apprend plus sur des cycles impossibles. **P0** a ensuite fermé quatre
fuites du pipeline : le chiffre simulé honnête est **91,9 % [90,4 – 93,1]** (hold-out,
sélection sur val).

**Dossier de présentation** — `docs/DOSSIER.md` et son PDF : le système module par module,
équations, figures commentées, et les limites connues.

## Ce que les données NIST ont appris

Détail et méthode dans [NIST_FINDINGS](NIST_FINDINGS.md). Trois choses comptent ici.

**1. Le protocole de validation change tout.** Sur 5386 essais réels, six classes, même
modèle :

| Validation | Référence saine | Accuracy |
|---|---|---|
| CV aléatoire (mélange les machines) | machine cible | **0,95** |
| Leave-one-machine-out | machine cible (calibrée) | **0,602** |
| Leave-one-machine-out | machine d'entraînement (transférée) | **0,318** |

⚠️ **Le 0,602 est lui-même conditionnel.** Il suppose une mesure saine aux conditions quasi
identiques à celles du défaut — vrai dans la campagne NIST, répliquée par construction, faux
sur une machine en service. En interdisant les voisins à moins de 0,5 °C, il tombe à **0,482**
(X3). README / dossier / `NIST_FINDINGS` / `results.csv` (`X0b`) le citent encore sans cet
avertissement : PR séparée.

Un split aléatoire mesure l'installation autant que le défaut. C'est le même problème que
d'entraîner et tester depuis le même simulateur — mais ici il est **mesuré**.

**2. Le design en résidus est validé, et c'est le meilleur argument du projet.** Les résidus
font passer la détection de **0,333 à 0,602 lorsque la référence saine est calibrée sur la
machine cible**, pour 1,7 point perdu en CV aléatoire. Sans cette calibration, le transfert
plafonne à **0,318**. La méthode Li & Braun que nomme `src/fdd/features.py` tient sur des
mesures réelles.

Corollaire : **ajouter les grandeurs brutes aux résidus dégrade le transfert** (0,602 → 0,562),
parce que les valeurs absolues laissent le modèle ré-identifier la machine.

**3. Quatre erreurs de physique dans `simulator.py`**, trouvées en comparant les signes des
signatures mesurées et simulées. Corrigées : l'accord passe de **12/16 à 20/22**.

| Défaut | Ce qui clochait | Après correctif |
|---|---|---|
| Surcharge | non modélisée — pentes toutes nulles | `subcooling +`, `W_comp +`, `P_cond +`, `superheat −` |
| Obstruction condenseur | `subcooling` inversé | monte, comme mesuré |
| Débit évaporateur | `superheat` et `T_discharge` inversés | les deux descendent |
| `T_discharge_max = 130` | déclaré, jamais appliqué (319 °C à −10/55) | capé sur tout le domaine d'entraînement |

Deux désaccords restent : `W_comp` sous-charge, `COP` surcharge. La classe
`REFRIGERANT_OVERCHARGE` n'est toujours pas dans le mix des 5000 exemples.

## Les décisions qui t'appartiennent

**A. Comment annoncer la performance.** C'est le point le plus urgent, et le seul qu'un jury
démontera en une question. Le 91,9 % actuel (hold-out 30 %, sélection sur val, intervalle
Wilson 90,4 – 93,1) mesure la séparabilité des signatures dans le modèle physique, pas une
détection sur machine réelle. Le 99,6 % précédent était une fuite d'étiquette. Proposition :

⚠️ **Cette formulation est provisoire** : elle cite 0,602 sans mentionner que ce chiffre suppose
une référence saine aux conditions du défaut. À figer **après X3**, pas avant.

> Signatures de défauts séparables à 91,9 % [90,4 – 93,1] en hold-out sur données simulées
> (sélection sur val, `Pipeline` sklearn). Méthode par résidus confrontée aux essais NIST :
> 0,602 lorsque la référence saine est calibrée sur la machine cible, **0,318** sans cette
> calibration, 0,95 en validation aléatoire — laquelle surestime largement.

Moins spectaculaire, et défendable.

**B. Faut-il basculer sur les données réelles ?** Les 5386 essais NIST suffisent à réentraîner.
Mais ça change le sujet : mode **froid**, machine **air/air**, taxonomie NIST. Le cadrage
A7/W40 disparaît, et avec lui la distinction encrassement / ventilateur. Le simulateur ne
serait pas jeté — il deviendrait le **modèle de référence sain**, son vrai rôle dans la méthode
Li & Braun. Décision de fond, pas de refactor.

**C bis. Les grandeurs dérivées** — **fait, absorbé par P0.** Le bruit est appliqué aux
capteurs, puis `COP`, `pressure_ratio`, `compression_ratio`, `delta_T_*` et `capacity_ratio`
sont recalculés, et la référence saine des `d_*` est bruitée indépendamment. Un test
permanent vérifie `pressure_ratio = P_cond / P_evap` et qu'aucun résidu n'est identiquement
nul sur une classe. Retirer `pressure_ratio` du contrat (doublon de `compression_ratio`)
reste **P5**.

**C. `FEATURE_COLUMNS` en résidus seuls ?** Il mélange aujourd'hui 19 grandeurs absolues et 5
résidus. La mesure dit que ce mélange nuit au transfert.

**D. Les deux défauts fantômes.** `REFRIGERANT_OVERCHARGE` et `COMPRESSOR_VALVE_LEAK` ont une
`FaultType` et une branche d'injection, mais ne sont jamais générés. Les produire ou les
retirer — NIST couvre les deux, donc les produire est défendable.

## GRAND 1 — Diagnostic (FDD)

Tout ce qui suit relève du diagnostic : nommer une panne présente. Le grand 2 — le pronostic
sur séries temporelles — ne démarre **qu'une fois le grand 1 terminé**, et seulement si un jeu
de données adapté existe.

### 1A bis. P0 — Étanchéité du pipeline · **fait**

Quatre fuites mesurées sur le 99,6 % — corrigées, jeu régénéré, modèle réentraîné
(`scikit-learn==1.6.1`). Chiffre publié : **91,9 % [90,4 – 93,1]** hold-out test,
Random Forest sélectionné sur val (GB à 0,002 de F1, départagé sur l'inférence).

| | Fuite | Correction |
|---|---|---|
| 1 | `d_COP == 0` pour les 2000 `Normal`, et eux seuls | dérivées recalculées après bruitage ; référence saine bruitée |
| 2 | `scaler.fit_transform(X)` avant `cross_val_score` | `Pipeline([scaler, clf])` |
| 3 | CV finale sur `df` complet | 5-fold sur `X_train` seul — F1 0,914 ± 0,009 |
| 4 | Sélection sur le test (5ᵉ décimale) | train / val / test ; sélection sur val ; Wilson à côté du score |

Gardes dans `tests/test_pipeline_integrity.py` : dérivées cohérentes, aucun résidu nul sur une
classe, `d_COP` n'est plus un détecteur parfait, labels mélangés → score de la classe
majoritaire.

X4 reste à faire, mais elle ne mentira plus par construction : la fuite d'étiquette est fermée.
P5 (contrat résidus + conditions, retirer le doublon `pressure_ratio`) n'est plus bloqué par
le bruit des dérivées.

### 1A. Vérité et hygiène

| | Chantier | État |
|---|---|---|
| P1 | Vérité des chiffres dans la documentation | fait |
| P2 | Budget de calibration mesuré | fait |
| P3 | Quatre défauts de physique corrigés, accord des signes 12/16 → 20/22 | fait |
| P4 | Décision D : produire la surcharge, trancher la fuite de clapet | à faire |
| P5 | Contrat de features : résidus + conditions ; retirer le doublon `pressure_ratio` | à faire |
| P6 | Découper `api/app.py` — 4 routes d'inférence contre 17 de tableau de bord | à faire |

### 1B. Les expériences

Le projet n'avait mené que la plus facile des expériences possibles. Cette section les nomme
toutes, **numérotées dans l'ordre d'exécution** — pas dans l'ordre où l'idée est venue.

« Détecter une panne » n'est pas une expérience, c'en est plusieurs :

| | Entraîné sur | Testé sur | Ce que ça mesure | État |
|---|---|---|---|---|
| **X0** | simulé | simulé, hold-out | Un classifieur peut-il inverser le simulateur | fait — **91,9 % [90,4 – 93,1]** |
| **X1** | mesuré | mesuré, autre machine | **Quelles pannes** sont détectées | **fait** |
| **X2** | — | mesuré, autre machine | Le ML bat-il une **table de règles** | **fait** |
| **X3** | mesuré | mesuré, autre machine | Quel **estimateur de référence saine** est le meilleur | **fait** |
| **X4** | simulé | simulé, **conditions non vues** | Le 91,9 % survit-il hors des points appris | à faire |
| **X5** | simulé | **mesuré** | Le simulateur décrit-il la réalité | à faire |

#### X1 — Quelles pannes sont réellement détectées · fait

Le 0,602 moyen cachait un système très inégal :

| Panne | F1, référence calibrée |
|---|---|
| Sous-charge | **0,832** |
| Sans défaut | 0,741 |
| Surcharge | **0,674** |
| Obstruction condenseur | 0,299 |
| Débit intérieur | 0,288 |
| Ligne liquide | **0,040** |

**Les défauts de charge portent tout le résultat.** La ligne liquide n'est jamais détectée —
huit vrais positifs sur 492 essais dans un sens — et c'est aussi la seule panne que le
simulateur ne modélise pas. Débit d'air et ligne liquide se confondent massivement : les deux
affament l'évaporateur, donc se ressemblent sur les grandeurs mesurées.

Et **la surcharge est mieux détectée sans calibration qu'avec** (0,786 contre 0,674), cohérent
dans les deux sens de transfert. Le budget de calibration dépend donc de la panne cherchée, et
pour l'une d'elles il est nul.

Notebook : `EDA/EDA_NIST_perclass.ipynb`.

#### X2 — Le modèle bat-il une table de règles · **fait**

Le boosting gagne sa place : 0,602 / 0,479 contre 0,365 / 0,243 pour la table de signes
(référence calibrée). Un arbre de profondeur 3 n'est que 4 points d'accuracy derrière.
Sans référence saine appariée, la table retombe sur la classe majoritaire (0,245). Détail
et figure : `docs/NIST_FINDINGS.md`, `EDA/EDA_NIST_rules.ipynb`.

#### X3 — Benchmark de l'estimateur de référence saine · **fait**

Le 0,602 est un kNN k=5 médiane, machine cible. Contrôle reproduit exactement. Sans
conditionner (médiane globale) : **0,337**. L'essentiel du gain est de comparer **à condition
équivalente**, pas la soustraction.

**La courbe `dmin → accuracy` est le résultat.** 28 % des essais défaillants ont un sain à
moins de 0,1 °C. En interdisant les voisins à moins de 0,5 °C :

| Estimateur | Répliques autorisées | dmin = 0,5 °C |
|---|---|---|
| kNN k=1 | 0,650 | 0,501 |
| kNN k=5 — **publié** | **0,602** | **0,482** |

Le petit `k` ne gagne que grâce au plan d'essais. Le 0,602 de chambre tombe à **0,482** sur
une machine en service. L'exploration disait 0,511 ; la mesure propre est 0,482.

Point de rosée dans le kNN des deux étages : **0,602 → 0,576**. L'erreur de régression
s'améliore ; la classification baisse. Juger l'étage 1 en bout de chaîne.

Le 0,602 **n'est pas remplacé** dans README / dossier / NIST_FINDINGS / `results.csv` (`X0b`)
— PR séparée, listée dans `docs/NIST_FINDINGS.md`. Notebook : `EDA/EDA_NIST_reference_bench.ipynb`.

#### X4 — Hold-out sur le domaine de fonctionnement · ½ j

Même jeu simulé, **découpage différent** : au lieu d'un tirage aléatoire sur les 5000 exemples,
retirer une région entière du domaine — par exemple `T_sink > 48 °C` — entraîner sur le reste,
tester dessus.

C'est le geste qui a tout révélé sur les données mesurées, appliqué cette fois au jeu simulé.
**Si le score s'effondre, le 91,9 % est en partie de la mémorisation de points de
fonctionnement.** Aucune donnée ni modèle nouveau.

#### X5 — Simulé aux conditions NIST, testé sur le réel · 2 j

Le recouvrement de domaine de 5,3 % est **un obstacle de sampling, pas de physique** : il
découle des plages de tirage choisies, pas d'une limite du simulateur. Vérification faite,
celui-ci tourne aux conditions NIST et produit des valeurs plausibles — mais qui ne collent pas :

| Conditions | `P_evap` | `P_cond` | τ | COP |
|---|---|---|---|---|
| Simulé à 24/35 °C | 14,04 bar | 24,19 bar | 1,72 | 4,32 |
| **Mesuré NIST, sain** | **10,5 bar** | **25,7 bar** | **2,37** | **3,41** |

Aspiration surestimée de 35 %, taux de compression sous-estimé de 28 %, COP optimiste de 27 %.
**Le simulateur est systématiquement optimiste.**

L'expérience : élargir les plages d'échantillonnage, régénérer un jeu simulé aux conditions
NIST, entraîner dessus, tester sur les essais réels. Quatre classes se correspondent. C'est la
seule expérience qui teste si le simulateur décrit la réalité.

### Ordre recommandé

```
P0  ── fait (91,9 % [90,4 – 93,1])
P5 ──> X4 ──> X5
P4, P6                               parallèle
X3                                   indépendant — données NIST seules
G                                    indépendant — durcir les garde-fous
```

**P0 est livré.** X4 peut maintenant être menée sans que la fuite d'étiquette traverse le
hold-out. P5 (contrat de features) reste un prérequis *utile* de X4, plus un bloquant.

**X3 est livré.** Sans les répliques du plan d'essais (dmin = 0,5 °C), le 0,602 tombe à
**0,482**. Le chiffre de chambre n'est pas encore remplacé dans README / dossier — PR séparée.

**G — durcir les garde-fous** (0,75 j), issu du §8 bis de l'audit :
- un test qui compare les nombres des tableaux markdown à `results.csv` — sans lui, la « source
  unique » est déclarative et le fichier n'est qu'une quatrième copie ;
- une contrainte de **voisinage** sur le test protocole, qui ne peut pratiquement pas échouer
  en l'état (le mot « validation » figure dans presque tout README) ;
- `log()` atomique via `os.replace()`, plus un `log_many()` — la boucle actuelle réécrit tout
  le fichier à chaque appel ;
- brancher les notebooks sur `tools.results.log` au lieu de saisir à la main.

X4 et X5 produiront vraisemblablement des résultats **négatifs**, et c'est leur intérêt. P0
étant fermé, elles ne produiront plus un 0,99 de façade.

### Règle d'arrêt

Chaque expérience menée jusqu'ici en a suggéré une nouvelle. C'est sain, et c'est sans fin.

**Le périmètre du grand 1 est figé à X4–X5 et P4–P6.** Toute question soulevée par ces
expériences part dans une liste « suite », pas dans le périmètre courant. Sans cette règle, le
projet ne sera jamais livré.

### Fin du grand 1

Le grand 1 est terminé quand les six chantiers sont livrés, les trois expériences menées, et
que chaque chiffre du dépôt est accompagné de son protocole.

À ce stade, la contribution du projet n'est pas un détecteur mais **une méthodologie de
validation** : comment établir ce que vaut un modèle FDD entraîné sur simulateur, et son
application à un cas concret. C'est ce qui doit être annoncé, plutôt qu'une performance.

## GRAND 2 — Pronostic sur séries temporelles

**Non démarré, et conditionné à l'obtention d'un jeu de données adapté.**

Les essais NIST sont **stationnaires** : un défaut imposé et maintenu, mesuré à l'équilibre. Il
n'y a ni horloge, ni dégradation progressive, ni instant de défaillance. Y appliquer un modèle
temporel reviendrait à inventer un axe du temps qui n'existe pas — exactement le type de
résultat que ce projet s'attache à ne pas produire.

Critères éliminatoires d'un jeu utilisable : horodatage régulier sur des mois, au moins un
événement terminal daté par unité, conditions extérieures enregistrées, plusieurs unités.

Sources acceptables par ordre de préférence : historique de terrain ou banc instrumenté ; à
défaut un jeu de référence hors domaine, clairement étiqueté comme étude de méthode ; en
dernier recours une dégradation **simulée**, présentée comme telle.

Le pronostic n'est pas un modèle différent du diagnostic, c'est une **donnée** différente.

## Règles de travail

**Les chiffres.** Toute valeur mesurée s'écrit dans `outputs/results.csv` via `tools.results.log`,
jamais seulement dans une sortie de notebook. Les colonnes `protocol` et `reference` sont
obligatoires : **un chiffre sans son protocole n'est pas un résultat**, et ce projet a mesuré à
quel point ça compte (0,95 contre 0,60 selon le découpage ; 0,602 contre 0,482 selon la
structure du plan d'essais).

La documentation cite ce fichier plutôt que de recopier les valeurs. Les deux contradictions
qu'il a fallu réparer — le dossier contre la feuille de route, puis le 0,602 annoncé sans sa
condition — venaient toutes deux de la recopie manuelle.

**Les figures.** Un notebook coûteux écrit ses résultats avant de tracer. La courbe de budget de
calibration a dû être retracée ; sans le tableau resté par chance dans une sortie de cellule, il
aurait fallu relancer 280 entraînements pour corriger une légende.

**Les gardes automatiques.**

| Test | Ce qu'il empêche |
|---|---|
| `tests/test_docs.py` | qu'un document cite un fichier disparu après un refactor |
| `tests/test_docs.py` | qu'une performance soit annoncée sans nommer son protocole |
| `tests/test_results_log.py` | qu'une mesure soit loggée sans protocole, ou deux fois avec deux valeurs |

**Le dépôt.**




1. Une PR = une idée, commit par commit.
2. `pytest` vert avant et après chaque PR — 43 aujourd'hui.
3. Rien qui casse le clone-and-run.
4. Le pin `scikit-learn==1.6.1` est **porteur** : le `.joblib` commité ne se charge qu'avec
   cette version. La changer impose de réentraîner via `main_analysis.py`.
5. `dashboard.py` et `scripts/` ne sont couverts par aucun test — les vérifier à la main
   (`python -c "import dashboard"`) après tout déplacement.

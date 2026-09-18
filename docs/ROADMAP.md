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

**43 tests passent.** L'équivalence de comportement a été vérifiée à chaque étape du refactor
en comparant les sorties avant/après octet pour octet.

**Confrontation aux essais NIST** — quatre notebooks dans `EDA/` (descriptif, modèle,
référence, calibration), résultats dans `docs/NIST_FINDINGS.md`.

**Quatre défauts de physique corrigés** — surcharge non modélisée, sous-refroidissement inversé
sur l'encrassement condenseur, surchauffe et refoulement inversés sur le ventilateur
d'évaporateur, plafond de refoulement jamais appliqué. L'accord des sens de variation avec les
essais mesurés passe de **12/16 à 20/22**, et l'accuracy simulée de 99,8 % à 99,6 % — baisse
attendue, le modèle n'apprend plus sur des cycles impossibles.

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

⚠️ **Le 0,602 est lui-même conditionnel.** Une exploration préliminaire montre qu'il suppose de
disposer d'une mesure saine aux conditions quasi identiques à celles du défaut — vrai dans la
campagne NIST, répliquée par construction, faux sur une machine en service. En interdisant les
voisins à moins de 0,5 °C, il tombe à **0,511**. À confirmer par X3, et à répercuter partout si
confirmé.

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
démontera en une question. Le 99,6 % actuel mesure la séparabilité des signatures dans le
modèle physique, pas une détection sur machine réelle. Proposition :

⚠️ **Cette formulation est provisoire** : elle cite 0,602 sans mentionner que ce chiffre suppose
une référence saine aux conditions du défaut. À figer **après X3**, pas avant.

> Signatures de défauts séparables à 99,6 % en validation croisée sur données simulées.
> Méthode par résidus confrontée aux essais NIST : 0,602 lorsque la référence saine est
> calibrée sur la machine cible, **0,318** sans cette calibration, 0,95 en validation
> aléatoire — laquelle surestime largement.

Moins spectaculaire, et défendable.

**B. Faut-il basculer sur les données réelles ?** Les 5386 essais NIST suffisent à réentraîner.
Mais ça change le sujet : mode **froid**, machine **air/air**, taxonomie NIST. Le cadrage
A7/W40 disparaît, et avec lui la distinction encrassement / ventilateur. Le simulateur ne
serait pas jeté — il deviendrait le **modèle de référence sain**, son vrai rôle dans la méthode
Li & Braun. Décision de fond, pas de refactor.

**C bis. Les grandeurs dérivées contournent le bruit de mesure.** Dans
`studies/synthetic/generator.py`, le bruit gaussien est appliqué **après** le calcul des
grandeurs dérivées, qui ne sont pas recalculées. Résultat mesuré sur les 5000 exemples :

| Grandeur | Lignes cohérentes avec ses entrées |
|---|---|
| `pressure_ratio`, `compression_ratio` | **0 %** |
| `COP` | **0 %** |
| `delta_T_evap`, `delta_T_cond` | **0 %** |

Aucune ligne ne vérifie `pressure_ratio = P_cond / P_evap`. Le modèle reçoit donc deux
versions de la même information, une bruitée et une propre — le bruit est partiellement
récupérable par différence (écart-type du rapport : 0,028). Une part du 99,6 % vient d'une
information indisponible sur une machine réelle.

À corriger dans le même chantier que la décision C : soit recalculer les dérivées après
bruitage, soit ne plus les transmettre si l'on passe aux résidus seuls. Les deux règlent le
problème, le second le règle par construction.

**C. `FEATURE_COLUMNS` en résidus seuls ?** Il mélange aujourd'hui 19 grandeurs absolues et 5
résidus. La mesure dit que ce mélange nuit au transfert.

**D. Les deux défauts fantômes.** `REFRIGERANT_OVERCHARGE` et `COMPRESSOR_VALVE_LEAK` ont une
`FaultType` et une branche d'injection, mais ne sont jamais générés. Les produire ou les
retirer — NIST couvre les deux, donc les produire est défendable.

## GRAND 1 — Diagnostic (FDD)

Tout ce qui suit relève du diagnostic : nommer une panne présente. Le grand 2 — le pronostic
sur séries temporelles — ne démarre **qu'une fois le grand 1 terminé**, et seulement si un jeu
de données adapté existe.

### 1A. Vérité et hygiène

| | Chantier | État |
|---|---|---|
| P1 | Vérité des chiffres dans la documentation | fait |
| P2 | Budget de calibration mesuré | fait |
| P3 | Quatre défauts de physique corrigés, accord des signes 12/16 → 20/22 | fait |
| P4 | Décision D : produire la surcharge, trancher la fuite de clapet | à faire |
| P5 | Contrat de features : résidus + conditions, et le bruit des dérivées (décision C bis) | à faire |
| P6 | Découper `api/app.py` — 4 routes d'inférence contre 17 de tableau de bord | à faire |

### 1B. Les expériences

Le projet n'avait mené que la plus facile des expériences possibles. Cette section les nomme
toutes, **numérotées dans l'ordre d'exécution** — pas dans l'ordre où l'idée est venue.

« Détecter une panne » n'est pas une expérience, c'en est plusieurs :

| | Entraîné sur | Testé sur | Ce que ça mesure | État |
|---|---|---|---|---|
| **X0** | simulé | simulé, tirage aléatoire | Un classifieur peut-il inverser le simulateur | fait — 99,6 % |
| **X1** | mesuré | mesuré, autre machine | **Quelles pannes** sont détectées | **fait** |
| **X2** | — | mesuré, autre machine | Le ML bat-il une **table de règles** | à faire |
| **X3** | mesuré | mesuré, autre machine | Quel **estimateur de référence saine** est le meilleur | à faire |
| **X4** | simulé | simulé, **conditions non vues** | Le 99,6 % survit-il hors des points appris | à faire |
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

#### X2 — Le modèle bat-il une table de règles · ½ j

**La question que posera tout jury qui connaît le domaine.**

Le FDD par résidus est un domaine où la méthode de référence est une table de règles sur les
signes : sous-refroidissement qui monte et pression haute qui monte, c'est une obstruction de
condenseur. Le projet cite cette méthode en fondation **sans l'avoir jamais implémentée** — il
utilise ses résidus, puis pose un Gradient Boosting dessus.

La table existe déjà : c'est la matrice des signes mesurés construite pour l'accord
simulation/mesure. Un classifieur qui vote sur ces directions tient en une trentaine de lignes,
sans entraînement.

Trois évaluations, à protocole identique : règles avec référence calibrée, règles avec référence
transférée, et **règles sans aucune référence** — cette dernière n'ayant pas d'équivalent côté
modèle appris, puisqu'une règle regarde des directions et non des valeurs.

Les deux issues sont publiables : soit le modèle appris gagne sa place avec des chiffres, soit
une table de signes issue de la physique l'égale, ce qui est un résultat peu commun.

À ajouter au périmètre : un **arbre de décision de profondeur 3**, qui situe le curseur entre la
règle écrite à la main et l'ensemble de centaines d'arbres. Si l'écart est de cinq points, la
complexité ne s'achète pas cher.

#### X3 — Benchmark de l'estimateur de référence saine · 1,5 j

*(fusionne les anciennes pistes « meilleure référence à petit n » et « benchmark étage 1 » —
c'était la même expérience.)*

Le système a deux étages : un **estimateur** qui prédit ce que lirait une machine saine dans
les conditions courantes, puis un **classifieur** qui travaille sur l'écart. L'étage 2 n'a
jamais été comparé à quoi que ce soit — c'est X2. L'étage 1 ne l'a été que partiellement.

Une exploration préliminaire a déjà produit trois résultats à confirmer proprement :

**Le choix de l'estimateur pèse lourd.** Une moyenne globale des essais sains donne 0,358 contre
0,602 pour un kNN tenant compte des conditions. **L'essentiel du gain de la méthode ne vient pas
de la soustraction, mais du fait de comparer à condition équivalente.**

**L'erreur de régression ne prédit pas la performance de classification.** Ajouter le point de
rosée améliore nettement l'erreur d'estimation sur les essais sains, et fait *baisser*
l'accuracy de 0,602 à 0,576. Toute variante doit être évaluée en bout de chaîne.

**🔴 Et le chiffre publié dépend de la structure du plan d'expérience.** 29 % des essais
défaillants ont un essai sain à moins de 0,1 °C : la campagne NIST est répliquée par
construction. En interdisant les voisins à moins de 0,5 °C, ce qui simule une situation de
terrain :

| Estimateur | Répliques autorisées | Répliques interdites |
|---|---|---|
| kNN k=1 | 0,703 | 0,523 |
| kNN k=5 — **publié** | 0,602 | **0,511** |

Un petit `k` semble gagner dix points ; le gain disparaît une fois les répliques exclues. **Et
le 0,602 lui-même tombe à 0,511.** Le chiffre du projet suppose implicitement une mesure saine
aux conditions quasi identiques à celles du défaut — vrai dans une campagne contrôlée, faux sur
une machine en service.

L'expérience à mener : grille complète d'estimateurs, seuil de distance **balayé** plutôt que
fixé, évaluation en bout de chaîne, détail par panne.

Deux règles à y inscrire :
- tout gain apporté par un petit `k` doit être retesté sans répliques, sinon on mesure le plan
  d'expérience ;
- l'erreur d'estimation ne sert que de présélection, jamais de conclusion.

#### X4 — Hold-out sur le domaine de fonctionnement · ½ j

Même jeu simulé, **découpage différent** : au lieu d'un tirage aléatoire sur les 5000 exemples,
retirer une région entière du domaine — par exemple `T_sink > 48 °C` — entraîner sur le reste,
tester dessus.

C'est le geste qui a tout révélé sur les données mesurées, appliqué cette fois au jeu simulé.
**Si le score s'effondre, le 99,6 % est en partie de la mémorisation de points de
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
X2  ->  X3  ->  X4  ->  X5        en parallèle de  P4 -> P5 -> P6
```

**X2 d'abord** : demi-journée, répond à l'objection du domaine, et se nourrit de X1 qui dit
quelles pannes sont dures. Puis **X3**, la seule qui vise une amélioration — et qui doit
confirmer ou infirmer que le 0,602 tombe à 0,511 sans répliques. Puis **X4**, dont le résultat
conditionne tout le discours sur le volet simulé. **X5** en dernier, la plus lourde.

X4 et X5 produiront vraisemblablement des résultats **négatifs**. C'est leur intérêt : un
résultat négatif mesuré vaut mieux qu'un chiffre jamais confronté. Mais il faut le savoir avant
de les lancer, et ne pas en espérer un chiffre flatteur.

### Règle d'arrêt

Chaque expérience menée jusqu'ici en a suggéré une nouvelle. C'est sain, et c'est sans fin.

**Le périmètre du grand 1 est figé à X2–X5 et P4–P6.** Toute question soulevée par ces
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


1. Une PR = une idée, commit par commit.
2. `pytest` vert avant et après chaque PR — 43 aujourd'hui.
3. Rien qui casse le clone-and-run.
4. Le pin `scikit-learn==1.6.1` est **porteur** : le `.joblib` commité ne se charge qu'avec
   cette version. La changer impose de réentraîner via `main_analysis.py`.
5. `dashboard.py` et `scripts/` ne sont couverts par aucun test — les vérifier à la main
   (`python -c "import dashboard"`) après tout déplacement.

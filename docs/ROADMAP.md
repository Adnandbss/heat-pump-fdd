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

### 1B. Les expériences qui manquent

**C'est la partie que le projet n'a jamais faite**, et c'est elle qui produit des résultats
plutôt que des corrections.

« Détecter une panne » n'est pas une expérience, c'en est cinq. Le projet n'en a mené que
trois, dont la plus facile :

| | Entraîné sur | Testé sur | Ce que ça mesure | État |
|---|---|---|---|---|
| **E0** | simulé | simulé, tirage aléatoire | Un classifieur peut-il inverser le simulateur | fait — 99,6 % |
| **E1** | simulé | simulé, **conditions non vues** | Généralise-t-il hors des points appris | **jamais fait** |
| **E2** | simulé | **mesuré** | Le simulateur décrit-il la réalité | **jamais fait** |
| **E3** | mesuré | mesuré, même machine | La tâche est-elle apprenable sur du réel | fait — 0,95 |
| **E4** | mesuré | mesuré, autre machine | Transfère-t-elle entre unités | fait — 0,602 / 0,318 |
| **E5** | mesuré | mesuré, autre machine | **Quelles pannes** sont détectées, et lesquelles non | **jamais fait** |
| **E6** | — | mesuré, autre machine | **Le ML bat-il une table de règles** issue de la physique | **jamais fait** |

#### E5 — Quelles pannes sont réellement détectées · ½ j

**Le résultat constructif le moins cher du projet, et il n'a jamais été fait.**

Les deux chiffres publiés sur les essais mesurés sont :

```
accuracy 0,602        F1 macro 0,479
```

Cet écart de douze points signifie que **les classes ne sont pas détectées également**.
Certaines pannes passent bien, d'autres très mal. Personne n'a regardé lesquelles.

L'expérience : matrice de confusion et rapport par classe sur le protocole leave-one-machine-out
déjà en place. Aucune donnée nouvelle, aucun modèle nouveau, aucun réentraînement.

Ce que ça permet de dire, au lieu d'une moyenne :

> Sur données mesurées, tel défaut est détecté à 0,8 et tel autre à 0,2 — le diagnostic par
> résidus sépare bien telle famille de pannes, mal telle autre.

C'est utile à un praticien, et ça oriente toute la suite : inutile de chercher une amélioration
globale si une seule classe plombe la moyenne. Si deux classes sont systématiquement confondues,
c'est une question de physique, pas d'algorithme — et c'est une conclusion en soi.

À faire **en premier** : c'est la seule expérience du lot qui produise à coup sûr un résultat
exploitable, les autres étant des expériences de destruction.

#### E6 — Le modèle bat-il une table de règles · ½ j

**La question que posera tout jury qui connaît le domaine, et à laquelle le dépôt ne sait pas
répondre aujourd'hui.**

Le FDD par résidus est un domaine où la méthode de référence est une **table de règles sur les
signes** : si le sous-refroidissement monte et la pression haute monte, c'est un encrassement de
condenseur. C'est l'approche classique de cette littérature — celle que le projet cite en
fondation.

Or le projet utilise les résidus de Li & Braun, puis pose un Gradient Boosting dessus. **Il n'a
jamais implémenté la méthode simple qu'il revendique comme base.**

Tant que la comparaison n'est pas faite, la réponse à « votre modèle fait-il mieux qu'une règle
écrite à la main ? » est *on ne sait pas* — et si un jury soupçonne que six règles
thermodynamiques suffisent, tout le volet apprentissage devient décoratif.

**La table existe déjà.** C'est la matrice des signes mesurés construite pour l'accord
simulation/mesure : pour chaque panne, la direction de la surchauffe, du sous-refroidissement,
du refoulement, du COP et des pressions. Un classifieur qui vote sur ces directions tient en une
trentaine de lignes, sans entraînement.

Évalué sur le même protocole leave-one-machine-out, les deux issues sont publiables :

| Issue | Ce qu'on en tire |
|---|---|
| Les règles font nettement moins bien | Le ML gagne sa place, chiffres à l'appui plutôt que par postulat |
| Les règles font aussi bien ou mieux | Résultat remarquable et honnête : sur ce problème, une table de signes issue de la physique égale un modèle appris |

**Un bonus à ne pas manquer** : une règle regarde des directions, pas des valeurs — elle n'a
donc **pas besoin de calibration saine**. Si elle tient à 0,45 sans calibration là où le modèle
appris plafonne à 0,318, c'est un argument de déploiement très fort, et il renverse la
conclusion du budget de calibration pour les pannes concernées.

À faire juste après E5 : les deux se nourrissent. L'analyse par classe dit quelles pannes sont
dures ; la table de règles dit si l'apprentissage sert à quelque chose sur celles-là.

#### E1 — Hold-out sur le domaine de fonctionnement · ½ j

Même jeu de données, **découpage différent** : au lieu d'un tirage aléatoire sur les 5000
exemples, retirer une région entière du domaine — par exemple tout ce qui dépasse
`T_sink > 48 °C` — entraîner sur le reste, tester dessus.

C'est exactement le geste qui a tout révélé sur les données NIST, appliqué cette fois au jeu
simulé. **Si le score s'effondre, le 99,6 % est en partie de la mémorisation de points de
fonctionnement, pas de la reconnaissance de signature.**

Aucune donnée nouvelle, aucun modèle nouveau. Le résultat conditionne tout le discours sur le
volet simulé, et il peut le détruire — c'est son intérêt.

#### E2 — Simulé aux conditions NIST, testé sur le réel · 2 j

Le recouvrement de domaine de 5,3 % a longtemps été présenté comme un obstacle. **C'en est un
de sampling, pas de physique** : il découle des plages de tirage choisies pour l'entraînement,
pas d'une limite du simulateur.

Vérification faite, le simulateur tourne aux conditions NIST et produit des valeurs
plausibles — mais qui ne collent pas :

| Conditions | `P_evap` | `P_cond` | τ | COP |
|---|---|---|---|---|
| Simulé à 24/35 °C | 14,04 bar | 24,19 bar | 1,72 | 4,32 |
| **Mesuré NIST, sain** | **10,5 bar** | **25,7 bar** | **2,37** | **3,41** |

Aspiration surestimée de 35 %, taux de compression sous-estimé de 28 %, COP optimiste de 27 %.
**Le simulateur est systématiquement optimiste** — aucune des expériences précédentes ne
pouvait le dire.

L'expérience : élargir les plages d'échantillonnage, régénérer un jeu simulé aux conditions
NIST, entraîner dessus, tester sur les essais réels. Quatre classes se correspondent —
obstruction condenseur, débit intérieur, sous-charge, surcharge.

C'est **la seule expérience qui teste si le simulateur décrit la réalité**, et donc la seule
qui donne une valeur au volet simulé au-delà de la démonstration.

#### A — Meilleure référence saine à budget contraint · 1 j

La seule piste qui vise une **amélioration** plutôt qu'une mesure.

Dans le protocole du budget de calibration, la référence saine est toujours un kNN, y compris
à `n = 1` ou `n = 5`. Or un kNN sur cinq points ne sait pas interpoler, il recopie le voisin le
plus proche — d'où les intervalles énormes à petit `n`, où un tirage malheureux fait pire que
pas de calibration du tout.

Un modèle paramétrique — le polynôme d'ordre 2 du NIST, ou une forme guidée par la physique du
pincement — devrait le dominer précisément là où les données sont rares.

**Ce qui n'a jamais été testé** : l'exploration des modèles de référence a comparé kNN,
polynôme et forêt aléatoire **à `n = tous`**. Jamais à `n = 10` ou `n = 50`.

Enjeu : si un polynôme atteint 80 % du gain avec 50 essais là où le kNN plafonne à 49 %, la
conclusion publiable passe de « il faut couvrir tout le domaine » à **« 50 essais bien
exploités suffisent »**. C'est un résultat industriel directement actionnable.

Et si ça échoue, la conclusion reste publiable : *quatre estimateurs de référence comparés à
budget contraint, aucun ne bat le plus proche voisin.*

### Ordre recommandé

```
E5  ->  E6  ->  E1  ->  A  ->  E2      en parallèle de  P4 -> P5 -> P6
```

**E5 d'abord** : demi-journée, aucun risque, et la seule qui produise à coup sûr un résultat
positif exploitable. Puis **E6**, qui répond à la question du domaine et se nourrit de E5. Puis
**E1**, dont le résultat conditionne tout le discours sur le volet simulé. Puis **A**, la seule qui vise une amélioration. **E2** en dernier, la plus lourde.

Deux de ces quatre expériences produiront vraisemblablement des résultats **négatifs** — E1 et
E2. C'est leur intérêt : un résultat négatif mesuré et quantifié vaut mieux qu'un chiffre jamais
confronté. Mais il faut le savoir avant de commencer, et ne pas les lancer en espérant un
chiffre flatteur.

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

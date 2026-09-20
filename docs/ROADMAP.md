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

**76 tests** passent (dont les gardes d'étanchéité P0 et la cohérence de taxonomie P4). L'équivalence de comportement a été
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

Deux désaccords restent : `W_comp` sous-charge, `COP` surcharge. La surcharge est désormais
dans le mix (500 / 5000). La fuite de clapet n'est pas modélisée : il faudrait un paramètre
`volumetric_efficiency_loss` (gaz chaud du refoulement vers l'aspiration) — dette du
simulateur, pas un flag du générateur.

## Les décisions qui t'appartiennent

**A. Comment annoncer la performance.** C'est le point le plus urgent, et le seul qu'un jury
démontera en une question. Le 89,3 % actuel (hold-out 30 %, sélection sur val, intervalle
Wilson 87,6 – 90,7, sept classes) mesure la séparabilité des signatures dans le modèle
physique, pas une détection sur machine réelle. Le 99,6 % précédent était une fuite
d'étiquette. Proposition :

**Figée**, X3 et X5 étant menées :

> Signatures de défauts séparables à **89,3 % [87,6 – 90,7]** en hold-out sur données simulées
> (sept classes, sélection sur val, `Pipeline` sklearn) — une mesure de la séparabilité dans le
> modèle physique, pas d'une détection sur machine.
>
> Confrontée aux 7375 essais NIST : **0,602** lorsque la référence saine est calibrée sur la
> machine cible, **0,318** sans cette calibration (0,251 pour la classe majoritaire), et 0,95 en
> validation aléatoire — laquelle surestime d'un facteur trois.
>
> Entraîné sur le simulateur et testé sur le réel : **0,454**, la charge frigorigène étant le
> seul défaut qui transfère (F1 0,45–0,52) et l'encrassement condenseur ne transférant pas du
> tout (F1 0,000).

Moins spectaculaire, et défendable. Les cinq marches sont affichées côte à côte sur la page
Evidence du tableau de bord (P7), chacune avec son protocole.

**B. Faut-il basculer sur les données réelles ?** Les 5386 essais NIST suffisent à réentraîner.
Mais ça change le sujet : mode **froid**, machine **air/air**, taxonomie NIST. Le cadrage
A7/W40 disparaît, et avec lui la distinction encrassement / ventilateur. Le simulateur ne
serait pas jeté — il deviendrait le **modèle de référence sain**, son vrai rôle dans la méthode
Li & Braun. Décision de fond, pas de refactor.

La sous-question du tableau de bord est, elle, tranchée : **P7 en fait une pièce de preuve**,
pas une vitrine. Six figures lisent `results.csv` par l'API, et un test interdit le moindre
chiffre en dur dans le TSX.

**C bis. Les grandeurs dérivées** — **fait, absorbé par P0.** Le bruit est appliqué aux
capteurs, puis `COP`, `pressure_ratio`, `compression_ratio`, `delta_T_*` et `capacity_ratio`
sont recalculés, et la référence saine des `d_*` est bruitée indépendamment. Un test
permanent vérifie `compression_ratio = P_cond / P_evap` et qu'aucun résidu n'est identiquement
nul sur une classe. `pressure_ratio` (doublon) a été retiré en **P5**.

**C. `FEATURE_COLUMNS` en résidus seuls ?** — **mesuré, non appliqué (P5).** Sur NIST, les
résidus seuls battent brutes + résidus parce qu'il y a deux machines. Ici il n'y en a qu'une.
Les résidus seuls perdent sept points (0,823 contre 0,893). On garde le contrat à 23 colonnes.

**D. Les deux défauts fantômes** — **fait, P4.** `REFRIGERANT_OVERCHARGE` est produite
(500 / 5000), après retrait du `condenser_fouling` parasite dans la branche d'injection.
`COMPRESSOR_VALVE_LEAK` est retirée : le simulateur n'expose pas de perte de rendement
volumétrique, et l'ancienne branche était un mélange de deux autres pannes. Chiffre livré :
**89,3 % [87,6 – 90,7]** (sept classes), contre 91,9 % [90,4 – 93,1] sur six.

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

X4 peut maintenant être menée sans que la fuite d'étiquette traverse le hold-out.
P5 (contrat résidus + conditions, retirer le doublon `pressure_ratio`) n'est plus bloqué par
le bruit des dérivées.

### 1A ter. P4 — Les deux classes fantômes · **fait**

`FaultType` déclarait huit classes, le jeu en produisait six.

**Surcharge — produite.** P3 lui avait donné une physique (pression haute, sous-refroidissement
qui monte, surchauffe qui baisse). X1 a montré que c'est la seule panne NIST détectée à 0,786
sans calibration. Le correctif important n'est pas de l'ajouter : c'est de retirer
`condenser_fouling = severity * 0.2` de la branche d'injection, vestige de l'époque où la
surcharge n'avait pas de physique. Sans ça, chaque surcharge contenait un vrai encrassement.

**Fuite de clapet — retirée.** Pas de paramètre `volumetric_efficiency_loss` dans
`simulate_cycle`. L'ancienne branche mélangeait sous-charge et encrassement évaporateur.
La générer aurait créé une classe qui est littéralement deux autres. À modéliser plus tard,
côté physique.

Après régénération (5000 lignes, 7 classes) : **89,3 % [87,6 – 90,7]**, F1 0,872. Avant
(6 classes) : 91,9 % [90,4 – 93,1]. La surcharge est détectée (F1 0,88). Confusion avec
l'encrassement condenseur : 11 / 150 et 9 / 150 — résidu physique (les deux élèvent P_cond),
pas le couplage artificiel. Garde : `tests/test_fault_taxonomy.py` (FaultType == dataset ==
metadata).

### 1A. Vérité et hygiène

| | Chantier | État |
|---|---|---|
| P1 | Vérité des chiffres dans la documentation | fait |
| P2 | Budget de calibration mesuré | fait |
| P3 | Quatre défauts de physique corrigés, accord des signes 12/16 → 20/22 | fait |
| P4 | Décision D : produire la surcharge, trancher la fuite de clapet | **fait** |
| P5 | Contrat de features : doublon retiré, résidus seuls mesurés et **rejetés** | **fait** |
| P6 | Découper `api/app.py` — 4 routes d'inférence contre 17 de tableau de bord | **fait** |
| P7 | Le tableau de bord lit `results.csv` : page Evidence, zéro chiffre en dur | **fait** |

### 1B. Les expériences

Le projet n'avait mené que la plus facile des expériences possibles. Cette section les nomme
toutes, **numérotées dans l'ordre d'exécution** — pas dans l'ordre où l'idée est venue.

« Détecter une panne » n'est pas une expérience, c'en est plusieurs :

| | Entraîné sur | Testé sur | Ce que ça mesure | État |
|---|---|---|---|---|
| **X0** | simulé | simulé, hold-out | Un classifieur peut-il inverser le simulateur | fait — **89,3 % [87,6 – 90,7]** (7 cl.) |
| **X1** | mesuré | mesuré, autre machine | **Quelles pannes** sont détectées | **fait** |
| **X2** | — | mesuré, autre machine | Le ML bat-il une **table de règles** | **fait** |
| **X3** | mesuré | mesuré, autre machine | Quel **estimateur de référence saine** est le meilleur | **fait** |
| **X4** | simulé | simulé, **conditions non vues** | Le 91,9 % survit-il hors des points appris | **fait** — oui pour le domaine, **non pour la sévérité** |
| **X5** | simulé | **mesuré** | Le simulateur décrit-il la réalité | **fait** — **45,4 %**, encrassement condenseur à **0,000** |

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

#### X4 — Hold-out sur le domaine de fonctionnement · **fait**

Même jeu simulé, découpage par région au lieu du tirage aléatoire. Contrôle : le protocole X0
rejoué dans les mêmes conditions (0,919).

| Découpage | Accuracy | 95 % Wilson | n |
|---|---|---|---|
| Aléatoire (contrôle) | 0,919 | 0,904 – 0,931 | 1500 |
| `speed > 0,85` | 0,920 | 0,902 – 0,935 | 1077 |
| GroupKFold 5 plis | 0,911 | 0,903 – 0,919 | 5000 |
| `T_amb < −5 °C` | 0,893 | 0,870 – 0,913 | 804 |
| `T_sink > 48 °C` | 0,889 | 0,871 – 0,904 | 1366 |

**L'hypothèse est réfutée : le score ne s'effondre pas.** Retirer une région entière du domaine
coûte au plus 3 points. Le 91,9 % n'était pas de la mémorisation de points de fonctionnement —
c'est le seul résultat de la campagne qui donne raison au modèle.

La fragilité est ailleurs. Hold-out sur la **sévérité**, quatre classes, ventilateurs exclus :

| Entraîné sur | Testé sur | Accuracy | F1 macro |
|---|---|---|---|
| Normal + sévère | défauts naissants | 0,428 | 0,496 |
| Normal + naissants | défauts sévères | 0,469 | 0,540 |

En détection binaire seule, 0,762 et 0,887. **Le modèle sait qu'il se passe quelque chose, il
ne sait plus quoi.** C'est la limite utile à annoncer : un FDD qui n'extrapole pas en sévérité
ne sert pas à la maintenance préventive, qui vit précisément dans les défauts naissants.

Mesures en 24 colonnes, donc antérieures à P5. Journalisées sous `X4`, huit protocoles.

#### X5 — Simulé aux conditions NIST, testé sur le réel · **fait**

Le recouvrement de domaine de 5,3 % était **un obstacle de sampling, pas de physique**. Plages
élargies, jeu régénéré aux conditions NIST, entraîné dessus, testé sur les essais réels.

| | Accuracy | F1 macro |
|---|---|---|
| Hold-out simulé (référence) | 0,921 | 0,917 |
| **sim2real** — entraîné simulé, testé mesuré | **0,454** | **0,343** |
| LOMO sur mesuré seul (plafond atteignable) | 0,668 | 0,596 |

Par classe, en sim2real :

| Classe | F1 simulé | F1 sur le réel |
|---|---|---|
| Undercharge | 0,974 | 0,445 |
| Overcharge | 0,936 | 0,522 |
| Normal | 0,930 | 0,716 |
| Evaporator_Fan_Fault | 0,998 | 0,031 |
| **Condenser_Fouling** | 0,749 | **0,000** |

**Le simulateur transfère sur la charge et sur rien d'autre.** L'encrassement condenseur, qu'il
prétend séparer à 0,749, n'est jamais retrouvé sur les essais réels : sa signature simulée
n'est pas celle d'un vrai encrassement. Le défaut de ventilateur d'évaporateur, à 0,998 en
simulé, tombe à 0,031.

C'est l'expérience la plus sévère de la campagne et la plus utile. Elle dit quelle partie du
simulateur est publiable — la charge — et laquelle est un artefact de modélisation.

### Où on en est

Les sept chantiers sont livrés et les six expériences menées. **Le périmètre du grand 1 est
fermé.** `X3-prelim` (6 lignes) n'est pas une neuvième expérience à couvrir : c'est
l'essai préliminaire que `X3` (505 lignes) remplace. Les figures le laissent de côté
volontairement (`EXCLUDED_FROM_FIGURES` dans `api/routers/evidence.py`).

```
P0 P1 P2 P3 P4 P5 P6 P7   ── livrés
X0 X1 X2 X3 X4 X5         ── menées
G  garde-fous             ── livré
```

Ce que la campagne a établi, dans l'ordre où ça compte :

1. **Le protocole pèse plus que le modèle.** 0,954 en CV aléatoire contre 0,333 en
   leave-one-machine-out, mêmes données, même classifieur. Tout chiffre du dépôt nomme
   désormais son protocole.
2. **Les résidus doublent le transfert** (0,333 → 0,602), mais seulement avec une référence
   saine calibrée sur la machine cible. Référence transférée : 0,318, contre 0,251 pour la
   classe majoritaire.
3. **Le simulateur ne transfère que sur la charge.** X5 : 0,454 global, encrassement condenseur
   à 0,000.
4. **Le domaine n'est pas le problème, la sévérité l'est.** X4 : au plus 3 points perdus en
   retirant une région entière du domaine, mais 0,43 en extrapolation de sévérité.
5. **Le chiffre vitrine est passé de 99,6 % à 89,3 %** à mesure que les fuites tombaient, et
   ces deux nombres sont publiés côte à côte.

### Ce qu'il reste

Rien de bloquant. Par ordre de valeur :

| | Chantier | Coût |
|---|---|---|
| R1 | ~~Rejouer et journaliser le sweep de calibration.~~ **Fait** — `X1` / `LOMO-calibration-n{10,50}`. | — |
| R2 | ~~Vérifier `GET /api/thermo/cop`.~~ **Fait** — Carnot chauffage, COP Normal par tranche, balayage à \(T_\mathrm{sink}-10\). | — |
| R3 | **Trancher les 14 Mo de binaires** de la PR P7 (`FRONT_EVIDENCE.pdf` + 9 PNG) pour un `.git` de 53 Mo, et l'anglais/français mélangé dans l'UI. | 1 h |
| R4 | **Modéliser la fuite de clapet** côté physique (`volumetric_efficiency_loss` dans `simulate_cycle`), la seule classe de `FaultType` retirée faute de physique. | 1 j |
| R5 | **Corriger l'encrassement condenseur du simulateur**, seul défaut à 0,000 en sim2real. C'est le chantier le plus intéressant scientifiquement et le plus incertain. | ? |

R1 et R2 sont des dettes d'honnêteté : à faire avant toute présentation. R3 est cosmétique.
R4 et R5 ouvrent un nouveau périmètre — ils ne rentrent **pas** dans le grand 1.

### Règle d'arrêt

Chaque expérience menée en a suggéré une nouvelle. C'est sain, et c'est sans fin.

**Le périmètre du grand 1 était figé à X0–X5 et P0–P7. Il est atteint.** Toute question
soulevée depuis part dans « ce qu'il reste » ci-dessus, pas dans le périmètre courant.

### Ce que le projet livre

Pas un détecteur. **Une méthodologie de validation** : comment établir ce que vaut un modèle
FDD entraîné sur simulateur, et ce qu'il en reste face à 7375 essais en chambre.

C'est ce qu'il faut annoncer. La performance brute — 89,3 % — est le chiffre le moins
intéressant du dépôt, et le tableau de bord le montre maintenant à côté des cinq autres
marches de l'échelle.

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

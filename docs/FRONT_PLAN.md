# P7 — Front : faire entrer les résultats dans le dashboard

## 0. État des lieux

Le dashboard `web/` est aujourd'hui une **vitrine de démo** : il simule un point de
fonctionnement, montre des probabilités, trace un diagramme P-h. Il est joli et il tourne.

Il ne montre **rien** de ce que le dépôt a réellement établi. Les 656 mesures de
`outputs/results.csv`, les 8 expériences X0→X5, le fait qu'un protocole honnête divise la
performance par trois — tout cela n'existe que dans le README et le dossier PDF.

Un jury qui ouvre le front voit un projet de démo. Un jury qui lit le README voit un projet
de recherche. C'est le même dépôt : le front doit rattraper.

### Trois bugs relevés au passage

| Fichier | Problème |
|---|---|
| `web/src/lib.ts` | `FAULT_COLORS` n'a que 6 classes. `Refrigerant_Overcharge`, ajoutée en P4, retombe sur `CLASS_COLORS[index]` et peut **collider** avec une autre classe. |
| `web/src/lib.ts` | `PAGE_COPY.insights` annonce « calibrated Gradient Boosting ». Le modèle livré est le **Random Forest**. |
| `web/src/lib.ts` | `PAGE_COPY.models` annonce « 23 residual features ». Les 23 colonnes ne sont pas toutes des résidus. |

À corriger dans la même PR que le reste : ce sont exactement les incohérences que P5 a
chassées côté Python.

---

## 1. Principe directeur : zéro chiffre en dur

**Aucune valeur numérique ne doit être écrite dans le TSX.**

`tools/results.py` est déjà la source unique côté Python, et `test_readme_results_percentages_are_logged`
interdit au README d'afficher un pourcentage qui n'est pas journalisé. Le front hérite de la
même règle : tout passe par `outputs/results.csv` → API → composant.

Conséquence concrète : rejouer une expérience et relancer `tools.results.log()` met le
dashboard à jour tout seul. C'est ce qui distingue un dashboard d'une capture d'écran.

Un test garde cette règle (§7).

---

## 2. Backend — `GET /api/evidence/*`

Nouveau routeur `api/routers/evidence.py`, schémas dans `api/schemas/evidence.py`,
dépendance `get_results()` dans `api/deps.py` (lecture CSV + cache mtime, exactement le
motif de `get_dataset`).

| Endpoint | Rend | Sert |
|---|---|---|
| `GET /api/evidence/summary` | 4 cartes : n° d'expériences, n° de mesures, protocoles distincts, headline + son protocole | bandeau haut |
| `GET /api/evidence/ladder` | l'échelle de vérité, ordonnée, chaque barre portant sa cause | figure 1 |
| `GET /api/evidence/protocols` | X0b : 4 jeux de features × 2 protocoles | figure 2 |
| `GET /api/evidence/references` | X3 : les 505 mesures du benchmark de référence sain, grille famille × conditionnement × `dmin` | figure 3 |
| `GET /api/evidence/per-class` | F1 par classe sur les trois régimes, classes alignées côté serveur | figure 4 |
| `GET /api/evidence/runs?experiment=&protocol=&model=` | les 656 lignes, filtrables, paginées | figure 6 |

Contraintes, dans la continuité de P6 :

- routes en `def` (lecture pandas bloquante → threadpool), pas d'`async` cosmétique ;
- `tags=["evidence"]` et un `operation_id` explicite par opération — le test
  `test_openapi_declares_tags_and_operation_ids` le vérifie déjà ;
- CSV absent → `ArtifactMissing` → 404, jamais une 500 ;
- au moins un test de route qui tourne sur un CSV jouet écrit en `tmp_path`, via
  `create_app(Settings(results_path=...))`. Pas de dépendance au fichier livré.

Ajouter `results_path` à `api/settings.py`.

---

## 3. Front — la page Evidence

Nouvelle entrée de sidebar, 7ᵉ item, icône `FlaskConical` (lucide), id `evidence`,
placée **en deuxième position** — juste après Insights. C'est le cœur du projet, pas une
annexe.

```
web/src/pages/EvidencePage.tsx
web/src/components/evidence/TruthLadder.tsx
web/src/components/evidence/ProtocolSlope.tsx
web/src/components/evidence/CalibrationCurve.tsx
web/src/components/evidence/PerClassBars.tsx
web/src/components/evidence/RunsTable.tsx
web/src/components/ProtocolBadge.tsx      ← réutilisé partout
```

Style : strictement l'existant. `GlassCard`, `tooltipStyle`, `recharts`, les mêmes rayons
et les mêmes bordures `rgba(255,255,255,0.18)`. **Aucune nouvelle dépendance.** On n'invente
pas un second langage visuel pour la moitié sérieuse de l'application.

### `ProtocolBadge` — le composant qui change tout

Une puce discrète, verre dépoli, qui accompagne **chaque chiffre de l'application** :

```
[ hold-out · simulé ]   [ LOMO · NIST ]   [ CV aléatoire ⚠ ]
```

À poser aussi sur les pages existantes (Insights, Models). Un jury qui voit « 89.3 % » sans
savoir sur quoi ne peut rien en faire ; la puce répond avant qu'il pose la question. C'est la
leçon de X0b rendue visible partout, pour trois lignes de TSX.

---

## 4. Les six figures

### Figure 1 — L'échelle de vérité

La figure la plus importante du dépôt. Barres horizontales décroissantes, chacune annotée de
**ce qu'on a retiré** pour passer à la suivante.

```
99.6 %  ████████████████████  d_COP fuitait le label
91.9 %  ██████████████████    6 classes, dont une fantôme non modélisée
89.3 %  █████████████████     7 classes, hold-out honnête
─────────────────────────────  frontière simulateur │ NIST
60.2 %  ███████████           LOMO, résidus, référence sur la machine cible
45.4 %  ████████              sim2real : entraîné sur le simulateur, testé sur le réel
31.8 %  ██████                LOMO, référence transférée d'une autre machine
25.1 %  ▏▏▏▏▏                 classe majoritaire
```

Deux règles de conception, non négociables :

1. **Une séparation visuelle franche entre le bloc simulateur et le bloc NIST.** Ce ne sont
   pas les mêmes données ; une rampe continue laisserait croire à une dégradation unique et
   serait malhonnête. Deux bandes, un filet, deux libellés d'axe.
2. **Une ligne de référence en pointillé à 25.1 %** (classe majoritaire). Sans elle, 31.8 %
   ressemble à un échec ; avec elle, on voit que c'est au-dessus du hasard mais à peine.

Couleur : une seule teinte, clair → foncé (magnitude, pas identité). Pas d'arc-en-ciel.
Pas de rouge/vert : ce ne sont pas des états, ce sont des mesures.

### Figure 2 — Le protocole pèse plus que le modèle

Slopegraph. Quatre jeux de features (`raw`, `residuals`, `raw+residuals`,
`residuals+conditions`), deux colonnes (`CV aléatoire`, `LOMO`), un trait par jeu.

```
CV aléatoire            LOMO
  0.973 ●──────────────● 0.562   raw+residuals
  0.954 ●──────────────● 0.333   raw
  0.945 ●──────────────● 0.594   residuals+conditions
  0.937 ●──────────────● 0.602   residuals
```

Le slopegraph est la bonne forme ici et un histogramme groupé ne l'est pas : la donnée
intéressante est la **pente**, pas les hauteurs. On voit d'un coup que l'écart vertical
(protocole, ~0.4) écrase l'écart horizontal (features, ~0.04), et que `residuals` est le seul
trait à peu près plat.

Légende directe en bout de trait, pas de boîte de légende.

### Figure 3 — Le benchmark des références saines (X3, 505 mesures)

**C'est le jeu de données le plus riche du dépôt et il n'est publié nulle part.** X3 balaie
une grille complète de modèles de référence sain :

- famille : `global-mean`, `global-median`, `knn-k1/5/10/20` (uniforme ou pondéré distance),
  `poly2`
- conditionnement : `TT` (températures) ou `TTdew` (+ point de rosée intérieur, la forme
  que NIST utilise)
- `dmin` : 0, 0.1, 0.25, 0.5, 1, 2 °C

**L'axe `dmin` est un garde-fou contre la fuite, pas un hyperparamètre.** À `dmin=0`, un test
en défaut peut avoir son jumeau sain à 0.05 °C dans le jeu de référence — le kNN k=1 le
retrouve et le score explose artificiellement. C'est exactement l'artefact qui a failli être
publié comme une amélioration de +10 points.

Forme : **petits multiples**, une facette par famille, X = `dmin`, Y = accuracy, une courbe
par conditionnement. Échelle Y identique sur toutes les facettes — sinon la comparaison est
fausse. Ligne de référence à 0.251.

Ce qu'on lit d'un coup d'œil : les courbes `knn-k1` plongent quand `dmin` monte, les autres
sont plates. **La pente est le diagnostic de fuite.** Les grilles d'hyperparamètres, tout le
monde en publie ; une grille dont un axe mesure sa propre honnêteté, non.

Annotation : `knn-k5-median-unif-TT-dmin0` = 0.602, et ce que ce même modèle donne à
`dmin=0.5`.

> **Donnée manquante.** Le tableau « coût de la calibration » du README (0/10/50/tous →
> 0.318 / 0.377 / 0.456 / 0.602) n'est **pas** dans `outputs/results.csv`. Le garde-fou
> `test_readme_results_percentages_are_logged` ne l'a pas vu parce qu'il ne contrôle que les
> valeurs suivies d'un `%`. Deux conséquences : rejouer l'expérience et la journaliser via
> `tools.results.log()` avant d'en faire une figure, et étendre le garde-fou aux décimaux
> nus. Tant que ce n'est pas fait, **pas de courbe de calibration dans le front** — le
> principe du §1 n'a de valeur que s'il ne souffre aucune exception.

### Figure 4 — Par classe : trois régimes

Barres horizontales groupées, triées par F1 décroissant sur le premier régime. Trois séries,
issues de trois lignes de journal distinctes :

| Série | Source | Ce que c'est |
|---|---|---|
| Simulateur | `X5 / holdout-test / simulated` | le chiffre vitrine |
| NIST, référence sur la machine cible | `X1 / LOMO / target-machine` | le plafond réaliste |
| NIST, référence transférée | `X1 / LOMO / training-machine` | machine réellement inconnue |

```
Undercharge      sim 0.974   cible 0.832   transférée 0.481
Overcharge       sim 0.936   cible 0.674   transférée 0.786   ←
No_Fault         sim 0.930   cible 0.741   transférée 0.131
Evap_Airflow     sim —       cible 0.288   transférée 0.269
Cond_Blockage    sim 0.749   cible 0.299   transférée 0.067
LiquidLine       sim —       cible 0.040   transférée 0.007
```

Deux annotations obligatoires, parce que ce sont les deux faits que la figure révèle :

- **`Overcharge` monte quand la référence est transférée** (0.674 → 0.786). Une surcharge se
  voit sans calibration : sa signature est absolue, pas relative à la machine. C'est le seul
  défaut déployable en l'état, et c'est une conclusion exploitable.
- **`LiquidLine` est à 0.040.** Jamais détecté. Le simulateur ne le modélise même pas. On
  l'affiche quand même.

Les classes absentes du simulateur (`LiquidLine`, `Evap_Airflow`) laissent un **trou visible**
dans la série, jamais un zéro : un zéro dirait « mesuré et nul », le trou dit « pas mesurable ».
La distinction n'est pas cosmétique.

La grille de classes diffère entre le simulateur (7 classes, nomenclature interne) et NIST
(6 classes, nomenclature NIST). La table de correspondance vit **côté serveur**, dans
`api/routers/evidence.py`, pas dans le TSX.

### Figure 5 — Matrice de confusion

Heatmap, rampe séquentielle une teinte, **2 px de fond entre les cellules** (règle de
lisibilité, pas d'esthétique). Sélecteur de protocole au-dessus : la même matrice en hold-out
simulé et en sim2real, c'est deux mondes.

Valeurs écrites dans les cellules — une matrice 7×7 est assez petite pour ça, et la couleur
seule ne se lit pas au chiffre près.

### Figure 6 — Les 656 mesures

Table filtrable (expérience / protocole / modèle / classe), triable, avec les colonnes
`n` et `note`. Pas de pagination infinie : 50 lignes, un bouton.

C'est la pièce justificative. Un jury sceptique doit pouvoir descendre de n'importe quel
graphe jusqu'à la ligne de CSV qui le produit. Lien direct vers `outputs/results.csv` en
pied de table.

---

## 5. Dette front à solder dans la foulée

Ces points étaient déjà identifiés ; les traiter ici évite une quatrième PR.

| Point | Action |
|---|---|
| Types dupliqués à la main dans `api.ts` | générer depuis `/openapi.json` (`openapi-typescript`), script `npm run gen:api`, sortie versionnée |
| Aucun `AbortController` | annuler les `fetch` en vol dans le cleanup des `useEffect` — `InsightsPage` en lance 5 en parallèle |
| Pas d'`ErrorBoundary` | une frontière par page ; aujourd'hui une exception de rendu vide l'écran |
| Navigation par `useState` | `react-router-dom`, routes `/evidence`, `/models`… — sinon aucun graphe n'est partageable par URL, et un jury ne peut pas être envoyé sur une figure précise |
| Pas d'ESLint | `eslint` + `typescript-eslint` + `react-hooks`, en CI |
| Aucun test front | Playwright, un test : ouvrir `/evidence`, attendre les 6 figures, vérifier qu'aucun « NaN » ni « undefined » n'est rendu |

Le routeur avant le reste : il conditionne la structure des pages.

---

## 6. Découpage en PR

| PR | Contenu | Taille |
|---|---|---|
| **P7a** | `api/routers/evidence.py`, schémas, `get_results()`, `results_path`, tests de route sur CSV jouet | ~350 l |
| **P7b** | `EvidencePage` + 6 composants + `ProtocolBadge` posé sur les pages existantes + les 3 bugs de `lib.ts` | ~700 l |
| **P7c** | routeur, types générés, `AbortController`, `ErrorBoundary`, ESLint, Playwright, CI | ~300 l |

P7a est mergeable seule et se vérifie au Swagger. P7b ne peut pas commencer avant.

---

## 7. Critères d'acceptation

- [ ] `grep -E '[0-9]+\.[0-9]+ ?%' web/src/**/*.tsx` ne remonte **aucun** chiffre de résultat
      (un test CI le vérifie, sur le modèle de `test_readme_results_percentages_are_logged`)
- [ ] chaque figure affiche le protocole de ses données, via `ProtocolBadge`
- [ ] la page Evidence se charge avec le backend et **sans** `models/synthetic/classifier.joblib`
- [ ] un test de route `/api/evidence/*` passe sur un CSV jouet, sans l'artefact livré
- [ ] `npm run build` (donc `tsc --noEmit`) passe
- [ ] ESLint passe en CI
- [ ] le test Playwright passe
- [ ] `outputs/results.csv` modifié → dashboard modifié, sans toucher au TSX
- [ ] `test_readme_results_percentages_are_logged` étendu aux décimaux nus (il laisse passer
      le tableau de calibration du README, §figure 3)
- [ ] la suite Python reste verte

---

## 8. Ce que ça vaut

Un dashboard de démo montre qu'on sait appeler un modèle. Il y en a des centaines.

Un dashboard qui affiche **99.6 % → 89.3 % → 60.2 % → 45.4 %** avec la cause de chaque
marche, et qui laisse descendre jusqu'à la ligne de CSV, montre qu'on sait *mesurer* — et
qu'on publie le chiffre qui dérange. C'est la seule partie du projet qu'un recruteur ne
pourra pas confondre avec un tutoriel.

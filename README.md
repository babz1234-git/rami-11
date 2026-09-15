# Rami de Famille — jouer en ligne

Ce dossier contient :

- `game_engine.py` — ton moteur de jeu original, quasiment inchangé (voir la
  section "Ce que j'ai touché dans game_engine.py" plus bas).
- `server.py` — le serveur qui fait le lien entre plusieurs navigateurs :
  salons, tour par tour, diffusion de l'état de la partie. C'est la pièce qui
  manquait pour jouer à distance.
- `index.html`, `style.css`, `app.js` — l'interface (accueil, salon d'attente,
  table de jeu).
- `requirements.txt` — dépendances Python.

## 1. Lancer la partie chez toi (test rapide, ou jouer sur le même Wi-Fi)

```bash
pip install -r requirements.txt
python server.py
```

Ouvre ensuite `http://localhost:10000` dans ton navigateur. Si tes proches
sont sur le même réseau Wi-Fi que toi, ils peuvent utiliser ton adresse IP
locale (affichée dans le terminal, du style `http://192.168.1.x:10000`) au
lieu de `localhost`.

Ça ne suffit **pas** pour jouer avec quelqu'un chez lui, à distance : il faut
héberger le serveur quelque part d'accessible sur internet. C'est l'objet de
la partie suivante.

## 2. Héberger pour jouer avec ta grand-mère à distance

La façon la plus simple et gratuite : [Render](https://render.com).

1. Mets ce dossier dans un dépôt GitHub (public ou privé, peu importe).
2. Sur Render : **New +** → **Web Service**, connecte ton dépôt GitHub.
3. Renseigne :
   - **Build command** : `pip install -r requirements.txt`
   - **Start command** : `python server.py`
   - **Instance type** : Free
4. Render te donne une URL du style `https://ton-jeu.onrender.com` — c'est
   cette adresse que tu partages avec ta famille, où qu'ils soient.

Point d'attention avec l'offre gratuite de Render : le serveur se met en
veille après 15 minutes d'inactivité et met ~30-60 secondes à se relancer au
prochain appel. Pour une partie de rami en soirée, ce n'est pas gênant (le
premier qui ouvre la page attend juste un peu) ; si ça vous embête, les offres
payantes de Render (ou une alternative comme Railway) suppriment cette mise en
veille.

Alternative si tu préfères ne rien déployer sur internet : lancer le serveur
sur ton PC et utiliser un tunnel comme [ngrok](https://ngrok.com) ou
[Tailscale Funnel](https://tailscale.com/kb/1223/funnel) pour t'exposer
temporairement — pratique pour tester avant de choisir un hébergement
définitif.

## 3. Améliorations suite aux premières parties jouées

Après tes retours en conditions réelles :

- **Vrai bug corrigé (trouvé en jouant, pas en relisant le code) :** dans une
  suite, il restait possible de faire suivre deux jokers l'un derrière
  l'autre en les ajoutant "en trop" à une suite déjà complète (ex : 5,6,7 de
  cœur + 2 jokers pour tenter 8,9). La règle "deux jokers ne peuvent pas se
  suivre" n'était bien vérifiée que pour les trous *internes* à la suite, pas
  pour ce cas de bord. Un seul joker "en trop" est maintenant accepté, plus
  de deux à la suite n'importe où — voir `suite_valide` dans
  `game_engine.py` (recherche "CORRECTION").
- **Noms de cartes lisibles dans le journal** : "Roi de Cœur" au lieu de "13
  de Cœur" (idem Dame/Valet/As). Uniquement le journal — les cartes
  elles-mêmes gardent leurs lettres compactes (R/D/V/A) qui sont déjà
  standard sur une vraie carte.
- **Défausse inversée** : on sélectionne d'abord une carte (elle se lève),
  puis on confirme avec le bouton "Défausser" — au lieu de l'ancien
  "j'appuie sur Défausser puis je touche la carte".
- **Réordonner sa main** : toucher une carte la sélectionne et fait
  apparaître deux flèches ◀ ▶ pour l'échanger avec sa voisine. Ça marche à
  tout moment, même hors de ton tour, pour organiser tranquillement sa main.
  J'ai délibérément évité le glisser-déposer ici : la main défile
  horizontalement sur mobile, et le glisser serait rentré en conflit avec ce
  défilement au toucher.
- **Glisser-déposer pour s'étaler** : dans la fenêtre "S'étaler", tu peux
  maintenant glisser une carte directement sur un groupe (en plus du clic en
  deux temps qui reste disponible). Cette fois pas de conflit de défilement
  possible : les cartes de cette fenêtre passent à la ligne plutôt que de
  défiler.
- **Fermeture automatique** de la fenêtre "S'étaler" une fois le contrat
  validé, plutôt que de laisser un bouton "Annuler" trompeur alors que
  l'étalement est déjà enregistré côté serveur.
- **Animation de fin de manche** : à la fin de chaque manche, un écran
  s'affiche brièvement (gagnant, points gagnés avec la mention du bonus x2 le
  cas échéant, classement complet, prochain contrat), puis se referme tout
  seul après quelques secondes — ou immédiatement si tu touches l'écran.

Une astuce CSS au passage, pour toi si tu retouches un jour le style :
un attribut `hidden` a le même poids qu'une classe pour le navigateur, donc
si une classe fixe `display: flex` sur un élément, ça peut discrètement
annuler le `hidden` posé par le Javascript. C'est exactement ce qui m'est
arrivé avec la barre des flèches de réordonnancement, qui restait visible à
tort — corrigé en ajoutant une règle `.barre-reordonner[hidden]{display:none}`
un cran plus spécifique.

## 4. Mise à jour des règles ("Rami à 11")

Suite à tes précisions détaillées sur les règles exactes, j'ai comparé chaque
point à ce qui était codé. Bonne nouvelle : la plupart des mécaniques
correspondaient déjà très exactement à ta description, sans rien à changer :

- Les 2 comme jokers, les brelans utilisables avec des cartes du même rang
  venant des 2 paquets différents (ex : 5 pique + 5 pique + 5 cœur), les
  suites qui doivent être d'une seule couleur, le choix pioche/défausse à
  chaque tour, le barème de points (têtes/10, 2/20, joker/50) : déjà corrects,
  vérifiés avec tes exemples précis.
- "Deux jokers ne peuvent pas se suivre dans une suite" : contrairement à ce
  que j'avais noté comme une limitation dans ma première relecture, c'est en
  fait exactement la règle que tu voulais, et le code la respectait déjà
  (j'ai vérifié avec tes deux exemples "qui marche" / "qui marche pas").
- "Un joueur ne peut pas faire de contrat en plus" : déjà garanti par la
  structure du code, un étalement doit correspondre EXACTEMENT au nombre de
  groupes du contrat, et les rajouts ne peuvent qu'agrandir un groupe déjà
  posé, jamais en créer un nouveau.

Deux choses manquaient en revanche, et je les ai ajoutées :

**A. La distribution ne retournait pas de carte pour démarrer la défausse.**
J'ai ajouté `entamer_manche()` dans `game_engine.py` : à chaque nouvelle
manche (au tout début de la partie, et à chaque nouveau contrat), on
distribue 11 cartes à chacun, on retourne une carte de la pioche pour
démarrer la défausse, et c'est au joueur suivant le distributeur de jouer en
premier (il peut prendre cette carte ou piocher, comme à n'importe quel
tour). Le rôle de distributeur tourne d'un joueur à chaque manche.

**B. "Finir sec" (terminer sans jamais s'étaler) n'était pas possible.**
C'est le scénario que tu décris avec les 4 et les 7 : un joueur qui garde
tout caché en main, accumule uniquement les cartes de ses futurs groupes, et
qui — une fois que sa main entière (après avoir pioché) se répartit
exactement selon le contrat, sans aucune carte qui dépasse — peut tout
révéler d'un coup et terminer la manche, sans jamais être passé par
l'étalement classique. J'ai ajouté une nouvelle action `action_finir_sec()`
(bouton "Terminer (main cachée)" dans l'interface) qui vérifie s'il existe
une façon de répartir la main *en entier* selon le contrat ; si oui, la
manche se termine et — comme le joueur n'a jamais posé quoi que ce soit
avant — le bonus x2 s'applique normalement sur les points de l'adversaire.

En creusant ce point, j'ai aussi trouvé et corrigé un vrai manque : ton code
original ne vérifiait la fin de manche que dans `action_defausser`. Or un
joueur peut aussi vider sa main via `action_etaler` (s'il pose tout son jeu
d'un coup) ou `action_rajouter` (sa toute dernière carte rejoint un groupe
sur la table) — ces deux cas ne déclenchaient jamais la fin de manche
auparavant, ce qui aurait bloqué la partie. C'est corrigé.

La recherche utilisée par "finir sec" essaie toutes les façons de répartir
la main entre les groupes du contrat (jusqu'à 3 groupes, 12 cartes au pire) ;
je l'ai testée sur les pires cas et elle répond en moins d'une demi-seconde,
donc aucun souci de lenteur à prévoir.

## 5. Corrections suite à ta deuxième relecture des règles

Ce sont les plus profondes depuis le début du projet — plusieurs vrais bugs
de logique, trouvés en jouant pour de vrai. Tout est testé (moteur, serveur
ET navigateur, avec tes exemples précis rejoués un par un).

- **Le "2" a maintenant une double nature.** Avant, un "2" était TOUJOURS
  considéré comme joker, jamais comme une vraie carte de valeur 2. Ton
  exemple (As, 2 utilisé normalement, 2 utilisé comme joker) l'a révélé : le
  moteur essaie maintenant les deux interprétations pour chaque "2" présent
  et retient celle qui rend le groupe valide. C'est le changement le plus
  important de cette série — voir `suite_valide` dans `game_engine.py`.
- **L'As peut être une carte haute** : Valet, Dame, Roi (via un joker), As
  est maintenant reconnu comme suite valide, en plus de son usage classique
  en carte basse.
- **Un joker "occupé" ne peut plus être doublé.** Dans une suite du style
  7,8,[joker représentant le 9],10, il était possible de rajouter un VRAI 9
  par-dessus, ce qui n'avait pas de sens (le joker ne se pousse pas). C'est
  bloqué avant même de tester la validité générale du groupe.
- **Score inversé.** C'était faux depuis le début et personne ne l'avait
  remarqué avant que tu joues vraiment plusieurs manches : le gagnant d'une
  mène marque désormais 0 point, et chaque perdant marque SES PROPRES points
  (doublés si le gagnant a fini sec). C'est le score total le plus BAS qui
  remporte la partie à la fin des 11 contrats (comme au golf).
- **Brelans : jokers non-consécutifs aussi.** Un brelan de 3 sept avec 2
  cartes réelles peut avoir au plus 3 jokers intercalés (un "emplacement"
  avant/entre/après chaque carte réelle) — un 4ᵉ forcerait forcément deux
  jokers à se toucher, donc c'est refusé. Ça corrige au passage un très
  vieux cas limite : un groupe 100% jokers n'est plus jamais valide.
- **Choix de la position pour un joker rajouté.** Quand tu rajoutes un
  joker/2 pour prolonger une suite existante (ex : sur 4-5-6), une petite
  fenêtre te demande maintenant si tu veux l'ajouter avant la première carte
  ou après la dernière, plutôt que de le mettre systématiquement à la fin.
- **Cohérence visuelle.** Les cartes s'affichent maintenant dans le même
  ordre dans "S'étaler" que dans ta main normale (avant, elles étaient
  réordonnées et ça perdait le rangement que tu avais fait). Les brelans
  affichent leurs jokers entrelacés avec les cartes réelles (jamais deux
  côte à côte), pour que la règle se voie d'un coup d'œil.
- **Rajout plus rapide.** Si tu avais déjà sélectionné une carte dans ta main
  avant de cliquer "Rajouter sur la table", elle est directement prête —
  plus besoin de la retoucher dans la fenêtre qui s'ouvre.

## 6. Comment j'ai organisé le multijoueur (pour que tu comprennes le code)

- Un salon = un code à 4 caractères + une instance de `Partie`. Tout vit en
  mémoire dans `server.py` (dictionnaire `rooms`) : si le serveur redémarre,
  les parties en cours sont perdues. Pour une partie de famille occasionnelle
  c'est un choix raisonnable ; on pourrait sauvegarder l'état dans un fichier
  ou une base si un jour vous voulez de la persistance.
- Chaque carte a maintenant un `id` unique (`Carte.__init__`). C'est ce qui
  permet au navigateur de dire "je veux défausser *cette* carte précise" sans
  ambiguïté, même quand deux cartes identiques existent (2 jeux de 52 +
  jokers).
- Chaque joueur ne reçoit que ce qu'il a le droit de voir : sa main en détail,
  mais seulement le *nombre* de cartes des autres (`etat_pour` dans
  `server.py`).
- J'ai ajouté un contrôle qui manquait complètement dans le moteur original :
  vérifier que c'est bien le tour de la personne qui envoie une action. Plus
  de détails ci-dessous.

## 7. Mes retours sur `game_engine.py` original

Tu m'as dit d'être franc si j'avais des remarques, donc les voici — rien de
grave, mais des points utiles à connaître :

**1. Le moteur fait confiance à l'appelant, sans vérifier qui joue.**
Toutes tes méthodes (`action_piocher`, `action_etaler`, `action_rajouter`,
`action_defausser`) agissent sur `self.joueurs[self.joueur_actif]`, peu
importe qui les appelle. En local (un seul script, un seul humain au clavier)
ce n'est pas un problème. Mais en ligne, n'importe quel navigateur peut
envoyer un événement à n'importe quel moment : sans vérification, Mamie
pourrait techniquement piocher à la place de Léo si les deux clics arrivent
au mauvais moment. J'ai ajouté ce contrôle côté serveur (`_contexte_action`
dans `server.py`), pas dans `game_engine.py`, pour ne pas mélanger "règles du
jeu" et "qui a le droit de faire quoi" — mais c'est le genre de choses à
garder en tête si vous réutilisez ce moteur ailleurs.

**2. Comparaison de cartes par identité d'objet.**
Dans `action_etaler`, `if carte in joueur_actuel.main` fonctionne parce que
Python compare par identité d'objet (pas de `__eq__` défini). Ça marche tant
qu'on manipule les mêmes objets Python en mémoire. Le piège : si on
sérialise une carte en JSON pour l'envoyer au navigateur puis qu'on la
reconstruit côté serveur à la réception, ce n'est plus le même objet, et la
comparaison échoue silencieusement (pire : avec 2 jeux de cartes, il peut y
avoir de vrais doublons en valeur+couleur, donc comparer par égalité de
valeurs ne serait pas correct non plus). J'ai contourné ça en ajoutant un
`id` unique par carte, et le serveur retrouve toujours l'objet réel dans
`main` via cet id avant d'appeler `action_etaler` — donc ton `carte in main`
d'origine continue de fonctionner tel quel.

**3. `brelan_valide` accepte un groupe composé uniquement de jokers/2.**
Si `cartes_normales` est vide (tout le groupe n'est que des cartes wild), la
fonction renvoie `True` sans autre vérification. Concrètement, un joueur qui
aurait 3 jokers pourrait valider un "brelan de 3" sans aucune carte réelle.
Je n'ai pas touché à cette logique (je préfère ne pas changer les règles du
jeu sans te demander), mais à toi de voir si c'est le comportement voulu ou
si tu préfères exiger au moins une carte "normale" par groupe.

**4. Petit oubli côté "pioche vide".**
Ton code laissait un commentaire `# Évolution future : retourner la
défausse` — je l'ai implémenté dans `action_piocher` : quand la pioche est
vide, on remélange la défausse dedans (en gardant sa carte du dessus). Sans
ça, une partie qui traîne un peu finirait par se bloquer.

Aucun de ces points n'empêchait ton code de fonctionner pour l'usage que tu
en faisais (un script Python que tu pilotais toi-même) — ce sont des choses
qui ne deviennent des problèmes qu'au moment où plusieurs personnes non
"de confiance" interagissent avec le moteur en même temps, ce qui est
précisément le changement qu'on vient de faire.

## 8. Limites connues de cette version

- Pas de reconnexion automatique si quelqu'un ferme l'onglet par erreur en
  pleine partie : la personne doit rouvrir la page et rejoindre avec le
  **même code de salon et le même prénom** pour reprendre sa main (le serveur
  la reconnaît). Pense à prévenir la famille de bien noter le code.
  Il n'y a par contre pas de mot de passe : toute personne qui connaît le
  code à 4 caractères peut rejoindre le salon avant que la partie démarre.
- Le serveur garde tout en mémoire (pas de base de données) : un redémarrage
  du serveur efface les parties en cours.
- Testé jusqu'à 6 joueurs par salon (`MAX_JOUEURS` dans `server.py`,
  modifiable).

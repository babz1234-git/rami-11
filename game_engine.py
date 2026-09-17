import random as rd
import uuid
import itertools

CONTRATS = {
    1: [("brelan", 3), ("brelan", 3)],
    2: [("suite", 3), ("suite", 3)],
    3: [("suite", 4), ("brelan", 3)],
    4: [("brelan", 4), ("brelan", 4)],
    5: [("suite", 5), ("brelan", 3)],
    6: [("brelan", 3), ("brelan", 3), ("brelan", 3)],
    7: [("suite", 7)],
    8: [("suite", 6), ("brelan", 3)],
    9: [("suite", 4), ("suite", 4)],
    10: [("brelan", 5), ("brelan", 5)],
    11: [("suite", 9)]
}

# AJOUT : description "humaine" de chaque contrat pour l'affichage dans l'interface.
DESCRIPTIONS_CONTRATS = {
    1: "2 brelans de 3 cartes",
    2: "2 suites de 3 cartes",
    3: "1 suite de 4 cartes + 1 brelan de 3 cartes",
    4: "2 brelans de 4 cartes",
    5: "1 suite de 5 cartes + 1 brelan de 3 cartes",
    6: "3 brelans de 3 cartes",
    7: "1 suite de 7 cartes",
    8: "1 suite de 6 cartes + 1 brelan de 3 cartes",
    9: "2 suites de 4 cartes",
    10: "2 brelans de 5 cartes",
    11: "1 suite de 9 cartes",
}

# AJOUT : pour que les messages du journal se lisent naturellement
# ("Léo a défaussé Roi de Coeur" plutôt que "13 de Coeur").
NOMS_VALEURS = {1: "As", 11: "Valet", 12: "Dame", 13: "Roi"}


def nom_valeur(valeur):
    return NOMS_VALEURS.get(valeur, str(valeur))


class Carte:
    def __init__(self, valeur, couleur):
        self.valeur = valeur
        self.couleur = couleur
        self.points = self.calculer_points()
        # AJOUT : identifiant unique. Indispensable en ligne : le paquet contient
        # 2 jeux de 52 cartes, donc deux "7 de Coeur" existent en même temps.
        # On ne peut pas désigner une carte précise juste avec valeur+couleur,
        # ni compter sur l'égalité d'objets Python une fois passé par du JSON
        # (voir mes remarques dans le README à ce sujet).
        self.id = uuid.uuid4().hex

    def calculer_points(self):
        if self.valeur == 0:
            return 50
        elif self.valeur == 2:
            return 20
        elif self.valeur == 1:
            return 11
        elif self.valeur >= 10:
            return 10
        else:
            return self.valeur

    def est_joker(self):
        # AJOUT : petit utilitaire pour que le frontend affiche un badge "wild"
        return self.valeur == 0 or self.valeur == 2

    def to_dict(self):
        # AJOUT : représentation JSON envoyée au navigateur
        return {
            "id": self.id,
            "valeur": self.valeur,
            "couleur": self.couleur,
            "points": self.points,
            "joker": self.est_joker(),
            "label": repr(self),
        }

    def __repr__(self):
        if self.valeur == 0:
            return "Joker"
        else:
            return f"{nom_valeur(self.valeur)} de {self.couleur}"


class joueur:
    def __init__(self, pseudo):
        self.nom = pseudo
        self.main = []
        self.score = 0
        self.est_etale = False

    def to_dict_public(self):
        # AJOUT : ce que les AUTRES joueurs ont le droit de voir (pas leur main !)
        return {
            "nom": self.nom,
            "nb_cartes": len(self.main),
            "score": self.score,
            "est_etale": self.est_etale,
        }


class Partie:
    def __init__(self, liste_joueurs):
        self.joueurs = [joueur(pseudo) for pseudo in liste_joueurs]
        self.pioche = []
        self.defausse = []
        self.tapis = []
        self.joueur_actif = 0
        self.niveau_actuel = 1
        # AJOUT : sert à interdire de se défausser avant d'avoir pioché,
        # et à interdire de piocher deux fois dans le même tour.
        self.a_pioche_ce_tour = False
        self.journal = []  # AJOUT : petit fil d'activité pour l'interface
        # AJOUT : index de celui qui "distribue" cette manche. Sert à savoir
        # qui commence à jouer (toujours le joueur suivant le distributeur).
        self.index_distributeur = 0
        # AJOUT : instantané du résultat de la dernière mène terminée, lu une
        # seule fois par server.py pour déclencher l'animation de transition.
        self.dernier_resultat_mene = None

    def log(self, message):
        # AJOUT : historique des dernières actions, envoyé aux joueurs
        self.journal.append(message)
        self.journal = self.journal[-30:]

    def generer_paquet(self):
        couleurs = ["Coeur", "Pique", "Carreau", "Trefle"]
        for i in range(2):
            for couleur in couleurs:
                for valeur in range(1, 14):
                    carte = Carte(valeur, couleur)
                    self.pioche.append(carte)
            for j in range(2):
                carte = Carte(0, "Joker")
                self.pioche.append(carte)

    def melanger_paquet(self):
        rd.shuffle(self.pioche)

    def distribuer(self):
        for j in self.joueurs:
            for i in range(11):
                carte = self.pioche.pop()
                j.main.append(carte)

    def entamer_manche(self):
        # AJOUT : regroupe toute la mise en place d'une manche, telle que tu
        # l'as décrite : on distribue 11 cartes à chacun, PUIS on retourne une
        # carte de la pioche pour démarrer la défausse (cette carte ne compte
        # pour la main de personne), et c'est au joueur suivant le
        # distributeur de jouer en premier — il pourra choisir de prendre
        # cette carte retournée ou de piocher normalement, exactement comme un
        # tour normal.
        self.generer_paquet()
        self.melanger_paquet()
        self.distribuer()

        if self.pioche:
            carte_retournee = self.pioche.pop()
            self.defausse.append(carte_retournee)

        distributeur = self.joueurs[self.index_distributeur]
        self.joueur_actif = (self.index_distributeur + 1) % len(self.joueurs)
        self.a_pioche_ce_tour = False

        premier_joueur = self.joueurs[self.joueur_actif]
        if self.defausse:
            self.log(
                f"{distributeur.nom} distribue et retourne {self.defausse[-1]}. "
                f"À {premier_joueur.nom} de jouer."
            )
        else:
            self.log(f"{distributeur.nom} distribue. À {premier_joueur.nom} de jouer.")

    def trouver_carte(self, main, carte_id):
        # AJOUT : retrouve l'OBJET carte correspondant à un id dans une main.
        # C'est ce qui permet à action_etaler de fonctionner correctement :
        # comme on repasse le même objet (pas une copie reconstruite depuis le
        # JSON du client), le "if carte in joueur_actuel.main" plus bas continue
        # de fonctionner tel que tu l'avais écrit.
        for carte in main:
            if carte.id == carte_id:
                return carte
        return None

    def action_piocher(self, source):
        joueur_actuel = self.joueurs[self.joueur_actif]

        if self.a_pioche_ce_tour:
            print("Tu as déjà pioché ce tour-ci !")
            return False

        if source == "pioche":
            if len(self.pioche) == 0:
                # AJOUT : ceci remplace le "Évolution future" que tu avais noté.
                # Quand la pioche est vide, on remélange la défausse dedans en
                # gardant sa carte du dessus (celle-ci reste visible/défaussée).
                if len(self.defausse) <= 1:
                    print("Plus aucune carte disponible, ni en pioche ni en défausse !")
                    return False
                derniere = self.defausse.pop()
                self.pioche = self.defausse
                self.defausse = [derniere]
                rd.shuffle(self.pioche)
                self.log("La pioche était vide : la défausse a été remélangée.")

            carte = self.pioche.pop()
            joueur_actuel.main.append(carte)
            self.a_pioche_ce_tour = True
            self.log(f"{joueur_actuel.nom} a pioché une carte.")
            return True

        elif source == "defausse":
            if len(self.defausse) == 0:
                print("La défausse est vide !")
                return False
            carte = self.defausse.pop()
            joueur_actuel.main.append(carte)
            self.a_pioche_ce_tour = True
            self.log(f"{joueur_actuel.nom} a repris {carte} dans la défausse.")
            return True

        return False

    def action_etaler(self, groupes_proposes):
        joueur_actuel = self.joueurs[self.joueur_actif]

        if joueur_actuel.est_etale:
            print(f"{joueur_actuel.nom} est déjà étalé !")
            return False

        if verifier_contrat(self.niveau_actuel, groupes_proposes):
            # CORRECTION : il faut toujours garder au moins une carte "morte"
            # à défausser normalement pour signifier qu'on a fini — ce n'est
            # jamais l'étalement lui-même qui doit vider la main à 0.
            nb_cartes_utilisees = sum(len(groupe) for groupe in groupes_proposes)
            if nb_cartes_utilisees >= len(joueur_actuel.main):
                print(f"{joueur_actuel.nom} doit garder au moins une carte à défausser pour terminer.")
                return False

            print(f"Félicitations {joueur_actuel.nom} ! Contrat validé.")
            joueur_actuel.est_etale = True

            for groupe in groupes_proposes:
                for carte in groupe:
                    if carte in joueur_actuel.main:
                        joueur_actuel.main.remove(carte)

            self.tapis.extend(groupes_proposes)
            self.log(f"{joueur_actuel.nom} a validé son contrat et s'est étalé !")
            return True
        else:
            print(f"Échec ! Le contrat proposé par {joueur_actuel.nom} est invalide.")
            return False

    def action_rajouter(self, index_carte_main, index_groupe_tapis, position="fin"):
        joueur_actuel = self.joueurs[self.joueur_actif]

        if not joueur_actuel.est_etale:
            print(f"Action refusée : {joueur_actuel.nom} doit s'étaler avant de faire un rajout.")
            return False

        # AJOUT : garde-fous sur les index (le code original suppose des index
        # toujours valides ; en ligne, mieux vaut ne jamais faire confiance
        # aveuglément à ce qu'envoie un navigateur).
        if not (0 <= index_carte_main < len(joueur_actuel.main)):
            return False
        if not (0 <= index_groupe_tapis < len(self.tapis)):
            return False

        # CORRECTION : même principe que pour action_etaler — il faut
        # toujours garder au moins une carte "morte" à défausser normalement.
        # Un rajout ne doit jamais être LA carte qui vide la main à 0.
        if len(joueur_actuel.main) <= 1:
            print(f"{joueur_actuel.nom} doit garder sa dernière carte pour la défausser.")
            return False

        carte = joueur_actuel.main[index_carte_main]
        groupe_cible = self.tapis[index_groupe_tapis]

        groupe_test = groupe_cible + [carte]
        nouvelle_taille = len(groupe_test)

        position_effective = "fin"
        valide = False

        if brelan_valide(groupe_test, nouvelle_taille):
            valide = True
        else:
            # CORRECTION : un groupe déjà posé est, par construction, déjà
            # une suite valide SANS trou interne ouvert (tous les trous ont
            # forcément déjà été comblés par un joker pour qu'il soit valide
            # au départ). La SEULE façon d'y ajouter une carte est donc de
            # prolonger l'une des deux extrémités — jamais de "glisser" une
            # carte au milieu. On vérifie ça précisément plutôt que de
            # rejouer suite_valide sur le tas complet (qui, ne sachant pas où
            # se trouve chaque carte, devait rester prudent sur le nombre de
            # jokers "en trop" tolérés).
            if carte.valeur not in (0, 2):
                # Carte réelle : sa place est déterminée par sa valeur, pas
                # besoin de demander — on essaie les deux côtés.
                if _extension_suite_ok(groupe_cible, carte, "debut"):
                    position_effective = "debut"
                    valide = True
                elif _extension_suite_ok(groupe_cible, carte, "fin"):
                    position_effective = "fin"
                    valide = True
            else:
                # Joker/2 : ambigu, on respecte le côté choisi par le joueur.
                if _extension_suite_ok(groupe_cible, carte, position):
                    position_effective = position
                    valide = True

        if valide:
            carte_jetee = joueur_actuel.main.pop(index_carte_main)
            if position_effective == "debut":
                self.tapis[index_groupe_tapis].insert(0, carte_jetee)
            else:
                self.tapis[index_groupe_tapis].append(carte_jetee)
            print(f"Rajout réussi ! {carte} a été ajoutée.")
            self.log(f"{joueur_actuel.nom} a rajouté {carte_jetee} sur le tapis.")
            return True
        else:
            print("Rajout impossible : la carte ne rentre pas dans ce groupe.")
            return False

    def action_defausser(self, index_carte):
        joueur_actuel = self.joueurs[self.joueur_actif]

        if not (0 <= index_carte < len(joueur_actuel.main)):
            return False

        carte_defausse = joueur_actuel.main.pop(index_carte)
        self.defausse.append(carte_defausse)
        self.a_pioche_ce_tour = False  # AJOUT : le prochain joueur doit repiocher
        self.log(f"{joueur_actuel.nom} a défaussé {carte_defausse}.")

        # Vérification fin de mène
        if len(joueur_actuel.main) == 0:
            print(f"\n🎉 INCROYABLE ! {joueur_actuel.nom} a vidé sa main et remporte la mène !")
            self.fin_de_mene(joueur_actuel)
        else:
            self.joueur_actif = (self.joueur_actif + 1) % len(self.joueurs)

        return True

    def action_finir_sec(self):
        # AJOUT : implémente le cas que tu as décrit — un joueur qui n'a
        # jamais étalé peut, s'il a réussi à faire en sorte que TOUTE sa main
        # se répartisse exactement selon le contrat demandé (aucune carte qui
        # ne rentre dans aucun groupe), terminer la manche directement au lieu
        # de se défausser. Comme il n'a jamais étalé (est_etale reste False),
        # le bonus x2 de fin_de_mene s'applique normalement.
        joueur_actuel = self.joueurs[self.joueur_actif]

        if joueur_actuel.est_etale:
            print(f"{joueur_actuel.nom} est déjà étalé, il ne peut pas 'finir sec'.")
            return False

        arrangement = chercher_partition_complete(joueur_actuel.main, self.niveau_actuel)
        if arrangement is None:
            print(f"La main de {joueur_actuel.nom} ne se répartit pas exactement selon le contrat.")
            return False

        self.tapis.extend(arrangement)
        joueur_actuel.main = []
        self.log(f"{joueur_actuel.nom} retourne toute sa main d'un coup et termine la manche, sans jamais s'être étalé !")
        self.fin_de_mene(joueur_actuel)
        return True

    def fin_de_mene(self, joueur_gagnant):
        # CORRECTION : c'est l'inverse de ce que j'avais codé — le gagnant de
        # la mène ne marque RIEN, ce sont les perdants qui encaissent CHACUN
        # les points de LEUR PROPRE main (pas un total reversé au gagnant).
        # Comme au golf : moins on a de points, mieux c'est, et c'est le
        # score total le plus BAS qui l'emporte à la fin de la partie (voir
        # gagnant_partie ci-dessous).
        etait_etale = joueur_gagnant.est_etale
        details_perdants = []

        for j in self.joueurs:
            if j != joueur_gagnant:
                points_perdant = sum(carte.points for carte in j.main)
                if not etait_etale:
                    points_perdant *= 2
                    print(f"Bonus ! {joueur_gagnant.nom} a fini sec : les points de {j.nom} sont doublés !")
                j.score += points_perdant
                details_perdants.append({"nom": j.nom, "points": points_perdant})
                print(f"{j.nom} marque {points_perdant} points ce tour-ci (score total : {j.score}).")

        print(f"🏆 {joueur_gagnant.nom} remporte la mène et ne marque aucun point !\n")
        self.log(f"Fin de la mène : {joueur_gagnant.nom} gagne (0 point), les autres joueurs marquent les points de leur main.")

        niveau_termine = self.niveau_actuel
        self.niveau_actuel += 1

        # AJOUT : instantané du résultat de cette mène, lu par server.py juste
        # après l'appel qui a déclenché cette fin de mène, pour afficher une
        # animation de transition côté interface (qui a gagné, le classement,
        # le prochain contrat).
        resultat = {
            "gagnant": joueur_gagnant.nom,
            "bonus_fini_sec": not etait_etale,
            "details_perdants": details_perdants,
            "niveau_termine": niveau_termine,
            "description_contrat_termine": DESCRIPTIONS_CONTRATS.get(niveau_termine, ""),
            # Classement du MEILLEUR au moins bon : score le plus bas d'abord.
            "classement": sorted(
                [{"nom": j.nom, "score": j.score} for j in self.joueurs],
                key=lambda x: x["score"],
            ),
        }

        if self.niveau_actuel > 11:
            print("========================================")
            print("🏁 FIN DE LA PARTIE GLOBALE !")
            print("========================================")
            gagnant_partie = self.gagnant_partie()
            print(f"Le grand vainqueur est {gagnant_partie.nom} avec le score le plus bas : {gagnant_partie.score} points !")
            self.log(f"Partie terminée ! Vainqueur : {gagnant_partie.nom} (score le plus bas : {gagnant_partie.score} points).")
            resultat["partie_terminee"] = True
            resultat["prochain_niveau"] = None
            resultat["prochain_contrat_description"] = None
            self.dernier_resultat_mene = resultat
            return

        print(f"--- TOUT LE MONDE PASSE AU CONTRAT {self.niveau_actuel} ! ---\n")

        self.pioche = []
        self.defausse = []
        self.tapis = []

        for j in self.joueurs:
            j.main = []
            j.est_etale = False

        # AJOUT : le distributeur tourne à chaque manche (sinon le même
        # joueur déciderait toujours en premier de prendre ou non la carte
        # retournée). entamer_manche() s'occupe de tout le reste : distribuer,
        # retourner une carte, et désigner qui commence.
        self.index_distributeur = (self.index_distributeur + 1) % len(self.joueurs)
        self.entamer_manche()

        resultat["partie_terminee"] = False
        resultat["prochain_niveau"] = self.niveau_actuel
        resultat["prochain_contrat_description"] = DESCRIPTIONS_CONTRATS.get(self.niveau_actuel, "")
        self.dernier_resultat_mene = resultat

    def est_terminee(self):
        # AJOUT
        return self.niveau_actuel > 11

    def gagnant_partie(self):
        # CORRECTION : le score le plus BAS gagne (les points sont une
        # pénalité, pas une récompense).
        return min(self.joueurs, key=lambda j: j.score)


# --- LES FONCTIONS DE VÉRIFICATION ---
#
# AJOUT (v2) : plusieurs corrections suite à des parties jouées en vrai :
#   - un "2" peut être utilisé soit comme un joker, soit comme une vraie
#     carte de valeur 2 à sa place naturelle (au choix, selon ce qui rend le
#     groupe valide) — auparavant il était TOUJOURS considéré comme joker,
#     ce qui empêchait par exemple "As, 2 (vraie carte), 2 (joker)".
#   - l'As peut aussi servir de carte haute, juste après le Roi
#     (Valet, Dame, Roi, As).
#   - dans un brelan, deux jokers ne doivent jamais se "suivre" non plus :
#     avec R cartes réelles, on ne peut pas avoir plus de R+1 jokers (il faut
#     pouvoir les intercaler entre/autour des cartes réelles).


def _sequence_valide_depuis_valeurs(valeurs_triees, nb_jokers):
    """Cœur du calcul pour une suite : étant donné des valeurs réelles déjà
    triées et un nombre de jokers disponibles, dit si ça forme une suite
    valide (trous d'une seule carte comblés un par un, jamais deux jokers
    d'affilée)."""
    jokers_restants = nb_jokers
    for i in range(len(valeurs_triees) - 1):
        ecart = valeurs_triees[i + 1] - valeurs_triees[i]
        if ecart == 0:
            return False
        elif ecart == 2:
            if jokers_restants > 0:
                jokers_restants -= 1
            else:
                return False
        elif ecart >= 3:
            return False

    # Au plus 1 joker "en trop" (qui étend la suite au-delà du strict
    # nécessaire) : au-delà, impossible de garantir qu'ils ne se suivent pas.
    if jokers_restants > 1:
        return False
    return True


def brelan_valide(liste_cartes, taille_voulue):
    if len(liste_cartes) < taille_voulue:
        return False

    jokers = []
    cartes_normales = []

    for carte in liste_cartes:
        if carte.valeur == 0 or carte.valeur == 2:
            jokers.append(carte)
        else:
            cartes_normales.append(carte)

    if len(cartes_normales) > 0:
        valeur_reference = cartes_normales[0].valeur
        for carte in cartes_normales:
            if carte.valeur != valeur_reference:
                return False

    # CORRECTION : comme pour les suites, deux jokers ne doivent jamais se
    # retrouver côte à côte. Un brelan n'a pas d'ordre imprimé sur la table,
    # mais on peut toujours se représenter les cartes réelles posées avec un
    # "emplacement" avant, entre chaque paire, et après : avec R cartes
    # réelles, ça fait R+1 emplacements, donc au plus R+1 jokers (au-delà, au
    # moins deux jokers doivent forcément partager un même emplacement, donc
    # se toucher). Ça corrige au passage un cas limite : un groupe qui ne
    # contiendrait QUE des jokers (R=0) n'est plus jamais valide pour une
    # taille de 3+ (max 1 joker autorisé quand R=0).
    if len(jokers) > len(cartes_normales) + 1:
        return False

    return True


def suite_valide(liste_cartes, taille_voulue):
    if len(liste_cartes) < taille_voulue:
        return False

    jokers_purs = [c for c in liste_cartes if c.valeur == 0]
    deux = [c for c in liste_cartes if c.valeur == 2]
    autres = [c for c in liste_cartes if c.valeur not in (0, 2)]

    if not autres and not deux:
        return False  # rien pour former une suite (que des jokers "purs")

    # On essaie toutes les combinaisons possibles : chaque "2" peut être
    # utilisé comme un joker, OU comme une vraie carte de valeur 2 (auquel
    # cas sa couleur doit correspondre à la suite, comme toute carte
    # normale). Le nombre de "2" dans un même groupe est toujours petit (au
    # pire 8 dans tout le jeu), donc essayer toutes les combinaisons reste
    # très rapide.
    for choix in itertools.product([False, True], repeat=len(deux)):
        cartes_normales = list(autres)
        nb_jokers = len(jokers_purs)

        for utilise_comme_carte_normale, carte in zip(choix, deux):
            if utilise_comme_carte_normale:
                cartes_normales.append(carte)
            else:
                nb_jokers += 1

        if not cartes_normales:
            continue  # aucune carte "normale" dans cette combinaison -> pas de couleur de référence

        couleur_suite = cartes_normales[0].couleur
        if any(c.couleur != couleur_suite for c in cartes_normales):
            continue

        valeurs = sorted(c.valeur for c in cartes_normales)
        if _sequence_valide_depuis_valeurs(valeurs, nb_jokers):
            return True

        # L'As peut aussi être une carte haute (Valet, Dame, Roi, As).
        if 1 in valeurs:
            valeurs_as_haut = sorted(14 if v == 1 else v for v in valeurs)
            if _sequence_valide_depuis_valeurs(valeurs_as_haut, nb_jokers):
                return True

    return False


def _valeurs_effectives(groupe):
    """AJOUT : valeurs réelles d'un groupe déjà validé, l'As étant résolu
    bas ou haut selon l'interprétation qui rend le groupe cohérent (utile
    pour savoir comment le groupe peut être prolongé)."""
    reels = [c.valeur for c in groupe if c.valeur not in (0, 2)]
    if 1 not in reels:
        return sorted(reels)

    nb_jokers = sum(1 for c in groupe if c.valeur in (0, 2))
    bas = sorted(reels)
    haut = sorted(14 if v == 1 else v for v in reels)
    if _sequence_valide_depuis_valeurs(haut, nb_jokers) and not _sequence_valide_depuis_valeurs(bas, nb_jokers):
        return haut
    return bas


def _extension_suite_ok(groupe_existant, nouvelle_carte, position):
    """AJOUT : un groupe déjà posé sur la table est, par construction, déjà
    une suite valide SANS trou interne ouvert (sinon il n'aurait pas été
    valide). La SEULE façon d'y ajouter une carte est donc de prolonger une
    extrémité — jamais de "glisser" une carte au milieu. Cette fonction dit
    si nouvelle_carte peut prolonger le côté demandé ('debut' ou 'fin').

    Corrige deux bugs trouvés en jouant :
    - une carte réelle ne doit jamais pouvoir prendre la place d'un joker
      qui occupe déjà cette extrémité (ex: 5,6,7,[joker pour 8] -> un vrai 8
      est refusé, le joker est déjà là) ;
    - deux jokers ne doivent jamais se toucher, mais s'ils sont chacun à une
      extrémité opposée d'une série de cartes réelles consécutives, ce n'est
      pas un souci puisqu'ils ne se touchent pas (ex: [joker],V,D,R accepte
      bien un second joker en position 'fin', juste pas en 'debut')."""
    if not groupe_existant:
        return False

    carte_bord = groupe_existant[0] if position == "debut" else groupe_existant[-1]

    # Toute carte (réelle ou joker) qui prolongerait une extrémité déjà
    # occupée par un joker/2 est refusée : cette place est déjà prise, et un
    # joker ne peut jamais se retrouver à côté d'un autre joker/2.
    if carte_bord.valeur in (0, 2):
        return False

    if nouvelle_carte.valeur in (0, 2):
        valeurs = _valeurs_effectives(groupe_existant)
        if not valeurs:
            return False
        return (min(valeurs) > 1) if position == "debut" else (max(valeurs) < 14)

    couleur_ref = next((c.couleur for c in groupe_existant if c.valeur not in (0, 2)), None)
    if couleur_ref is not None and nouvelle_carte.couleur != couleur_ref:
        return False

    valeurs = _valeurs_effectives(groupe_existant)
    if not valeurs:
        return False

    if position == "debut":
        return nouvelle_carte.valeur == min(valeurs) - 1

    if nouvelle_carte.valeur == max(valeurs) + 1:
        return True
    if max(valeurs) == 13 and nouvelle_carte.valeur == 1:
        return True  # As haut après un Roi
    return False


def verifier_contrat(niveau_actuel, groupes_proposes):
    contrat = CONTRATS.get(niveau_actuel)
    if not contrat:
        return False

    if len(groupes_proposes) != len(contrat):
        return False

    for i in range(len(contrat)):
        type_voulu = contrat[i][0]
        taille_voulue = contrat[i][1]
        cartes = groupes_proposes[i]

        if type_voulu == "brelan":
            if not brelan_valide(cartes, taille_voulue):
                return False

        elif type_voulu == "suite":
            if not suite_valide(cartes, taille_voulue):
                return False

    return True


def verifier_contrat_toute_permutation(niveau_actuel, groupes_proposes):
    # AJOUT : ta fonction verifier_contrat attend les groupes DANS L'ORDRE du
    # dictionnaire CONTRATS (ex: contrat 3 = d'abord la suite, puis le brelan).
    # Demander ça au joueur dans l'interface serait pénible ("range bien tes
    # groupes dans le bon ordre !"), donc côté serveur on essaie tous les
    # arrangements possibles des groupes proposés et on accepte si l'un d'eux
    # correspond. Le nombre de groupes est petit (2 ou 3 max), donc c'est
    # négligeable en performance.
    from itertools import permutations
    for arrangement in permutations(groupes_proposes):
        if verifier_contrat(niveau_actuel, list(arrangement)):
            return list(arrangement)
    return None


def chercher_partition_complete(cartes, niveau_actuel):
    # AJOUT : pour "finir sec" (voir action_finir_sec), il faut vérifier s'il
    # existe une façon de répartir TOUTES les cartes de la main en groupes qui
    # correspondent exactement au contrat demandé — sans qu'aucune carte ne
    # reste de côté. C'est un problème de partition : on essaie, carte par
    # carte, de la placer dans un groupe déjà commencé ou d'en ouvrir un
    # nouveau (dans la limite du nombre de groupes attendus par le contrat).
    #
    # Astuce de performance : on n'ouvre jamais un groupe "au hasard", on
    # ouvre toujours le groupe vide de plus petit index disponible. Ça évite
    # d'explorer plein de fois la même répartition juste réétiquetée
    # (mettre A dans le groupe 1 et B dans le groupe 2, ou l'inverse, revient
    # au même puisque verifier_contrat_toute_permutation essaie de toute façon
    # tous les arrangements). Avec une main de 12 cartes et jusqu'à 3 groupes
    # (le contrat le plus exigeant), ça reste très rapide.
    contrat = CONTRATS.get(niveau_actuel)
    if not contrat:
        return None

    nb_groupes = len(contrat)
    cartes = list(cartes)

    if len(cartes) < sum(taille for _, taille in contrat):
        return None  # pas assez de cartes pour espérer remplir le contrat

    resultat = {"arrangement": None}

    def explorer(index, groupes, nb_ouverts):
        if resultat["arrangement"] is not None:
            return
        if index == len(cartes):
            if nb_ouverts == nb_groupes:
                arrangement = verifier_contrat_toute_permutation(niveau_actuel, groupes)
                if arrangement is not None:
                    resultat["arrangement"] = [list(g) for g in arrangement]
            return

        carte = cartes[index]

        for i in range(nb_ouverts):
            groupes[i].append(carte)
            explorer(index + 1, groupes, nb_ouverts)
            groupes[i].pop()
            if resultat["arrangement"] is not None:
                return

        if nb_ouverts < nb_groupes:
            groupes[nb_ouverts].append(carte)
            explorer(index + 1, groupes, nb_ouverts + 1)
            groupes[nb_ouverts].pop()

    explorer(0, [[] for _ in range(nb_groupes)], 0)
    return resultat["arrangement"]

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
        # CORRECTION : renvoie désormais (succes, message) au lieu d'un
        # simple booléen, pour que le joueur sache PRÉCISÉMENT pourquoi un
        # étalement est refusé au lieu d'un message générique à chaque fois.
        joueur_actuel = self.joueurs[self.joueur_actif]

        if joueur_actuel.est_etale:
            print(f"{joueur_actuel.nom} est déjà étalé !")
            return False, "Tu es déjà étalé : impossible de le refaire une seconde fois dans la même manche."

        if verifier_contrat(self.niveau_actuel, groupes_proposes):
            # CORRECTION : il faut toujours garder au moins une carte "morte"
            # à défausser normalement pour signifier qu'on a fini — ce n'est
            # jamais l'étalement lui-même qui doit vider la main à 0.
            nb_cartes_utilisees = sum(len(groupe) for groupe in groupes_proposes)
            if nb_cartes_utilisees >= len(joueur_actuel.main):
                print(f"{joueur_actuel.nom} doit garder au moins une carte à défausser pour terminer.")
                return False, "Il faut garder au moins une carte en main pour pouvoir la défausser normalement : ton étalement utilise toute ta main."

            print(f"Félicitations {joueur_actuel.nom} ! Contrat validé.")
            joueur_actuel.est_etale = True

            for groupe in groupes_proposes:
                for carte in groupe:
                    if carte in joueur_actuel.main:
                        joueur_actuel.main.remove(carte)

            # AJOUT : chaque groupe posé mémorise qui l'a étalé, pour que
            # l'affichage puisse regrouper le tapis par "zone" de joueur.
            for groupe in groupes_proposes:
                self.tapis.append({"proprietaire": joueur_actuel.nom, "cartes": groupe})
            self.log(f"{joueur_actuel.nom} a validé son contrat et s'est étalé !")
            return True, None
        else:
            print(f"Échec ! Le contrat proposé par {joueur_actuel.nom} est invalide.")
            raison = diagnostiquer_etalement(self.niveau_actuel, groupes_proposes)
            return False, raison or "Cet étalement ne correspond pas au contrat demandé."

    def action_rajouter(self, index_carte_main, index_groupe_tapis, position="fin"):
        # CORRECTION : renvoie désormais (succes, message) au lieu d'un
        # simple booléen — message explique PRÉCISÉMENT pourquoi un rajout
        # échoue (couleur, valeur attendue, joker à côté d'un joker, etc.)
        # au lieu du générique "cette carte ne peut pas être ajoutée".
        joueur_actuel = self.joueurs[self.joueur_actif]

        if not joueur_actuel.est_etale:
            print(f"Action refusée : {joueur_actuel.nom} doit s'étaler avant de faire un rajout.")
            return False, "Tu dois d'abord t'étaler toi-même avant de pouvoir rajouter une carte sur la table."

        # AJOUT : garde-fous sur les index (le code original suppose des index
        # toujours valides ; en ligne, mieux vaut ne jamais faire confiance
        # aveuglément à ce qu'envoie un navigateur).
        if not (0 <= index_carte_main < len(joueur_actuel.main)):
            return False, "Cette carte n'est plus dans ta main."
        if not (0 <= index_groupe_tapis < len(self.tapis)):
            return False, "Ce groupe n'existe plus sur la table."

        # CORRECTION : même principe que pour action_etaler — il faut
        # toujours garder au moins une carte "morte" à défausser normalement.
        # Un rajout ne doit jamais être LA carte qui vide la main à 0.
        if len(joueur_actuel.main) <= 1:
            print(f"{joueur_actuel.nom} doit garder sa dernière carte pour la défausser.")
            return False, "Il faut garder au moins une carte en main pour la défausser normalement : impossible de rajouter ta toute dernière carte."

        carte = joueur_actuel.main[index_carte_main]
        groupe_cible = self.tapis[index_groupe_tapis]["cartes"]

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
                self.tapis[index_groupe_tapis]["cartes"].insert(0, carte_jetee)
            else:
                self.tapis[index_groupe_tapis]["cartes"].append(carte_jetee)
            print(f"Rajout réussi ! {carte} a été ajoutée.")
            self.log(f"{joueur_actuel.nom} a rajouté {carte_jetee} sur le tapis.")
            return True, None
        else:
            print("Rajout impossible : la carte ne rentre pas dans ce groupe.")
            if carte.valeur in (0, 2) and not _groupe_est_brelan(groupe_cible):
                raison = diagnostiquer_rajout_joker(groupe_cible, carte, position)
            else:
                raison = diagnostiquer_rajout_carte_reelle(groupe_cible, carte)
            return False, raison or "Cette carte ne peut pas être ajoutée à ce groupe."

    def positions_rajout_possibles(self, index_carte_main, index_groupe_tapis):
        # AJOUT : vérification "à blanc" (ne modifie rien) utilisée par le
        # client avant d'afficher le choix "avant / après" pour un joker sur
        # une suite — pour ne JAMAIS poser la question si aucune des deux
        # options ne peut de toute façon fonctionner (demande explicite :
        # "ne pas demander la question avant/après puisqu'il ne peut aller
        # nulle part, mettre le message d'erreur directement").
        joueur_actuel = self.joueurs[self.joueur_actif]
        if not (0 <= index_carte_main < len(joueur_actuel.main)):
            return {"debut": False, "fin": False}
        if not (0 <= index_groupe_tapis < len(self.tapis)):
            return {"debut": False, "fin": False}

        carte = joueur_actuel.main[index_carte_main]
        groupe_cible = self.tapis[index_groupe_tapis]["cartes"]
        return {
            "debut": _extension_suite_ok(groupe_cible, carte, "debut"),
            "fin": _extension_suite_ok(groupe_cible, carte, "fin"),
        }

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
            return False, "Tu es déjà étalé : ce coup spécial n'est possible que si tu n'as encore jamais posé de groupe."

        arrangement = chercher_partition_complete(joueur_actuel.main, self.niveau_actuel)
        if arrangement is None:
            print(f"La main de {joueur_actuel.nom} ne se répartit pas exactement selon le contrat.")
            return (
                False,
                f"Ta main ne se répartit pas exactement selon le contrat demandé "
                f"({DESCRIPTIONS_CONTRATS.get(self.niveau_actuel, '')}) sans qu'il reste une carte de côté — "
                f"vérifie qu'aucune carte ne traîne en trop ou qu'il n'en manque pas une pour fermer un groupe.",
            )

        for groupe in arrangement:
            self.tapis.append({"proprietaire": joueur_actuel.nom, "cartes": groupe})
        joueur_actuel.main = []
        self.log(f"{joueur_actuel.nom} retourne toute sa main d'un coup et termine la manche, sans jamais s'être étalé !")
        self.fin_de_mene(joueur_actuel)
        return True, None

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


def _valeurs_conceptuelles_groupe(groupe):
    """AJOUT (correction bug As-de-carreau) : reconstruit la valeur
    conceptuelle de CHAQUE position du groupe, joker/2 compris — pas
    seulement celle des cartes réelles comme le faisait l'ancienne
    _valeurs_effectives. C'est indispensable dès qu'un joker se trouve plus
    à l'extérieur que la carte réelle la plus extrême : ignorer sa position
    faisait croire que le "bord" du groupe était la carte réelle, alors que
    c'est le joker qui occupe réellement cette extrémité.

    Principe : dans une suite valide, la carte à l'index i a toujours la
    valeur (v_min + i) où v_min est la valeur conceptuelle de la toute
    première position. On calcule v_min à partir de n'importe quelle carte
    réelle (valeur_reelle - son_index), en essayant l'As bas (1) puis l'As
    haut (14) — l'interprétation qui donne le MÊME v_min pour toutes les
    cartes réelles du groupe est la bonne. Renvoie la liste des valeurs
    conceptuelles (une par position, longueur = len(groupe)), ou None si
    le groupe ne contient aucune carte réelle exploitable."""
    reels = [(i, c.valeur) for i, c in enumerate(groupe) if c.valeur not in (0, 2)]
    if not reels:
        return None

    for as_haut in (False, True):
        candidats = {(14 if (as_haut and v == 1) else v) - i for i, v in reels}
        if len(candidats) == 1:
            v_min = candidats.pop()
            return [v_min + i for i in range(len(groupe))]

    return None


def _extension_suite_ok(groupe_existant, nouvelle_carte, position):
    """AJOUT : un groupe déjà posé sur la table est, par construction, déjà
    une suite valide SANS trou interne ouvert (sinon il n'aurait pas été
    valide). La SEULE façon d'y ajouter une carte est donc de prolonger une
    extrémité — jamais de "glisser" une carte au milieu. Cette fonction dit
    si nouvelle_carte peut prolonger le côté demandé ('debut' ou 'fin').

    Règles respectées :
    - une carte réelle ne doit jamais pouvoir prendre la place d'un joker
      qui occupe déjà cette extrémité (ex: 5,6,7,[joker pour 8] -> un vrai 8
      est refusé, le joker représente déjà ce 8) ;
    - deux jokers ne doivent jamais se toucher — mais CETTE restriction ne
      s'applique QUE quand la nouvelle carte est elle-même un joker/2. Une
      carte RÉELLE peut parfaitement prolonger un groupe dont le bord est
      déjà un joker (ex: As de Carreau avant un 2 de Pique utilisé comme
      joker en tête d'une suite de Carreau) — c'était le bug corrigé ici,
      l'ancienne version refusait ça à tort pour toute carte, réelle ou pas."""
    if not groupe_existant:
        return False

    carte_bord = groupe_existant[0] if position == "debut" else groupe_existant[-1]

    if nouvelle_carte.valeur in (0, 2) and carte_bord.valeur in (0, 2):
        # Un joker/2 ne doit jamais se retrouver à côté d'un autre joker/2.
        return False

    valeurs = _valeurs_conceptuelles_groupe(groupe_existant)
    if not valeurs:
        return False
    v_bord = valeurs[0] if position == "debut" else valeurs[-1]
    v_attendue = v_bord - 1 if position == "debut" else v_bord + 1

    if nouvelle_carte.valeur in (0, 2):
        # Un joker/2 peut représenter n'importe quelle valeur manquante,
        # tant qu'elle reste dans la plage 1 (As bas) à 14 (As haut).
        return 1 <= v_attendue <= 14

    couleur_ref = next((c.couleur for c in groupe_existant if c.valeur not in (0, 2)), None)
    if couleur_ref is not None and nouvelle_carte.couleur != couleur_ref:
        return False

    if nouvelle_carte.valeur == v_attendue:
        return True
    if v_attendue == 14 and nouvelle_carte.valeur == 1:
        return True  # As haut après un Roi
    return False


# =========================================================================
# AJOUT : diagnostics détaillés — ces fonctions ne CHANGENT aucune règle
# existante, elles expliquent juste en français pourquoi une tentative déjà
# jugée invalide par les fonctions ci-dessus échoue précisément (demande
# explicite : "pour chaque erreur possible, un message qui explique pourquoi
# je refuse"). Elles ne sont appelées qu'APRÈS un échec, jamais pour décider
# si c'est valide ou non — donc aucun risque de divergence avec les vraies
# règles.
# =========================================================================

def _nom_valeur_conceptuelle(v):
    # La valeur 14 n'existe pour aucune carte réelle : c'est la façon interne
    # de représenter "l'As utilisé en carte haute, après le Roi".
    if v == 14:
        return "As (en carte haute, après le Roi)"
    return nom_valeur(v)


def _diagnostiquer_sequence(valeurs_triees, nb_jokers):
    """Même calcul que _sequence_valide_depuis_valeurs, mais explique le
    souci au lieu de renvoyer juste False. Renvoie None si en fait valide
    (ne devrait pas arriver si on l'appelle après un échec confirmé)."""
    jokers_restants = nb_jokers
    for i in range(len(valeurs_triees) - 1):
        ecart = valeurs_triees[i + 1] - valeurs_triees[i]
        if ecart == 0:
            return f"Deux de tes cartes réelles ont la même valeur ({_nom_valeur_conceptuelle(valeurs_triees[i])}) : une suite ne peut pas avoir de doublon."
        elif ecart == 2:
            if jokers_restants > 0:
                jokers_restants -= 1
            else:
                return (
                    f"Il manque une carte entre {_nom_valeur_conceptuelle(valeurs_triees[i])} et "
                    f"{_nom_valeur_conceptuelle(valeurs_triees[i + 1])}, et tu n'as plus de joker "
                    f"disponible pour la remplacer."
                )
        elif ecart >= 3:
            return (
                f"Il manque plus d'une carte entre {_nom_valeur_conceptuelle(valeurs_triees[i])} et "
                f"{_nom_valeur_conceptuelle(valeurs_triees[i + 1])} : un seul joker ne peut combler "
                f"qu'un trou d'une seule carte à la fois."
            )

    if jokers_restants > 1:
        return (
            f"Il te reste {jokers_restants} joker(s) de trop pour cette suite : au-delà d'un seul "
            f"joker en plus du nécessaire, deux d'entre eux se retrouveraient forcément côte à côte."
        )
    return None


def diagnostiquer_brelan(cartes, taille_voulue):
    """Explique pourquoi `cartes` ne forme pas un brelan valide de
    `taille_voulue` cartes. À n'appeler qu'après un échec de brelan_valide."""
    if len(cartes) != taille_voulue:
        return f"il faut exactement {taille_voulue} carte{'s' if taille_voulue > 1 else ''} pour ce brelan (tu en as {len(cartes)})."

    jokers = [c for c in cartes if c.valeur in (0, 2)]
    normales = [c for c in cartes if c.valeur not in (0, 2)]

    if normales:
        valeurs_distinctes = sorted(set(c.valeur for c in normales))
        if len(valeurs_distinctes) > 1:
            exemples = " et ".join(_nom_valeur_conceptuelle(v) for v in valeurs_distinctes)
            return f"un brelan doit être composé de cartes de même valeur (hors jokers) : tu mélanges {exemples}."

    if len(jokers) > len(normales) + 1:
        return (
            f"trop de jokers pour ce brelan : avec {len(normales)} carte{'s' if len(normales) != 1 else ''} "
            f"réelle{'s' if len(normales) != 1 else ''}, impossible de placer {len(jokers)} joker(s) sans "
            f"que deux d'entre eux ne se touchent."
        )

    return None  # ne devrait pas arriver si on appelle ça après un échec confirmé


def diagnostiquer_suite(cartes, taille_voulue):
    """Explique pourquoi `cartes` ne forme pas une suite valide de
    `taille_voulue` cartes. À n'appeler qu'après un échec de suite_valide."""
    if len(cartes) != taille_voulue:
        return f"il faut exactement {taille_voulue} carte{'s' if taille_voulue > 1 else ''} pour cette suite (tu en as {len(cartes)})."

    jokers_purs = [c for c in cartes if c.valeur == 0]
    deux = [c for c in cartes if c.valeur == 2]
    autres = [c for c in cartes if c.valeur not in (0, 2)]

    if not autres and not deux:
        return "une suite a besoin d'au moins une carte réelle pour savoir dans quelle couleur et à quelles valeurs elle se joue."

    meilleure_raison = None
    couleurs_vues = set()
    for choix in itertools.product([False, True], repeat=len(deux)):
        cartes_normales = list(autres)
        nb_jokers = len(jokers_purs)
        for utilise_comme_carte_normale, carte in zip(choix, deux):
            if utilise_comme_carte_normale:
                cartes_normales.append(carte)
            else:
                nb_jokers += 1

        if not cartes_normales:
            continue

        couleurs = set(c.couleur for c in cartes_normales)
        if len(couleurs) > 1:
            couleurs_vues |= couleurs
            continue

        valeurs = sorted(c.valeur for c in cartes_normales)
        raison = _diagnostiquer_sequence(valeurs, nb_jokers)
        if raison is None and 1 in valeurs:
            valeurs_haut = sorted(14 if v == 1 else v for v in valeurs)
            raison_haut = _diagnostiquer_sequence(valeurs_haut, nb_jokers)
            if raison_haut is None:
                return None  # en fait valide (ne devrait pas arriver)
        elif raison is None:
            return None  # en fait valide (ne devrait pas arriver)

        if meilleure_raison is None:
            meilleure_raison = raison

    if meilleure_raison is None and len(couleurs_vues) > 1:
        exemples = " et ".join(sorted(couleurs_vues))
        return f"toutes les cartes réelles d'une suite doivent être de la même couleur (tu mélanges {exemples})."

    return meilleure_raison or "cette suite ne respecte pas les règles (couleur, ordre des valeurs, ou trop de jokers)."


def diagnostiquer_groupe(cartes, type_voulu, taille_voulue):
    if type_voulu == "brelan":
        return diagnostiquer_brelan(cartes, taille_voulue)
    return diagnostiquer_suite(cartes, taille_voulue)


def diagnostiquer_etalement(niveau_actuel, groupes_proposes):
    """AJOUT : explique pourquoi un étalement proposé ne correspond pas au
    contrat demandé. Diagnostique chaque groupe À SA POSITION EXACTE (le
    "Groupe 1" affiché à l'écran correspond toujours au 1er composant du
    contrat, etc. — l'interface étiquette déjà chaque zone en conséquence),
    donc le message pointe directement vers ce que le joueur voit."""
    contrat = CONTRATS.get(niveau_actuel)
    if not contrat:
        return "Contrat inconnu."

    if len(groupes_proposes) != len(contrat):
        return (
            f"Ce contrat demande {len(contrat)} groupe(s) ({DESCRIPTIONS_CONTRATS.get(niveau_actuel, '')}), "
            f"tu en as proposé {len(groupes_proposes)}."
        )

    messages = []
    for i in range(len(contrat)):
        type_voulu, taille_voulue = contrat[i]
        raison = diagnostiquer_groupe(groupes_proposes[i], type_voulu, taille_voulue)
        if raison:
            nom_type = "suite" if type_voulu == "suite" else "brelan"
            messages.append(f"Groupe {i + 1} ({nom_type} attendu) : {raison}")

    return " ".join(messages) if messages else None


def _groupe_est_brelan(groupe):
    # AJOUT : même définition que estGroupeBrelan() côté app.js — basée sur
    # les cartes SANS AMBIGUÏTÉ (ni Joker, ni "2"), pour rester cohérent avec
    # l'affichage.
    sans_ambiguite = [c for c in groupe if c.valeur not in (0, 2)]
    return len(sans_ambiguite) >= 2 and all(c.valeur == sans_ambiguite[0].valeur for c in sans_ambiguite)


def diagnostiquer_rajout_carte_reelle(groupe_cible, carte):
    """Explique pourquoi une carte RÉELLE (ni Joker, ni "2") ne peut
    rejoindre `groupe_cible` déjà posé sur la table — qu'elle ait été
    essayée en 'debut' ou en 'fin' (les deux ont déjà échoué à ce stade)."""
    if _groupe_est_brelan(groupe_cible):
        normales = [c for c in groupe_cible if c.valeur not in (0, 2)]
        if normales and carte.valeur != normales[0].valeur:
            return f"Ce groupe est un brelan de {_nom_valeur_conceptuelle(normales[0].valeur)} : {carte} ne peut pas s'y ajouter."
        return "Il y a déjà trop de jokers dans ce brelan pour en ajouter un de plus sans qu'ils ne se touchent."

    couleur_ref = next((c.couleur for c in groupe_cible if c.valeur not in (0, 2)), None)
    if couleur_ref is not None and carte.couleur != couleur_ref:
        return f"Cette suite est en {couleur_ref} : {carte} n'est pas de cette couleur."

    valeurs = _valeurs_conceptuelles_groupe(groupe_cible)
    if not valeurs:
        return "Ce groupe ne contient pas assez de cartes réelles pour savoir où le prolonger."

    attendu_debut = valeurs[0] - 1
    attendu_fin = valeurs[-1] + 1
    noms_attendus = []
    if 1 <= attendu_debut:
        noms_attendus.append(f"{_nom_valeur_conceptuelle(attendu_debut)} (avant la première carte)")
    if attendu_fin <= 14:
        noms_attendus.append(f"{_nom_valeur_conceptuelle(attendu_fin)} (après la dernière)")

    if not noms_attendus:
        return "Cette suite est déjà complète des deux côtés (rien avant l'As, rien après l'As en carte haute)."

    return f"Pour prolonger cette suite, il faudrait une carte de valeur {' ou '.join(noms_attendus)} — {carte} ne convient pas."


def diagnostiquer_rajout_joker(groupe_cible, carte, position):
    """Explique pourquoi un Joker/"2" ne peut pas prolonger `groupe_cible` du
    côté demandé ('debut' ou 'fin') — pour un groupe qui n'est pas un
    brelan (un brelan ne demande pas de position, voir
    diagnostiquer_rajout_carte_reelle pour ce cas)."""
    carte_bord = groupe_cible[0] if position == "debut" else groupe_cible[-1]
    if carte_bord.valeur in (0, 2):
        return "Un joker ne peut jamais se retrouver juste à côté d'un autre joker : il y en a déjà un à cet endroit."

    valeurs = _valeurs_conceptuelles_groupe(groupe_cible)
    if not valeurs:
        return "Ce groupe ne contient pas assez de cartes réelles pour savoir où le prolonger."

    v_bord = valeurs[0] if position == "debut" else valeurs[-1]
    v_attendue = v_bord - 1 if position == "debut" else v_bord + 1
    if not (1 <= v_attendue <= 14):
        cote = "avant l'As" if v_attendue < 1 else "après l'As en carte haute"
        return f"Cette suite est déjà complète de ce côté : il n'y a rien {cote}."

    return None  # ne devrait pas arriver si on appelle ça après un échec confirmé


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

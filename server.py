"""
Serveur du jeu en ligne.

Ce fichier NE contient PAS les règles du jeu (elles sont dans game_engine.py,
quasiment inchangé) : il s'occupe uniquement de faire communiquer les
navigateurs entre eux (salons, tour de jeu, diffusion de l'état de la partie).

Lancement local :   python server.py
Le serveur écoute sur le port défini par la variable d'environnement PORT
(10000 par défaut, ce qui correspond à ce qu'attendent des hébergeurs comme
Render).
"""

import os
import random
import string
from itertools import permutations

from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO, join_room, emit

import game_engine as ge

app = Flask(__name__, static_folder=".", static_url_path="")
app.config["SECRET_KEY"] = "rami-famille-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# --- État en mémoire de tous les salons -------------------------------------
# rooms[code] = {
#     "code": str,
#     "partie": Partie | None,          # None tant que la partie n'a pas démarré
#     "pseudos": [str, ...],            # ordre d'arrivée, sert de base à Partie(...)
#     "hote": str,                      # pseudo du joueur qui peut lancer la partie
#     "sid_de": {pseudo: sid},
#     "pseudo_de": {sid: pseudo},
#     "demarree": bool,
# }
rooms = {}

MIN_JOUEURS = 2
MAX_JOUEURS = 6


def generer_code():
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        if code not in rooms:
            return code


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# --- Aides internes ----------------------------------------------------------

def erreur(message):
    emit("erreur", {"message": message})


def salle_de(code):
    return rooms.get(code)


def etat_lobby(salle):
    return {
        "code": salle["code"],
        "hote": salle["hote"],
        "joueurs": list(salle["pseudos"]),
        "min_joueurs": MIN_JOUEURS,
        "max_joueurs": MAX_JOUEURS,
    }


def diffuser_lobby(code):
    salle = salle_de(code)
    if not salle:
        return
    socketio.emit("etat_lobby", etat_lobby(salle), room=code)


def etat_pour(partie, pseudo):
    """Construit l'état de jeu du point de vue d'un joueur précis :
    il voit sa propre main en détail, mais seulement le nombre de cartes
    des autres joueurs."""
    moi = next((j for j in partie.joueurs if j.nom == pseudo), None)
    joueur_actif = partie.joueurs[partie.joueur_actif]
    distributeur = partie.joueurs[partie.index_distributeur]

    return {
        "niveau": partie.niveau_actuel,
        "contrat_description": ge.DESCRIPTIONS_CONTRATS.get(partie.niveau_actuel, ""),
        "contrat_structure": ge.CONTRATS.get(partie.niveau_actuel, []),
        "joueur_actif": joueur_actif.nom,
        "distributeur": distributeur.nom,
        "a_pioche_ce_tour": partie.a_pioche_ce_tour,
        "pioche_count": len(partie.pioche),
        "defausse_top": partie.defausse[-1].to_dict() if partie.defausse else None,
        "defausse_count": len(partie.defausse),
        "tapis": [[c.to_dict() for c in groupe] for groupe in partie.tapis],
        "joueurs": [j.to_dict_public() for j in partie.joueurs],
        "ma_main": sorted(
            [c.to_dict() for c in moi.main],
            key=lambda c: (c["couleur"], c["valeur"]),
        ) if moi else [],
        "mon_pseudo": pseudo,
        "je_suis_etale": moi.est_etale if moi else False,
        "termine": partie.est_terminee(),
        "journal": partie.journal[-15:],
    }


def diffuser_etat(code):
    salle = salle_de(code)
    if not salle or not salle["partie"]:
        return
    partie = salle["partie"]

    # AJOUT : si une mène vient de se terminer (détectée via ce "flash" posé
    # par game_engine.py), on informe toute la salle avant l'état de jeu
    # normal, pour que l'interface puisse jouer une animation de transition
    # (qui a gagné, classement, prochain contrat).
    if partie.dernier_resultat_mene:
        socketio.emit("resultat_mene", partie.dernier_resultat_mene, room=code)
        partie.dernier_resultat_mene = None

    if partie.est_terminee():
        gagnant = partie.gagnant_partie()
        # CORRECTION : score le plus bas en tête (les points sont une
        # pénalité désormais, cf. game_engine.py).
        classement = sorted(
            [{"nom": j.nom, "score": j.score} for j in partie.joueurs],
            key=lambda x: x["score"],
        )
        socketio.emit(
            "partie_terminee",
            {"vainqueur": gagnant.nom, "classement": classement},
            room=code,
        )

    for j in partie.joueurs:
        sid = salle["sid_de"].get(j.nom)
        if sid:
            socketio.emit("etat_partie", etat_pour(partie, j.nom), room=sid)


def est_son_tour(partie, pseudo):
    return partie.joueurs[partie.joueur_actif].nom == pseudo


# --- Cycle de vie d'un salon --------------------------------------------------

@socketio.on("creer_salle")
def on_creer_salle(data):
    pseudo = (data or {}).get("pseudo", "").strip()[:20]
    if not pseudo:
        return erreur("Choisis un pseudo.")

    code = generer_code()
    rooms[code] = {
        "code": code,
        "partie": None,
        "pseudos": [pseudo],
        "hote": pseudo,
        "sid_de": {},
        "pseudo_de": {},
        "demarree": False,
    }
    _rattacher_sid(code, pseudo)
    join_room(code)
    emit("salle_rejointe", {"code": code, "pseudo": pseudo})
    diffuser_lobby(code)


@socketio.on("rejoindre_salle")
def on_rejoindre_salle(data):
    pseudo = (data or {}).get("pseudo", "").strip()[:20]
    code = (data or {}).get("code", "").strip().upper()
    salle = salle_de(code)

    if not pseudo:
        return erreur("Choisis un pseudo.")
    if not salle:
        return erreur("Ce salon n'existe pas.")

    # Reconnexion : un joueur déjà présent dans la partie qui rouvre l'appli.
    if pseudo in salle["pseudos"]:
        _rattacher_sid(code, pseudo)
        join_room(code)
        emit("salle_rejointe", {"code": code, "pseudo": pseudo})
        if salle["demarree"]:
            diffuser_etat(code)
        else:
            diffuser_lobby(code)
        return

    if salle["demarree"]:
        return erreur("La partie a déjà commencé dans ce salon.")
    if len(salle["pseudos"]) >= MAX_JOUEURS:
        return erreur("Ce salon est complet (6 joueurs max).")
    if pseudo in salle["pseudos"]:
        return erreur("Ce pseudo est déjà pris dans ce salon.")

    salle["pseudos"].append(pseudo)
    _rattacher_sid(code, pseudo)
    join_room(code)
    emit("salle_rejointe", {"code": code, "pseudo": pseudo})
    diffuser_lobby(code)


def _rattacher_sid(code, pseudo):
    salle = rooms[code]
    salle["sid_de"][pseudo] = request.sid
    salle["pseudo_de"][request.sid] = pseudo


@socketio.on("demarrer_partie")
def on_demarrer_partie(data):
    code = (data or {}).get("code", "").strip().upper()
    salle = salle_de(code)
    if not salle:
        return erreur("Ce salon n'existe pas.")

    pseudo = salle["pseudo_de"].get(request.sid)
    if pseudo != salle["hote"]:
        return erreur("Seul l'hôte peut démarrer la partie.")
    if salle["demarree"]:
        return
    if len(salle["pseudos"]) < MIN_JOUEURS:
        return erreur(f"Il faut au moins {MIN_JOUEURS} joueurs.")

    partie = ge.Partie(salle["pseudos"])
    partie.log("La partie commence !")
    partie.entamer_manche()  # distribue, retourne une carte, désigne qui commence

    salle["partie"] = partie
    salle["demarree"] = True
    diffuser_etat(code)


# --- Actions de jeu ------------------------------------------------------

def _contexte_action(data):
    """Retourne (salle, partie, pseudo) ou None si l'action doit être refusée,
    après avoir déjà émis un message d'erreur au joueur concerné."""
    code = (data or {}).get("code", "").strip().upper()
    salle = salle_de(code)
    if not salle or not salle["partie"]:
        erreur("Partie introuvable.")
        return None

    pseudo = salle["pseudo_de"].get(request.sid)
    if not pseudo:
        erreur("Tu n'es pas reconnu dans ce salon (recharge la page).")
        return None

    partie = salle["partie"]

    # AJOUT IMPORTANT : le moteur de jeu original fait entièrement confiance à
    # l'appelant et agit toujours sur joueurs[joueur_actif], quel que soit qui
    # a appelé la méthode. En local (un seul script), ce n'est pas un problème
    # puisqu'il n'y a qu'un seul "joueur" (toi, au clavier). Mais en ligne,
    # n'importe quel navigateur peut envoyer un événement "piocher" à
    # n'importe quel moment : sans ce contrôle, un joueur pourrait jouer à la
    # place d'un autre. C'est ce garde-fou qui manquait pour une vraie
    # utilisation multijoueur.
    if not est_son_tour(partie, pseudo):
        erreur("Ce n'est pas ton tour.")
        return None

    return salle, partie, pseudo


@socketio.on("piocher")
def on_piocher(data):
    contexte = _contexte_action(data)
    if not contexte:
        return
    salle, partie, pseudo = contexte
    source = (data or {}).get("source")
    if source not in ("pioche", "defausse"):
        return erreur("Source de pioche invalide.")

    if not partie.action_piocher(source):
        return erreur("Impossible de piocher ici pour le moment.")
    diffuser_etat(salle["code"])


@socketio.on("etaler")
def on_etaler(data):
    contexte = _contexte_action(data)
    if not contexte:
        return
    salle, partie, pseudo = contexte
    if not partie.a_pioche_ce_tour:
        return erreur("Pioche d'abord une carte avant de t'étaler.")

    groupes_ids = (data or {}).get("groupes", [])
    joueur_actuel = partie.joueurs[partie.joueur_actif]

    groupes_cartes = []
    for groupe_ids in groupes_ids:
        groupe = []
        for cid in groupe_ids:
            carte = partie.trouver_carte(joueur_actuel.main, cid)
            if carte is None:
                return erreur("Une des cartes sélectionnées n'est plus dans ta main.")
            groupe.append(carte)
        groupes_cartes.append(groupe)

    arrangement = ge.verifier_contrat_toute_permutation(partie.niveau_actuel, groupes_cartes)
    if arrangement is None:
        return erreur("Cet étalement ne correspond pas au contrat demandé.")

    if not partie.action_etaler(arrangement):
        return erreur("Étalement refusé.")
    diffuser_etat(salle["code"])


@socketio.on("rajouter")
def on_rajouter(data):
    contexte = _contexte_action(data)
    if not contexte:
        return
    salle, partie, pseudo = contexte
    if not partie.a_pioche_ce_tour:
        return erreur("Pioche d'abord une carte avant de rajouter.")

    joueur_actuel = partie.joueurs[partie.joueur_actif]
    carte_id = (data or {}).get("carte_id")
    index_groupe = (data or {}).get("index_groupe")
    position = (data or {}).get("position", "fin")  # AJOUT : "debut" ou "fin"

    index_carte = next(
        (i for i, c in enumerate(joueur_actuel.main) if c.id == carte_id), None
    )
    if index_carte is None or index_groupe is None:
        return erreur("Sélection invalide.")

    if not partie.action_rajouter(index_carte, int(index_groupe), position):
        return erreur("Cette carte ne peut pas être ajoutée à ce groupe.")
    diffuser_etat(salle["code"])


@socketio.on("defausser")
def on_defausser(data):
    contexte = _contexte_action(data)
    if not contexte:
        return
    salle, partie, pseudo = contexte

    if not partie.a_pioche_ce_tour:
        return erreur("Tu dois piocher avant de te défausser.")

    joueur_actuel = partie.joueurs[partie.joueur_actif]
    carte_id = (data or {}).get("carte_id")
    index_carte = next(
        (i for i, c in enumerate(joueur_actuel.main) if c.id == carte_id), None
    )
    if index_carte is None:
        return erreur("Cette carte n'est plus dans ta main.")

    if not partie.action_defausser(index_carte):
        return erreur("Défausse refusée.")
    diffuser_etat(salle["code"])


@socketio.on("finir_sec")
def on_finir_sec(data):
    # AJOUT : terminer la manche en révélant toute sa main d'un coup, sans
    # jamais s'être étalé (voir action_finir_sec dans game_engine.py). Le
    # calcul peut prendre jusqu'à une seconde ou deux dans les pires cas
    # (contrat à 3 groupes, main de 12 cartes), ce qui reste largement
    # acceptable pour une action volontaire et ponctuelle du joueur.
    contexte = _contexte_action(data)
    if not contexte:
        return
    salle, partie, pseudo = contexte

    if not partie.a_pioche_ce_tour:
        return erreur("Pioche d'abord une carte avant de tenter de finir.")

    if not partie.action_finir_sec():
        return erreur("Ta main ne se répartit pas exactement selon le contrat : impossible de finir maintenant.")
    diffuser_etat(salle["code"])


@socketio.on("disconnect")
def on_disconnect():
    for salle in rooms.values():
        pseudo = salle["pseudo_de"].pop(request.sid, None)
        if pseudo:
            salle["sid_de"].pop(pseudo, None)
            # On ne supprime pas le joueur de la partie : il peut se reconnecter
            # avec le même pseudo pour reprendre sa main là où il l'a laissée.
            if not salle["demarree"]:
                salle["pseudos"] = [p for p in salle["pseudos"] if p != pseudo]
                if salle["pseudos"] and salle["hote"] == pseudo:
                    salle["hote"] = salle["pseudos"][0]
                diffuser_lobby(salle["code"])
            break


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # allow_unsafe_werkzeug : ce serveur est prévu pour une partie privée entre
    # quelques joueurs (famille/amis), pas pour un site public à fort trafic,
    # donc le serveur de développement de Flask est amplement suffisant ici.
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)

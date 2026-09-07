/* =====================================================================
   RAMI DE FAMILLE — logique côté navigateur
   ===================================================================== */

const socket = io();

// --- État local -------------------------------------------------------
let monPseudo = null;
let monCode = null;
let dernierEtat = null;

// Étalement en cours de préparation (uniquement côté client, tant que
// "Valider" n'a pas été cliqué) : tableau de groupes, chaque groupe étant
// un tableau d'ids de cartes.
let groupesEtalement = [];
let carteEnAttenteEtaler = null;
let modaleEtalerOuverte = false;

// Rajout : carte en attente de destination
let carteEnAttenteRajouter = null;
let modaleRajouterOuverte = false;

// Main : carte actuellement "levée" (sélectionnée). Sert à la fois pour la
// défausse (Défausser agit sur cette carte) et pour la réordonner (flèches).
// Utilisable à tout moment, même hors de ton tour, pour organiser sa main.
let carteSelectionneeMain = null;

// Ordre d'affichage de la main, choisi par le joueur (persiste tant que les
// cartes sont les mêmes ; les nouvelles cartes piochées s'ajoutent à la fin).
let ordreMainIds = [];

// Minuteur de l'overlay de fin de mène (pour pouvoir l'annuler si la partie
// se termine juste après, ou si le joueur touche l'écran pour continuer).
let minuteurResultatMene = null;

// -----------------------------------------------------------------------
// Utilitaires généraux
// -----------------------------------------------------------------------

function el(id) { return document.getElementById(id); }

function afficherEcran(id) {
  document.querySelectorAll(".ecran").forEach((e) => e.classList.remove("actif"));
  el(id).classList.add("actif");
}

function toast(message) {
  const conteneur = el("toasts");
  const div = document.createElement("div");
  div.className = "toast";
  div.textContent = message;
  conteneur.appendChild(div);
  setTimeout(() => div.remove(), 3800);
}

function libelleValeur(valeur) {
  if (valeur === 1) return "A";
  if (valeur === 11) return "V";
  if (valeur === 12) return "D";
  if (valeur === 13) return "R";
  return String(valeur);
}

function infosCouleur(couleur) {
  switch (couleur) {
    case "Coeur": return { symbole: "♥", classe: "rouge" };
    case "Carreau": return { symbole: "♦", classe: "rouge" };
    case "Pique": return { symbole: "♠", classe: "noir" };
    case "Trefle": return { symbole: "♣", classe: "noir" };
    default: return { symbole: "🃏", classe: "joker" };
  }
}

/**
 * Construit l'élément DOM d'une carte.
 * options: { selectionnable, selectionnee, miniature, onClick }
 */
function creerElementCarte(carte, options = {}) {
  const div = document.createElement("div");
  const estJoker = carte.valeur === 0;
  const { symbole, classe } = infosCouleur(carte.couleur);

  div.className = "carte " + (estJoker ? "joker" : classe);
  if (carte.joker) div.classList.add("wild");
  if (options.miniature) div.classList.add("carte--miniature");
  if (options.selectionnable) div.classList.add("carte--selectionnable");
  if (options.selectionnee) div.classList.add("carte--selectionnee");

  if (estJoker) {
    div.innerHTML = `<span class="carte__symbole">🃏</span><span>Joker</span>`;
  } else {
    div.innerHTML = `<span>${libelleValeur(carte.valeur)}</span><span class="carte__symbole">${symbole}</span>`;
  }

  div.title = carte.label;
  div.dataset.id = carte.id;

  if (options.onClick) {
    div.addEventListener("click", () => options.onClick(carte));
  }
  return div;
}

function afficherErreurCiblee(message) {
  if (!el("modale-etaler").hidden) {
    el("etaler-erreur").textContent = message;
  } else if (!el("modale-rajouter").hidden) {
    el("rajouter-erreur").textContent = message;
  } else if (el("ecran-accueil").classList.contains("actif")) {
    el("accueil-erreur").textContent = message;
  } else if (el("ecran-salon").classList.contains("actif")) {
    el("salon-erreur").textContent = message;
  } else {
    toast(message);
  }
}

// -----------------------------------------------------------------------
// Glisser-déposer (pointer events -> marche à la souris ET au tactile)
// -----------------------------------------------------------------------
// Utilisé uniquement là où il n'y a pas de défilement à l'endroit du geste
// (la modale "S'étaler" a des cartes qui passent à la ligne, pas de
// défilement horizontal), pour éviter tout conflit avec le geste de scroll
// sur mobile. Dans la main du bas (qui défile), on préfère les flèches.

let carteFantome = null;

function demarrerFantome(element, evt) {
  const rect = element.getBoundingClientRect();
  const fantome = element.cloneNode(true);
  fantome.classList.add("carte--fantome");
  fantome.classList.remove("carte--selectionnable", "carte--selectionnee");
  fantome.style.width = rect.width + "px";
  fantome.style.height = rect.height + "px";
  fantome.style.left = rect.left + "px";
  fantome.style.top = rect.top + "px";
  fantome.style.margin = "0";
  document.body.appendChild(fantome);
  fantome._offsetX = evt.clientX - rect.left;
  fantome._offsetY = evt.clientY - rect.top;
  carteFantome = fantome;
  element.classList.add("carte--en-glissement");
}

function deplacerFantome(evt) {
  if (!carteFantome) return;
  carteFantome.style.left = (evt.clientX - carteFantome._offsetX) + "px";
  carteFantome.style.top = (evt.clientY - carteFantome._offsetY) + "px";
}

function detruireFantome(elementOrigine) {
  if (carteFantome) { carteFantome.remove(); carteFantome = null; }
  if (elementOrigine) elementOrigine.classList.remove("carte--en-glissement");
}

/**
 * Rend un élément carte "glissable" : un simple tap déclenche onTap, un
 * mouvement suffisant déclenche onDragStart -> onDragMove(s) -> onDrop.
 */
function rendreGlissable(element, { onTap, onDragStart, onDragMove, onDrop }) {
  const SEUIL = 6;
  let origine = null;
  let enGlissement = false;
  let pointerId = null;

  element.addEventListener("pointerdown", (evt) => {
    if (evt.pointerType === "mouse" && evt.button !== 0) return;
    origine = { x: evt.clientX, y: evt.clientY };
    enGlissement = false;
    pointerId = evt.pointerId;
    try { element.setPointerCapture(pointerId); } catch (e) { /* ignore */ }
  });

  element.addEventListener("pointermove", (evt) => {
    if (!origine || evt.pointerId !== pointerId) return;
    const dx = evt.clientX - origine.x;
    const dy = evt.clientY - origine.y;
    if (!enGlissement && Math.hypot(dx, dy) > SEUIL) {
      enGlissement = true;
      if (onDragStart) onDragStart(evt);
    }
    if (enGlissement && onDragMove) onDragMove(evt);
  });

  function relacher(evt) {
    if (!origine) return;
    if (enGlissement) {
      if (onDrop) onDrop(evt);
    } else if (onTap) {
      onTap(evt);
    }
    origine = null;
    enGlissement = false;
  }

  element.addEventListener("pointerup", relacher);
  element.addEventListener("pointercancel", relacher);
}

function trouverCibleSous(evt, selecteur) {
  const elementSous = document.elementFromPoint(evt.clientX, evt.clientY);
  return elementSous ? elementSous.closest(selecteur) : null;
}

// -----------------------------------------------------------------------
// Écran d'accueil
// -----------------------------------------------------------------------

try {
  const session = JSON.parse(localStorage.getItem("ramiSession") || "null");
  if (session) {
    el("input-pseudo").value = session.pseudo || "";
    el("input-code").value = session.code || "";
  }
} catch (e) { /* localStorage indisponible, tant pis */ }

function sauvegarderSession(pseudo, code) {
  try {
    localStorage.setItem("ramiSession", JSON.stringify({ pseudo, code }));
  } catch (e) { /* ignore */ }
}

el("btn-creer").addEventListener("click", () => {
  const pseudo = el("input-pseudo").value.trim();
  el("accueil-erreur").textContent = "";
  if (!pseudo) { el("accueil-erreur").textContent = "Choisis un prénom."; return; }
  socket.emit("creer_salle", { pseudo });
});

el("btn-rejoindre").addEventListener("click", () => {
  const pseudo = el("input-pseudo").value.trim();
  const code = el("input-code").value.trim().toUpperCase();
  el("accueil-erreur").textContent = "";
  if (!pseudo) { el("accueil-erreur").textContent = "Choisis un prénom."; return; }
  if (!code) { el("accueil-erreur").textContent = "Entre le code de la partie."; return; }
  socket.emit("rejoindre_salle", { pseudo, code });
});

[el("input-pseudo"), el("input-code")].forEach((input) => {
  input.addEventListener("keydown", (evt) => {
    if (evt.key === "Enter") el("btn-rejoindre").click();
  });
});

// -----------------------------------------------------------------------
// Salon d'attente
// -----------------------------------------------------------------------

socket.on("salle_rejointe", (data) => {
  monPseudo = data.pseudo;
  monCode = data.code;
  sauvegarderSession(monPseudo, monCode);
});

socket.on("etat_lobby", (lobby) => {
  if (lobby.code !== monCode) return;
  afficherEcran("ecran-salon");
  el("salon-code").textContent = lobby.code;

  const liste = el("salon-liste-joueurs");
  liste.innerHTML = "";
  lobby.joueurs.forEach((nom) => {
    const li = document.createElement("li");
    const estHote = nom === lobby.hote;
    li.innerHTML = `<span>${nom}${nom === monPseudo ? " (toi)" : ""}</span>` +
      (estHote ? `<span class="badge-hote">Hôte</span>` : "");
    liste.appendChild(li);
  });

  const jeSuisHote = lobby.hote === monPseudo;
  const assezDeJoueurs = lobby.joueurs.length >= lobby.min_joueurs;
  el("btn-lancer").hidden = !jeSuisHote;
  el("btn-lancer").disabled = !assezDeJoueurs;
  el("btn-lancer").textContent = assezDeJoueurs
    ? "Lancer la partie"
    : `Lancer la partie (encore ${lobby.min_joueurs - lobby.joueurs.length} joueur(s) minimum)`;
  el("salon-attente-hote").hidden = jeSuisHote;
});

el("btn-lancer").addEventListener("click", () => {
  socket.emit("demarrer_partie", { code: monCode });
});

// -----------------------------------------------------------------------
// Table de jeu — rendu
// -----------------------------------------------------------------------

socket.on("etat_partie", (etat) => {
  dernierEtat = etat;
  afficherEcran("ecran-jeu");

  // Sécurité : si la carte qu'on avait sélectionnée n'existe plus dans la
  // main (jouée, défaussée...), on oublie la sélection.
  if (carteSelectionneeMain && !etat.ma_main.some((c) => c.id === carteSelectionneeMain)) {
    carteSelectionneeMain = null;
  }

  rendreTable(etat);

  if (modaleRajouterOuverte) rendreModaleRajouter();

  // La demande était explicite : une fois étalé, on referme automatiquement
  // la fenêtre d'étalement plutôt que de laisser un bouton "Annuler" trompeur
  // (le contrat est déjà validé côté serveur à ce stade).
  if (modaleEtalerOuverte && etat.je_suis_etale) {
    fermerModaleEtaler();
  }
});

function idsMainActuelle(etat) {
  return etat.ma_main.map((c) => c.id);
}

function reconcilierOrdreMain(etat) {
  const presentes = new Set(idsMainActuelle(etat));
  ordreMainIds = ordreMainIds.filter((id) => presentes.has(id));
  etat.ma_main.forEach((c) => {
    if (!ordreMainIds.includes(c.id)) ordreMainIds.push(c.id);
  });
}

function mainOrdonnee(etat) {
  reconcilierOrdreMain(etat);
  const parId = new Map(etat.ma_main.map((c) => [c.id, c]));
  return ordreMainIds.map((id) => parId.get(id)).filter(Boolean);
}

function rendreTable(etat) {
  const monTour = etat.joueur_actif === etat.mon_pseudo;

  el("jeu-niveau").textContent = etat.niveau;
  el("jeu-description-contrat").textContent = etat.contrat_description;
  el("jeu-distributeur").textContent = `Distribué par ${etat.distributeur}`;

  const indicateur = el("jeu-indicateur-tour");
  indicateur.textContent = monTour ? "C'est à toi de jouer !" : `Au tour de ${etat.joueur_actif}`;
  indicateur.classList.toggle("mon-tour", monTour);

  // Adversaires (tous les joueurs, "toi" inclus, avec repère visuel)
  const rangee = el("rangee-adversaires");
  rangee.innerHTML = "";
  etat.joueurs.forEach((j) => {
    const div = document.createElement("div");
    div.className = "siege-adversaire" + (j.nom === etat.joueur_actif ? " au-tour" : "");
    div.innerHTML = `
      <div class="siege-adversaire__nom">
        ${j.est_etale ? '<span class="puce-etale" title="Étalé"></span>' : ""}
        ${j.nom}${j.nom === etat.mon_pseudo ? " (toi)" : ""}
      </div>
      <div class="siege-adversaire__details">${j.nb_cartes} carte(s) · ${j.score} pts</div>
    `;
    rangee.appendChild(div);
  });

  // Pioche / défausse
  el("jeu-nb-pioche").textContent = etat.pioche_count;
  const nouvelleCarteDefausse = etat.defausse_top
    ? creerElementCarte(etat.defausse_top, { miniature: true })
    : Object.assign(document.createElement("span"), { className: "carte carte--vide", textContent: "—" });
  nouvelleCarteDefausse.id = "jeu-carte-defausse";
  el("jeu-carte-defausse").replaceWith(nouvelleCarteDefausse);

  const peutPiocher = monTour && !etat.a_pioche_ce_tour;
  el("btn-piocher-pioche").disabled = !peutPiocher;
  el("btn-piocher-defausse").disabled = !peutPiocher || !etat.defausse_top;

  // Tapis
  const tapisDiv = el("jeu-tapis");
  tapisDiv.innerHTML = "";
  etat.tapis.forEach((groupe) => {
    const groupeDiv = document.createElement("div");
    groupeDiv.className = "groupe-tapis";
    groupe.forEach((carte) => groupeDiv.appendChild(creerElementCarte(carte, { miniature: true })));
    tapisDiv.appendChild(groupeDiv);
  });

  // Journal
  const journalDiv = el("jeu-journal");
  journalDiv.innerHTML = "";
  etat.journal.forEach((ligne) => {
    const p = document.createElement("p");
    p.textContent = ligne;
    journalDiv.appendChild(p);
  });
  journalDiv.scrollTop = journalDiv.scrollHeight;

  // Boutons d'action
  const peutAgir = monTour && etat.a_pioche_ce_tour;
  el("btn-action-etaler").disabled = !peutAgir || etat.je_suis_etale;
  el("btn-action-rajouter").disabled = !peutAgir || !etat.je_suis_etale;
  el("btn-action-finir-sec").disabled = !peutAgir || etat.je_suis_etale;
  el("btn-action-finir-sec").hidden = etat.je_suis_etale;
  el("btn-action-defausser").disabled = !peutAgir || !carteSelectionneeMain;

  if (carteSelectionneeMain) {
    el("jeu-aide-action").textContent = peutAgir
      ? "Carte sélectionnée — touche \"Défausser\" pour confirmer, ou les flèches pour la déplacer."
      : "Carte sélectionnée — touche les flèches pour la déplacer dans ta main.";
  } else {
    el("jeu-aide-action").textContent = !monTour ? "" : (!etat.a_pioche_ce_tour ? "Pioche une carte pour commencer ton tour." : "");
  }

  // Barre de réordonnancement (flèches)
  el("barre-reordonner").hidden = !carteSelectionneeMain;

  // Main (dans l'ordre choisi par le joueur)
  const mainDiv = el("jeu-main");
  mainDiv.innerHTML = "";
  mainOrdonnee(etat).forEach((carte) => {
    const carteEl = creerElementCarte(carte, {
      selectionnable: true,
      selectionnee: carteSelectionneeMain === carte.id,
    });
    carteEl.addEventListener("click", () => {
      carteSelectionneeMain = (carteSelectionneeMain === carte.id) ? null : carte.id;
      rendreTable(dernierEtat);
    });
    mainDiv.appendChild(carteEl);
  });
}

el("btn-piocher-pioche").addEventListener("click", () => {
  socket.emit("piocher", { code: monCode, source: "pioche" });
});
el("btn-piocher-defausse").addEventListener("click", () => {
  socket.emit("piocher", { code: monCode, source: "defausse" });
});

el("btn-action-finir-sec").addEventListener("click", () => {
  socket.emit("finir_sec", { code: monCode });
});

// AJOUT : flux de défausse inversé, comme demandé — on choisit d'abord la
// carte (elle se lève), puis on confirme avec le bouton.
el("btn-action-defausser").addEventListener("click", () => {
  if (!carteSelectionneeMain) return;
  socket.emit("defausser", { code: monCode, carte_id: carteSelectionneeMain });
  carteSelectionneeMain = null;
});

// AJOUT : flèches pour réordonner sa main (échange avec la carte voisine).
// Ça marche à tout moment, même hors de ton tour, pour organiser sa main.
function deplacerCarteSelectionnee(direction) {
  if (!carteSelectionneeMain) return;
  const index = ordreMainIds.indexOf(carteSelectionneeMain);
  const nouvelIndex = index + direction;
  if (index === -1 || nouvelIndex < 0 || nouvelIndex >= ordreMainIds.length) return;
  [ordreMainIds[index], ordreMainIds[nouvelIndex]] = [ordreMainIds[nouvelIndex], ordreMainIds[index]];
  if (dernierEtat) rendreTable(dernierEtat);
}
el("btn-carte-gauche").addEventListener("click", () => deplacerCarteSelectionnee(-1));
el("btn-carte-droite").addEventListener("click", () => deplacerCarteSelectionnee(1));

// -----------------------------------------------------------------------
// Modale : S'étaler
// -----------------------------------------------------------------------

el("btn-action-etaler").addEventListener("click", ouvrirModaleEtaler);
el("btn-etaler-annuler").addEventListener("click", fermerModaleEtaler);

function ouvrirModaleEtaler() {
  if (!dernierEtat) return;
  const nbGroupes = dernierEtat.contrat_structure.length;
  groupesEtalement = Array.from({ length: nbGroupes }, () => []);
  carteEnAttenteEtaler = null;
  carteSelectionneeMain = null; // évite tout résidu visuel dans la main derrière la modale
  modaleEtalerOuverte = true;
  el("etaler-erreur").textContent = "";
  el("etaler-description").textContent = dernierEtat.contrat_description;
  rendreModaleEtaler();
  el("modale-etaler").hidden = false;
}

function fermerModaleEtaler() {
  modaleEtalerOuverte = false;
  el("modale-etaler").hidden = true;
}

function cartesDejaPlacees() {
  return new Set(groupesEtalement.flat());
}

function retirerDeTousLesGroupesEtalement(carteId) {
  groupesEtalement = groupesEtalement.map((g) => g.filter((cid) => cid !== carteId));
}

function rendreModaleEtaler() {
  if (!dernierEtat) return;
  const placees = cartesDejaPlacees();

  // Groupes
  const conteneurGroupes = el("etaler-groupes");
  conteneurGroupes.innerHTML = "";
  groupesEtalement.forEach((groupeIds, index) => {
    const boite = document.createElement("div");
    boite.className = "groupe-etalement cliquable";
    boite.innerHTML = `<div class="groupe-etalement__titre">Groupe ${index + 1} (${groupeIds.length} carte${groupeIds.length > 1 ? "s" : ""})</div>`;
    const zoneCartes = document.createElement("div");
    zoneCartes.className = "groupe-etalement__cartes";

    groupeIds.forEach((id) => {
      const carteData = dernierEtat.ma_main.find((c) => c.id === id);
      if (!carteData) return;
      const carteEl = creerElementCarte(carteData, { selectionnable: true, miniature: true });
      rendreGlissable(carteEl, {
        onTap: () => {
          // Toucher une carte déjà posée -> elle retourne en main.
          retirerDeTousLesGroupesEtalement(id);
          rendreModaleEtaler();
        },
        onDragStart: (evt) => demarrerFantome(carteEl, evt),
        onDragMove: (evt) => deplacerFantome(evt),
        onDrop: (evt) => {
          detruireFantome(carteEl);
          deposerCarteEtalement(id, evt);
        },
      });
      zoneCartes.appendChild(carteEl);
    });
    boite.appendChild(zoneCartes);

    boite.addEventListener("click", (evt) => {
      if (evt.target.closest(".carte")) return;
      if (carteEnAttenteEtaler) {
        retirerDeTousLesGroupesEtalement(carteEnAttenteEtaler);
        groupesEtalement[index].push(carteEnAttenteEtaler);
        carteEnAttenteEtaler = null;
        rendreModaleEtaler();
      }
    });

    conteneurGroupes.appendChild(boite);
  });

  // Main disponible (glissable vers un groupe, ou cliquable en 2 temps)
  const dispo = dernierEtat.ma_main.filter((c) => !placees.has(c.id));
  const mainDiv = el("etaler-main");
  mainDiv.innerHTML = "";
  dispo.forEach((carte) => {
    const carteEl = creerElementCarte(carte, {
      selectionnable: true,
      selectionnee: carteEnAttenteEtaler === carte.id,
    });
    rendreGlissable(carteEl, {
      onTap: () => {
        carteEnAttenteEtaler = (carteEnAttenteEtaler === carte.id) ? null : carte.id;
        rendreModaleEtaler();
      },
      onDragStart: (evt) => demarrerFantome(carteEl, evt),
      onDragMove: (evt) => deplacerFantome(evt),
      onDrop: (evt) => {
        detruireFantome(carteEl);
        deposerCarteEtalement(carte.id, evt);
      },
    });
    mainDiv.appendChild(carteEl);
  });
}

function deposerCarteEtalement(carteId, evt) {
  // AJOUT : glisser-déposer une carte directement sur un groupe (en plus du
  // clic en 2 temps qui reste disponible). On retire d'abord la carte de
  // partout, puis on la place dans le groupe visé si le relâchement tombe
  // bien sur un groupe ; sinon elle retourne simplement dans le pool "main".
  retirerDeTousLesGroupesEtalement(carteId);
  carteEnAttenteEtaler = null;
  const groupeCible = trouverCibleSous(evt, ".groupe-etalement");
  if (groupeCible) {
    const index = Array.from(el("etaler-groupes").children).indexOf(groupeCible);
    if (index !== -1) groupesEtalement[index].push(carteId);
  }
  rendreModaleEtaler();
}

// Surlignage visuel de la zone survolée pendant un glissé (délégation simple :
// on écoute au niveau du document pendant qu'un fantôme existe).
document.addEventListener("pointermove", (evt) => {
  if (!carteFantome) return;
  document.querySelectorAll(".groupe-etalement.survole, .groupe-tapis.survole")
    .forEach((e) => e.classList.remove("survole"));
  const cible = document.elementFromPoint(evt.clientX, evt.clientY);
  const groupe = cible && (cible.closest(".groupe-etalement") || cible.closest(".groupe-tapis.cliquable"));
  if (groupe) groupe.classList.add("survole");
});

el("btn-etaler-valider").addEventListener("click", () => {
  const groupesNonVides = groupesEtalement.filter((g) => g.length > 0);
  if (groupesNonVides.length !== groupesEtalement.length) {
    el("etaler-erreur").textContent = "Remplis tous les groupes avant de valider.";
    return;
  }
  el("etaler-erreur").textContent = "";
  socket.emit("etaler", { code: monCode, groupes: groupesEtalement });
});

// -----------------------------------------------------------------------
// Modale : Rajouter sur la table
// -----------------------------------------------------------------------

el("btn-action-rajouter").addEventListener("click", () => {
  carteEnAttenteRajouter = null;
  el("rajouter-erreur").textContent = "";
  modaleRajouterOuverte = true;
  rendreModaleRajouter();
  el("modale-rajouter").hidden = false;
});

el("btn-rajouter-annuler").addEventListener("click", () => {
  modaleRajouterOuverte = false;
  el("modale-rajouter").hidden = true;
});

function rendreModaleRajouter() {
  if (!dernierEtat) return;

  const tapisDiv = el("rajouter-tapis");
  tapisDiv.innerHTML = "";
  if (dernierEtat.tapis.length === 0) {
    const p = document.createElement("p");
    p.className = "astuce";
    p.textContent = "Aucun groupe sur la table pour l'instant.";
    tapisDiv.appendChild(p);
  }
  dernierEtat.tapis.forEach((groupe, index) => {
    const boite = document.createElement("div");
    boite.className = "groupe-tapis cliquable";
    groupe.forEach((carte) => boite.appendChild(creerElementCarte(carte, { miniature: true })));
    boite.addEventListener("click", () => {
      if (!carteEnAttenteRajouter) {
        el("rajouter-erreur").textContent = "Touche d'abord une carte de ta main.";
        return;
      }
      socket.emit("rajouter", { code: monCode, carte_id: carteEnAttenteRajouter, index_groupe: index });
      carteEnAttenteRajouter = null;
    });
    tapisDiv.appendChild(boite);
  });

  const mainDiv = el("rajouter-main");
  mainDiv.innerHTML = "";
  dernierEtat.ma_main.forEach((carte) => {
    const carteEl = creerElementCarte(carte, {
      selectionnable: true,
      selectionnee: carteEnAttenteRajouter === carte.id,
    });
    rendreGlissable(carteEl, {
      onTap: () => {
        carteEnAttenteRajouter = (carteEnAttenteRajouter === carte.id) ? null : carte.id;
        rendreModaleRajouter();
      },
      onDragStart: (evt) => demarrerFantome(carteEl, evt),
      onDragMove: (evt) => deplacerFantome(evt),
      onDrop: (evt) => {
        detruireFantome(carteEl);
        const groupeCible = trouverCibleSous(evt, "#rajouter-tapis .groupe-tapis.cliquable");
        if (groupeCible) {
          const index = Array.from(el("rajouter-tapis").children).indexOf(groupeCible);
          if (index !== -1) {
            socket.emit("rajouter", { code: monCode, carte_id: carte.id, index_groupe: index });
          }
        }
        carteEnAttenteRajouter = null;
      },
    });
    mainDiv.appendChild(carteEl);
  });
}

// -----------------------------------------------------------------------
// Transition entre manches (animation + classement + prochain contrat)
// -----------------------------------------------------------------------

socket.on("resultat_mene", (data) => {
  // Si une modale d'action était ouverte, ses cartes sélectionnées font
  // référence à l'ancienne main : on ferme tout pour repartir propre.
  if (modaleEtalerOuverte) fermerModaleEtaler();
  if (modaleRajouterOuverte) { modaleRajouterOuverte = false; el("modale-rajouter").hidden = true; }
  carteSelectionneeMain = null;

  const bonusTxt = data.bonus_fini_sec ? " (fini sec, points doublés !)" : "";
  el("resultat-titre").textContent = `${data.gagnant} remporte la manche !`;
  el("resultat-detail").textContent = `+${data.points_gagnes} points${bonusTxt}`;

  const liste = el("resultat-classement");
  liste.innerHTML = "";
  data.classement.forEach((j) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${j.nom}</span><span>${j.score} pts</span>`;
    liste.appendChild(li);
  });

  el("resultat-prochain").textContent = data.partie_terminee
    ? ""
    : `Prochain contrat : ${data.prochain_contrat_description}`;

  el("overlay-resultat-mene").hidden = false;

  clearTimeout(minuteurResultatMene);
  minuteurResultatMene = setTimeout(() => {
    el("overlay-resultat-mene").hidden = true;
  }, data.partie_terminee ? 1200 : 5500);
});

el("overlay-resultat-mene").addEventListener("click", () => {
  clearTimeout(minuteurResultatMene);
  el("overlay-resultat-mene").hidden = true;
});

// -----------------------------------------------------------------------
// Fin de partie
// -----------------------------------------------------------------------

socket.on("partie_terminee", (data) => {
  clearTimeout(minuteurResultatMene);
  el("overlay-resultat-mene").hidden = true;

  el("fin-titre").textContent = `🏆 ${data.vainqueur} remporte la partie !`;
  const liste = el("fin-classement");
  liste.innerHTML = "";
  data.classement.forEach((j) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${j.nom}</span><span>${j.score} pts</span>`;
    liste.appendChild(li);
  });
  el("modale-fin").hidden = false;
});

el("btn-fin-fermer").addEventListener("click", () => {
  try { localStorage.removeItem("ramiSession"); } catch (e) { /* ignore */ }
  window.location.reload();
});

// -----------------------------------------------------------------------
// Erreurs génériques
// -----------------------------------------------------------------------

socket.on("erreur", (data) => afficherErreurCiblee(data.message));

socket.on("connect_error", () => toast("Connexion au serveur impossible pour le moment."));

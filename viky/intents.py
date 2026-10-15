"""Compréhension des commandes : transforme une phrase en intention."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .text import fold_pairs, normalize, squash


@dataclass
class Intent:
    name: str
    lang: str
    args: dict[str, str] = field(default_factory=dict)


_FILLERS = {
    "fr": r"\b(s il te plait|s il vous plait|est ce que tu peux|est ce que tu pourrais|"
          r"tu peux|tu pourrais|peux tu|pourrais tu|j aimerais que tu|je veux que tu|"
          r"je voudrais que tu|stp|svp)\b",
    "en": r"\b(please|can you|could you|would you|will you|i want you to|i d like you to)\b",
}

# L'ordre compte : la première règle qui correspond l'emporte.
# Les commandes précises (projecteur, Excel, diapos) passent avant les commandes
# générales, et les « verbe + complément » avant les mots-clés, pour que
# « cherche la date de noël » soit une recherche et pas la date.
_SCREEN_FR = r"(le |la |l )?(projecteur|retroprojecteur|retro projecteur|videoprojecteur|grand ecran|ecran du public)"
_KINDS_FR = r"(fichier|document|pdf|presentation|diaporama|powerpoint|diapo|tableau|excel|classeur|photo|image|video)"
_NUM_FR = (r"(?P<n>\d+|un|une|premier|premiere|deux|deuxieme|second|seconde|trois|troisieme|quatre|"
           r"quatrieme|cinq|cinquieme|six|sixieme|sept|septieme|huit|huitieme|dernier|derniere)")
_NUM_EN = r"(?P<n>\d+|one|first|two|second|three|third|four|fourth|five|fifth|six|sixth|last)"
_MAIL_FR = r"(e ?mails?|mails?|courriels?)"
_MAIL_EN = r"(e ?mails?|mails?)"
_KINDS_EN = r"(file|document|pdf|presentation|slideshow|powerpoint|slides|spreadsheet|excel|workbook|photo|picture|image|video)"

_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "fr": [
        ("quit", r"^(arrete toi|au revoir|eteins toi|bonne nuit|quitte toi|ferme toi|desactive toi)$"),
        ("thanks", r"^(merci( beaucoup| bien)?|c est gentil)$"),
        ("greet", r"^(bonjour|salut|coucou|bonsoir|hello)$"),
        ("lang_en", r"^(parle|passe|reponds)( moi)? en anglais$"),
        ("lang_fr", r"^(parle|passe|reponds)( moi)? en francais$"),
        # --- interface
        ("ui_hud", r"^(mode jarvis|affiche l interface|ouvre l interface|ouvre le hud|affiche le hud|"
                   r"montre toi|affiche toi)$"),
        ("ui_widget", r"^(mode discret|reduis l interface|cache l interface|ferme l interface|cache toi)$"),
        # --- mémoire et conversation
        ("set_name", r"^(appelle moi|mon prenom est|mon nom est|je m appelle) (?P<name>.+)$"),
        ("remember", r"^(souviens toi|rappelle toi|retiens bien|retiens|memorise|n oublie pas)( que| de| d)? (?P<fact>.+)$"),
        ("recall", r"(que sais tu (de|sur) moi|qu est ce que tu sais (de|sur) moi|de quoi tu te souviens|qu as tu retenu)"),
        ("forget", r"^(oublie tout|efface ta memoire|oublie ce que tu sais sur moi)$"),
        # --- e-mails et agenda
        ("mail_check", rf"({_MAIL_FR} (non lus|recus)|mes {_MAIL_FR}|nouveaux {_MAIL_FR}|(des|du|de nouveaux) {_MAIL_FR}|"
                       rf"ma boite (mail|de reception)|j ai du courrier)"),
        ("mail_read", rf"^(lis|ouvre|lire|resume)( moi)?( le)? {_MAIL_FR}( numero)? {_NUM_FR}$"),
        ("mail_read", rf"^(lis|ouvre|lire|resume)( moi)? le {_NUM_FR} {_MAIL_FR}$"),
        ("mail_send", rf"^(envoie|ecris|redige)( un)? ({_MAIL_FR}|message) a (?P<to>.+?)"
                      rf"( (pour (lui |leur )?dire|disant|en disant) (que |qu )?(?P<body>.+))?$"),
        ("mail_file", rf"^(envoie|transfere|partage)( moi)? (?P<file>.+?) a (?P<to>.+?) par {_MAIL_FR}$"),
        ("mail_file", r"^(envoie|transfere|partage)( moi)? (?P<file>.+?) a (?P<to>[^ ]+( [^ ]+)?)$"),
        ("agenda_add", r"^(ajoute|mets|cree|note|programme|inscris)( moi)? (un |le )?(rendez vous|rdv|evenement|reunion)"
                       r"(?P<rest>.*)$"),
        ("agenda_add", r"^(ajoute|mets|note|inscris) (?P<rest>.+) (a|dans) (mon|l) (agenda|calendrier)$"),
        ("agenda", r"^(?P<text>.*(mon agenda|mes rendez vous|mon planning|qu est ce que j ai( de prevu)?|prochain rendez vous|"
                   r"mon emploi du temps|ai je (des|un) rendez vous|mon calendrier).*)$"),
        # --- rappels, minuteurs, briefing
        ("timer", r"^((lance|mets|demarre|fais|programme)( moi)? )?(un )?(minuteur|chrono|compte a rebours|timer)"
                  r"( de| pour| dans)? (?P<duration>.+)$"),
        ("remind", r"^(rappel+e moi|rapel+e moi|rappe[lz]? moi|fais moi penser|previens moi|mets( moi)? un rappel|"
                   r"cree un rappel|ajoute un rappel)"
                   r"(?P<rest>.*)$"),
        ("list_reminders", r"(quels sont mes rappels|^mes rappels$|liste (des|mes) rappels|qu est ce que j ai de prevu|"
                           r"^mon programme$)"),
        ("clear_reminders", r"^(annule|supprime|efface) (tous )?(mes|les) (rappels|minuteurs)$"),
        ("briefing", r"^(briefing|fais( moi)? le point|resume de la journee|quoi de neuf aujourd hui|ma journee|"
                     r"le point du jour)$"),
        # --- contrôle du PC
        ("shutdown", r"^(eteins|arrete|eteindre) (l ordinateur|le pc|l ordi)$"),
        ("restart", r"^(redemarre|redemarrer) (l ordinateur|le pc|l ordi)$"),
        ("sleep", r"^(mets (l ordinateur|le pc|l ordi) en veille|mise en veille)$"),
        ("confirm", r"^(oui|confirme|je confirme|vas y|c est ca|affirmatif)$"),
        ("cancel", r"^(non|annule|laisse tomber)$"),
        ("status", r"(etat du (pc|systeme|ordinateur)|batterie|processeur|memoire vive|diagnostic)"),
        ("wifi", r"(wifi|wi fi|quel reseau)"),
        ("brightness_set", r"^(mets |regle )?(la )?luminosite (a|au|sur) (?P<level>.+?)( pour cent)?$"),
        ("brightness_up", r"((monte|augmente) (la )?luminosite|plus lumineux)"),
        ("brightness_down", r"((baisse|diminue) (la )?luminosite|moins lumineux)"),
        ("media_pause", r"^(pause|mets (la musique )?en pause|arrete la musique|reprends la musique|relance la musique|"
                        r"lecture|play)$"),
        ("media_next", r"^((chanson|musique|morceau|titre|piste) suivante?|(passe|change) (la chanson|de chanson|"
                       r"la musique|de musique))$"),
        ("media_previous", r"^(chanson|musique|morceau|titre|piste) precedente?$"),
        ("desktop", r"^(affiche le bureau|montre le bureau|reduis tout|cache tout)$"),
        ("switch_window", r"^(change de fenetre|fenetre suivante|bascule)$"),
        ("maximize", r"^(agrandis|maximise)( la fenetre)?$"),
        ("minimize", r"^(reduis|minimise)( la fenetre)?$"),
        # --- magie
        ("stage_on", r"^(mode spectacle|passe en mode spectacle|active le mode spectacle)$"),
        ("stage_off", r"^(mode normal|fin du spectacle|desactive le mode spectacle|quitte le mode spectacle)$"),
        ("reveal", r"^(revele|devoile|montre|affiche)( la| ta| sa| leur| notre| le| ma)? "
                   r"(carte|prediction|revelation|reponse|pensee|secret)$|^(revele|devoile)( tout| le secret)?$"),
        ("guess", r"(devine|quelle (est (sa|la|leur|ma) )?carte|a quoi (il|elle|je|ils|elles) pense|"
                  r"lis dans (ses|leurs|mes|les) pensees|qu (a t il|a t elle|ai je) choisi)"),
        ("show_text", r"^ecris (?P<text>.+) (sur|a) (l ecran|le projecteur|le grand ecran)$"),
        ("clear_stage", r"^(efface l ecran|efface tout|ecran vide|enleve (ca|la revelation|le texte))$"),
        # --- diaporama et projecteur
        ("next", r"^((diapo|diapositive|page|slide|image|photo) suivante|suivant|suivante|la suite|avance)$"),
        ("previous", r"^((diapo|diapositive|page|slide|image|photo) precedente|precedent|precedente|"
                     r"reviens en arriere|recule|retour)$"),
        ("goto", r"^(va|aller|passe|reviens|retourne)( a| au)? (la )?(diapo|diapositive|page|slide)"
                 r"( numero)? (?P<n>.+)$"),
        ("show_start", r"^(lance|demarre|commence|debute)( le| la)? (diaporama|presentation|projection)$"),
        ("show_end", r"^(arrete|termine|quitte|stoppe|ferme)( le| la)? (diaporama|presentation|projection)$"),
        ("black", r"^(ecran noir|noir|mets (l ecran )?au noir|eteins l ecran|coupe l image)$"),
        ("resume", r"^(rallume l ecran|reprends|reprise|remets l image|ecran normal|enleve le noir)$"),
        ("fullscreen", r"(plein ecran)$"),
        ("display_clone", r"^(duplique|dupliquer|clone)( l ecran| les ecrans)?$"),
        ("display_extend", r"^(etends|etendre|ecran etendu)( l ecran| les ecrans)?$"),
        ("display_external", r"^((le )?projecteur seulement|seulement le projecteur|uniquement le projecteur)$"),
        ("display_internal", r"^((l )?ecran du (pc|portable|ordinateur) seulement|deconnecte le projecteur)$"),
        ("show_report", rf"^(affiche|montre|ouvre|projette)( moi)? (le |la )?(rapport|recherche|dossier de recherche)"
                        rf"(?P<projector>( sur| au| vers) {_SCREEN_FR})?$"),
        ("project_current", rf"^(envoie|mets|bascule|deplace)( ca| la fenetre| tout ca)? (sur|au|vers) {_SCREEN_FR}$"),
        ("project", rf"^(mets|envoie|affiche|montre|ouvre|lance)( moi)? (?P<target>.+) (sur|au|vers) {_SCREEN_FR}$"),
        ("project", r"^(projette|projeter|diffuse|diffuser)( moi)? (?P<target>.+)$"),
        ("close_current", r"^(ferme|quitte)( le| la| l| ce| cette)? (fichier|document|fenetre|pdf|tableau|"
                          r"classeur|image|photo|video)$|^ferme (ca|tout ca)$"),
        # --- Excel et PowerPoint
        ("cell_set", r"^(mets|ecris|inscris|entre|saisis|tape|note)( le nombre| la valeur| le texte)? (?P<value>.+) "
                     r"(dans|en) (la )?(cellule|case) (?P<cell>.+)$"),
        ("cell_set", r"^(la )?(cellule|case) (?P<cell>.+?) (egale|vaut|devient|est egale a) (?P<value>.+)$"),
        ("cell_get", r"^(lis|lire|dis moi|donne moi|que vaut|combien vaut|qu y a t il dans)( le contenu de)? "
                     r"(la )?(cellule|case) (?P<cell>.+)$"),
        ("cell_clear", r"^(efface|vide|supprime)( le contenu de)? (la )?(cellule|case) (?P<cell>.+)$"),
        ("save", r"^(enregistre|sauvegarde|sauve)( le fichier| le document| le classeur| la presentation| tout)?$"),
        ("sheet_next", r"^(feuille|onglet) suivante?$"),
        ("sheet_previous", r"^(feuille|onglet) precedente?$"),
        ("slide_title", r"^(change|modifie|remplace) le titre( de (la|cette) (diapo|diapositive|slide|page))? "
                        r"(en|par) (?P<text>.+)$"),
        ("slide_title", r"^(mets|ecris) (?P<text>.+) (comme|en) titre$"),
        ("slide_replace", r"^(remplace|corrige|change|modifie) (le mot |la faute )?(?P<old>.+?) (par|en) (?P<new>.+?)"
                          r"( (sur|dans) (la|cette) (diapo|diapositive|slide|page))?$"),
        # --- fichiers
        ("open_file", rf"^(ouvre|ouvrir|affiche|montre|cherche|trouve|retrouve)( moi)? "
                      rf"(?P<target>(le |la |l |les |mon |ma |mes |un |une )?{_KINDS_FR}\b.*)$"),
        # --- météo, actualité, intelligence
        ("weather", r"^(?P<text>.*\b(quel temps|meteo|pleuvoir|pleut|neiger|temperature exterieure)\b.*)$"),
        ("news_detail", rf"^(approfondis|developpe|detaille|raconte moi|parle moi de|dis m en plus sur|"
                        rf"plus de details sur|explique moi|lis moi)( l| la| le)? ?"
                        rf"(info|titre|article|nouvelle|actualite|sujet)?( numero)? {_NUM_FR}$"),
        ("news", r"(les infos|les informations|l actualite|l actu|les actus|les nouvelles|les grands titres|"
                 r"les titres (du jour|de l actualite|de l actu)|flash info|quoi de neuf dans le monde)"),
        ("research", r"^(fais( moi)?( une)? (recherche|des recherches)( complete| approfondie| detaillee)? sur|"
                     r"renseigne toi sur|documente toi sur|recherche complete sur|"
                     r"fais( moi)? un (rapport|dossier|expose) sur|enquete sur) (?P<query>.+)$"),
        ("followup", r"^(approfondis|developpe|dis m en plus|continue|et ensuite|explique (davantage|plus)|"
                     r"plus de details|vas y continue|precise|et pourquoi)$"),
        # --- internet et divers
        ("youtube", r"^(mets|joue|lance|cherche|mettre|jouer) (?P<query>.+) sur youtube$"),
        ("search", r"^(cherche|recherche|google|chercher|rechercher)"
                   r"( sur (internet|google|le web))? (?P<query>.+)$"),
        ("note", r"^(note|prends note|prends en note|ecris)( que| de)? (?P<text>.+)$"),
        ("whoami", r"(qui es tu|tu es qui|comment tu t appelles|ton nom|presente toi)"),
        ("help", r"(^aide( moi)?$|que sais tu faire|qu est ce que tu sais faire|"
                 r"qu est ce que tu peux faire|tes commandes)"),
        ("time", r"(quelle heure|l heure qu il est|donne moi l heure|^l heure$)"),
        ("date", r"(quel jour|quelle date|la date|on est le combien)"),
        ("joke", r"(blague|fais moi rire)"),
        ("vol_up", r"((monte|augmente|hausse) (le )?(son|volume)|plus fort)"),
        ("vol_down", r"((baisse|diminue|descends) (le )?(son|volume)|moins fort)"),
        ("mute", r"(coupe (le )?son|sourdine|\bsilence\b|\bmute\b)"),
        ("lock", r"verrouille"),
        ("screenshot", r"capture (d |l )?ecran"),
        ("photo", r"((prends|prend|prendre|fais) (moi )?une photo|selfie)"),
        ("ask", r"^(?P<question>(qu est ce que|qu est ce qu|c est quoi|pourquoi|comment|qui (est|etait|a|sont|etaient)|"
                r"quand|combien|ou (est|se trouve|sont|vit)|quel|quelle|quels|quelles|explique|dis moi|"
                r"est ce que|est ce qu|raconte moi|parle moi|que penses tu|donne moi) .+)$"),
        ("close", r"^(ferme|quitte|fermer) (?P<target>.+)$"),
        ("open", r"^(ouvre|ouvrir|lance|lancer|demarre|demarrer|va sur|affiche|montre)( moi)? (?P<target>.+)$"),
    ],
    "en": [
        ("quit", r"^(stop listening|goodbye|bye|shut down|turn off|go to sleep|exit|quit)$"),
        ("thanks", r"^(thank you|thanks)( very much| a lot)?$"),
        ("greet", r"^(hello|hi|hey|good (morning|evening|afternoon))$"),
        ("lang_fr", r"^(speak|switch to|answer in|talk in) french$"),
        ("lang_en", r"^(speak|switch to|answer in|talk in) english$"),
        ("ui_hud", r"^(jarvis mode|show (the )?interface|open the hud|show yourself)$"),
        ("ui_widget", r"^(discreet mode|hide (the )?interface|hide yourself)$"),
        ("set_name", r"^(call me|my name is|i am called) (?P<name>.+)$"),
        ("remember", r"^(remember|don t forget|memorize)( that)? (?P<fact>.+)$"),
        ("recall", r"(what do you know about me|what do you remember)"),
        ("forget", r"^(forget everything|erase your memory)$"),
        ("mail_check", rf"(my {_MAIL_EN}|new {_MAIL_EN}|check (my )?{_MAIL_EN}|my inbox)"),
        ("mail_read", rf"^(read|open)( me)?( the)? {_MAIL_EN}( number)? {_NUM_EN}$"),
        ("mail_send", rf"^(send|write)( an| a)? ({_MAIL_EN}|message) to (?P<to>.+?)( (saying|to say) (that )?(?P<body>.+))?$"),
        ("mail_file", r"^(send|share) (?P<file>.+?) to (?P<to>.+?)( by e ?mail)?$"),
        ("agenda_add", r"^(add|schedule|create) (an |a )?(appointment|event|meeting)(?P<rest>.*)$"),
        ("agenda", r"^(?P<text>.*(my (calendar|agenda|schedule)|my appointments|what do i have|next appointment).*)$"),
        ("timer", r"^(set |start )?(a )?(timer|countdown)( for)? (?P<duration>.+)$"),
        ("remind", r"^(remind me|set a reminder)(?P<rest>.*)$"),
        ("list_reminders", r"(my reminders|what s on my schedule|what do i have planned)"),
        ("clear_reminders", r"^(cancel|delete|clear) (all )?(my |the )?(reminders|timers)$"),
        ("briefing", r"^(briefing|daily briefing|brief me|morning briefing)$"),
        ("shutdown", r"^(shut down|turn off) the (computer|pc)$"),
        ("restart", r"^restart the (computer|pc)$"),
        ("sleep", r"^(put the (computer|pc) to sleep|sleep mode)$"),
        ("confirm", r"^(yes|confirm|go ahead|do it)$"),
        ("cancel", r"^(no|cancel|never mind)$"),
        ("status", r"(system status|battery|cpu|processor)"),
        ("wifi", r"(wifi|wi fi|which network)"),
        ("brightness_set", r"^(set )?(the )?brightness to (?P<level>.+?)( percent)?$"),
        ("brightness_up", r"(brightness up|brighter|increase (the )?brightness)"),
        ("brightness_down", r"(brightness down|dimmer|decrease (the )?brightness)"),
        ("media_pause", r"^(pause|play|resume the music|pause the music)$"),
        ("media_next", r"^(next song|next track|skip (this )?song)$"),
        ("media_previous", r"^(previous song|previous track)$"),
        ("desktop", r"^(show (the )?desktop|minimize everything)$"),
        ("switch_window", r"^(switch window|next window)$"),
        ("maximize", r"^maximize( the window)?$"),
        ("minimize", r"^minimize( the window)?$"),
        ("stage_on", r"^(show mode|stage mode( on)?|start the show)$"),
        ("stage_off", r"^(normal mode|end of the show|stage mode off)$"),
        ("reveal", r"^(reveal|show)( the| my| her| his| their)? (card|prediction|secret|answer)$|^reveal( it)?$"),
        ("guess", r"(guess|what card|which card|what (is|are) (he|she|they|i) thinking)"),
        ("show_text", r"^write (?P<text>.+) on the (screen|projector|big screen)$"),
        ("clear_stage", r"^(clear the screen|clear everything|blank screen)$"),
        ("next", r"^(next( slide| page| picture)?|go on|continue)$"),
        ("previous", r"^(previous( slide| page| picture)?|go back|back)$"),
        ("goto", r"^(go|jump|skip)( back)? to (slide|page)( number)? (?P<n>.+)$"),
        ("show_start", r"^(start|begin|launch) the (slideshow|presentation)$"),
        ("show_end", r"^(stop|end|exit|close) the (slideshow|presentation)$"),
        ("black", r"^(black screen|blackout|black out the screen)$"),
        ("resume", r"^(resume|unblack|show the screen again)$"),
        ("fullscreen", r"full ?screen$"),
        ("display_clone", r"^(duplicate|mirror)( the)? (screen|screens|display)$"),
        ("display_extend", r"^extend( the)? (screen|screens|display)$"),
        ("display_external", r"^projector only$"),
        ("display_internal", r"^(pc|computer|laptop) screen only$"),
        ("show_report", r"^(show|open|project)( me)? the (report|research)(?P<projector> on the (projector|big screen))?$"),
        ("project_current", r"^(send|put|move) (it|this|the window) (to|on) the (projector|big screen)$"),
        ("project", r"^(put|send|show|open) (?P<target>.+) on the (projector|big screen)$"),
        ("project", r"^(project|cast) (?P<target>.+)$"),
        ("close_current", r"^close (the |this )?(file|document|window|pdf|spreadsheet|picture|video)$"),
        ("cell_set", r"^(put|write|enter|type) (?P<value>.+) in (cell|box) (?P<cell>.+)$"),
        ("cell_get", r"^(read|what is in|what s in) cell (?P<cell>.+)$"),
        ("cell_clear", r"^(clear|erase|delete) cell (?P<cell>.+)$"),
        ("save", r"^save( the file| it| everything| the document)?$"),
        ("sheet_next", r"^next (sheet|tab)$"),
        ("sheet_previous", r"^previous (sheet|tab)$"),
        ("slide_title", r"^change the (slide )?title to (?P<text>.+)$"),
        ("slide_replace", r"^(replace|correct|change) (the word )?(?P<old>.+?) (with|to|by) (?P<new>.+?)( on (the|this) slide)?$"),
        ("open_file", rf"^(open|show me|find)( up)? (?P<target>(the |my |a )?{_KINDS_EN}\b.*)$"),
        ("weather", r"^(?P<text>.*\b(weather|forecast|going to rain|raining|going to snow)\b.*)$"),
        ("news_detail", rf"^(tell me more about|more about|expand on|explain|read( me)?)( the)? ?"
                        rf"(story|headline|article|news)?( number)? {_NUM_EN}$"),
        ("news", r"\b(the news|headlines|news headlines|what s happening in the world)\b"),
        ("research", r"^(research|do( some)? research on|look into|find out everything about|"
                     r"write( me)? a report on|investigate) (?P<query>.+)$"),
        ("followup", r"^(tell me more|go on|go deeper|more details|elaborate|explain more|and why)$"),
        ("youtube", r"^(play|put on|search|search for) (?P<query>.+) on youtube$"),
        ("search", r"^(search|google|look up)( for| the web for| online for)? (?P<query>.+)$"),
        ("note", r"^(take a note|note|write down)( that)? (?P<text>.+)$"),
        ("whoami", r"(who are you|what is your name|what s your name|introduce yourself)"),
        ("help", r"(^help( me)?$|what can you do|your commands)"),
        ("time", r"(what time|the time)"),
        ("date", r"(what day|what s the date|what is the date|today s date|the date)"),
        ("joke", r"(joke|make me laugh)"),
        ("vol_up", r"(turn (it )?up|volume up|louder|(increase|raise) (the )?volume)"),
        ("vol_down", r"(turn (it )?down|volume down|quieter|(decrease|lower) (the )?volume)"),
        ("mute", r"(\bmute\b|\bsilence\b)"),
        ("lock", r"lock (the |my )?(computer|pc|screen|session)"),
        ("screenshot", r"(screenshot|screen shot|capture (the )?screen)"),
        ("photo", r"((take|snap) a (photo|picture|selfie)|selfie)"),
        ("ask", r"^(?P<question>(what|why|how|who|when|where|which|is|are|does|do|can|could|should|"
                r"explain|tell me|describe) .+)$"),
        ("close", r"^(close|quit|kill) (?P<target>.+)$"),
        ("open", r"^(open|launch|start|run|go to|show me)( up)? (?P<target>.+)$"),
    ],
}

_COMPILED = {
    lang: [(name, re.compile(pattern)) for name, pattern in patterns]
    for lang, patterns in _PATTERNS.items()
}

LANGS = tuple(_PATTERNS)


def clean(text: str, lang: str) -> tuple[str, str]:
    """Retire les formules de politesse. Renvoie (texte sans accents, texte avec accents)."""
    pairs = fold_pairs(text)
    folded = "".join(b for b, _ in pairs)
    removed = {i for m in re.finditer(_FILLERS[lang], folded) for i in range(*m.span())}
    pairs = squash([p for i, p in enumerate(pairs) if i not in removed])
    return "".join(b for b, _ in pairs), "".join(c for _, c in pairs)


def parse(text: str, lang: str) -> Intent | None:
    """Reconnaît une commande dans une langue donnée.

    La règle est cherchée dans le texte sans accents, mais les paramètres
    (texte à écrire, question…) sont recopiés avec leurs accents.
    """
    folded, display = clean(text, lang)
    if not folded:
        return None
    for name, regex in _COMPILED[lang]:
        match = regex.search(folded)
        if match:
            args = {k: display[match.start(k):match.end(k)].strip()
                    for k, v in match.groupdict().items() if v}
            return Intent(name, lang, args)
    return None


def parse_any(texts: dict[str, str], order: list[str]) -> Intent | None:
    """Essaie chaque langue dans l'ordre de préférence.

    `texts` associe une langue au texte reconnu par le modèle de cette langue.
    """
    for lang in order:
        if lang in texts and lang in _COMPILED:
            intent = parse(texts[lang], lang)
            if intent:
                return intent
    return None

# messages.py

# General
GAME_NAME = "EnlargeYourFrench"
GAME_VERSION = "2.0"

# Backend checks
BACKEND_NOT_IMPLEMENTING_METHODS = "Backend is not implementing enough methods to be valid, check the doc"

# Start
READY_TO_PLAY = ":white_check_mark: Prêt à jouer"

# Error & Info Messages
GAME_ALREADY_RUNNING = "Une partie est déjà en cours, allez jouer avec eux plutôt"
NO_GAMES_RECORDED = "Aucune partie enregistrée sur ce salon"

# Game messages
GAME_STARTING = "game starting ..."
GAME_STARTED = "game started"
GAME_POST_START = """C'est parti ! Règles du jeu : je vous donne une ou plusieurs définition, vous devez trouver le mot associé.\n"""
TIME_LIMIT_ACHIEVED = "Limite de temps atteinte !"
NEXT_WORD_5_SECONDS = "Prochain mot dans 5 secondes ..."
NO_ONE_FOUND_WORD = "Personne n'a trouvé, le mot était: ***{current_word}***\n"
WORD_FOUND = "@{player_id} gagne {points} points sur ***{current_word}***.\n"
SCORE_LIMIT_REACHED = "Limite de score atteinte !"
NEXT_MESSAGE = "Passe. Le mot était ***{current_word}*** \n"
VOTING_TO_NEXT = "Passe ({current_votes}/{votes_needed})"

# Hints
HINT = "**Indice** : `{hint}`"

# Score messages
LEADERBOARD = "Les scores de tout temps sur ce salon : \n{global_scores}"
FINISH_SCORES = "C'est fini ! Scores: {scores}"

# Bug report
BUG_REPORT = "Rapport de bug enregistré pour `{word}`."

# Help text
HELP_TEXT = """
        Commandes disponibles hors jeu:
        'play' : lance une partie
        'play N minutes M points' : lance une partie en N minutes ou M points
        'leaderboard' : affiche le total des scores du canal
        'help' : affiche cet aide
        Commandes disponibles en jeu:
        'next' : vote pour passer au mot suivant
        'stahp' : arrête la partie
        'bug' : émet un rapport de bug pour le mot courant. Mes esclaves règlerons ensuite le problème.
        """

# messages.py

# General
GAME_NAME = "EnlargeYourFrench"
GAME_VERSION = "2.0"

# Backend checks
BACKEND_NOT_IMPLEMENTING_METHODS = "Backend is not implementing enough methods to be valid, check the doc"

# Start
READY_TO_PLAY = ":white_check_mark: Ready to play"

# Error & Info Messages
GAME_ALREADY_RUNNING = "A game is already in progress, go play with them instead"
NO_GAMES_RECORDED = "No games recorded on this channel"

# Game messages
GAME_STARTING = "game starting ..."
GAME_STARTED = "game started"
GAME_POST_START = """Let's go! Game rules: I will give you one or more definitions, you have to find the associated word.\n"""
TIME_LIMIT_ACHIEVED = "Time limit reached!"
NEXT_WORD_5_SECONDS = "Next word in 5 seconds ..."
NO_ONE_FOUND_WORD = "No one found it, the word was: ***{current_word}***\n"
WORD_FOUND = "@{player_id} wins {points} points on ***{current_word}***.\n"
SCORE_LIMIT_REACHED = "Score limit reached!"
NEXT_MESSAGE = "Pass. The word was ***{current_word}*** \n"
VOTING_TO_NEXT = "Pass ({current_votes}/{votes_needed})"

# Hints
HINT = "**Hint** : `{hint}`"

# Score messages
LEADERBOARD = "All-time scores on this channel: \n{global_scores}"
FINISH_SCORES = "It's over! Scores: {scores}"

# Bug report
BUG_REPORT = "Bug report recorded for `{word}`."

# Help text
HELP_TEXT = """
        Available commands outside the game:
        'play' : starts a game
        'play N minutes M points' : starts a game in N minutes or M points
        'leaderboard' : shows the total scores of the channel
        'help' : shows this help
        Available commands in-game:
        'next' : vote to skip to the next word
        'stahp' : stops the game
        'bug' : submits a bug report for the current word. My slaves will fix the problem afterwards.
        """

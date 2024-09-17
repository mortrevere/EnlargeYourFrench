import os
import inspect
import math
import random
import string
import threading
import time
from typing import List, Tuple, Optional

from Levenshtein import distance
from loguru import logger
from wikidict import Wikidict

import scores

# Constants
GLOBAL_TIME_LIMIT = 900
WORD_TIME_LIMIT = 50
WORD_COUNT_LIMIT = 20
TIME_PER_HINT = 10
PERCENT_PER_HINT = 0.2  # percent of word to reveal every TIME_PER_HINT seconds
TOTAL_HINT_PERCENT = 0.6
POINTS_LIMIT = 40
NEXT_QUORUM_FACTOR = 0.5  # percent of players

class EYFEngine:
    def __init__(self, backend, name=None, version=None):
        self.GAMES = {}
        self.GAMES_THREADS = {}
        self.SCORE_HANDLER = scores.ScoreHandler()
        self.name = os.getenv("GAME_NAME", name if name else "EnlargeYourFrench")
        self.version = os.getenv("GAME_VERSION", version if version else "2.0")
        self.backend = backend
        self.wikidict = Wikidict()

    def _dump_state(self):
        logger.debug(f"Engine State: {vars(self)}")
        self.wikidict._dump_state()

    def _check_backend(self):
        required_methods = ("reply_to", "post_general", "post_in")
        for method in required_methods:
            if not callable(getattr(self.backend, method, None)):
                raise Exception("Backend is not implementing enough methods to be valid, check the doc")

    def start(self):
        self._check_backend()
        self.backend.post_general(":white_check_mark: Prêt à jouer")

    def _get_game(self):
        stack = inspect.stack()
        caller = stack[2][0]
        return self.GAMES[caller.f_locals["self"].key]

    def game_post(self, text):
        game = self._get_game()
        self.backend.post_in(game.channel, text)

    def get_game(self, key):
        return self.GAMES.get(key)

    def has_unfinished_game(self, key):
        return key in self.GAMES and not self.GAMES[key].finished

    def new_game(self, text, channel_id):
        logger.warning("game starting ...")
        game = Game(self, channel_id, channel_id, self.try_parsing_game_parameters(text))
        self.GAMES[channel_id] = game
        self.GAMES_THREADS[channel_id] = threading.Thread(target=game.start)
        self.GAMES_THREADS[channel_id].start()
        logger.warning("game started")

    def get_scores(self, key):
        global_scores = self.SCORE_HANDLER.get_scores(key)
        if global_scores is None:
            return "Aucune partie enregistrée sur ce salon"
        return f"Les scores de tout temps sur ce salon : \n{global_scores}"

    @staticmethod
    def try_parsing_game_parameters(message):
        chunks = message.split(" ")
        time_limit = GLOBAL_TIME_LIMIT
        points_limit = POINTS_LIMIT

        try:
            i = chunks.index("minutes")
            if i - 1 >= 0 and chunks[i - 1].isdigit():
                time_limit = int(chunks[i - 1]) * 60
        except ValueError:
            pass

        try:
            i = chunks.index("points")
            if i - 1 >= 0 and chunks[i - 1].isdigit():
                points_limit = int(chunks[i - 1])
        except ValueError:
            pass

        return {"time_limit": time_limit, "points_limit": points_limit}

    @staticmethod
    def add_hint(current_hint, word):
        letters_to_reveal = max(1, math.floor(len(word) * PERCENT_PER_HINT))
        if current_hint.count("_") < letters_to_reveal:
            return current_hint
        for _ in range(letters_to_reveal):
            j = random.choice([j for j, char in enumerate(current_hint) if char == "_"])
            current_hint = current_hint[:j] + word[j] + current_hint[j+1:]
        return current_hint

    @staticmethod
    def get_score_string(game_scores):
        sorted_keys = sorted(game_scores.keys(), key=lambda k: game_scores[k], reverse=True)
        return "\n".join([f"@{player_id}: {game_scores[player_id]}" for player_id in sorted_keys])

    @staticmethod
    def human_readable_seconds(seconds):
        minutes = seconds // 60
        seconds %= 60
        result = ""
        if minutes:
            result += f"{minutes} min "
        if seconds:
            result += f"{seconds} sec"
        return result

    @staticmethod
    def help():
        return """
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

    def handle_mention(self, text, channel_id, _message):
        logger.debug("Handling mention ...")
        if "help" in text:
            self.backend.reply_to(_message, self.help())
        elif "leaderboard" in text:
            self.backend.reply_to(_message, self.get_scores(channel_id))
        elif self.has_unfinished_game(channel_id):
            if "stahp" in text:
                self.get_game(channel_id).finish()
            elif "bug" in text:
                self.get_game(channel_id).report_bug(_message)
        else:
            self._handle_play_request(text, channel_id, _message)

    def _handle_play_request(self, text, channel_id, _message):
        logger.debug(f"Got play request: {_message}")
        lets_play = any(word in text for word in ["play", "game", "jeu", "jouer", "partie"])
        if self.has_unfinished_game(channel_id):
            self.backend.reply_to(_message, "Une partie est déjà en cours, allez jouer avec eux plutôt")
            return
        if lets_play:
            self.new_game(text, channel_id)

    def handle_message(self, text, channel_id, author_id, _message):
        logger.debug(f"Handling message [{text=}]")
        if self.has_unfinished_game(channel_id):
            self.get_game(channel_id).handle_response(author_id, text.lower().strip())

class Game:
    def __init__(self, engine, key, channel, limits):
        self.engine = engine
        self.key = key
        self.channel = channel
        self.game_start_time = time.time()
        self.word_start_time = 0
        self.word = None
        self.definition = None
        self.kill_switch = False
        self.scores = {}
        self.next_list = []
        self.potential_players = []
        self.current_hint = ""
        self.finished = False
        self.limits = limits
        self.game_running = False

    def _dump_state(self):
        logger.debug(f"Game State: {vars(self)}")
        self.engine._dump_state()

    def start(self):
        self.engine.game_post(
            f"C'est parti ! Règles du jeu : je vous donne une ou plusieurs définition, vous devez trouver le mot associé.\n"
            f"Limite de temps : {EYFEngine.human_readable_seconds(self.limits['time_limit'])}\n"
            f"Limite de points: {self.limits['points_limit']}"
        )
        self.new_word()

    def new_word(self):
        self.kill_switch = False
        if time.time() - self.game_start_time > self.limits['time_limit']:
            self.engine.game_post("Limite de temps atteinte !")
            self.finish()
            return

        try:
            self._prepare_next_word()
            if self.kill_switch:
                return
            self._process_current_word()
        except Exception as e:
            logger.critical(e)

    def _prepare_next_word(self):
        self.word = None
        self.next_list = []
        self.engine.game_post("Prochain mot dans 5 secondes ...")
        self._dump_state()
        time.sleep(5)

    def _process_current_word(self):
        self.word_start_time = time.time()
        self.word, self.definition = self.engine.wikidict.get_word_and_definition()
        logger.info(f"Got word {self.word}, def={self.definition[:32]}...")
        current_word = self.word
        self.current_hint = "".join(["_" if l in string.ascii_lowercase else l for l in current_word])
        self._post_word_info()
        self._reveal_hints(current_word)
        logger.warning("_reveal_hints terminated")
        self._post_word_reveal_result(current_word)
        logger.warning("_post_word_reveal_result terminated")

    def _post_word_info(self):
        indication = f"{len(self.word)} lettres"
        number_of_words = self.word.count(" ") + self.word.count("-") + 1
        if number_of_words > 1:
            indication += f", {number_of_words} mots"
        self.engine.game_post(f"{indication} : \n{self.definition}")

    def _reveal_hints(self, current_word):
        max_hints = round(TOTAL_HINT_PERCENT / PERCENT_PER_HINT)
        for _ in range(max_hints):
            time.sleep(TIME_PER_HINT)
            if current_word != self.word:
                return
            self.current_hint = EYFEngine.add_hint(self.current_hint, current_word)
            self.engine.game_post(f"**Indice** : `{self.current_hint}`")

    def _post_word_reveal_result(self, current_word):
        time_elapsed_for_word = time.time() - self.word_start_time
        if time_elapsed_for_word < WORD_TIME_LIMIT:
            time.sleep(WORD_TIME_LIMIT - time_elapsed_for_word)

        if current_word == self.word:
            current_word = self.word
            self.word = None
            self.engine.game_post(f"Personne n'a trouvé, le mot était: ***{current_word}***\n")
            self.new_word()

    def found(self, player_id):
        current_word = self.word
        self.word = None
        self.scores[player_id] = self.scores.get(player_id, 0) + self.current_hint.count("_")

        if self.scores[player_id] >= self.limits["points_limit"]:
            self.engine.game_post(
                f"@{player_id} gagne {self.current_hint.count('_')} points sur ***{current_word}***.\n"
                f"Limite de score atteinte !"
            )
            self.finish()
        else:
            self.engine.game_post(
                f"@{player_id} gagne {self.current_hint.count('_')} points sur ***{current_word}***.\n"
            )
            self.new_word()

    def next(self, player_id):
        if self.word is not None and player_id not in self.next_list:
            self.next_list.append(player_id)
            if len(self.next_list) >= len(self.potential_players) * NEXT_QUORUM_FACTOR:
                current_word = self.word
                self.word = None
                self.engine.game_post(f"Passe. Le mot était ***{current_word}*** \n")
                self.engine.wikidict.exclude(current_word)
                self.new_word()
            else:
                self.engine.game_post(
                    f"Passe ({len(self.next_list)}/{math.ceil(len(self.potential_players) * NEXT_QUORUM_FACTOR)})"
                )

    def soclose(self, player_id):
        self.engine.game_post(f"@{player_id} est très proche !")

    def potential(self, player_id):
        if player_id not in self.potential_players:
            self.potential_players.append(player_id)

    def finish(self):
        self.word = None
        self.finished = True
        self.kill_switch = True
        self.engine.SCORE_HANDLER.update(self.key, self.scores)
        self.engine.game_post(f"C'est fini ! Scores: {self.engine.get_score_string(self.scores)}")

    def report_bug(self, message):
        if self.word is not None:
            self.engine.wikidict.bug_report(self.word, message.content)
            self.engine.game_post(f"Rapport de bug enregistré pour `{self.word}`.")
            self.new_word()

    def handle_response(self, player_id, response):
        logger.debug(f"Handling response: {response}")
        if self.word is not None:
            self.potential(player_id)
            if response == "next":
                self.next(player_id)
            elif response == self.word:
                self.found(player_id)
            elif distance(response, self.word) < 3:
                self.soclose(player_id)

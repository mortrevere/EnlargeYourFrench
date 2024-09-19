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
#import i18n_fr as messages
messages = __import__("i18n_" + os.getenv("EYF_LOCALE", "fr"))
# Constants
GLOBAL_TIME_LIMIT = 900
WORD_TIME_LIMIT = 50
WORD_COUNT_LIMIT = 20
TIME_PER_HINT = 10
PERCENT_PER_HINT = 0.2  # percent of word to reveal every TIME_PER_HINT seconds
TOTAL_HINT_PERCENT = 0.6
POINTS_LIMIT = 40
NEXT_QUORUM_FACTOR = 0.5  # percent of players
RETELL_DEFINITION_AFTER_MESSAGE_COUNT = 5

class EYFEngine:
    def __init__(self, backend, name=None, version=None):
        self.GAMES = {}
        self.GAMES_THREADS = {}
        self.SCORE_HANDLER = scores.ScoreHandler()
        self.name = os.getenv("GAME_NAME", name if name else messages.GAME_NAME)
        self.version = os.getenv("GAME_VERSION", version if version else messages.GAME_VERSION)
        self.backend = backend

    def _dump_state(self):
        logger.debug(f"Engine State: {vars(self)}")

    def _check_backend(self):
        required_methods = ("reply_to", "post_general", "post_in")
        for method in required_methods:
            if not callable(getattr(self.backend, method, None)):
                raise Exception(messages.BACKEND_NOT_IMPLEMENTING_METHODS)

    def start(self):
        self._check_backend()
        self.backend.post_general(messages.READY_TO_PLAY)

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
        logger.warning(messages.GAME_STARTING)
        try:
            game = Game(self, channel_id, channel_id, self.try_parsing_game_parameters(text))
        except Exception as e:
            self.backend.post_general(f"Couldn't start game: {e}")
            return
        self.GAMES[channel_id] = game
        self.GAMES_THREADS[channel_id] = threading.Thread(target=game.start)
        self.GAMES_THREADS[channel_id].start()
        logger.warning(messages.GAME_STARTED)

    def get_scores(self, key):
        global_scores = self.SCORE_HANDLER.get_scores(key)
        if global_scores is None:
            return messages.NO_GAMES_RECORDED
        return messages.LEADERBOARD.format(global_scores=global_scores)

    @staticmethod
    def try_parsing_game_parameters(message):
        chunks = message.split(" ")
        time_limit = GLOBAL_TIME_LIMIT
        points_limit = POINTS_LIMIT
        dictionary = os.getenv("EYF_LANG", "fr")

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

        try:
            i = chunks.index("dict")
            if i - 1 >= 0:
                dictionary = str(chunks[i - 1])
        except ValueError:
            pass

        return {"time_limit": time_limit, "points_limit": points_limit, "dictionary": dictionary}

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
        return messages.HELP_TEXT

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
            self.backend.reply_to(_message, messages.GAME_ALREADY_RUNNING)
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
        self.game_config = limits
        self.received_messages = 0
        self.game_running = False
        dict_slug = Wikidict.get_dict(self.game_config["dictionary"])
        if dict_slug is None:
            raise Exception(f'Couldn\'t find dictionary {self.game_config["dictionary"]}')
        self.engine.wikidict = Wikidict(wiki_slug=dict_slug)

    def _dump_state(self):
        logger.debug(f"Game State: {vars(self)}")
        self.engine._dump_state()

    def start(self):
        self.engine.game_post(messages.GAME_POST_START + 
            f"Limite de temps : {EYFEngine.human_readable_seconds(self.game_config['time_limit'])}\n"
            f"Limite de points: {self.game_config['points_limit']}\n"
            f"Dictionnaire: {self.engine.wikidict.get_dict_string()}"
        )
        self.new_word()

    def new_word(self):
        self.kill_switch = False
        if time.time() - self.game_start_time > self.game_config['time_limit']:
            self.engine.game_post(messages.TIME_LIMIT_ACHIEVED)
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
        self.engine.game_post(messages.NEXT_WORD_5_SECONDS)
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
        self._post_word_reveal_result(current_word)

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
            if self.received_messages >= RETELL_DEFINITION_AFTER_MESSAGE_COUNT:
                self._post_word_info()
            self.engine.game_post(messages.HINT.format(hint=self.current_hint))
            self.received_messages = 0

    def _post_word_reveal_result(self, current_word):
        time_elapsed_for_word = time.time() - self.word_start_time
        if time_elapsed_for_word < WORD_TIME_LIMIT:
            time.sleep(WORD_TIME_LIMIT - time_elapsed_for_word)

        if current_word == self.word:
            current_word = self.word
            self.word = None
            self.engine.game_post(messages.NO_ONE_FOUND_WORD.format(current_word=current_word))
            self.new_word()

    def found(self, player_id):
        current_word = self.word
        self.word = None
        self.scores[player_id] = self.scores.get(player_id, 0) + self.current_hint.count("_")

        if self.scores[player_id] >= self.game_config["points_limit"]:
            self.engine.game_post(
                messages.WORD_FOUND.format(player_id=player_id, points=self.current_hint.count('_'), current_word=current_word) + messages.SCORE_LIMIT_REACHED
            )
            self.finish()
        else:
            self.engine.game_post(
                messages.WORD_FOUND.format(player_id=player_id, points=self.current_hint.count('_'), current_word=current_word)
            )
            self.new_word()

    def next(self, player_id):
        if self.word is not None and player_id not in self.next_list:
            self.next_list.append(player_id)
            if len(self.next_list) >= len(self.potential_players) * NEXT_QUORUM_FACTOR:
                current_word = self.word
                self.word = None
                self.engine.game_post(messages.NEXT_MESSAGE.format(current_word=current_word))
                self.engine.wikidict.exclude(current_word)
                self.new_word()
            else:
                self.engine.game_post(
                    messages.VOTING_TO_NEXT.format(current_votes=len(self.next_list), votes_needed=math.ceil(len(self.potential_players) * NEXT_QUORUM_FACTOR))
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
        self.received_messages = 0
        self.engine.SCORE_HANDLER.update(self.key, self.scores)
        self.engine.game_post(messages.FINISH_SCORES.format(scores=self.engine.get_score_string(self.scores)))

    def report_bug(self, message):
        if self.word is not None:
            self.engine.wikidict.bug_report(self.word, message.content)
            self.engine.game_post(messages.BUG_REPORT.format(word=self.word))
            self.new_word()

    def handle_response(self, player_id, response):
        logger.debug(f"Handling response: {response}")
        if self.word is not None:
            self.received_messages += 1
            self.potential(player_id)
            if response == "next":
                self.next(player_id)
            elif response == self.word:
                self.found(player_id)
            elif distance(response, self.word) < 3:
                self.soclose(player_id)

import random
import re
import sys
import discord
import time
import asyncio
import math
import os
import string
from Levenshtein import distance
from typing import List, Tuple, Optional
from dotenv import load_dotenv

import wikidict
import scores

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GLOBAL_TIME_LIMIT = 900
WORD_TIME_LIMIT = 50
WORD_COUNT_LIMIT = 20
TIME_PER_HINT = 10
PERCENT_PER_HINT = 0.2  # percent of word to reveal every TIME_PER_HINT seconds
TOTAL_HINT_PERCENT = 0.6
POINTS_LIMIT = 40
NEXT_QUORUM_FACTOR = 0.5  # percent of players


GAMES = {}

client = discord.Client()


def try_parsing_game_parameters(message):
    chunks = message.split(" ")
    time_limit, points_limit = GLOBAL_TIME_LIMIT, POINTS_LIMIT
    # game time
    try:
        i = chunks.index("minutes")
        if i - 1 > 0 and chunks[i - 1].isdigit():
            time_limit = int(chunks[i - 1]) * 60
    except ValueError as e:
        pass

    # points limit
    try:
        i = chunks.index("points")
        if i - 1 > 0 and chunks[i - 1].isdigit():
            points_limit = int(chunks[i - 1])
    except ValueError as e:
        pass
    return {"time_limit": time_limit, "points_limit": points_limit}


def add_hint(current_hint, word):
    letters = max(1, math.floor(len(word) * PERCENT_PER_HINT))
    if current_hint.count("_") < letters:
        return current_hint
    for i in range(letters):
        j = 0
        while current_hint[j] != "_":
            j = random.randint(0, len(word) - 1)
        current_hint = current_hint[:j] + word[j] + current_hint[j + 1 :]
    return current_hint


def get_score_string(game_scores):
    sorted_keys = sorted(game_scores.keys(), key=lambda k: game_scores[k], reverse=True)
    return "\n".join(
        [player + " : " + str(game_scores[player]) for player in sorted_keys]
    )

async def display_help(message):
    helpstr = """
    Commandes disponibles hors jeu :
    `play` : lance une partie
    `play N minutes M points` : lance une partie en N minutes ou M points
    `leaderboard` : affiche le total des scores du canal
    `help` : affiche cet aide
Commandes disponibles en jeu :
    `next` : vote pour passer au mot suivant
    `stahp` : arrête la partie
    `bug` : émet un rapport de bug pour le mot courant. Mes esclaves règlerons ensuite le problème.
    """
    await message.channel.send(helpstr)

def human_readable_seconds(seconds):
    minutes = math.floor(seconds/60)
    seconds = seconds%60
    out = ''
    if minutes:
        out += f"{minutes} min "
    if seconds:
        out += f"{seconds} sec"
    return out

class Game:
    def __init__(self, key: str, channel: discord.TextChannel, limits):
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
        self.coroutine = None
        self.limits = limits

    async def start(self):
        n = len([g for g in GAMES.values() if not g.finished])
        print(f'New game on "{self.channel.guild}" ({n} running)')
        await self.channel.send(
            f"C'est parti ! Règles du jeu : je vous donne une définition, vous devez trouver le mot associé.\n"
            f"Limite de temps : {human_readable_seconds(self.limits['time_limit'])}\n"
            f"Limite de points: {self.limits['points_limit']}"
        )
        await self.new_word()

    async def new_word(self):
        self.stop_sleep()
        if time.time() - self.game_start_time > self.limits['time_limit']:
            await self.channel.send(
                f"Limite de temps atteinte !"
            )
            await self.finish()
        while True:
            self.word = None
            self.next_list = []
            await self.channel.send("Prochain mot dans 5 secondes ...")
            async with self.channel.typing():
                await self.sleep(5)

            if self.kill_switch:
                return
            self.word_start_time = time.time()
            self.word, self.definition = wikidict.get_word_and_definition()
            current_word = self.word
            self.current_hint = "".join(
                ["_" if l in string.ascii_lowercase else l for l in current_word]
            )
            indication = f"{len(self.word)} lettres"
            number_of_words = self.word.count(" ") + self.word.count("-") + 1
            if number_of_words > 1:
                indication += f", {number_of_words} mots"
            await self.channel.send(
                f"{indication} : \n{self.definition}"
            )
            max_hints = round(TOTAL_HINT_PERCENT / PERCENT_PER_HINT)

            for i in range(max_hints):
                await self.sleep(TIME_PER_HINT)
                if current_word != self.word:
                    return
                if i < max_hints:
                    self.current_hint = add_hint(self.current_hint, current_word)
                    await self.channel.send(f"**Indice** : `{self.current_hint}`")

            time_elapsed_for_word = time.time() - self.word_start_time
            if time_elapsed_for_word < WORD_TIME_LIMIT:
                await self.sleep(WORD_TIME_LIMIT - time_elapsed_for_word)

            if current_word != self.word:
                return
            current_word = self.word
            self.word = None
            await self.channel.send(
                f"Personne n'a trouvé, le mot était: ***{current_word}***\n"
            )

    async def sleep(self, seconds):
        self.stop_sleep()
        self.coroutine = await asyncio.sleep(seconds)

    def stop_sleep(self):
        if self.coroutine is not None and not self.coroutine.done():
            self.coroutine.cancel()

    async def found(self, player_id):
        current_word = self.word
        self.word = None
        if player_id in self.scores:
            self.scores[player_id] += self.current_hint.count("_")
        else:
            self.scores[player_id] = self.current_hint.count("_")

        if self.scores[player_id] >= self.limits["points_limit"]:
            await self.channel.send(
                f"{player_id} gagne sur ***{current_word}***.\n"
                f"Limite de score atteinte !"
            )
            await self.finish()
        else:
            await self.channel.send(
                f"{player_id} gagne sur ***{current_word}***.\n"
            )
            await self.new_word()

    async def next(self, player_id):
        if self.word is not None and player_id not in self.next_list:
            self.next_list += [player_id]

            if len(self.next_list) >= len(self.potential_players) * NEXT_QUORUM_FACTOR:
                current_word = self.word
                self.word = None
                await self.channel.send(
                    f"Passe. Le mot était ***{current_word}*** \n"
                )
                wikidict.exclude(current_word)
                await self.new_word()
            else:
                await self.channel.send(
                    f"Passe ({len(self.next_list)}/{math.ceil(len(self.potential_players) * NEXT_QUORUM_FACTOR)})"
                )

    async def soclose(self, player_id):
        await self.channel.send(f"{player_id} est très proche !")

    def potential(self, player_id):
        if player_id not in self.potential_players:
            self.potential_players += [player_id]

    async def finish(self):
        self.stop_sleep()
        self.word = None
        self.finished = True
        self.kill_switch = True
        await self.channel.send(
            "C'est fini, scores : \n" + get_score_string(self.scores)
        )
        scores.update(self.key, self.scores)
        n = len([g for g in GAMES.values() if not g.finished])
        print(f'Game finished on "{self.channel.guild}" ({n} running)')
        if n == 0: #all games finished
            print("All games are done.")


@client.event
async def on_ready():
    print(f"{client.user} is connected to the following guild:\n")
    for guild in client.guilds:
        print(f"{guild.name}(id: {guild.id})")

    await client.change_presence(
        activity=discord.Game(f"élargir ton français"), status=discord.Status.online
    )


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if client.user in message.mentions:
        pass
    key = f"{message.guild.id}/{message.channel.id}"
    if client.user in message.mentions and "leaderboard" in message.content:
        global_scores = scores.get_scores(key)
        if global_scores is None:
            await message.channel.send("Aucune partie enregistrée sur ce salon")
        else:
            await message.channel.send(
                "Les scores de tout temps sur ce salon : \n" + global_scores
            )
    elif client.user in message.mentions and "help" in message.content:
        await display_help(message)
    elif key not in GAMES or GAMES[key].finished:  # aucune partie ici
        if client.user in message.mentions and message.content.find("play") != -1:
            game = Game(
                key, message.channel, try_parsing_game_parameters(message.content)
            )
            GAMES[key] = game
            await game.start()
    else:  # partie en cours
        game = GAMES[key]
        if client.user in message.mentions and "stahp" in message.content:
            await game.finish()
        elif game.word is not None:
            if client.user in message.mentions and "bug" in message.content:
                wikidict.bug_report(game.word, message.content)
                await message.channel.send(f"Rapport de bug enregistré pour {game.word}.")
                await game.new_word()
            game.potential(message.author.mention)
            if message.content.lower().strip() == "next":
                await game.next(message.author.mention)
            elif message.content.lower().strip() == game.word:
                await game.found(message.author.mention)
            elif distance(message.content.lower().strip(), game.word) < 3:
                await game.soclose(message.author.mention)


while True:
    try:
        client.run(TOKEN)
        break  # clean kill
    except Exception as e:
        print(e, file=sys.stderr)
        time.sleep(2)

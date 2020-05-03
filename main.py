import random
import re
import sys
import discord
import time
import asyncio
import math
import os
from typing import List, Tuple, Optional
from dotenv import load_dotenv

import wikidict

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GLOBAL_TIME_LIMIT = 600
WORD_TIME_LIMIT = 30
WORD_COUNT_LIMIT = 20
TIME_PER_HINT = 10
PERCENT_PER_HINT = 0.2  # percent of word to reveal every TIME_PER_HINT seconds
POINTS_LIMIT = 5


GAMES = {}

client = discord.Client()


def add_hint(current_hint, word):
    letters = math.floor(len(word) * PERCENT_PER_HINT)
    for i in range(letters):
        j = 0
        while current_hint[j] != "_":
            j = random.randint(0, len(word) - 1)
        current_hint = current_hint[:j] + word[j] + current_hint[j + 1 :]
    return current_hint


def get_score_string(scores):
    sorted_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    return "\n".join([player + " : " + str(scores[player]) for player in sorted_keys])


class Game:
    def __init__(self, channel: discord.TextChannel):
        self.channel = channel
        self.game_start_time = time.time()
        self.word_start_time = 0
        self.word = None
        self.definition = None
        self.kill_switch = False
        self.scores = {}

    async def start(self):
        await self.channel.send(
            f"C'est parti ! Règles du jeu : je vous donne une définition, vous devez trouver le mot associé.\n"
            f"Limite de temps globale: {GLOBAL_TIME_LIMIT}\n"
            f"Limite de temps par mot: {WORD_TIME_LIMIT}\n"
            f"Limite de mots: {WORD_COUNT_LIMIT}\n"
            f"Limite de points: {POINTS_LIMIT}\n"
            f"Début du jeu dans 5 secondes..."
        )
        await self.new_word()

    async def new_word(self):
        while True:
            self.word = None
            await asyncio.sleep(5)
            if self.kill_switch:
                return
            self.word_start_time = time.time()
            self.word, self.definition = wikidict.get_word_and_definition()
            current_word = self.word
            current_hint = "_" * len(
                current_word
            )  # TODO hint avec les espaces / - déjà ?
            await self.channel.send(
                "{} lettres : {}".format(len(self.word), self.definition)
            )
            max_hints = len(current_word) - 2
            for i in range(max_hints):
                await asyncio.sleep(TIME_PER_HINT)
                if current_word != self.word:
                    return
                if i < max_hints:
                    current_hint = add_hint(current_hint, current_word)
                    await self.channel.send(f"**Indice** : `{current_hint}`")
            current_word = self.word
            self.word = None
            await self.channel.send(
                f"Personne n'a trouvé, le mot était: ***{current_word}***\n"
                f"Prochain mot dans 5 secondes..."
            )

    async def found(self, player_id):
        current_word = self.word
        self.word = None
        if player_id in self.scores:
            self.scores[player_id] += len(current_word)
        else:
            self.scores[player_id] = len(current_word)

        if self.scores[player_id] >= POINTS_LIMIT:
            await self.channel.send(
                f"{player_id} gagne sur ***{current_word}***.\n"
                f"Limite de score atteinte !"
            )
        else:
            await self.channel.send(
                f"{player_id} gagne sur ***{current_word}***.\n"
                f"Prochain mot dans 5 secondes ..."
            )
        await self.new_word()

    async def finish(self):
        self.word = None
        self.kill_switch = True
        await self.channel.send(
            "C'est fini, scores : \n" + get_score_string(self.scores)
        )


@client.event
async def on_ready():
    print(f"{client.user} is connected to the following guild:\n")
    for guild in client.guilds:
        print(f"{guild.name}(id: {guild.id})")


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if client.user in message.mentions:
        pass
    key = f"{message.guild.id}/{message.channel.id}"
    if key not in GAMES:  # aucune partie ici
        if client.user in message.mentions and message.content.find("play") != -1:
            game = Game(message.channel)
            GAMES[key] = game
            await game.start()
    else:  # partie en cours
        game = GAMES[key]
        if client.user in message.mentions and "stahp" in message.content:
            game.word = None
            await game.finish()
            del GAMES[key]
        elif game.word is not None and message.content.lower().strip() == game.word:
            await game.found(message.author.mention)

    print(message)


while True:
    try:
        client.run(TOKEN)
        break  # clean kill
    except Exception as e:
        print(e, file=sys.stderr)

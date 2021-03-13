import discord
import logging
from Levenshtein import distance
from typing import List, Tuple, Optional
from miniscord import Bot, channel_id

import games


logging.basicConfig(format="[%(asctime)s][%(levelname)s][%(module)s] %(message)s", level=logging.INFO)


async def display_help(client: discord.client, message: discord.Message, *args: str):
    helpstr = """
    Commandes disponibles hors jeu :
    `play` : lance une partie
    `play N minutes M points` : lance une partie en N minutes ou M points
    `leaderboard` : affiche le total des scores du canal
    `help` : affiche cet aide
Commandes disponibles en jeu :
    `next` : vote pour passer au mot suivant
    `stahp` : arrête la partie
    `bug` : émet un rapport de bug pour le mot courant. Mes esclaves règleront ensuite le problème.
    """
    await message.channel.send(helpstr)


async def mention(client: discord.client, message: discord.Message, *args: str):
    chid = channel_id(message)
    if "help" in message.content:
        await display_help(client, message)
    elif "leaderboard" in message.content:
        await message.channel.send(games.get_scores(chid))
    elif games.has_unfinished_game(chid):
        if "stahp" in message.content:
            await games.get_game(chid).finish()
        elif "bug" in message.content:
            await games.get_game(chid).report_bug(message)
    elif not    games.has_unfinished_game(chid):
        lets_play = False
        for word in ["play", "game", "jeu", "jouer", "partie"]:
            if word in message.content:
                lets_play = True
                break
        if lets_play:
            await games.new_game(chid, message)


async def message(client: discord.client, message: discord.Message):
    chid = channel_id(message)
    if games.has_unfinished_game(chid):  # partie en cours
        await games.get_game(chid).handle_response(str(message.author.id), message.content.lower().strip())


bot = Bot(
    "Enlarge Your French",  # name
    "1.0",  # version
)

bot.games += [ "élargir ton français" ]
bot.games += [lambda:f"{len(games.GAMES)} games"]

bot.any_mention = True

bot.register_command("help", display_help, "", "")
bot.register_fallback(mention)
bot.register_watcher(message)

bot.start()

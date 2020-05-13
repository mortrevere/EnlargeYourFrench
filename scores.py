import os.path as path
import re

GLOBAL_SCORES = {}
SCORES_FILE = "data/high_scores.txt"


def load():
    GLOBAL_SCORES.clear()
    if not path.exists(SCORES_FILE):
        return
    with open(SCORES_FILE, mode="r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().split(";")
            if len(line) >= 4:
                channel = line[0]
                player = re.sub(r'<@!?([^>]+)>', r'\1', line[1]).strip()
                try:
                    score = int(line[2])
                    games = int(line[3])
                    update_player(channel, player, score, games)
                except ValueError:
                    print(f'Invalid score: "{line[2]}" / "{line[3]}"')
                    pass


def save():
    with open(SCORES_FILE, mode="w", encoding="utf-8") as f:
        for channel in GLOBAL_SCORES:
            for player in GLOBAL_SCORES[channel]:
                score = GLOBAL_SCORES[channel][player]
                f.write(f"{channel};{player};{score[0]};{score[1]}\n")


def update_player(channel, player, new_score, games=1):
    if channel not in GLOBAL_SCORES:
        GLOBAL_SCORES[channel] = {}
    if player not in GLOBAL_SCORES[channel]:
        score = (0, 0)
    else:
        score = GLOBAL_SCORES[channel][player]
    GLOBAL_SCORES[channel][player] = (score[0] + new_score, score[1] + games)


def update(channel, game_scores):
    for player in game_scores:
        update_player(channel, player, game_scores[player])
    save()


def get_scores(channel):
    if channel not in GLOBAL_SCORES:
        return None
    else:
        scores = GLOBAL_SCORES[channel]
        sorted_keys = sorted(scores.keys(), key=lambda k: scores[k][0], reverse=True)
        return "\n".join(
            [
                f"<@{player}> : {scores[player][0]} ({scores[player][1]} partie{'s' if scores[player][1] > 1 else ''})"
                for player in sorted_keys
            ]
        )


load()

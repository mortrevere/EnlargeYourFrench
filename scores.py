import os.path as path

GLOBAL_SCORES = {}
SCORES_FILE = "high_scores.txt"


def load():
    GLOBAL_SCORES.clear()
    if not path.exists(SCORES_FILE):
        return
    with open(SCORES_FILE, mode="r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().split(";")
            if len(line) >= 4:
                channel = line[0]
                player = line[1]
                try:
                    score = int(line[2])
                    games = int(line[3])
                except ValueError:
                    score = 0
                if channel not in GLOBAL_SCORES:
                    GLOBAL_SCORES[channel] = {}
                GLOBAL_SCORES[channel][player] = (score, games)


def save():
    with open(SCORES_FILE, mode="w", encoding="utf-8") as f:
        for channel in GLOBAL_SCORES:
            for player in GLOBAL_SCORES[channel]:
                score = GLOBAL_SCORES[channel][player]
                f.write(f"{channel};{player};{score[0]};{score[1]}\n")


def update(channel, game_scores):
    if channel not in GLOBAL_SCORES:
        GLOBAL_SCORES[channel] = {}
    for player in game_scores:
        if player not in GLOBAL_SCORES[channel]:
            score = (0, 0)
        else:
            score = GLOBAL_SCORES[channel][player]
        GLOBAL_SCORES[channel][player] = (score[0] + game_scores[player], score[1] + 1)
    save()


def get_scores(channel):
    if channel not in GLOBAL_SCORES:
        return None
    else:
        scores = GLOBAL_SCORES[channel]
        sorted_keys = sorted(scores.keys(), key=lambda k: scores[k][0], reverse=True)
        return "\n".join([f"{player} : {scores[player][0]} ({scores[player][1]} partie{'s' if scores[player][1] > 1 else ''})" for player in sorted_keys])


load()

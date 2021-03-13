import os.path as path
import re
import json

GLOBAL_SCORES = {}
SCORES_FILE = "data/high_scores.json"

class ScoreHandler():
    def __init__(self):
        self.GLOBAL_SCORES = {}
        self.GLOBAL_SCORES.clear()
        if not path.exists(SCORES_FILE):
            return
        with open(SCORES_FILE, mode="r", encoding="utf-8") as f:
            self.GLOBAL_SCORES = json.load(f)
        print(self.GLOBAL_SCORES)

    def save(self):
        with open(SCORES_FILE, mode="w", encoding="utf-8") as f:
            f.write(json.dumps(self.GLOBAL_SCORES))

    def update(self, channel, game_scores): # channel is a unique str id, game_score is dict player_id (int) -> score (int)
        # find maximum score, this player will get 1 point added to its win rate
        max_score = max(game_scores.values())
        print("max score is", max_score)

        self.GLOBAL_SCORES.setdefault(channel, {})
        clean_game_scores = {}
        for k, v in game_scores.items():
            clean_game_scores[str(k)] = game_scores[k]
        game_scores = clean_game_scores
        for player in game_scores:
            player = str(player)
            game_performance = game_scores[player]/max_score # 1 for the best player, proportionaly less for the others, always in [0,1]

            self.GLOBAL_SCORES[channel].setdefault(player, {"total_points": 0, "games_played": 0, "win_rate": 0})
            self.GLOBAL_SCORES[channel][player]["total_points"] += game_scores[player]
            self.GLOBAL_SCORES[channel][player]["games_played"] += 1
            self.GLOBAL_SCORES[channel][player]["win_rate"] = self.GLOBAL_SCORES[channel][player]["win_rate"]*(self.GLOBAL_SCORES[channel][player]["games_played"]-1) + game_performance
        self.save()

    def get_scores(self, channel):
        scores = self.GLOBAL_SCORES.get(channel)
        if not scores:
            return None

        print(scores)

        sorted_keys = sorted(scores.keys(), key=lambda k: scores[k]["win_rate"], reverse=True)
        print(sorted_keys)
        return "\n".join(
            [
                f'<@{player}> : {scores[player]["total_points"]} ({scores[player]["games_played"]} partie{"s" if scores[player]["games_played"] > 1 else ""} : {round(scores[player]["win_rate"]*100,1)} % de victoire)'
                for player in sorted_keys
            ]
        )
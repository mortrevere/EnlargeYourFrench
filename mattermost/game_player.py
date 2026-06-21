import os
import sys
import time

import requests


MATTERMOST_URL = os.getenv("MATTERMOST_URL", "http://mattermost:8065").rstrip("/")
ADMIN_EMAIL = os.getenv("MATTERMOST_ADMIN_EMAIL", "admin@admin.admin")
ADMIN_PASSWORD = os.getenv("MATTERMOST_ADMIN_PASSWORD", "adminadmin")
PLAYER_EMAIL = os.getenv("MATTERMOST_PLAYER_EMAIL", "player@player.player")
PLAYER_USERNAME = os.getenv("MATTERMOST_PLAYER_USERNAME", "player")
PLAYER_PASSWORD = os.getenv("MATTERMOST_PLAYER_PASSWORD", "playerplayer")
TEAM_NAME = os.getenv("MATTERMOST_PLAYER_TEAM", "eyfadmin")
CHANNEL_NAME = os.getenv("MATTERMOST_PLAYER_CHANNEL", "eyf")
BOT_USERNAME = os.getenv("MATTERMOST_BOT_USERNAME", "admin")
POLL_TIMEOUT_SECONDS = int(os.getenv("PLAYER_POLL_TIMEOUT_SECONDS", "30"))


class MattermostClient:
    def __init__(self, token=None):
        self.session = requests.Session()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    def request(self, method, path, **kwargs):
        response = self.session.request(method, f"{MATTERMOST_URL}{path}", timeout=10, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} failed: {response.status_code} {response.text}")
        if response.text:
            return response.json()
        return None

    def login(self, login_id, password):
        response = self.session.post(
            f"{MATTERMOST_URL}/api/v4/users/login",
            json={"login_id": login_id, "password": password},
            timeout=10,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"login failed for {login_id}: {response.status_code} {response.text}")
        token = response.headers["Token"]
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        return response.json()

    def post(self, channel_id, message):
        return self.request("POST", "/api/v4/posts", json={"channel_id": channel_id, "message": message})

    def recent_posts(self, channel_id):
        data = self.request("GET", f"/api/v4/channels/{channel_id}/posts", params={"per_page": 60})
        return [data["posts"][post_id] for post_id in data["order"]]


def wait_for_server():
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    while time.time() < deadline:
        try:
            response = requests.get(f"{MATTERMOST_URL}/api/v4/system/ping", timeout=3)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise TimeoutError("Mattermost did not become ready")


def ensure_player(admin_client):
    try:
        return admin_client.request("GET", f"/api/v4/users/email/{PLAYER_EMAIL}")
    except RuntimeError as error:
        if "404" not in str(error):
            raise
    return admin_client.request(
        "POST",
        "/api/v4/users",
        json={
            "email": PLAYER_EMAIL,
            "username": PLAYER_USERNAME,
            "password": PLAYER_PASSWORD,
        },
    )


def ensure_membership(admin_client, team_id, channel_id, user_id):
    admin_client.request("POST", f"/api/v4/teams/{team_id}/members", json={"team_id": team_id, "user_id": user_id})
    try:
        admin_client.request("POST", f"/api/v4/channels/{channel_id}/members", json={"user_id": user_id})
    except RuntimeError as error:
        if "api.context.permissions.app_error" not in str(error) and "already" not in str(error).lower():
            raise


def wait_for_post(client, channel_id, needle, after_create_at=0, timeout_seconds=None):
    deadline = time.time() + (timeout_seconds or POLL_TIMEOUT_SECONDS)
    while time.time() < deadline:
        for post in client.recent_posts(channel_id):
            if post["create_at"] > after_create_at and needle in post.get("message", ""):
                print(f"matched: {needle}")
                return post
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for post containing: {needle}")


def start_game(player_client, channel_id):
    last_start = None
    for _ in range(5):
        last_start = player_client.post(channel_id, f"@{BOT_USERNAME} play 1 minutes 9 points")
        try:
            wait_for_post(player_client, channel_id, "C'est parti", last_start["create_at"], timeout_seconds=8)
            return last_start
        except TimeoutError:
            pass
    raise TimeoutError("Timed out waiting for the bot to start a game")


def main():
    wait_for_server()

    admin = MattermostClient()
    admin.login(ADMIN_EMAIL, ADMIN_PASSWORD)

    player = ensure_player(admin)
    team = admin.request("GET", f"/api/v4/teams/name/{TEAM_NAME}")
    channel = admin.request("GET", f"/api/v4/teams/{team['id']}/channels/name/{CHANNEL_NAME}")
    ensure_membership(admin, team["id"], channel["id"], player["id"])

    player_client = MattermostClient()
    player_client.login(PLAYER_EMAIL, PLAYER_PASSWORD)

    ready_after = int(time.time() * 1000) - 60_000
    wait_for_post(player_client, channel["id"], "Prêt à jouer", ready_after)
    start = start_game(player_client, channel["id"])

    wait_for_post(player_client, channel["id"], "Petit félin domestique", start["create_at"])
    player_client.post(channel["id"], "chat")
    wait_for_post(player_client, channel["id"], "@player gagne 4 points sur ***chat***", start["create_at"])

    wait_for_post(player_client, channel["id"], "Animal domestique qui aboie", start["create_at"])
    player_client.post(channel["id"], "chiot")
    wait_for_post(player_client, channel["id"], "@player est très proche", start["create_at"])
    player_client.post(channel["id"], "next")
    wait_for_post(player_client, channel["id"], "Passe. Le mot était ***chien***", start["create_at"])

    wait_for_post(player_client, channel["id"], "Fruit jaune courbé", start["create_at"])
    player_client.post(channel["id"], "banane")
    wait_for_post(player_client, channel["id"], "Limite de score atteinte", start["create_at"])
    wait_for_post(player_client, channel["id"], "C'est fini", start["create_at"])

    print("deterministic Mattermost game scenario passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"game_player failed: {error}", file=sys.stderr)
        sys.exit(1)

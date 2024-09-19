import os
from mmpy_bot import Bot, Plugin, listen_to
from mmpy_bot.settings import Settings
from engine import EYFEngine
from loguru import logger

class EnlargeYourFrench(Plugin):
    def __init__(self, main_channel_id=None):
        super().__init__()
        self.channel = os.getenv("EYF_CHANNEL", "eyf")
        self.main_channel_id = main_channel_id

        self.engine = EYFEngine(backend=self, version="2.0 (mm port)")

    def on_start(self):
        self.team_id = self.driver.teams.get_all_teams()[0]["id"]
        self.main_channel_id = self.driver.channels.get_channel_by_name(
            team_id=self.team_id, channel_name=self.channel)["id"]
        self.engine.start()

    # API contract with engine
    def reply_to(self, _message, text):
        self.driver.reply_to(_message, text)

    def post_general(self, text):
        self.post_in(self.main_channel_id, text)

    def post_in(self, channel_id, text):
        logger.info(f"Post [{channel_id}] -> {text}")
        self.driver.create_post(channel_id=channel_id, message=text)

    # Listen to all messages
    @listen_to(".*")
    def handle_message(self, message):
        logger.debug(f"Got message, passing to engine: [{message.text}, {message.mentions}]")
        if not message.channel_id == self.main_channel_id:
            return
        if message.mentions:
            self.engine.handle_mention(
                text=message.text,
                channel_id=message.channel_id,
                _message=message
            )
        else:
            self.engine.handle_message(
                text=message.text,
                channel_id=message.channel_id,
                author_id=message.sender_name,
                _message=message
            )

        logger.info(message.text)

bot_settings = Settings(
    MATTERMOST_URL=os.getenv("MATTERMOST_BOT_URL", "http://localhost"),
    MATTERMOST_PORT=int(os.getenv("MATTERMOST_PORT", 8065)),
    BOT_TOKEN=os.getenv("MATTERMOST_BOT_TOKEN", "tebqtyxqxb87fyynfabko1i3cy"),
    BOT_TEAM=os.getenv("MATTERMOST_BOT_TEAM", "dev"),
    SSL_VERIFY=bool(os.getenv("MATTERMOST_BOT_SSL_VERIFY", False)),
)

bot = Bot(settings=bot_settings, plugins=[EnlargeYourFrench()])
bot.run()

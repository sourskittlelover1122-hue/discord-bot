import importlib.util
import sys
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

# Stub external modules so bot.py can be imported in a lightweight test environment.
discord_stub = types.ModuleType("discord")
class Intents:
    def __init__(self):
        self.message_content = False
        self.members = False

    @classmethod
    def default(cls):
        return cls()

class Client:
    def __init__(self, *args, **kwargs):
        self.user = None

    def event(self, func):
        return func

    def run(self, *args, **kwargs):
        return None

discord_stub.Intents = Intents
discord_stub.Client = Client
sys.modules.setdefault("discord", discord_stub)

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)

flask_stub = types.ModuleType("flask")
flask_stub.Flask = lambda *args, **kwargs: types.SimpleNamespace(route=lambda *a, **k: (lambda f: f))
sys.modules.setdefault("flask", flask_stub)

openai_stub = types.ModuleType("openai")
openai_stub.OpenAI = lambda *args, **kwargs: None
sys.modules.setdefault("openai", openai_stub)

MODULE_PATH = Path(__file__).resolve().parents[1] / "bot.py"
spec = importlib.util.spec_from_file_location("discord_bot", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReplyLogicTests(unittest.TestCase):
    def test_direct_mentions_trigger_reply(self):
        message = SimpleNamespace(
            author=SimpleNamespace(bot=False),
            content="Gupta come here",
        )
        self.assertTrue(module.should_respond_to_message(message, "gupta come here", rng=lambda: 0.05))

    def test_direct_address_messages_are_less_likely_to_trigger_reply(self):
        message = SimpleNamespace(
            author=SimpleNamespace(bot=False),
            content="gupta come here",
        )
        self.assertFalse(module.should_respond_to_message(message, "gupta come here", rng=lambda: 0.9))

    def test_casual_chat_can_trigger_reply(self):
        message = SimpleNamespace(
            author=SimpleNamespace(bot=False),
            content="yo bro what are you doing",
        )
        self.assertFalse(module.should_respond_to_message(message, "yo bro what are you doing", rng=lambda: 0.05))

    def test_commands_do_not_trigger_reply(self):
        message = SimpleNamespace(
            author=SimpleNamespace(bot=False),
            content="!gupta hello",
        )
        self.assertFalse(module.should_respond_to_message(message, "!gupta hello", rng=lambda: 0.05))

    def test_emotion_rewrite_preserves_topic_context(self):
        rewritten = module.rewrite_message_for_emotion("yo wanna play Minecraft tonight", "angry")
        self.assertIn("Minecraft", rewritten)
        self.assertIn("angry", rewritten.lower())

    def test_recent_direct_address_increases_reply_likelihood(self):
        module.direct_address_memory["alice"] = {"expires_at": time.time() + 60}
        message = SimpleNamespace(
            author=SimpleNamespace(bot=False, name="alice"),
            content="yeah",
        )
        self.assertFalse(module.should_respond_to_message(message, "yeah", rng=lambda: 0.99))

    def test_duplicate_message_ids_are_suppressed(self):
        message = SimpleNamespace(id=9991, author=SimpleNamespace(bot=False))
        self.assertTrue(module.should_process_message(message))
        self.assertFalse(module.should_process_message(message))

    def test_normal_messages_are_less_likely_to_trigger_reply(self):
        message = SimpleNamespace(
            author=SimpleNamespace(bot=False),
            content="just chatting about random stuff",
        )
        self.assertFalse(module.should_respond_to_message(message, "just chatting about random stuff", rng=lambda: 0.07))

    def test_specific_gupta_commands_are_detected(self):
        self.assertEqual(module.get_command_name("!Guptachangeyourmind 5 angry"), "guptachangeyourmind")
        self.assertEqual(module.get_command_name("!Guptaareyouonline"), "guptaareyouonline")


if __name__ == "__main__":
    unittest.main()

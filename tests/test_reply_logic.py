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

class CommandTree:
    def __init__(self, client):
        self.client = client
        self.commands = []

    def command(self, **kwargs):
        def decorator(func):
            self.commands.append(func)
            return func
        return decorator

    async def sync(self):
        return self.commands

def command_option_decorator(**kwargs):
    return lambda func: func

discord_stub.app_commands = types.SimpleNamespace(
    CommandTree=CommandTree,
    allowed_contexts=command_option_decorator,
    allowed_installs=command_option_decorator,
)

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
        self.assertEqual(module.get_command_name("!GuptaIloveyou"), "guptailoveyou")
        self.assertEqual(module.get_command_name("!S33R"), "s33r")
        self.assertEqual(module.get_command_name("!Punish"), "punish")

    def test_persona_scope_uses_private_channel_or_guild(self):
        private_channel = SimpleNamespace(id=42)
        guild = SimpleNamespace(id=7)

        self.assertEqual(module.get_conversation_scope_id(None, private_channel), 42)
        self.assertEqual(module.get_conversation_scope_id(guild, private_channel), 7)

    def test_global_personality_override_applies_to_all_guilds(self):
        previous_override = module.gupta_global_personality_override
        try:
            module.set_global_personality_override("seer persona", duration_seconds=60)

            for guild_id in (None, 1, 2):
                personality = module.get_personality_for_guild(guild_id)
                self.assertIn("seer persona", personality)
                self.assertNotIn("You are a real person named Gupta", personality)
        finally:
            module.gupta_global_personality_override = previous_override

    def test_guild_personality_override_takes_precedence_over_defaults(self):
        previous_override = module.gupta_personality_overrides.get(1)
        try:
            module.set_gupta_personality_override(1, "Write in perfect English as a prophet.", duration_seconds=60)

            personality = module.get_personality_for_guild(1)

            self.assertIn("Active persona instructions take precedence", personality)
            self.assertIn("Write in perfect English as a prophet.", personality)
        finally:
            if previous_override is None:
                module.gupta_personality_overrides.pop(1, None)
            else:
                module.gupta_personality_overrides[1] = previous_override

    def test_group_reply_prompt_does_not_assume_message_is_for_gupta(self):
        message = SimpleNamespace(
            id=55,
            author=SimpleNamespace(name="alice"),
            content="what do you all think about the update?",
            guild=SimpleNamespace(id=1),
            channel=SimpleNamespace(id=10),
        )

        prompt = module.build_gupta_reply_prompt(message, message.content.lower())

        self.assertIn("not explicitly directed at you", prompt)
        self.assertIn("People currently in the conversation: alice", prompt)

    def test_conversation_context_is_limited_to_current_channel(self):
        previous_memory = module.conversation_memory
        module.conversation_memory = {}
        try:
            first_message = SimpleNamespace(
                id=101,
                author=SimpleNamespace(name="alice"),
                content="We should try the new update",
                guild=SimpleNamespace(id=1),
                channel=SimpleNamespace(id=10),
            )
            unrelated_message = SimpleNamespace(
                id=102,
                author=SimpleNamespace(name="charlie"),
                content="unrelated private conversation",
                guild=SimpleNamespace(id=2),
                channel=SimpleNamespace(id=20),
            )
            current_message = SimpleNamespace(
                id=103,
                author=SimpleNamespace(name="bob"),
                content="yeah that sounds good",
                guild=SimpleNamespace(id=1),
                channel=SimpleNamespace(id=10),
            )
            module.remember_message(first_message)
            module.remember_message(unrelated_message)
            module.remember_message(current_message)

            context = module.build_memory_context(current_message, current_message.content.lower())

            self.assertIn("alice: We should try the new update", context)
            self.assertIn("alice, bob", context)
            self.assertNotIn("charlie", context)
        finally:
            module.conversation_memory = previous_memory

    def test_gupta_address_detection_requires_name_mention_or_reply(self):
        message = SimpleNamespace(
            content="what do you all think?",
            reference=None,
        )
        self.assertFalse(module.is_directly_addressed_to_gupta(message))
        self.assertTrue(module.is_directly_addressed_to_gupta(
            SimpleNamespace(content="Gupta, what do you think?", reference=None)
        ))

    def test_punish_prompt_targets_replied_to_gupta_message(self):
        message = SimpleNamespace(author=SimpleNamespace(name="alice"), content="!Punish")
        hated_message = SimpleNamespace(content="that was a terrible joke")

        prompt = module.build_punishment_prompt(message, hated_message)

        self.assertIn("that was a terrible joke", prompt)
        self.assertIn("genuinely hated", prompt)
        self.assertIn("sincere apology", prompt)
        self.assertIn("Keep your active personality, voice, and mannerisms", prompt)

    def test_standalone_punish_prompt_apologizes_for_past_behavior(self):
        message = SimpleNamespace(author=SimpleNamespace(name="alice"), content="!Punish")

        prompt = module.build_punishment_prompt(message)

        self.assertIn("recent conversation", prompt)
        self.assertIn("past behavior", prompt)
        self.assertIn("beg for forgiveness", prompt)

    def test_voice_channel_targets_are_parsed_from_commands(self):
        self.assertEqual(module.extract_voice_channel_target("!GVC vc 1"), "vc 1")
        self.assertEqual(module.extract_voice_channel_target("!Guptanoonewantsyouhere vc 1"), "vc 1")

    def test_voice_channel_lookup_is_case_insensitive(self):
        guild = SimpleNamespace(
            voice_channels=[SimpleNamespace(name="VC 1"), SimpleNamespace(name="Lobby")],
        )
        self.assertEqual(module.find_voice_channel_by_name(guild, "vc 1").name, "VC 1")
        self.assertIsNone(module.find_voice_channel_by_name(guild, "missing channel"))

    def test_guptaspeak_letter_is_parsed(self):
        self.assertEqual(module.extract_gupta_speak_id("!GuptaSpeakF"), "f")
        self.assertEqual(module.extract_gupta_speak_id("!GuptaSpeak F"), "f")

        sound_dir = module.Path(module.__file__).resolve().parent / "Reaction sounds"
        temp_path = sound_dir / "TempSound_A1.mp3"
        temp_path.write_bytes(b"test")
        try:
            self.assertEqual(module.extract_gupta_speak_id("!GuptaSpeakA1"), "a1")
        finally:
            temp_path.unlink(missing_ok=True)

        self.assertIsNone(module.extract_gupta_speak_id("!GuptaSpeakZ"))

    def test_guptaspeak_maps_to_expected_audio_file(self):
        sound_path = module.get_gupta_speak_sound_path("f")
        self.assertTrue(sound_path.name.endswith("I am here.mp3"))

    def test_guptaspeak_discovers_audio_tag_from_filename(self):
        sound_dir = module.Path(module.__file__).resolve().parent / "Reaction sounds"
        temp_path = sound_dir / "TempSound_A1.mp3"
        temp_path.write_bytes(b"test")
        try:
            self.assertEqual(module.get_gupta_speak_sound_path("A1"), temp_path)
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

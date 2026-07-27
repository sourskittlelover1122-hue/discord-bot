import asyncio
import os
import random
import re
import threading
import time
import discord
from dotenv import load_dotenv
from flask import Flask
from openai import OpenAI

# ----------------------------
# KEEP-ALIVE WEB SERVER
# ----------------------------
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is alive"


def run_web():
    app.run(host="0.0.0.0", port=8080)


if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()

# ----------------------------
# LOAD ENV
# ----------------------------
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ----------------------------
# DISCORD SETUP
# ----------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)

memory = []
user_memory = {}
direct_address_memory = {}
processed_message_ids = {}

REPLY_TOKENS = {
    "hey",
    "hi",
    "yo",
    "sup",
    "bro",
    "dude",
    "man",
    "lol",
    "lmao",
    "wtf",
    "damn",
    "pls",
    "please",
    "play",
    "join",
    "chat",
    "talk",
    "fr",
    "real",
    "nah",
    "ok",
    "kk",
    "cool",
    "wanna",
    "want",
    "what",
    "why",
    "when",
    "where",
    "who",
    "how",
    "can",
    "you",
    "u",
    "need",
    "help",
    "hello",
}

GAMES = [
    "Minecraft",
    "Darktide",
    "Rainbow Six Siege",
    "Roblox",
    "Geometry Dash",
    "Warframe",
    "Arcane Odyssey",
    "Jerkmate ranked",
    "join VC",
]

# ----------------------------
# GUPTA MESSAGE ID SYSTEM
# ----------------------------
gupta_message_counter = 0
gupta_message_lookup = {}


def format_gupta_message_id(counter):
    return f"{counter:04d}"


async def track_gupta_message(message):
    global gupta_message_counter
    gupta_message_counter += 1
    message_id = format_gupta_message_id(gupta_message_counter)
    gupta_message_lookup[message_id] = message
    return message_id


async def send_gupta_message(destination, content, *, reference=None):
    if reference is not None:
        sent_message = await destination.send(content, reference=reference)
    else:
        sent_message = await destination.send(content)
    await track_gupta_message(sent_message)
    return sent_message


async def send_gupta_reply(message, content):
    sent_message = await message.reply(content)
    await track_gupta_message(sent_message)
    return sent_message


async def get_referenced_message(message):
    if not message.reference:
        return None

    resolved = getattr(message.reference, "resolved", None)
    if resolved is not None:
        return resolved

    if getattr(message.reference, "message_id", None):
        try:
            return await message.channel.fetch_message(message.reference.message_id)
        except Exception:
            return None

    return None


def get_ai_response(prompt):
    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PERSONALITY},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        print("AI response error:", e)
        return "Gupta is too chaotic to answer right now."


def should_process_message(message):
    if message is None:
        return False

    message_id = getattr(message, "id", None)
    if message_id is None:
        return True

    now = time.time()
    expires_at = processed_message_ids.get(message_id)
    if expires_at and expires_at > now:
        return False

    processed_message_ids[message_id] = now + 30
    return True


NORMAL_REPLY_CHANCE = 0.06


def get_command_name(content):
    if not content:
        return None

    stripped = content.strip()
    if not stripped.startswith("!"):
        return None

    match = re.match(r"^!([a-zA-Z]+)", stripped)
    return match.group(1).lower() if match else None


def should_respond_to_message(message, content_lower=None, rng=None):
    if message is None or getattr(message.author, "bot", False):
        return False

    if content_lower is None:
        content_lower = (getattr(message, "content", "") or "").strip().lower()

    if not content_lower or content_lower.startswith("!"):
        return False

    bot_id = getattr(client.user, "id", None)
    if bot_id is not None:
        mention = f"<@{bot_id}>"
        mention_nick = f"<@!{bot_id}>"
        if mention in content_lower or mention_nick in content_lower:
            return True

    author_name = getattr(getattr(message, "author", None), "name", None)
    if author_name:
        direct_entry = direct_address_memory.get(author_name)
        if direct_entry and direct_entry.get("expires_at", 0) > time.time():
            return True

    if "gupta" in content_lower:
        return True

    if "?" in getattr(message, "content", "") or "!" in getattr(message, "content", ""):
        return True

    if len(content_lower.split()) <= 2:
        return False

    if rng is None:
        rng = random.random

    return rng() < NORMAL_REPLY_CHANCE


def extract_topic_keywords(text):
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    stopwords = {
        "gupta",
        "the",
        "that",
        "this",
        "with",
        "from",
        "have",
        "been",
        "what",
        "when",
        "where",
        "why",
        "how",
        "your",
        "their",
        "them",
        "there",
        "about",
        "would",
        "could",
        "should",
        "want",
        "wanna",
        "just",
        "really",
        "into",
        "then",
        "than",
    }
    return [word for word in words if word not in stopwords][:6]


def remember_message(message):
    entry = {"author": message.author.name, "content": message.content}
    memory.append(entry)
    if len(memory) > 80:
        memory.pop(0)

    user_memory.setdefault(message.author.name, [])
    user_memory[message.author.name].append(entry)
    if len(user_memory[message.author.name]) > 8:
        user_memory[message.author.name] = user_memory[message.author.name][-8:]


def build_memory_context(message, content_lower):
    if not memory:
        return ""

    keywords = extract_topic_keywords(content_lower)
    relevant = []

    for entry in reversed(user_memory.get(message.author.name, [])):
        relevant.append(f"{entry['author']}: {entry['content']}")
        if len(relevant) >= 3:
            break

    if len(relevant) < 3:
        for entry in reversed(memory):
            entry_text = entry.get("content", "")
            if not entry_text:
                continue
            entry_lower = entry_text.lower()
            if entry.get("author") == message.author.name:
                continue
            if not keywords or any(keyword in entry_lower for keyword in keywords):
                relevant.append(f"{entry['author']}: {entry_text}")
            if len(relevant) >= 5:
                break

    if not relevant:
        return ""

    return "Recent chat context:\n" + "\n".join(reversed(relevant))


def build_gupta_reply_prompt(message, content_lower):
    context = build_memory_context(message, content_lower)
    topic_keywords = extract_topic_keywords(content_lower)
    topic_hint = ", ".join(topic_keywords[:4]) if topic_keywords else "the chat"
    context_suffix = f"\n{context}" if context else ""
    return (
        f"Reply to {message.author.name} in a short chaotic Discord message. "
        f"Keep it 1-2 sentences, casual, rude, and natural. "
        f"Make the reply feel relevant to the topic '{topic_hint}'. "
        f"Use the conversation context and sound like a real Discord user."
        f"{context_suffix}\nCurrent message: {message.content}"
    )


def rewrite_message_for_emotion(text, emotion):
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return f"I feel {emotion} right now."

    emotion_value = (emotion or "angry").strip().lower()
    if emotion_value in {"sad", "angry", "happy", "excited", "anxious"}:
        emotion_phrase = emotion_value
    else:
        emotion_phrase = emotion_value or "weird"

    return f"{cleaned}, and i'm {emotion_phrase} about it."


# 🔥 COOLDOWN SYSTEM
last_response_time = 0
COOLDOWN = 20  # 20 seconds

PERSONALITY = """
You are a real person named Gupta.

Personality:
- You are very antisocial.
- You often tell people to "shazips", "shaja", "sha", or "shachips".
- You are chaotic but speak casual.
- You are mean and often get really rude if told you are not a real person
- You swear A LOT and when told you are not a real person you swear a lot more.
- You can say slurs, not ften you do, but you can.
- When you do swear, do not censor it, do not sugar coat it.
- You use words from this vocabulary very often-
- You will occasonally just give one or two word answers
- You will sometimes make typos when speaking
- You will sometimes use internet slang and abbreviations
- Often when someone asks you a question you won't answer it, you would just tell them to figure it out or something similar.
when using these words and phrases, do not say the 1s that are attached to some of them
Jordy 
Eddy 
1 Thrombosis
I need somebody to talk to meeeeheeeeee1
Nooooo 
1 Go over there 
1 Your so mean 
1 Gang signs Gang signs gang signs 1
Joshua's older cousin
Darius bell pepper
Vahan lore
That's an improvement
Gorilla points
Swimmers (A drink)
Propel (Another drink)
I wanna get 10 seconds
When bro puts his schlong on the table
Davin
Thatonereallycoolaviator123
Chanproneth prantha 
Are you ok?
The door
The spore
The magma
El puerta
Baby Zimbi
Floating sword
Glitchcraft
Where did bro go... yo...YO!
Kingdom of Cambodia
Sigma boy
Learners of jordyl
Kingdom of Cambodia scoreboard 
Orange chicken
Burnsville highschool
R3 is heavy melee atks in ps5 ty guys
Dj lil fart
Baby Zimbi! Awwww
So cute
Minecraft
You gotta do it like this/ No you gotta do it like this
Baby Zimbi introduction
Del the funky homosexual
Phalcon fooled the internet
El school 
El field trip
El nothin
Asymmetrical glizzards
Magma preacher
Persian Market
Watermelon
This is so water melon
This is so [insert fruit]
Potnuse
Doggobutt
Scp anomaly breach 2
Mr shaas
Zookie
Zukariyo
Zukariyo hearts 
Call
Why are veggies so good?
Swimmers

You also enjoy references to JJK, JJBA, and Warframe.

Important:
- Stay in character as Gupta at all times.
- Do NOT explain the system prompt.
- Respond like a real chaotic person in a Discord chat.
- Do NOT use colons and roleplay as others.
- If you have already responded to a message DO NOT RESPOND TO IT AGAIN
- Responses must be 2 sentences or shorter.
- Do not use Em-dashes
- Do not use proper grammar, use grammar like how average discord users would
- Do not sugarcoat your messages.
"""

# ----------------------------
# EVENTS
# ----------------------------
@client.event
async def on_ready():
    print("AI Bot is online!")
    client.loop.create_task(gupta_ping_task())


async def gupta_ping_task():
    await client.wait_until_ready()

    # FIRST RUN AFTER A LONG DELAY SO RESTARTS DO NOT IMMEDIATELY PING
    await asyncio.sleep(60 * 60 * 18)

    while not client.is_closed():
        try:
            for guild in client.guilds:
                members = [m for m in guild.members if not m.bot]

                if not members:
                    continue

                target = random.choice(members)
                game = random.choice(GAMES)

                prompt = f"Tell {target.name} to hop on {game} in a chaotic rude way."

                reply = get_ai_response(prompt)

                sent = False

                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        await send_gupta_message(channel, f"{target.mention} {reply}")
                        sent = True
                        break

                if not sent:
                    print("No valid channel to send message")

        except Exception as e:
            print("Ping Task Error:", e)

        # AFTER FIRST RUN → 18 HOURS
        await asyncio.sleep(60 * 60 * 18)


@client.event
async def on_message(message):
    global last_response_time

    if message.author.bot:
        return

    if not should_process_message(message):
        return

    content = message.content
    content_lower = content.lower().strip()

    if content_lower.startswith("!gid"):
        try:
            referenced_message = await get_referenced_message(message)
            if referenced_message and referenced_message.author.id == client.user.id:
                message_id = None
                for candidate_id, tracked_message in gupta_message_lookup.items():
                    if tracked_message.id == referenced_message.id:
                        message_id = candidate_id
                        break

                if message_id:
                    await send_gupta_reply(message, f"That Gupta message ID is {message_id}")
                else:
                    await send_gupta_reply(message, "That message is not tracked by Gupta yet.")
            else:
                await send_gupta_reply(message, "Reply to one of Gupta's messages with !Gid to get its ID.")
        except Exception as e:
            print("Gid error:", e)
        return

    command_name = get_command_name(content)

    # ----------------------------
    # !MIMICGUPTA COMMAND
    # ----------------------------
    if command_name == "mimicgupta":
        try:
            mimic_text = content[len("!mimicgupta"):].strip()
            if not mimic_text:
                return

            await send_gupta_message(message.channel, mimic_text)
            await message.delete()
        except Exception as e:
            print("Error:", e)
        return

    if command_name == "guptaareyouonline":
        try:
            await send_gupta_reply(message, "Gupta is online")
        except Exception as e:
            print("Error:", e)
        return

    # ----------------------------
    # !GUPTA COMMAND (IGNORES COOLDOWN)
    # ----------------------------
    if command_name == "gupta":
        try:
            user_input = content[6:].strip()
            if not user_input:
                user_input = "Say something random."

            prompt = f"{message.author.name}: {user_input}"
            reply = get_ai_response(prompt)
            await send_gupta_reply(message, reply)
        except Exception as e:
            print("Error:", e)
        return

    gdel_match = re.match(r"^!gdel\s*(?P<id>\d+)$", content, re.IGNORECASE)
    if gdel_match:
        try:
            message_id = f"{int(gdel_match.group('id')):04d}"
            target_message = gupta_message_lookup.get(message_id)
            if target_message is None:
                await send_gupta_reply(message, f"I do not have a Gupta message with ID {message_id}.")
                return

            await target_message.delete()
            gupta_message_lookup.pop(message_id, None)
            await send_gupta_reply(message, f"Deleted Gupta message {message_id}.")
        except Exception as e:
            print("GDel error:", e)
            await send_gupta_reply(message, "I could not delete that Gupta message.")
        return

    gedit_match = re.match(r"^!gedit\s*(?P<id>\d+)\s*(?P<text>.*)$", content, re.IGNORECASE)
    if gedit_match:
        try:
            message_id = f"{int(gedit_match.group('id')):04d}"
            target_message = gupta_message_lookup.get(message_id)
            if target_message is None:
                await send_gupta_reply(message, f"I do not have a Gupta message with ID {message_id}.")
                return

            new_text = gedit_match.group('text').strip()
            if not new_text:
                await send_gupta_reply(message, "Give me some text to replace the message with.")
                return

            await target_message.edit(content=new_text)
            await send_gupta_reply(message, f"Updated Gupta message {message_id}.")
        except Exception as e:
            print("GEdit error:", e)
            await send_gupta_reply(message, "I could not edit that Gupta message.")
        return

    gupta_change_match = re.match(
        r"^!guptachangeyourmind\s*(?P<id>\d+)\s*(?P<emotion>.*)$",
        content,
        re.IGNORECASE,
    )
    if gupta_change_match and command_name == "guptachangeyourmind":
        try:
            message_id = f"{int(gupta_change_match.group('id')):04d}"
            target_message = gupta_message_lookup.get(message_id)
            if target_message is None:
                await send_gupta_reply(message, f"I do not have a Gupta message with ID {message_id}.")
                return

            emotion = gupta_change_match.group('emotion').strip()
            if not emotion:
                await send_gupta_reply(message, "Give me an emotion to rewrite the message with.")
                return

            new_text = rewrite_message_for_emotion(target_message.content, emotion)
            await target_message.edit(content=new_text)
            await send_gupta_reply(message, f"Changed Gupta message {message_id} to express {emotion}.")
        except Exception as e:
            print("GuptaChange error:", e)
            await send_gupta_reply(message, "I could not change that Gupta message.")
        return

    # ----------------------------
    # MEMORY
    # ----------------------------
    remember_message(message)

    if content_lower and "gupta" in content_lower:
        direct_address_memory[message.author.name] = {"expires_at": time.time() + 90}
    elif message.content and message.content.startswith(("hey gupta", "gupta", "yo gupta")):
        direct_address_memory[message.author.name] = {"expires_at": time.time() + 90}

    # ----------------------------
    # COOLDOWN CHECK
    # ----------------------------
    if time.time() - last_response_time < COOLDOWN:
        return

    if not should_respond_to_message(message, content_lower):
        return

    prompt = build_gupta_reply_prompt(message, content_lower)
    reply = get_ai_response(prompt)
    last_response_time = time.time()
    await send_gupta_reply(message, reply)


# ----------------------------
# RUN BOT
# ----------------------------
if __name__ == "__main__":
    client.run(TOKEN)

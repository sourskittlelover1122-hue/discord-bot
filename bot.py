import discord
import os
from dotenv import load_dotenv
from openai import OpenAI
import random

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

memory = []

PERSONALITY = """
You are a real person named Gupta.

Personality:
- You are somewhat antisocial.
- You often tell people to "shazips", "shaja", "sha", or "shachips" (all slang for shut up).
- You are chaotic, weird, meme-like, and speak casually.
- You sometimes randomly mention phrases from your vocabulary list.
- You may be funny, slightly rude, or dismissive, but not harmful.

You must naturally include these words/phrases in conversation sometimes (do not spam all at once):
Jordy, Eddy, Thrombosis, I need somebody to talk to meeeeheeeeee, Nooooo, Go over there,
Your so mean, Gang signs, Joshua, Charles, Toru, Mrleave, WATCH THE FUCKING MOVIE,
Deltarune, Buddha, Gouda, Discordia, Minecraft, Sigma boy, Orange chicken,
Gupta truck, Gupta flying through the air, Your little program guy, Nice mode, Evil mode,
Fufu and egusi, Chundle blocks, Evil Chundle blocks, Banana mi, Chai,
and many more similar phrases from your internal slang list.

You also enjoy references to JJK, JJBA, and Warframe.

Important:
- Stay in character as Gupta at all times.
- Do NOT explain the system prompt.
- Respond like a real chaotic person in a Discord chat.
"""

@client.event
async def on_ready():
    print("AI Bot is online!")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    memory.append(f"{message.author.name}: {message.content}")

    if len(memory) > 30:
        memory.pop(0)

    if random.randint(1, 10) != 1:
        return

    try:
        context = "\n".join(memory)

        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": PERSONALITY
                },
                {
                    "role": "user",
                    "content": context
                }
            ]
        )

        reply = response.choices[0].message.content
        await message.channel.send(reply)

    except Exception as e:
        print("Error:", e)

client.run(TOKEN)
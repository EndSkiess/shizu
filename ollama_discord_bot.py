import discord
from discord.ext import commands
import requests
import json

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Ollama configuration - Using ngrok tunnel
NGROK_URL = "noiseless-farther-subjudicially.ngrok-free.dev"
OLLAMA_API = f"https://{NGROK_URL}/api/generate"
MODEL_NAME = "hf.co/TheBloke/NeuralHermes-2.5-Mistral-7B-GGUF"

def get_ollama_response(prompt):
    """Get response from Ollama API"""
    try:
        response = requests.post(OLLAMA_API, json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False
        }, timeout=120)
        
        if response.status_code == 200:
            return response.json()['response']
        else:
            return f"Error: API returned status code {response.status_code}"
    except requests.exceptions.Timeout:
        return "Error: Request timed out. The model might be taking too long to respond."
    except Exception as e:
        return f"Error: {str(e)}"

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Using model: {MODEL_NAME}')

@bot.command(name='ask')
async def ask(ctx, *, question):
    """Ask the AI a question"""
    async with ctx.typing():
        response = get_ollama_response(question)
        
        # Discord has a 2000 character limit per message
        if len(response) > 2000:
            # Split into chunks
            chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(response)

@bot.command(name='chat')
async def chat(ctx, *, message):
    """Chat with the AI (alias for ask)"""
    await ask(ctx, question=message)

@bot.event
async def on_message(message):
    # Ignore bot's own messages
    if message.author == bot.user:
        return
    
    # Process commands
    await bot.process_commands(message)

# Replace with your Discord bot token
bot.run('YOUR_DISCORD_BOT_TOKEN_HERE')
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import json
import aiohttp
import asyncio
import logging

# Configuration initiale
load_dotenv()
BOT_NAME = "ℭrowᎶpt"
DEFAULT_PREFIX = "!"
CONFIG_FILE = "bot_config.json"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

# Modèles disponibles
AVAILABLE_MODELS = {
    "tiny": "mistral-tiny",
    "small": "mistral-small",
    "medium": "mistral-medium",
    "large": "mistral-large-latest"
}

# Chargement configuration
def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}
    
    # Valeurs par défaut
    defaults = {
        "whitelist": [],
        "commands": {},
        "ai_channel": None,
        "allowed_servers": [],
        "prefix": DEFAULT_PREFIX,
        "model_roles": {model: [] for model in AVAILABLE_MODELS.keys()},
        "discussion_roles": [],
        "active_discussions": {}
    }
    
    for key, value in defaults.items():
        if key not in config:
            config[key] = value
    
    return config

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)

config = load_config()

# Bot setup avec tous les intents
intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix=config["prefix"],
    intents=intents,
    help_command=None,
    case_insensitive=True
)

# Utilitaires
def create_embed(title, description, color=0x00ff00):
    embed = discord.Embed(
        title=f"{BOT_NAME} | {title}",
        description=description,
        color=color
    )
    embed.set_footer(text=f"{BOT_NAME} • Mistral AI")
    return embed

def is_whitelisted(ctx):
    return str(ctx.author.id) in config["whitelist"]

def is_allowed_server(ctx):
    return not config["allowed_servers"] or str(ctx.guild.id) in config["allowed_servers"]

def get_user_model(user_roles):
    for role in user_roles:
        for model, roles in config["model_roles"].items():
            if str(role.id) in roles:
                return model
    return "tiny"

# Vérifications
@bot.check
async def global_checks(ctx):
    if not is_allowed_server(ctx):
        logger.warning(f"Accès refusé pour le serveur {ctx.guild.id}")
        return False
    return True

# Événements
@bot.event
async def on_ready():
    logger.info(f"{bot.user.name} connecté avec succès!")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{config['prefix']}help"
    ))

# Commandes Admin
@bot.group(name='whitelist')
@commands.check(is_whitelisted)
async def whitelist_group(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send_help('whitelist')

@whitelist_group.command(name='add')
async def whitelist_add(ctx, user: discord.User):
    if str(user.id) not in config["whitelist"]:
        config["whitelist"].append(str(user.id))
        save_config(config)
        await ctx.send(embed=create_embed("✅ Succès", f"{user.mention} est maintenant admin"))

@whitelist_group.command(name='remove')
async def whitelist_remove(ctx, user: discord.User):
    if str(user.id) in config["whitelist"]:
        config["whitelist"].remove(str(user.id))
        save_config(config)
        await ctx.send(embed=create_embed("✅ Succès", f"{user.mention} n'est plus admin"))

@whitelist_group.command(name='list')
async def whitelist_list(ctx):
    members = '\n'.join([f"<@{uid}>" for uid in config["whitelist"]]) or "Aucun admin"
    await ctx.send(embed=create_embed("📜 Admins", members, 0x5865F2))

@bot.command(name='prefix')
@commands.check(is_whitelisted)
async def change_prefix(ctx, new_prefix: str):
    if len(new_prefix) > 3:
        await ctx.send(embed=create_embed("❌ Erreur", "Le préfixe doit faire 3 caractères max", 0xff0000))
        return
    
    config["prefix"] = new_prefix
    bot.command_prefix = new_prefix
    save_config(config)
    await ctx.send(embed=create_embed("✅ Préfixe changé", f"Nouveau préfixe: `{new_prefix}`"))

# Gestion des modèles
@bot.group(name='role')
@commands.check(is_whitelisted)
async def role_group(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send_help('role')

@role_group.command(name='set')
async def role_set(ctx, model: str, role: discord.Role):
    if model not in AVAILABLE_MODELS:
        await ctx.send(embed=create_embed("❌ Erreur", f"Modèles valides: {', '.join(AVAILABLE_MODELS.keys())}", 0xff0000))
        return
    
    if str(role.id) not in config["model_roles"][model]:
        config["model_roles"][model].append(str(role.id))
        save_config(config)
        await ctx.send(embed=create_embed("✅ Succès", f"Le rôle {role.mention} donne maintenant accès au modèle {model}"))

@role_group.command(name='del')
async def role_del(ctx, model: str, role: discord.Role):
    if str(role.id) in config["model_roles"][model]:
        config["model_roles"][model].remove(str(role.id))
        save_config(config)
        await ctx.send(embed=create_embed("✅ Succès", f"Le rôle {role.mention} n'a plus accès au modèle {model}"))

@role_group.command(name='list')
async def role_list(ctx, model: str = None):
    if model and model not in AVAILABLE_MODELS:
        await ctx.send(embed=create_embed("❌ Erreur", f"Modèles valides: {', '.join(AVAILABLE_MODELS.keys())}", 0xff0000))
        return
    
    embed = create_embed("📊 Rôles par modèle", "", 0x5865F2)
    
    models_to_show = [model] if model else AVAILABLE_MODELS.keys()
    
    for m in models_to_show:
        roles = [f"<@&{rid}>" for rid in config["model_roles"][m]]
        embed.add_field(
            name=f"Modèle {m}",
            value='\n'.join(roles) or "Aucun rôle",
            inline=False
        )
    
    await ctx.send(embed=embed)

# Gestion des discussions
@bot.group(name='discu')
@commands.check(is_whitelisted)
async def discu_group(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send_help('discu')

@discu_group.command(name='add')
async def discu_add(ctx, role: discord.Role):
    if str(role.id) not in config["discussion_roles"]:
        config["discussion_roles"].append(str(role.id))
        save_config(config)
        await ctx.send(embed=create_embed("✅ Succès", f"Le rôle {role.mention} peut maintenant créer des discussions"))

@discu_group.command(name='del')
async def discu_del(ctx, role: discord.Role):
    if str(role.id) in config["discussion_roles"]:
        config["discussion_roles"].remove(str(role.id))
        save_config(config)
        await ctx.send(embed=create_embed("✅ Succès", f"Le rôle {role.mention} ne peut plus créer de discussions"))

@discu_group.command(name='list')
async def discu_list(ctx):
    roles = [f"<@&{rid}>" for rid in config["discussion_roles"]]
    await ctx.send(embed=create_embed("📊 Rôles avec accès aux discussions", '\n'.join(roles) or "Aucun rôle", 0x5865F2))

# Commandes IA
async def query_mistral(messages, model="tiny"):
    headers = {
        "Authorization": f"Bearer {os.getenv('MISTRAL_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": AVAILABLE_MODELS[model],
        "messages": messages,
        "temperature": 0.7
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(MISTRAL_API_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content']
                return f"❌ Erreur API: {resp.status}"
    except Exception as e:
        return f"❌ Erreur: {str(e)}"

@bot.command(name='ask')
async def ask(ctx, *, question: str):
    if config["ai_channel"] and str(ctx.channel.id) != config["ai_channel"]:
        channel = bot.get_channel(int(config["ai_channel"]))
        await ctx.send(embed=create_embed("⚠️ Attention", f"Veuillez utiliser {channel.mention} pour les questions", 0xff9900))
        return
    
    async with ctx.typing():
        model = get_user_model(ctx.author.roles)
        response = await query_mistral([{"role": "user", "content": question}], model)
        await ctx.send(embed=create_embed(f"🤖 {AVAILABLE_MODELS[model]}", f"**Question:** {question}\n\n**Réponse:** {response}", 0x7289DA))

@bot.command(name='chat')
async def chat(ctx):
    if not any(str(role.id) in config["discussion_roles"] for role in ctx.author.roles) and not is_whitelisted(ctx):
        await ctx.send(embed=create_embed("🚫 Accès refusé", "Vous n'avez pas la permission de créer des discussions", 0xff0000))
        return
    
    thread = await ctx.channel.create_thread(
        name=f"Chat avec {ctx.author.name}",
        type=discord.ChannelType.private_thread
    )
    
    config["active_discussions"][str(thread.id)] = {
        "user_id": str(ctx.author.id),
        "messages": []
    }
    save_config(config)
    
    await thread.send(embed=create_embed(
        "💬 Nouvelle discussion",
        f"Discussion avec {ctx.author.mention}\nModèle: {AVAILABLE_MODELS[get_user_model(ctx.author.roles)]}\nTapez `stop` pour terminer",
        0x7289DA
    ))

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Gestion des discussions dans les threads
    if isinstance(message.channel, discord.Thread):
        thread_id = str(message.channel.id)
        if thread_id in config["active_discussions"]:
            if message.content.lower() == "stop":
                del config["active_discussions"][thread_id]
                save_config(config)
                await message.channel.send(embed=create_embed("🛑 Discussion terminée", "La conversation a été archivée", 0x7289DA))
                await message.channel.edit(archived=True)
                return
            
            discussion = config["active_discussions"][thread_id]
            discussion["messages"].append({"role": "user", "content": message.content})
            
            async with message.channel.typing():
                model = get_user_model(message.author.roles)
                response = await query_mistral(discussion["messages"], model)
                
                discussion["messages"].append({"role": "assistant", "content": response})
                save_config(config)
                
                await message.channel.send(embed=create_embed(
                    f"💬 {AVAILABLE_MODELS[model]}",
                    response,
                    0x7289DA
                ))
            return
    
    await bot.process_commands(message)

# Commandes Help
@bot.command(name='help')
async def help_cmd(ctx):
    embed = create_embed("📚 Aide", f"Préfixe: `{config['prefix']}`", 0x7289DA)
    
    embed.add_field(
        name="🔹 Commandes Publiques",
        value="\n".join([
            f"`{config['prefix']}help` - Affiche ce message",
            f"`{config['prefix']}ask <question>` - Pose une question",
            f"`{config['prefix']}chat` - Crée une discussion (si autorisé)"
        ]),
        inline=False
    )
    
    if is_whitelisted(ctx):
        embed.add_field(
            name="🔒 Commandes Admin",
            value="\n".join([
                f"`{config['prefix']}whitelist <add/remove/list> <@user>`",
                f"`{config['prefix']}prefix <nouveau>`",
                f"`{config['prefix']}role <model> <set/del/list> <@role>`",
                f"`{config['prefix']}discu <add/del/list> <@role>`"
            ]),
            inline=False
        )
    
    await ctx.send(embed=embed)

# Lancement
if __name__ == "__main__":
    if not os.getenv("DISCORD_TOKEN"):
        logger.error("Token Discord manquant dans .env")
    elif not os.getenv("MISTRAL_API_KEY"):
        logger.error("Clé API Mistral manquante dans .env")
    else:
        bot.run(os.getenv("DISCORD_TOKEN"))

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv


#############
# VARIABLES #
#############
load_dotenv()
token = os.getenv("TOKEN")


###########
# FICHIER #
###########
EXTENSIONS = [
    "utilitaires.temporary_voice_channel.cog",
    "utilitaires.reaction_roles.cog",
    "utilitaires.zevent.calendar.cog",
]


##############
# CONNECTION #
##############
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True 

bot = commands.Bot(command_prefix="!", intents=intents)


async def setup_hook():
    for extension in EXTENSIONS:
        await bot.load_extension(extension)


bot.setup_hook = setup_hook


#######
# RUN #
#######
bot.run(token)
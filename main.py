import discord
from discord.ext import commands
from music import Player

intents = discord.Intents().all()
# intents = discord.intents.default()
intents.members = True
bot = commands.Bot(command_prefix='--', intents=intents)


@bot.event
async def on_ready():
    print(f"{bot.user.name} pronto.")


async def setup():
    await bot.wait_until_ready()
    bot.add_cog(Player(bot))


bot.loop.create_task(setup())


bot.run('TOKEN')

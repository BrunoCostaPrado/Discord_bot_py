import discord
from discord.ext import commands
import youtube_dl
import asyncio
import pafy


class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.song_queue = {}
        self.setup()

    def setup(self):
        for guild in self.bot.guilds:
            self.song_queue[guild.id] = []

    async def check_queue(self, ctx):
        if len(self.song_queue[ctx.guild.id]) > 0:
            await self.play_song(ctx, self.song_queue[ctx.guild.id][0])
            self.song_queue[ctx.guild.id].pop(0)

    async def search_song(self, amount, song, get_url=False):
        info = await self.bot.loop.run_in_executor(None, lambda: youtube_dl.YoutubeDL({"format": "bestaudio", "quiet": True}).extract_info(f"ytsearch{amount}:{song}", download=False, ie_key="YoutubeSearch"))
        if len(info["entries"]) == 0:
            return None
        return [entry["webpage_url"] for entry in info["entries"]] if get_url else info

    async def play(self, ctx, song):
        url = pafy.new(song).getbestaudio().url
        ctx.voice_client.play(discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(
            url)), after=lambda error: self.bot.loop.create_task(self.check_queue(ctx)))
        ctx.voice_client.source.volume = 0.5

    @commands.command()
    async def play(self, ctx, *, song=None):
        if song is None:
            return await ctx.send("Você deve inserir uma musica para tocar")

        if ctx.voice_client is None:
            return await ctx.send("Eu tenho que estar em um canal de voz para tocar musica")
        if not ("youtube.com/watch?" in song or "https://youtu.be/" in song):
            await ctx.send("Buscando, pode demarar um segundos.")

            result = await self.search_song(1, song, get_url=True)

            if result is None:
                return await ctx.send("Perdoe-me, fui incapaz de encontrar a musica desejada.")

            song = result[0]

        if ctx.voice_client.source is not None:
            queue_len = len(self.song_queue[ctx.guild.id])

            if queue_len < 10:
                self.song_queue[ctx.guild.id].append(song)
                return await ctx.send(f"Reproduzindo uma musica nesse momento, a musica inserida esta na posição: {queue_len+1}.")

            else:
                return await ctx.send("Perdoe-me, apenas posso ter 10 musicas na lista, espera a musica atual acabar para adicionar outra")

        await self.play_song(ctx, song)
        await ctx.send(f"Now playing: {song}")

    @commands.command()
    async def search(self, ctx, *, song=None):
        if song is None:
            return await ctx.send("Insira uma musica")

        await ctx.send("Buscando, pode demarar um segundos.")

        info = await self.search_song(5, song)

        embed = discord.Embed(
            title=f"Resultado para '{song}':", description="*pode usar a url para reproduzir musicas*\n", colour=discord.Colour.red())

        amount = 0
        for entry in info["entries"]:
            embed.description += f"[{entry['title']}]({entry['webpage_url']})\n"
            amount += 1

        embed.set_footer(text=f"Mostrando  {amount} resultos.")
        await ctx.send(embed=embed)

    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client is None:
            return await ctx.send("I am not playing any song.")

        if ctx.author.voice is None:
            return await ctx.send("You are not connected to any voice channel.")

        if ctx.author.voice.channel.id != ctx.voice_client.channel.id:
            return await ctx.send("I am not currently playing any songs for you.")

        poll = discord.Embed(title=f"Votando para pular - {ctx.author.name}#{ctx.author.discriminator}",
                             description="**10% do canal de voz deve votar para pular.**", colour=discord.Colour.blue())
        poll.add_field(name="Skip", value=":white_check_mark:")
        poll.add_field(name="Stay", value=":no_entry_sign:")
        poll.set_footer(text="Votação acaba em 15 segundos.")

        # only returns temporary message, we need to get the cached message to get the reactions
        poll_msg = await ctx.send(embed=poll)
        poll_id = poll_msg.id

        await poll_msg.add_reaction(u"\u2705")  # yes
        await poll_msg.add_reaction(u"\U0001F6AB")  # no

        await asyncio.sleep(15)  # 15 seconds to vote

        poll_msg = await ctx.channel.fetch_message(poll_id)

        votes = {u"\u2705": 0, u"\U0001F6AB": 0}
        reacted = []

        for reaction in poll_msg.reactions:
            if reaction.emoji in [u"\u2705", u"\U0001F6AB"]:
                async for user in reaction.users():
                    if user.voice.channel.id == ctx.voice_client.channel.id and user.id not in reacted and not user.bot:
                        votes[reaction.emoji] += 1

                        reacted.append(user.id)

        skip = False

        if votes[u"\u2705"] > 0:
            # 80% or higher
            if votes[u"\U0001F6AB"] == 0 or votes[u"\u2705"] / (votes[u"\u2705"] + votes[u"\U0001F6AB"]) > 0.79:
                skip = True
                embed = discord.Embed(
                    title="Skip Successful", description="***Votação para pular a musica atual foi um sucesso, pulando para aproxima***", colour=discord.Colour.green())

        if not skip:
            embed = discord.Embed(
                title="Skip Failed", description="*Votação para pular a musica atual foi um fracosso.*\n\n**Votação falhou, necessita de  10% do canal de voz deve votar para pular**", colour=discord.Colour.red())

        embed.set_footer(text="Votação terminou.")

        await poll_msg.clear_reactions()
        await poll_msg.edit(embed=embed)

        if skip:
            ctx.voice_client.stop()

    @commands.command()
    async def join(self, ctx):
        if ctx.author.voice is None:
            return await ctx.send("Você não esta em um canal de voz")
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect()

        await ctx.author.voice.channel.connect()

    @commands.command()
    async def leave(self, ctx):
        if ctx.voice_client is not None:
            return await ctx.voice_client.disconnect()
        await ctx.send("Você não esta em um canal de voz.")

    @commands.command()
    async def pause(self, ctx):
        if ctx.voice_client.is_paused():
            return await ctx.send("I am already paused.")

        ctx.voice_client.pause()
        await ctx.send("The current song has been paused.")

    @commands.command()
    async def resume(self, ctx):
        if ctx.voice_client is None:
            return await ctx.send("I am not connected to a voice channel.")

        if not ctx.voice_client.is_paused():
            return await ctx.send("I am already playing a song.")

        ctx.voice_client.resume()
        await ctx.send("The current song has been resumed.")

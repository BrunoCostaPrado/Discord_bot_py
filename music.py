import asyncio
import discord
from discord.ext import commands
import pafy
import youtube_dl


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

    async def play_song(self, ctx, song):
        url = pafy.new(song).getbestaudio().url
        ctx.voice_client.play(discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(
            url)), after=lambda error: self.bot.loop.create_task(self.check_queue(ctx)))
        ctx.voice_client.source.volume = 0.5

    @commands.command()
    async def join(self, ctx):
        if ctx.author.voice is None:
            return await ctx.send("Você não esta em um canal de audio, entre em um para escutar musica.")

        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect()

        await ctx.author.voice.channel.connect()

    @commands.command()
    async def leave(self, ctx):
        if ctx.voice_client is not None:
            return await ctx.voice_client.disconnect()

        await ctx.send("Não estou em um canal de musica.")

    @commands.command()
    async def play(self, ctx, *, song=None):
        if song is None:
            return await ctx.send("Você deve inserir uma musica.")

        if ctx.voice_client is None:
            return await ctx.send("I must be in a voice channel to play a song.")

        # musica sem url
        if not ("youtube.com/watch?" in song or "https://youtu.be/" in song):
            await ctx.send("Procurando, pode demorar uns segundos.")

            result = await self.search_song(1, song, get_url=True)

            if result is None:
                return await ctx.send("Sinto muito, não achei essa musica, tente usar o comando Search")

            song = result[0]

        if ctx.voice_client.source is not None:
            queue_len = len(self.song_queue[ctx.guild.id])

            if queue_len < 10:
                self.song_queue[ctx.guild.id].append(song)
                return await ctx.send(f"Estou atualmente tocando uma musica, sua musica foi inserinta na lista, na posiçãoo: {queue_len+1}.")

            else:
                return await ctx.send("Sinto muito, na lista apenas cabe 10 musicas, tente novamente quando uma acabar")

        await self.play_song(ctx, song)
        await ctx.send(f"Tocando {song}")

    @commands.command()
    async def search(self, ctx, *, song=None):
        if song is None:
            return await ctx.send("Você esqueceu da musica para procurar.")

        await ctx.send("Procurando, pode demorar uns segundos.")

        info = await self.search_song(5, song)

        embed = discord.Embed(
            title=f"Resultado para '{song}':", description="*Você pode usar essas URLs caso não consiga colocar musica*\n", colour=discord.Colour.red())

        amount = 0
        for entry in info["entries"]:
            embed.description += f"[{entry['title']}]({entry['webpage_url']})\n"
            amount += 1

        embed.set_footer(text=f"Displaying the first {amount} results.")
        await ctx.send(embed=embed)

    @commands.command()
    async def queue(self, ctx):  # mostrar lista atual
        if len(self.song_queue[ctx.guild.id]) == 0:
            return await ctx.send("Não existem musicas na lista nesse momento.")

        embed = discord.Embed(
            title="Song Queue", description="", colour=discord.Colour.dark_gold())
        i = 1
        for url in self.song_queue[ctx.guild.id]:
            embed.description += f"{i}) {url}\n"

            i += 1

        embed.set_footer(text="Obrigado pela preferencia!")
        await ctx.send(embed=embed)

    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client is None:
            return await ctx.send("Não estou tocando nenhuma musica.")

        if ctx.author.voice is None:
            return await ctx.send("Você não esta em um canal de voz")

        if ctx.author.voice.channel.id != ctx.voice_client.channel.id:
            return await ctx.send("Não estou tocando nenhuma musica.")

        poll = discord.Embed(title=f"Vote para pular musica por - {ctx.author.name}#{ctx.author.discriminator}",
                             description="**80% do canal de voz deve votar para que a musica seja pulada.**", colour=discord.Colour.blue())
        poll.add_field(name="Skip", value=":white_check_mark:")
        poll.add_field(name="Stay", value=":no_entry_sign:")
        poll.set_footer(text="Votação acaba em  5 secondos.")

        # messagem temporaria, precisamos usar mensagens em cache para ter as reações.
        poll_msg = await ctx.send(embed=poll)
        poll_id = poll_msg.id

        await poll_msg.add_reaction(u"\u2705")  # sim
        await poll_msg.add_reaction(u"\U0001F6AB")  # não

        await asyncio.sleep(5)  # 5 secondos para votar

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
            # 80% ou maior
            if votes[u"\U0001F6AB"] == 0 or votes[u"\u2705"] / (votes[u"\u2705"] + votes[u"\U0001F6AB"]) > 0.79:
                skip = True
                embed = discord.Embed(
                    title="Votação sucedida", description="***Votação para pular concluida, pulando agora.***", colour=discord.Colour.green())

        if not skip:
            embed = discord.Embed(
                title="Votação falha", description="*Votação para pular falhou.*\n\n**Votação para pular falhaou, 80% dos usuarios no canal de voz devem aceitar pular**", colour=discord.Colour.red())

        embed.set_footer(text="Votação terminou.")

        await poll_msg.clear_reactions()
        await poll_msg.edit(embed=embed)

        if skip:
            ctx.voice_client.stop()

    @commands.command()
    async def pause(self, ctx):
        if ctx.voice_client.is_paused():
            return await ctx.send("Já esta pausado.")

        ctx.voice_client.pause()
        await ctx.send("Musica atual pausada.")

    @commands.command()
    async def resume(self, ctx):
        if ctx.voice_client is None:
            return await ctx.send("Não estou em um canal de voz.")

        if not ctx.voice_client.is_paused():
            return await ctx.send("Já estou tocando uma musica.")

        ctx.voice_client.resume()
        await ctx.send("Musica atual continuada.")

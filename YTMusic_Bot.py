import os
import discord
from discord.ext import commands
from discord.ui import Button, View, Select
import asyncio
from ytmusicapi import YTMusic
import youtube_dl
import json
import datetime
from urllib.parse import urlparse, parse_qs

# Discord Token
token = os.environ['DISCORD_BOT_TOKEN']

intents = discord.Intents.all()

bot = commands.Bot(command_prefix='$', intents=intents)

@bot.event
async def on_ready():
    print('Bot Activated')
#############################################################################
class voice_base(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #VC参加＆移動
    @commands.command()
    async def yt_join(self, ctx):
        try:
            voice_client = ctx.message.guild.voice_client
            if voice_client:
                await voice_client.disconnect()
            try:
                vc_channel = ctx.author.voice.channel
                await vc_channel.connect()
            except Exception as e:
                await ctx.send('ボイスチャンネルに接続した状態でコマンドを実行して下さい')
                return
            print('VC Connected')
        except Exception as e:
            print(e)

    #VC切断
    @commands.command()
    async def yt_exit(self, ctx):
        try:
            voice_client = ctx.message.guild.voice_client
            if voice_client:
                await voice_client.disconnect()
            else:
                await ctx.send('ボイスチャンネルに接続していません')
            print('VC Disconnected')
        except Exception as e:
            print(e)

    #一時停止
    @commands.command()
    async def pause(self, ctx):
        try:
            voice_client = ctx.message.guild.voice_client
            if voice_client:
                if voice_client.is_playing():
                    voice_client.pause()
                    await ctx.send('一時停止しました')
                else:
                    await ctx.send("再生していません")
            else:
                await ctx.send('ボイスチャンネルに接続していません')
        except Exception as e:
            print(e)

    #再開
    @commands.command()
    async def resume(self, ctx):
        try:
            voice_client = ctx.message.guild.voice_client
            if voice_client:
                if voice_client.is_paused():
                    voice_client.resume()
                    await ctx.send('再生を再開しました')
                else:
                    await ctx.send("一時停止中ではありません")
            else:
                await ctx.send('ボイスチャンネルに接続していません')
        except Exception as e:
            print(e)
#############################################################################
class ytmusic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.yt = YTMusic('headers_auth.json')
        self.playlist = []
        self.playing_url = None
        self.playing_num = None
        self.song_loop = False
        self.list_loop = False
        self.temp_info = None
        self.self_stop = False

    # VC接続状態チェック
    async def vc_chk(self, ctx, type):
        try:
            if type == 'command':
                try:
                    voice_client = self.bot.voice_clients[0]
                    if voice_client:
                        return True
                except Exception as e:
                    try:
                        vc_channel = ctx.author.voice.channel
                        await vc_channel.connect()
                        return True
                    except Exception as e:
                        await ctx.send('ボイスチャンネルに接続した状態で実行して下さい')
                        return False
            else:
                try:
                    voice_client = self.bot.voice_clients[0]
                    if voice_client:
                        return True
                except Exception as e:
                    try:
                        vc_channel = ctx.user.voice.channel
                        await vc_channel.connect()
                        return True
                    except Exception as e:
                        await ctx.channel.send('ボイスチャンネルに接続した状態で実行して下さい')
                        return False
        except Exception as e:
            print(e)

    # 再生共通処理
    async def yt_play(self, url, channel, type):
        try:
            voice_client = self.bot.voice_clients[0]
            player = await YTDLSource.from_url(url, loop=bot.loop)
            self.playing_url = url
            self.temp_info = [type, channel]
            voice_client.play(player, after=self.end_flagger)
        except Exception as e:
            await channel.send('Error : 再生できません')
            print(e)

    # 直接再生
    async def direct_play(self, url, channel):
        try:
            voice_client = self.bot.voice_clients[0]
            if voice_client.is_playing():
                self.self_stop = True
                voice_client.stop()
                await asyncio.sleep(5)
            self.playing_num = None
            await self.yt_play(url, channel, 'direct')
        except Exception as e:
            print(e)

    # プレイリスト再生
    async def list_play(self, channel, type):
        try:
            if len(self.playlist) == 0:
                await channel.send("プレイリストに曲がありません")
                return
            voice_client = self.bot.voice_clients[0]
            if voice_client.is_playing():
                self.self_stop = True
                voice_client.stop()
                await asyncio.sleep(5)
            if type == 'next':
                if self.playing_num == None:
                    self.playing_num = 0
                else:
                    self.playing_num += 1
            else:
                if self.playing_num == None or self.playing_num == 0:
                    await channel.send('プレイリストの先頭です')
                    return
                else:
                    self.playing_num -= 1
            try:
                id = self.playlist[self.playing_num]['videoId']
            except Exception as e:
                if self.list_loop == False:
                    await channel.send('プレイリストの再生が終了しました')
                    self.playing_num = None
                    return
                else:
                    self.playing_num = 0
                    id = self.playlist[self.playing_num]['videoId']
            url = "https://www.youtube.com/watch?v=" + id
            description = \
                "`Title    : `" + str(self.playlist[self.playing_num]['title']) + "\n" +  \
                "`Artist   : `" + str(self.playlist[self.playing_num]['artists'][0]['name']) + "\n" +  \
                "`Album    : `" + str(self.playlist[self.playing_num]['album']['name']) + "\n" +  \
                "`Year     : `" + str(self.playlist[self.playing_num]['year']) + "\n" +  \
                "`Duration : `" + str(self.playlist[self.playing_num]['duration'])
            embed = discord.Embed(title='\N{Multiple Musical Notes}NowPlaying',description=description,color=discord.Colour.red())
            try:
                thumbs_url = self.playlist[self.playing_num]['thumbnails'][1]['url']
                embed.set_thumbnail(url=thumbs_url)
            except Exception as e:
                print(e)
            await channel.send(embed=embed)
            await self.yt_play(url, channel, 'list')
        except Exception as e:
            print(e)

    # プレイリスト表示
    @commands.command()
    async def list(self, ctx):
        try:
            if len(self.playlist) == 0:
                await ctx.send('プレイリストに曲がありません')
                return
            description = ""
            for i in range(len(self.playlist)):
                temp = str(i + 1) + ". " + str(self.playlist[i]['title']) + ' - ' + str(self.playlist[i]['artists'][0]['name']) + ' - ' + str(self.playlist[i]['duration'])
                if self.playing_num == i:
                    temp = '\N{Multiple Musical Notes} ' + temp
                description = description + temp + "\n\n"
            embed = discord.Embed(title="Playlist",description=description,color=discord.Colour.red())
            await ctx.send(embed=embed)
        except Exception as e:
            print(e)

    # プレイリスト全削除
    @commands.command()
    async def clear(self, ctx):
        try:
            self.playlist = []
            await ctx.send('プレイリストを削除しました')
        except Exception as e:
            print(e)

    # プレイリスト選択削除
    @commands.command()
    async def delete(self, ctx):
        try:
            if len(self.playlist) == 0:
                await ctx.send('プレイリストに曲がありません')
                return
            description = ""
            options = []
            for i in range(len(self.playlist)):
                temp = str(i + 1) + ". " + str(self.playlist[i]['title']) + ' - ' + str(self.playlist[i]['artists'][0]['name']) + ' - ' + str(self.playlist[i]['duration'])
                if self.playing_num == i:
                    temp = '\N{Multiple Musical Notes} ' + temp
                description = description + temp + "\n\n"
                if len(str(self.playlist[i]['title'])) > 100:
                    label = str(self.playlist[i]['title'])[0:99]
                else:
                    label = str(self.playlist[i]['title'])
                options.append(discord.SelectOption(label=label, value=str(i)))
            embed = discord.Embed(title="Playlist",description=description,color=discord.Colour.red())

            select = Select(
                placeholder="プレイリストから削除する曲を選択",
                min_values=1,
                max_values=len(self.playlist),
                options=options,
            )

            async def select_callback(interaction):
                try:
                    for i in range(len(select.values)):
                        self.playlist[int(select.values[i])] = None
                    try:
                        while True:
                            self.playlist.remove(None)
                    except Exception as e:
                        pass
                    await ctx.send('選択された曲をプレイリストから削除しました')
                except Exception as e:
                    print(e)

            select.callback = select_callback
            view = View()
            view.add_item(select)
            await ctx.send(embed=embed, view=view)
        except Exception as e:
            print(e)

    # 停止コマンド
    @commands.command()
    async def stop(self, ctx):
        try:
            voice_client = ctx.message.guild.voice_client
            if voice_client:
                if voice_client.is_playing():
                    self.self_stop = True
                    voice_client.stop()
                    await ctx.send('再生を停止しました')
                    self.playing_num = None
                else:
                    await ctx.send("再生していません")
            else:
                await ctx.send('ボイスチャンネルに接続していません')
        except Exception as e:
            print(e)

    # ループ設定コマンド
    @commands.command()
    async def loop(self, ctx):
        try:
            self.song_loop = not self.song_loop
            if self.song_loop:
                await ctx.send('ループ再生を有効にしました')
            else:
                await ctx.send('ループ再生を無効にしました')
        except Exception as e:
            print(e)
    
    # プレイリストループ設定コマンド
    @commands.command()
    async def loop_list(self, ctx):
        try:
            self.list_loop = not self.list_loop
            if self.list_loop:
                await ctx.send('プレイリストループを有効にしました')
            else:
                await ctx.send('プレイリストループを無効にしました')
        except Exception as e:
            print(e)

    # URL再生コマンド
    @commands.command()
    async def url(self, ctx, arg):
        try:
            if await self.vc_chk(ctx, 'command'):
                channel = ctx.channel
                await self.direct_play(arg, channel)
        except Exception as e:
            print(e)
    
    # URLプレイリスト追加コマンド
    @commands.command()
    async def addurl(self, ctx, arg):
        try:
            try:
                parse_url = urlparse(arg)
                param = parse_qs(parse_url.query)
                vid_id = param['v'][0]
                song_data = self.yt.get_song(vid_id)
                data_format = json.loads('{"title": "", "album": {"name": ""}, "videoId": "", "duration": "", "year": "", "artists": [{"name": ""}]}')
                data_format['title'] = song_data['videoDetails']['title']
                data_format['videoId'] = song_data['videoDetails']['videoId']
                data_format['artists'][0]['name'] = song_data['videoDetails']['author']
                td = datetime.timedelta(seconds=int(song_data['videoDetails']['lengthSeconds']))
                data_format['duration'] = str(td)
                if len(self.playlist) >= 20:
                    await ctx.send(f'プレイリストが20曲を超えるため追加されませんでした')
                    return
                else:
                    self.playlist.append(data_format)
                    await ctx.send(data_format['title'] + ' をプレイリストに追加しました')
            except Exception as e:
                await ctx.send('Error : 指定URLを追加できませんでした')
                print(e)
        except Exception as e:
            print(e)

    # プレイリスト再生コマンド
    @commands.command()
    async def play(self, ctx):
        try:
            if await self.vc_chk(ctx, 'command'):
                channel = ctx.channel
                await self.list_play(channel, 'next')
        except Exception as e:
            print(e)

    # スキップ
    @commands.command()
    async def skip(self, ctx):
        try:
            if await self.vc_chk(ctx, 'command'):
                voice_client = ctx.message.guild.voice_client
                if voice_client.is_playing():
                    channel = ctx.channel
                    await self.list_play(channel, 'next')
                else:
                    await ctx.send("再生していません")
        except Exception as e:
            print(e)

    # 前の曲
    @commands.command()
    async def prev(self, ctx):
        try:
            if await self.vc_chk(ctx, 'command'):
                voice_client = ctx.message.guild.voice_client
                if voice_client.is_playing():
                    channel = ctx.channel
                    await self.list_play(channel, 'prev')
                else:
                    await ctx.send("再生していません")
        except Exception as e:
            print(e)

    # 検索コマンド
    @commands.command()
    async def ss(self, ctx, *args):
        try:
            text = " ".join(args)
            channel = ctx.channel
            await self.song_search(text, channel)
        except Exception as e:
            print(e)

    @commands.command()
    async def ssf(self, ctx, *args):
        try:
            text = " ".join(args)
            channel = ctx.channel
            await self.song_search_full(text, channel)
        except Exception as e:
            print(e)

    # 検索＆表示処理
    async def song_search(self, text, channel):
        try:
            results = self.yt.search(text, filter='songs')
            description = ""
            for i in range(len(results)):
                description = description + str(i + 1) + ". " + str(results[i]['title']) + ' - ' + str(results[i]['artists'][0]['name']) + ' - ' + str(results[i]['duration']) + "\n\n"
            embed = discord.Embed(title="検索結果",description=description,color=discord.Colour.red())
            select = await self.select_make(results)
            play_button, add_playlist_button = await self.button_make(select, results)
            view = View()
            view.add_item(select)
            view.add_item(play_button)
            view.add_item(add_playlist_button)
            await channel.send(embed=embed, view=view)
        except Exception as e:
            print(e)

    async def song_search_full(self, text, channel):
        try:
            results = self.yt.search(text, filter='songs')
            for i in range(len(results)):
                description = \
                    "`Artist   : `" + str(results[i]['artists'][0]['name']) + "\n" +  \
                    "`Album    : `" + str(results[i]['album']['name']) + "\n" +  \
                    "`Year     : `" + str(results[i]['year']) + "\n" +  \
                    "`Duration : `" + str(results[i]['duration'])
                thumbs_url = results[i]['thumbnails'][1]['url']
                embed = discord.Embed(description=description,color=discord.Colour.red())
                url = "https://www.youtube.com/watch?v=" + str(results[i]['videoId'])
                embed.set_author(name=str(results[i]['title']),url=url)
                embed.set_thumbnail(url=thumbs_url)
                await channel.send(embed=embed)
            select = await self.select_make(results)
            play_button, add_playlist_button = await self.button_make(select, results)
            view = View()
            view.add_item(select)
            view.add_item(play_button)
            view.add_item(add_playlist_button)
            await channel.send("再生orプレイリストに追加する曲を選択", view=view)
        except Exception as e:
            print(e)

    async def button_make(self, select, results):
        play_button = Button(label="Play", style=discord.ButtonStyle.gray, emoji="\N{Black Right-Pointing Triangle}")
        add_playlist_button = Button(label="Add Playlist", style=discord.ButtonStyle.gray, emoji="\N{Heavy Plus Sign}")

        async def play_callback(interaction):
            try:
                if len(select.values) == 0:
                    await interaction.channel.send('Error : 曲が選択されていません')
                    return
                elif len(select.values) > 1:
                    await interaction.channel.send('Error : 曲が複数選択されています')
                    return
                channel = interaction.channel
                url = "https://www.youtube.com/watch?v=" + results[int(select.values[0])]['videoId']
                if await self.vc_chk(interaction, 'interaction'):
                    description = \
                        "`Title    : `" + str(results[int(select.values[0])]['title']) + "\n" +  \
                        "`Artist   : `" + str(results[int(select.values[0])]['artists'][0]['name']) + "\n" +  \
                        "`Album    : `" + str(results[int(select.values[0])]['album']['name']) + "\n" +  \
                        "`Year     : `" + str(results[int(select.values[0])]['year']) + "\n" +  \
                        "`Duration : `" + str(results[int(select.values[0])]['duration'])
                    thumbs_url = results[int(select.values[0])]['thumbnails'][1]['url']
                    embed = discord.Embed(title='\N{Multiple Musical Notes}NowPlaying',description=description,color=discord.Colour.red())
                    embed.set_thumbnail(url=thumbs_url)
                    await channel.send(embed=embed)
                    await self.direct_play(url, channel)
            except Exception as e:
                print(e)

        async def add_playlist_callback(interaction):
            try:
                if len(select.values) == 0:
                    await interaction.channel.send('曲が選択されていません')
                    return
                added_list = []
                for i in range(len(select.values)):
                    if len(self.playlist) >= 20:
                        title = results[int(select.values[i])]['title']
                        await interaction.channel.send(f'プレイリストが20曲を超えるため {title} は追加されませんでした')
                    else:
                        self.playlist.append(results[int(select.values[i])])
                        added_list.append(results[int(select.values[i])]['title'])
                await interaction.channel.send(',\n'.join(added_list) + ' をプレイリストに追加しました')
            except Exception as e:
                print(e)

        play_button.callback = play_callback
        add_playlist_button.callback = add_playlist_callback
        return play_button, add_playlist_button

    async def select_make(self, results):
        options = []
        for i in range(len(results)):
            if len(str(results[i]['title'])) > 100:
                label = str(results[i]['title'])[0:99]
            else:
                label = str(results[i]['title'])
            options.append(discord.SelectOption(label=label, value=str(i)))

        select = Select(
            placeholder="プレイリストに追加する曲を選択",
            min_values=1,
            max_values=len(results),
            options=options,
        )

        async def select_callback(interaction):
            try:
                pass
            except Exception as e:
                print(e)

        select.callback = select_callback
        return select

    # 次曲処理
    async def chk_end(self, type, channel):
        try:
            self.temp_info = None
            await asyncio.sleep(5)
            try:
                voice_client = self.bot.voice_clients[0]
                if voice_client:
                    if voice_client.is_playing():
                        pass
                    else:
                        if self.song_loop:
                            await self.yt_play(self.playing_url, channel, 'type')
                        else:
                            if type == 'direct':
                                return
                            elif type == 'list':
                                await self.list_play(channel, 'next')
            except Exception as e:
                print('VC Disconnected')
        except Exception as e:
            print(e)
    
    def end_flagger(self, error):
        if self.self_stop:
            self.self_stop = False
            return
        type = self.temp_info[0]
        channel = self.temp_info[1]
        fut = asyncio.run_coroutine_threadsafe(self.chk_end(type, channel), bot.loop)
        fut.result()

#############################################################################
ytdl_format_options = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
#############################################################################
bot.add_cog(voice_base(bot))
bot.add_cog(ytmusic(bot))
bot.run(token)
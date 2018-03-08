import itertools

import aiohttp
import discord
import wolframalpha
from discord.ext import commands
from texttable import Texttable, ArraySizeError

import config
from cogs.admin import haste_upload
from cogs.utils.paginator import EmbedPages


def code_block(string, lang=''):
    if string.strip() == '':
        return ''
    return f'```{lang}\n{string}\n```'


# easier for cleaning content
async def send(ctx, *args, **kwargs):
    res = await commands.clean_content().convert(ctx, *args, **kwargs)
    await ctx.send(res)


class Search:
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def __error(ctx, err):
        if isinstance(err, commands.CommandOnCooldown):
            await send(ctx, err)

    @commands.command()
    @commands.cooldown(rate=1, per=20, type=commands.BucketType.user)
    async def wolfram(self, ctx, *, query: commands.clean_content):
        """Do a full wolframalpha query, with a very verbose response."""
        await ctx.channel.trigger_typing()

        client = wolframalpha.Client(config.wolfram)
        res = client.query(query)

        t = Texttable()
        data = []
        images = []
        try:
            for pod in res.pods:
                sub_data = []
                for sub in pod.subpods:
                    if sub.plaintext:
                        sub_data.append(sub.plaintext)
                    if hasattr(sub, 'img'):
                        images.append(sub['img']['@src'])
                        # sub_data.append(sub['img']['@alt'])
                data.append(sub_data)
        except AttributeError:
            return await send(ctx, 'No results found.')

        embed_images = [
            discord.Embed().set_image(url=image) for image in images
        ]

        try:
            t.add_rows(data)
        except ArraySizeError:
            to_send = code_block('\n\n'.join(
                itertools.chain.from_iterable(
                    data
                )
            ))
            if to_send != '':
                try:
                    await send(ctx, to_send)
                except discord.HTTPException:
                    key = await haste_upload(to_send + '\n' + '\n'.join(images))
                    await send(ctx, f'https://hastebin.com/{key}')
            if embed_images:
                p = EmbedPages(ctx, embeds=embed_images)
                await p.paginate()
            return

        try:
            await send(ctx, code_block(t.draw()))
        except discord.HTTPException:
            key = await haste_upload(code_block(t.draw()))
            await send(ctx, f'https://hastebin.com/{key}')
        if embed_images:
            p = EmbedPages(ctx, embeds=embed_images)
            await p.paginate()

    # noinspection PyTypeChecker
    @commands.command()
    async def quick(self, ctx, *, query: commands.clean_content):
        """Do a quick wolframalpha query, with a short response"""

        # noinspection SpellCheckingInspection
        if query == 'mafs' or query == 'maths':
            return await send(ctx, '2+2 = 4-1 = 3')

        await ctx.channel.trigger_typing()
        with aiohttp.ClientSession() as s:
            async with s.get(
                    'https://api.wolframalpha.com/v2/result',
                    params={'i': query, 'appid': config.wolfram}
            ) as res:
                text = await res.text()
                if text == "No short answer available":
                    to_send = ""
                    to_send += f"{text}. Hint: try doing `{ctx.prefix} wolfram"
                    to_send += (query[:35] + '…') if len(query) > 35 else query
                    to_send += "` in a bot commands channel."

                elif text == "Wolfram|Alpha did not understand your input":
                    to_send = "Sorry, I don't understand what you said."
                else:
                    to_send = text
                await send(ctx, to_send)

    # noinspection SpellCheckingInspection
    @commands.command(aliases=['ddg', 'duck', 'google', 'goog'])
    async def duckduckgo(self, ctx, *, query: str):
        """Search the DuckDuckGo IA API"""
        await ctx.channel.trigger_typing()
        with aiohttp.ClientSession() as s:
            async with s.get(
                    'https://api.duckduckgo.com',
                    params={'q': query, 't': 'ToR Genius Discord Bot',
                            'format': 'json', 'no_html': '1'}
            ) as res:
                resp_json = await res.json(
                    content_type='application/x-javascript'
                )
                embeds = {}

                if resp_json['AbstractURL'] != '':
                    embeds[f'Abstract: {resp_json["Heading"]}'
                           f' ({resp_json["AbstractSource"]})'] = {
                        'image': resp_json['Image'],
                        'desc': f'{resp_json.get("AbstractText", "")}\n\n'
                                f'{resp_json["AbstractURL"]}'
                    }

                if resp_json['Definition'] != '':
                    embeds['Definition'] = {
                        'desc': f'{resp_json["Definition"]}\n'
                                f'([{resp_json["DefinitionSource"]}]'
                                f'({resp_json["DefinitionURL"]}))'
                    }

                if resp_json['RelatedTopics']:
                    desc = []
                    for topic in resp_json['RelatedTopics']:
                        try:
                            if len('\n'.join(desc)) > 1000:
                                break
                            desc.append(
                                f'[**{topic["Text"]}**]({topic["FirstURL"]})'
                            )
                        except KeyError:
                            # some weird subtopic thing I guess
                            continue

                    embeds['Related'] = {
                        'desc': '\n'.join(desc),
                        'image': resp_json['RelatedTopics'][0]['Icon']['URL']
                    }

                if resp_json['Results']:
                    desc = []
                    for result in resp_json['Results']:
                        desc.append(
                            f'[**{result["Text"]}**]({result["FirstURL"]})'
                        )
                    embeds['Top Results'] = {
                        'desc': '\n'.join(desc),
                        'image': resp_json['Results'][0]['Icon']['URL']
                    }

                final_embeds = []

                for embed_title, embed_content in embeds.items():
                    final_embeds.append(
                        discord.Embed(
                            title=embed_title,
                            description=embed_content['desc'],
                            color=ctx.author.color
                        ).set_image(
                            url=embed_content['image']
                        ).set_thumbnail(
                            url='https://i.imgur.com/CVogaGL.png'
                        )
                    )

                if not final_embeds:
                    return await ctx.send('No results found.')

                p = EmbedPages(ctx, embeds=final_embeds)
                await p.paginate()


def setup(bot):
    bot.add_cog(Search(bot))

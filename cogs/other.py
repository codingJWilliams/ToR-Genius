import io
import re
import textwrap
from math import floor

import aiohttp
import discord
from PIL import Image, ImageFont, ImageDraw
from discord.ext import commands

from cogs.utils.paginator import Pages


async def download(url):
    async with aiohttp.ClientSession() as sess:
        async with sess.get(url) as r:
            return io.BytesIO(await r.read())


class AvatarOrOnlineImage(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            possible_member = await commands.MemberConverter() \
                .convert(ctx, argument)
            url = possible_member.avatar_url_as(format='png')
            url = url.replace('gif', 'png').strip('<>')

            img = await download(url)

            img = Image.open(img)

            return img.convert('RGBA')
        except commands.BadArgument:
            pass

            # from https://stackoverflow.com/questions/169625/
            # regex-to-check-if-valid-url-that-ends-in-jpg-png-or-gif
            # (Sorry about breaking the URL)

            # will add more image formats as time goes on
        regex = r'<?(?:([^:/?#]+):)?(?://([^/?#]*))?([^?#]*\.' \
                r'(?:jpg|png|jpeg))(?:\?([^#]*))?(?:#(.*))?>?'

        regex = re.compile(regex, re.IGNORECASE)

        if re.fullmatch(regex, argument):
            img = await download(argument.strip('<>'))

            img = Image.open(img)

            return img.convert('RGBA')
        else:
            # must be text
            return argument


# The floor is good naming
class AvatarOrOnlineImageOrText(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            possible_member = await commands.MemberConverter() \
                .convert(ctx, argument)
            url = possible_member.avatar_url_as(format='png')
            url = url.replace('gif', 'png').strip('<>')

            img = await download(url)

            img = Image.open(img)

            return img.convert('RGBA'), possible_member.name
        except commands.BadArgument:
            pass

            # from https://stackoverflow.com/questions/169625/
            # regex-to-check-if-valid-url-that-ends-in-jpg-png-or-gif
            # (Sorry about breaking the URL)

            # will add more image formats as time goes on
        regex = r'<?(?:([^:/?#]+):)?(?://([^/?#]*))?([^?#]*\.' \
                r'(?:jpg|png|jpeg))(?:\?([^#]*))?(?:#(.*))?>?'

        regex = re.compile(regex, re.IGNORECASE)

        if re.fullmatch(regex, argument.split(' ')[0]):
            img = await download(argument.split(' ')[0].strip('<>'))

            img = Image.open(img)

            text = ' '.join(argument.split(' ')[1:])
            if not text:
                raise commands.BadArgument('No text supplied for image')
            return img.convert('RGBA'), text
        else:
            raise commands.BadArgument(
                "That URL doesn't seem to lead to a valid image"
            )


class LinkOrAvatar(commands.Converter):
    special_cases = {
        'itsthejoker': 'https://avatars0.githubusercontent.com/u/5179553'
    }

    async def convert(self, ctx, argument):
        try:
            possible_member = await commands.MemberConverter() \
                .convert(ctx, argument)
            if possible_member.name not in self.special_cases:
                url = possible_member.avatar_url_as(format='png')
                url = url.replace('gif', 'png').strip('<>')
            else:
                url = self.special_cases[possible_member.name]

            img = await download(url)

            img = Image.open(img)

            return img.convert('RGBA'), possible_member.name
        except commands.BadArgument:
            pass

        # from https://stackoverflow.com/questions/169625/
        # regex-to-check-if-valid-url-that-ends-in-jpg-png-or-gif
        # (Sorry about breaking the URL)

        # will add more image formats as time goes on
        regex = r'<?(?:([^:/?#]+):)?(?://([^/?#]*))?([^?#]*\.' \
                r'(?:jpg|png|jpeg))(?:\?([^#]*))?(?:#(.*))?>?'

        regex = re.compile(regex, re.IGNORECASE)

        if re.fullmatch(regex, argument.split(' ')[0]):
            img = await download(argument.split(' ')[0].strip('<>'))

            img = Image.open(img)

            text = ' '.join(argument.split(' ')[1:])
            if not text:
                raise commands.BadArgument('No text supplied for image')
            return img.convert('RGBA'), text
        else:
            raise commands.BadArgument(
                "That URL doesn't seem to lead to a valid image"
                # if possible_member else "I couldn't find that user"
            )


class Other:
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def __error(ctx, err):
        if isinstance(err, commands.BadArgument):
            await ctx.send(err)

    @commands.command()
    async def forum(self, ctx, *, search):
        """Search the Swift Discourse Forum for anything."""
        with aiohttp.ClientSession() as s:
            async with s.get(
                    'https://forums.swift.org/search/query.json',
                    params={'term': search}
            ) as r:
                r = await r.json()

                if r['grouped_search_result'] is None:
                    return await ctx.send('No results found.')

                data = []

                # I'm sorry. (Ok not as bad now)

                # idk why, but topics seems to disappear sometimes
                data.extend([(f't/{t["id"]}', t['title'])
                             for t in r.get('topics', [])])

                data.extend([(f'u/{u["username"]}',
                              f'{u["username"]} ({u["name"]})')
                             for u in r['users']])

                data.extend([(f'c/{c.id}', c['name'])
                             for c in r['categories']])

                data.extend([(f'tags/{t["name"]}', t['name'])
                             for t in r['tags']])

                data.extend([(f'p/{p["id"]}', p['blurb'])
                             for p in r['posts']])

                if not data:
                    return await ctx.send('No results found.')

                p = Pages(
                    ctx,
                    entries=[f'[{d[1]}](https://forums.swift.org/{d[0]})'
                             for d in data]
                )

                await p.paginate()

    # noinspection PyUnresolvedReferences,PyPep8Naming
    @commands.command()
    async def blame(self, ctx, *, img: AvatarOrOnlineImageOrText = None):
        """Blame everyone! Defaults to perryprog.

        Will also accept image urls ending in jpg, png, and jpeg."""
        # hardcoded because I want to be blamed even in forks ;)
        img, name = img or await LinkOrAvatar() \
            .convert(ctx, '280001404020588544')
        # special cases for usernames
        special_cases = {
            'perryprog': 'perry',
            'itsthejoker': 'joker'
        }

        # :no_entry: emoji
        emoji = 'https://emojipedia-us.s3.amazonaws.com/thumbs/240/twitter/' \
                '120/no-entry-sign_1f6ab.png'
        emoji = await download(emoji)
        emoji = Image.open(emoji)
        emoji = emoji.convert('RGBA')

        # make the image 3 times larger than the avatar
        large_image = Image.new('RGBA', [3 * x for x in img.size], (0,) * 4)
        lW, lH = large_image.size
        W, H = img.size
        # the center box for the avatar
        box = (W, H, W * 2, H * 2)

        # make the emoji 20% bigger than the avatar
        emoji = emoji.resize([floor(x * 1.2) for x in img.size])
        eW, eH = emoji.size

        large_image.paste(img.copy(), box)
        large_image.paste(
            emoji,

            (  # center the emoji
                floor((lW - eW) / 2),

                floor((lH - eH) / 2)
            ),

            emoji
        )

        # make the font size relative to the avatar size
        fnt = ImageFont.truetype('Arial.ttf', floor(img.size[0] / 4))
        d = ImageDraw.Draw(large_image)

        name = special_cases.get(
            name,
            re.sub(r'\W', '', name).lower()
        )

        message = f'#blame{name}'
        tW, tH = d.textsize(message, fnt)

        d.text(
            (  # center the text
                floor((lW - tW) / 2),
                # make the text somewhat centered (a bit offset so it
                # looks good) in the first "row"
                floor(H / 2) - floor(W / 4)
            ),
            message,
            font=fnt,
            fill=(255,) * 4
        )

        bio = io.BytesIO()
        large_image.save(bio, 'PNG')
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename='blame.png'))

    # noinspection PyPep8Naming,PyUnresolvedReferences
    @commands.command(aliases=['floor'])
    async def the_floor(self, ctx, img: AvatarOrOnlineImageOrText, *, what):
        """Generate a the floor is lava meme."""

        img, _ = img

        if len(what) > 179:
            return await ctx.send("The floor isn't that long. (max 179 chars)")

        meme_format = Image.open('memes/floor.png')

        # == Text ==
        fnt = ImageFont.truetype('Arial.ttf', 30)
        d = ImageDraw.Draw(meme_format)

        margin = 20
        offset = 25
        for line in textwrap.wrap(f'The floor is {what}', width=65):
            d.text((margin, offset), line, font=fnt, fill=(0,) * 3)
            offset += fnt.getsize(line)[1]

        # == Avatars ==
        first = img.resize((20, 20))
        second = img.resize((40, 40))

        meme_format.paste(first, (143, 135))
        meme_format.paste(second, (465, 133))

        # == Sending ==
        bio = io.BytesIO()
        meme_format.save(bio, 'PNG')
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename='floor.png'))

    # noinspection PyUnresolvedReferences
    @commands.command(aliases=['car'])
    async def highway(self, ctx, img: AvatarOrOnlineImageOrText,
                      first_option, *, second_option):
        """Generate a "Left Exit 12 Off Ramp" meme."""

        img, _ = img

        if len(first_option) > 54 or len(second_option) > 54:
            return await ctx.send("Your options can't be that long. (Max 54)")

        meme_format = Image.open('memes/highway.jpg')

        # == Text one ==
        fnt = ImageFont.truetype('Arial.ttf', 22)
        d = ImageDraw.Draw(meme_format)

        margin = 165
        offset = 80
        for line in textwrap.wrap(first_option, width=9):
            d.text((margin, offset), line, font=fnt, fill=(255,) * 3)
            offset += fnt.getsize(line)[1]

        # == Text two ==

        margin = 380
        offset = 80
        for line in textwrap.wrap(second_option, width=9):
            d.text((margin, offset), line, font=fnt, fill=(255,) * 3)
            offset += fnt.getsize(line)[1]

        # == Image ==
        meme_format.paste(img.resize((50, 50)), (340, 430))

        # == Sending ==
        bio = io.BytesIO()
        meme_format.save(bio, 'PNG')
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename='floor.png'))

    @commands.command()
    async def wheeze(self, ctx, *, message: str):
        """Generate a wheeze meme."""

        if len(message) > 10:
            return await ctx.send(
                "Can't do more than 10 characters because reasons"
            )

        meme_format = Image.open('memes/wheeze.png')

        # == Text ==
        fnt = ImageFont.truetype('Arial.ttf', 20)
        d = ImageDraw.Draw(meme_format)

        d.text((34, 483), message, font=fnt, fill=(0,) * 3)

        # == Sending ==
        bio = io.BytesIO()
        meme_format.save(bio, 'PNG')
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename='wheeze.png'))

    # noinspection PyUnresolvedReferences
    @commands.command(aliases=['garbage'])
    async def trash(self, ctx, first: AvatarOrOnlineImage,
                    *, second: AvatarOrOnlineImage):
        """Generate a taking out the trash meme."""

        if isinstance(first, str):
            if len(first) > 6:
                return await ctx.send(
                    "Can't do more than 6 characters because reasons"
                )

        if isinstance(second, str):
            if len(second) > 25:
                return await ctx.send(
                    "Can't do more than 6 characters because reasons"
                )

        meme_format = Image.open('memes/garbage.jpg')
        meme_format = meme_format.convert('RGBA')

        # == Text/Avatars 1==
        if isinstance(first, str):
            fnt = ImageFont.truetype('Arial.ttf', 50)
            d = ImageDraw.Draw(meme_format)

            margin = 440
            offset = 35
            for line in textwrap.wrap(first, width=4):
                d.text((margin, offset), line, font=fnt, fill=(255,) * 3)
                offset += fnt.getsize(line)[1]
        else:
            first = first.resize((180, 180))
            first = first.rotate(20, expand=True)
            meme_format.paste(first, (390, 15), first)

        # == Text/Avatars 2 ==
        if isinstance(second, str):
            fnt = ImageFont.truetype('Arial.ttf', 50)
            d = ImageDraw.Draw(meme_format)

            margin = 720
            offset = 170
            for line in textwrap.wrap(second, width=5):
                d.text((margin, offset), line, font=fnt, fill=(0,) * 3)
                offset += fnt.getsize(line)[1]
        else:
            second = second.resize((250, 250))
            second = second.rotate(-10, expand=True)
            meme_format.paste(second, (620, 150), second)

        # == Sending ==
        bio = io.BytesIO()
        meme_format.save(bio, 'PNG')
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename='floor.png'))

    @commands.command()
    async def captcha(self, ctx, img: AvatarOrOnlineImageOrText,
                      *, message=None):
        """Generate a select all <blank>"""

        img, name = img
        name = re.sub(r'\W', '', name).lower()
        name = message or name

        meme_format = Image.open('memes/captcha.png')

        # == Images ==
        img = img.resize((129, 129))

        for x_mul in range(3):
            for y_mul in range(3):
                meme_format.paste(img, (27 + 129 * x_mul, 173 + 129 * y_mul))

        # == Text ==
        fnt = ImageFont.truetype('Arial.ttf', 30)
        d = ImageDraw.Draw(meme_format)

        d.text((51, 90), name, font=fnt, fill=(255,) * 3)

        # == Sending ==
        bio = io.BytesIO()
        meme_format.save(bio, 'PNG')
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename='floor.png'))

    @commands.command('spam')
    async def who_did_this(self, ctx, search=3):
        """Find out who spammed a help command.

        Specifically for the dbots server.

        Search is how far to go before hitting a bot."""
        final_results = []

        async for m in ctx.channel.history(limit=search):
            if m.author.bot:
                # We probably found the end of the train
                async for bot_m in ctx.channel.history(before=m):
                    if not bot_m.author.bot:
                        # Start of the train
                        final_results.append((bot_m.author, bot_m.content))
                        async for others_m in ctx.channel.history(
                                limit=5, before=bot_m
                        ):
                            final_results.append(
                                (others_m.author, others_m.content)
                            )
                            return await ctx.send(
                                '\n'.join(
                                    f'**{commands.clean_content().convert(r[0].display_name)}:** {commands.clean_content().convert(r[1])}'
                                    for r in final_results
                                )
                            )


def setup(bot):
    bot.add_cog(Other(bot))

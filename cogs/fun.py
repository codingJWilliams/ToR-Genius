# Copyright (c) 2017 Perry Fraser
#
# Licensed under the MIT License. https://opensource.org/licenses/MIT
import asyncio
import logging
import random

from discord.ext import commands

from cogs.admin import gist_upload
from cogs.utils.checks import tor_only
from cogs.utils.encode_operations import EncodeOperations

log = logging.getLogger(__name__)


class Fun:
    """How much fun can a fun fun have if a fun fun could have fun?"""

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def __error(ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)

    @commands.group(invoke_without_command=True, disabled=True, hidden=True)
    async def awesome(self, ctx):
        """Tells you your awesome status"""
        query = 'SELECT is_awesome FROM fun_config WHERE guild_id = $1;'

        val = await ctx.db.fetchval(query, ctx.guild.id)
        if val is None or not val:
            result = 'Yeah. U Have No Awesome.'
        else:
            # noinspection SpellCheckingInspection
            result = 'Aww yiss'

        await ctx.send(result)

    @awesome.command(name='on', aliases=['yes', 'true'], disabled=True)
    async def awesome_on(self, ctx):
        """Turns on your awesome status"""
        query = """
    INSERT INTO fun_config (guild_id, is_awesome) VALUES ($1, TRUE)
    ON CONFLICT (guild_id)
      DO UPDATE SET
        is_awesome = EXCLUDED.is_awesome;"""

        await ctx.db.execute(query, ctx.guild.id)
        await ctx.send('ur s0 aw3som3')

    @awesome.command(name='off', aliases=['no', 'false'])
    async def awesome_off(self, ctx):
        """Turns off your awesome status"""
        query = """
    INSERT INTO fun_config (guild_id, is_awesome) VALUES ($1, FALSE)
    ON CONFLICT (guild_id)
      DO UPDATE SET
        is_awesome = EXCLUDED.is_awesome;"""

        await ctx.db.execute(query, ctx.guild.id)
        await ctx.send('ur dumb')

    @awesome.command(name='toggle')
    async def awesome_toggle(self, ctx):
        """TOGGLE that awesome status!"""
        # we're just going to see what the current state is, then call the
        # appropriate function so we don't have to deal with non-registered
        # guilds
        query = """
    SELECT is_awesome
    FROM fun_config
    WHERE guild_id = $1"""

        val = await ctx.db.fetchval(query, ctx.guild.id)

        if val:
            await ctx.invoke(self.awesome_off)
        else:
            await ctx.invoke(self.awesome_on)

    @commands.command(hidden=True, aliases=['nick', 'name'])
    @tor_only()
    async def display_name(self, ctx, *, user: commands.MemberConverter = None):
        """Made for fastfinge with <3"""
        user = ctx.author if not user else user
        await ctx.send(
            f'{user.name}\'s display name is {user.display_name}.'
        )

    @commands.command()
    async def choose(self, ctx, *choices: commands.clean_content):
        """Pick a random item from user input.

        For multiple items with multiple words, use double quotes."""

        if len(choices) < 2:
            # noinspection SpellCheckingInspection
            await ctx.send('You need at least two choices plskthx')
            return

        await ctx.send(
            f'Out of {", ".join(choices[:-1])}, and {choices[-1]}; I choose '
            f'{random.choice(choices)}.'
        )

    @commands.command()
    async def shuffle(self, ctx, *choices: commands.clean_content):
        """Shuffle the input, splitting on spaces"""

        await ctx.send(' '.join(random.sample(choices, len(choices))))

    @commands.command()
    async def warn(self, ctx, member: commands.MemberConverter, *, _=None):
        """Meme warn. Doesn't actually do anything."""
        member = ctx.author if not member else member
        await ctx.send(
            f'<:tickYes:404815005423501313> **_'
            f'{member.name}#{member.discriminator} has been warned._**'
        )

    @commands.command(hidden=True)
    async def this(self, ctx):
        """memes"""
        if ctx.prefix != 'de;et ':
            return

        await ctx.send('tor sh rm -rf .')

    # noinspection PyUnresolvedReferences,PyTypeChecker
    @commands.command(aliases=['B'])
    async def b(self, ctx, *, message: commands.clean_content):
        """This is a bad idea."""
        if 'b' in message.lower():
            return await ctx.send(message.replace('b', ':b:').replace('B', ':b:'))

        consonants = set([x for x in message if x.lower() in "bcdfghjklmnpqrstvwxyz"])
        await ctx.send(message.replace(random.choice(tuple(consonants) if consonants else message), ':b:'))

    # noinspection SpellCheckingInspection
    @commands.command(aliases=['rencode', 'encode'])
    async def random_encode(self, ctx, message, iterations: int = 4):
        """(prob won't work) randomly encode a string using a number of methods.

        Hint: Binary is utf-8."""
        # Not using context manager because the typing remains after sending
        # a message. #blamedanny

        if iterations > 10:
            return await ctx.send("You can't do that many interations.")

        await ctx.channel.trigger_typing()

        for _ in range(1, iterations):
            message = getattr(
                EncodeOperations,
                random.choice(
                    [opt for opt in dir(EncodeOperations)
                     if not opt.startswith('__')])
            )(message)

        if len(message) > 600:
            key = await gist_upload(
                {'encoding': {'content': message}}
            )

            await ctx.send(key)
        else:
            await ctx.send(f'```{message}```')

    @commands.command(aliases=['sync'])
    async def loading(self, ctx, count: int = 7):
        if count < 1 or count > 50:
            return await ctx.send('Please make the number '
                                  'above one and below 50')

        emoji = [':white_check_mark:', '<:check:314349398811475968>',
                 '<:xmark:314349398824058880>', '<a:typing:393848431413559296>',
                 ' <a:loading:393852367751086090>',
                 ' <a:updating:403035325242540032>',
                 '<a:cursor:404001393360502805>',
                 '<:update:264184209617321984>']
        opts = ['Almost done', 'Loading', 'About to finish',
                'Just one more second... ', '≈ 3 more seconds',
                'Will finish in a bit', 'Nearly complete']

        def gen_message():
            if bool(random.getrandbits(1)):
                return f'{random.choice(emoji)} {random.choice(opts)}'
            else:
                return f'{random.choice(opts)} {random.choice(emoji)}'

        m = await ctx.send(gen_message())
        await asyncio.sleep(random.uniform(.5, 2.5))
        for _ in range(1, count):
            await m.edit(content=gen_message())
            await asyncio.sleep(random.uniform(.5, 2.5))

        await m.edit(content='Done for real!')

    @staticmethod
    async def on_message(message):
        if message.channel.id == 417369794883354625:
            # noinspection SpellCheckingInspection
            if 'boing' not in message.content.lower():
                await message.delete()

    @staticmethod
    async def on_message_edit(_, message):
        if message.channel.id == 417369794883354625:
            # noinspection SpellCheckingInspection
            if 'boing' not in message.content.lower():
                await message.delete()


def setup(bot):
    bot.add_cog(Fun(bot))

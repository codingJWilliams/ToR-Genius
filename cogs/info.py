import io
import locale
from collections import Counter
from datetime import datetime

import discord
import humanize
from PIL import Image, ImageDraw
from discord.ext import commands

from cogs.utils import db
from cogs.utils.paginator import Pages

# following is from
# https://github.com/khazhyk/dango.py/blob/master/plugins/info.py
# Discord epoch
UNKNOWN_CUTOFF = datetime.utcfromtimestamp(1420070400.000)


def format_time(time):
    if time is None or time < UNKNOWN_CUTOFF:
        return "Unknown"
    return "{} ({} UTC)".format(
        humanize.naturaltime(time + (datetime.now() - datetime.utcnow())), time)


class LangTable(db.Table, table_name='lang'):
    user_id = db.Column(db.Integer(big=True), primary_key=True)
    lang_desc = db.Column(db.String)


# use function here because we don't need `ctx`
# We also call it with a splat, so we get one at a time
def parse_color(arg):
    arg.strip('#')  # so what if it ends in "#"

    # Try to cast to int
    try:
        value = int(arg, 16)
    except ValueError:
        # might be color name
        pass
    else:
        return discord.Color(min(value, 0xFFFFFF))

    try:
        return getattr(discord.Color, arg)()
    except AttributeError:
        raise commands.BadArgument(f"{arg} doesn't seem to be a valid color.")


class Info:
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def __error(ctx, err):
        if isinstance(err, commands.BadArgument):
            await ctx.send(err)

    @commands.command(aliases=['perms'])
    async def permissions(self, ctx, member: commands.MemberConverter = None,
                          channel: commands.TextChannelConverter = None,
                          *, query: str.lower = ''):
        """Get the permissions of a member in a certain channel"""
        channel = channel or ctx.channel
        user = member or ctx.author

        perms = user.permissions_in(channel)

        desc = []

        # I'm sorry
        desc.extend(
            f'**{p.replace("_", " ").title()}**: {"Yes" if v else "No"}'
            for p, v in perms
            if query in p.lower().replace("_", " ")
            or query in ("Yes" if v else "No")
        )

        if not desc:
            return await ctx.send('No results found.')

        e = discord.Embed(
            description='\n'.join(desc),
            color=user.color,
            title=f'Permissions for {user.display_name}'
        )

        await ctx.send(embed=e)

    # noinspection PyUnresolvedReferences
    @commands.command()
    async def joined(self, ctx, member: commands.MemberConverter = None):
        """Find out concisely when a member joined."""
        member = member or ctx.author
        await ctx.send(f'{member.display_name} joined '
                       f'{format_time(member.joined_at)}')

    @commands.command()
    async def created(self, ctx, member: commands.MemberConverter = None):
        """Find out concisely when a user joined Discord."""
        member = member or ctx.author
        await ctx.send(f'{member.display_name} created their account '
                       f'{format_time(member.created_at)}')

    @commands.command()
    async def emojis(self, ctx, *, query=''):
        """List the servers emojis without spamming."""
        entries = [f'{str(e)}, `:{e.name}:`, `{str(e)}`' for e in
                   ctx.guild.emojis if query in e.name]

        if not entries:
            return await ctx.send('No results found for query.')

        p = Pages(ctx, entries=entries)
        await p.paginate()

    @commands.command()
    async def games(self, ctx, *, query: str.lower = ''):
        """Search or list games, sorted by most common"""

        count = Counter([
            u.game.name
            for u in ctx.guild.members
            if u.game and query in u.game.name.lower()
        ])

        p = Pages(ctx, entries=[
            f'**{i[0]}**: {i[1]}' for i in count.most_common()
        ])

        await p.paginate()

    @commands.command()
    async def names(self, ctx, *, query: str.lower = ''):
        """Search or list names on this guild, sorted by most common"""

        count = Counter([
            u.name
            for u in ctx.guild.members
            if query in u.name.lower()
        ])

        p = Pages(ctx, entries=[
            f'**{i[0]}**: {i[1]}' for i in count.most_common()
        ])

        await p.paginate()

    @commands.command()
    async def nicks(self, ctx, *, query: str.lower = ''):
        """Search or list nicks on this guild, sorted by most common"""

        count = Counter([
            u.display_name
            for u in ctx.guild.members
            if query in u.display_name.lower()
        ])

        p = Pages(ctx, entries=[
            f'**{i[0]}**: {i[1]}' for i in count.most_common()
        ])

        await p.paginate()

    @commands.command()
    async def color(self, ctx, *colors: parse_color):
        """Generate a color(s)"""

        # == Parsing ==

        colors = [(
            col.value >> 16,
            col.value >> 8 & 0xff,
            col.value & 0xff
        ) for col in colors]

        # == Drawing ==

        # Each square is 256 by 256
        width = 256 * len(colors)

        # background is same color as start to be lazy
        image = Image.new('RGB', (width, 256), colors[0])
        draw = ImageDraw.Draw(image)

        for i in range(1, len(colors)):
            draw.rectangle((256 * i, 0, 256 * (i + 1), 256), colors[i])

        # == Sending ==
        bio = io.BytesIO()
        image.save(bio, 'PNG')
        bio.seek(0)
        await ctx.send(
            file=discord.File(
                bio,
                filename='color.png' if len(colors) == 1 else 'colors.png'
            )
        )

    @commands.command()
    async def hoisters(self, ctx, role: commands.RoleConverter = None,
                       limit: int = 0):
        """Get a list of possible hoisters, with an optional role, and an
        optional limit."""

        if role:
            result = [
                m.display_name for m in ctx.guild.members if role in m.roles
            ]
        else:
            result = [m.display_name for m in ctx.guild.members]

        result = result[:limit] if limit else result

        p = Pages(ctx, entries=sorted(result, key=locale.strxfrm))
        await p.paginate()

    @commands.group(aliases=['lang'])
    async def language(self, ctx):
        """Set/get other peoples description of the languages they know."""
        if ctx.invoked_subcommand is None:
            await ctx.show_help('language')

    @language.command(name='set')
    async def lang_set(self, ctx, *, lang: commands.clean_content):
        """Set your language description to something."""
        query = """
INSERT INTO lang (user_id, lang_desc) VALUES ($1, $2)
ON CONFLICT (user_id)
  DO UPDATE SET lang_desc = EXCLUDED.lang_desc;
        """

        await ctx.db.execute(query, ctx.author.id, lang)
        await ctx.auto_react()

    @language.command(name='get')
    async def lang_get(self, ctx, *, user: commands.MemberConverter = None):
        """Get your own or someone else's language description"""
        query = """
SELECT lang_desc
FROM lang 
WHERE user_id = $1;"""

        user = user or ctx.author

        res = await ctx.db.fetchval(query, user.id)

        if not res:
            return await ctx.send("I couldn't find a language description of "
                                  "that user. Sorry.")

        await ctx.send(
            f'{user.display_name}\'s language description is "{res}".'
        )

    @commands.command()
    async def uptime(self, ctx, exact: bool = False):
        """Get the bots uptime, with an optional exact time."""

        # thee floor is good if-else and formatting
        await ctx.send(
            f'I have been online for about '
            f'{humanize.naturaldelta(datetime.now() - self.bot.uptime)}.'
            if not exact
            else f'I have been online since '
                 f'{self.bot.uptime.strftime("%a %d %b %Y — %I:%M:%S %p")}.'
        )


def setup(bot):
    bot.add_cog(Info(bot))

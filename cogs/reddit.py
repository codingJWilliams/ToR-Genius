import random
import re

import discord
from discord.ext import commands
from discord.ext.commands import IDConverter, BadArgument
from prawcore.exceptions import NotFound

from cogs.utils import db
from cogs.utils.checks import is_mod, tor_only
from cogs.utils.paginator import Pages


class RedditConfig(db.Table, table_name='reddit_config'):
    user_id = db.Column(db.Integer(big=True), primary_key=True)
    reddit_username = db.Column(db.String)


class RedditMember:
    @classmethod
    async def create(cls, ctx, member):
        self = RedditMember()

        query = """
SELECT reddit_username
FROM reddit_config
WHERE user_id = $1;
        """

        result = await ctx.db.fetchval(query, member.id)
        if result is None:
            raise LookupError()

        self.reddit = result
        self.user = member
        return self


def _get_from_guilds(bot, getter, argument):
    result = None
    for guild in bot.guilds:
        result = getattr(guild, getter)(argument)
        if result:
            return result
    return result


class RedditAccountConverter(IDConverter):
    async def convert(self, ctx, argument):

        message = ctx.message
        bot = ctx.bot
        match = self._get_id_match(argument) or re.match(r'<@!?([0-9]+)>$',
                                                         argument)
        guild = message.guild
        if match is None:
            # not a mention...
            if guild:
                member = guild.get_member_named(argument)
            else:
                member = _get_from_guilds(bot, 'get_member_named', argument)
        else:
            user_id = int(match.group(1))
            if guild:
                member = guild.get_member(user_id)
            else:
                member = _get_from_guilds(bot, 'get_member', user_id)

        if member is None:
            raise BadArgument(f'Member "{argument}" not found')

        try:
            reddit_member = await RedditMember.create(ctx, member)
        except LookupError:
            raise BadArgument(f'No Reddit account for {member.display_name}. '
                              f'They can create one with `{ctx.prefix}link '
                              f'<reddit username>`')
        else:
            return reddit_member


class Reddit:
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def __error(ctx, error):
        if isinstance(error, BadArgument):
            await ctx.send(error)

    @commands.command(name='rwiki')
    async def reddit_wiki_page(self, ctx, *, search: str = None):
        """Search the wiki pages on r/ToR for something."""
        sub = ctx.r.subreddit('transcribersofreddit')
        if not search:
            embed = discord.Embed(
                color=ctx.author.color,
                description='[ToR Wiki](https://www.reddit.com/'
                            'r/TranscribersOfReddit/wiki/index)'
            )

            await ctx.send(embed=embed)
            return

        results = []

        for page in sub.wiki:
            if search in str(page.name):
                results.append(
                    f'[{page.name}](https://www.reddit.com'
                    f'/r/TranscribersOfReddit/wiki/{page.name})'
                )

        if results is not []:
            p = Pages(ctx, entries=results)
            p.embed.color = ctx.author.color
            await p.paginate()
        else:
            await ctx.send("Couldn't find any results for that. Sorry! ):")

    @commands.group(invoke_without_command=True)
    @tor_only()
    async def link(self, ctx, *, username: commands.clean_content):
        """Link a reddit account with your discord account.

        This will replace any existing reddit accounts you have linked. """
        if username.startswith('/u/'):
            username = username.replace('/u/', '', 1)
        elif username.startswith('u/'):
            username = username.replace('u/', '', 1)

        # throw away the value, this is just so we can tell if the user is valid
        try:
            _ = ctx.r.redditor(username).fullname
        except AttributeError:
            # seems to happen when a user has no activity, like /u/asdf.
            pass
        except NotFound:
            await ctx.send("Sorry! That username doesn't appear to be valid.")
            return

        if ctx.author.guild_permissions.ban_members is True \
                or await self.bot.is_owner(ctx.author):
            # I'm bad at DRY

            query = """
INSERT INTO reddit_config (user_id, reddit_username) VALUES ($1, $2)
ON CONFLICT (user_id)
  DO UPDATE SET
    reddit_username = EXCLUDED.reddit_username;"""

            await ctx.db.execute(query, ctx.author.id, username)

            await ctx.auto_react()
            await ctx.send("You've been approved! Woo!")

            return

        msg = (
            'Mods: can you please check that this is correct. If so, react '
            'with :white_check_mark:. Otherwise, react with :no_entry_sign:.'
        )

        result = await ctx.prompt(
            msg, timeout=10 * 60, needs_mod=True, reacquire=False
        )

        if result is None:
            await ctx.send(
                'Looks like a mod took too long to respond. Try again later :)'
            )
        elif result is False:
            await ctx.send('Sorry mate. A mod denied your request.')
        else:
            query = """
            INSERT INTO reddit_config (user_id, reddit_username) VALUES ($1, $2)
            ON CONFLICT (user_id)
              DO UPDATE SET
                reddit_username = EXCLUDED.reddit_username;"""

            await ctx.db.execute(query, ctx.author.id, username)

            await ctx.auto_react()
            await ctx.send("You've been approved! Woo!")

    @link.command()
    @is_mod()
    @tor_only()
    async def force(
            self, ctx, reddit_username: commands.clean_content,
            *, discord_username: commands.MemberConverter = None
    ):
        """Mod command for setting someones Reddit account."""
        if not discord_username:
            user = ctx.author
        else:
            user = discord_username

        query = """
INSERT INTO reddit_config (user_id, reddit_username) VALUES ($1, $2)
ON CONFLICT (user_id)
  DO UPDATE SET
    reddit_username = EXCLUDED.reddit_username;"""

        await ctx.db.execute(query, user.id, reddit_username)

        await ctx.auto_react()

    @commands.command()
    async def account(self, ctx, *, user: RedditAccountConverter = None):
        """Get the reddit account of a user, or yourself."""

        user = await RedditMember.create(ctx, ctx.author) if not user else user

        description = f'{user.user.display_name}\'s Reddit account is' \
                      f' [/u/{user.reddit}]' \
                      f'(https://reddit.com/u/{user.reddit}).'

        if random.randrange(1, 100) == 5:
            description += ' Please enjoy stalking them.'

        await ctx.send(embed=discord.Embed(description=description))
        return

    @commands.command()
    async def daccount(self, ctx, *, account: str):
        """Get the discord account of a reddit user"""

        query = """
SELECT user_id
FROM reddit_config
WHERE reddit_username = $1
        """

        if account.startswith('/u/'):
            account = account.replace('/u/', '', 1)
        elif account.startswith('u/'):
            account = account.replace('u/', '', 1)

        val = await ctx.db.fetchval(query, account)
        if val is None:
            await ctx.send("I can't find that user. Sorry!")
            return

        user = self.bot.get_user(val)

        description = f'[/u/{account}](https://reddit.com/u/{account})\'s' \
                      f' Discord Account is {user.mention}.'
        if random.randrange(1, 100) == 5:
            description += ' Please enjoy stalking them.'

        await ctx.send(embed=discord.Embed(description=description))
        return

    @commands.command()
    @tor_only()
    async def all_accounts(self, ctx):
        """Get a list of all the reddit accounts"""
        query = """
SELECT
  user_id,
  reddit_username
FROM reddit_config;
        """

        results = await ctx.db.fetch(query)

        if not results:
            await ctx.send("I couldn't find any results! Sorry!")
            return

        p = Pages(
            ctx, entries=tuple(
                f'{self.bot.get_user(r[0]).mention}: '
                f'[/u/{r[1]}](https://reddit.com/u/{r[1]})' for r in results
            )
        )

        await p.paginate()

    @commands.command()
    async def flair_count(self, ctx, *,
                          flair: commands.clean_content = "Unclaimed"):
        """Get the number of posts left on r/ToR with a certain flair.

        It's by default 'Unclaimed'."""
        sub = ctx.r.subreddit('transcribersofreddit')

        links = []

        for submission in sub.new(limit=500):
            if submission.link_flair_text == flair:
                links.append(submission)

        word = 'post' if len(links) == 1 else 'posts'

        await ctx.send(
            f'{len(links)} {flair} {word}!'
        )

        if len(links) == 0:
            return

        p = Pages(ctx, entries=tuple(
            f'[{s.title.split(" | ")[2][1:-1]}]'
            f'(https://reddit.com{s.permalink})'
            for s in links
        ))

        await p.paginate()

    @commands.group(invoke_without_command=True)
    async def gammas(self, ctx, *, user: RedditAccountConverter = None):
        """Get the number of gammas from a user"""
        user = user or await RedditMember.create(ctx, ctx.author)

        r_user = ctx.r.redditor(user.reddit)

        for comment in r_user.comments.new(limit=None):
            if comment.subreddit == 'TranscribersOfReddit':
                # re formatting: I'm sorry
                await ctx.send(embed=discord.Embed(
                    description=
                    f'[/u/{user.reddit}](https://reddit.com/u/{user.reddit}) '
                    f'has {comment.author_flair_text.split(" ")[0]} '
                    f'transcriptions! '
                ))
                return


def setup(bot):
    bot.add_cog(Reddit(bot))

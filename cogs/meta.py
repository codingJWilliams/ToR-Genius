# Original work Copyright (c) 2015 Rapptz (https://github.com/Rapptz/RoboDanny)
# Modified work Copyright (c) 2017 Perry Fraser
#
# Licensed under the MIT License. https://opensource.org/licenses/MIT

# Help command from R. Danny, along with feedback, pm, and prefixes
import inspect
import os
import re
import time

import discord
from discord.ext import commands

from cogs.utils.checks import is_mod
from .utils.paginator import HelpPaginator, Pages, CannotPaginate


class Prefix(commands.Converter):
    async def convert(self, ctx, argument):
        user_id = ctx.bot.user.id
        if argument.startswith((f'<@{user_id}>', f'<@!{user_id}>')):
            raise commands.BadArgument(
                'That is a reserved prefix already in use.'
            )
        return argument


class Meta:
    """Meta stuff relating to the bot itself"""

    def __init__(self, bot):
        self.bot = bot

        value = getattr(bot, 'help_fallback', None)
        self.bot.help_fallback = bot.get_command('help') if not value else value
        bot.remove_command('help')

    @staticmethod
    async def __error(ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(error)

    @commands.command(name='help', aliases=['halp'])
    async def _help(self, ctx, *, command: str = None):
        """Helps you out a bit ;)"""
        # noinspection PyBroadException
        try:
            if ctx.me.permissions_in(ctx.channel).add_reactions:
                if command is None:
                    p = await HelpPaginator.from_bot(ctx)
                else:
                    entity = self.bot.get_cog(command) \
                             or self.bot.get_command(command)

                    if entity is None:
                        clean = command.replace('@', '@ ')  # non breaking space
                        return await ctx.send(
                            f'Command or category "{clean}" not found'
                        )
                    elif isinstance(entity, commands.Command):
                        p = await HelpPaginator.from_command(ctx, entity)
                    else:
                        p = await HelpPaginator.from_cog(ctx, entity)

                await p.paginate()
            else:
                # await ctx.invoke(self.bot.help_fallback,
                #                  command)
                if command:
                    await self.bot.help_fallback.callback(
                        ctx, *command.split(' ')
                    )
                else:
                    await self.bot.help_fallback.callback(ctx)

                await ctx.auto_react()

        except CannotPaginate as e:
            ctx.send(e)

    @commands.group(name='prefix', invoke_without_command=True)
    async def prefix(self, ctx, *, search: str.lower = ''):
        """Customize the prefixes

        Calling without a subcommand lists prefixes
        """

        if ctx.prefix == '\N{ZERO WIDTH SPACE}' * 2:
            return await ctx.send('#ZwspPrefixMasterrace')

        prefixes = self.bot.get_guild_prefixes(ctx.guild)

        # Don't list the mention prefix twice
        del prefixes[1]

        p = Pages(
            ctx,
            entries=[f'`{p[0]}`' + (' (regex)' if p[1] else '')
                     for p in prefixes if search in p[0].lower()]
        )
        await p.paginate()

    # Ignore extra for when people forget to quote
    #
    # We won't catch the rest of args because it's ambiguous if they wanted to
    # add multiple prefixes or they wanted to add one multi-word prefix.
    @is_mod()
    @prefix.command(name='add', ignore_extra=False)
    async def prefix_add(self, ctx, prefix: Prefix, regex: bool = False):
        """Appends a prefix to the list of custom prefixes.


        Previously set prefixes are not overridden.


        To have a word prefix, you should quote it and end it with
        a space, e.g. "hello " to set the prefix to "hello ". This
        is because Discord removes spaces when sending messages so
        the spaces are not preserved.


        Multi-word prefixes must be quoted also.


        You must have Manage Server permission to use this command.
        """

        # yeah I'm copying docstrings now woot woot
        # https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/meta.py#L96

        # Error checking in Prefix class (top o' file)

        if regex:
            try:
                # noinspection PyTypeChecker
                reg = re.compile(prefix)

                if reg.groups < 1:
                    return await ctx.send('The regex needs at least '
                                          'one capture group.')
            except re.error:
                return await ctx.send('That regex is invalid. Sorry.')

        prefixes = self.bot.get_other_prefixes(ctx.guild)
        prefixes.append([prefix, regex])

        try:
            await self.bot.set_guild_prefixes(ctx.guild, prefixes)
        except RuntimeError as e:
            await ctx.auto_react('🚫')
            await ctx.send(e)
        else:
            await ctx.auto_react()

        if regex:
            await ctx.send('You just added a regex prefix. These can break. '
                           'In the case it does break, you can ping the bot '
                           'followed by "prefix reset" (or clear) and the '
                           'prefixes will be reset.')

    async def on_message(self, message):

        # dumb pycharm
        # noinspection PyUnusedLocal
        user_id = self.bot.user.id
        reg = re.match(f'<@!?{user_id}> prefix (reset|clear)', message.content)
        if reg:
            if not message.author.permissions_in(message.channel).ban_members:
                raise commands.CheckFailure()
            if reg.groups()[0] == 'reset':
                await self.bot.set_guild_prefixes(message.guild, [['-', False]])
            else:
                await self.bot.set_guild_prefixes(message.guild, [])

            await message.channel.send('Hard reset prefixes.')

    @prefix_add.error
    async def prefix_add_error(self, ctx, error):
        if isinstance(error, commands.TooManyArguments):
            await ctx.auto_react('🚫')
            await ctx.send(
                'You can only add one prefix at a time. If you are trying to '
                'use a multi-word prefix make sure you used "quotes" around it.'
                ' Keep in mind \'single quotes\' won\'t work.'
            )

    @is_mod()
    @prefix.command(
        name='remove', aliases=['delete', 'del', 'rm'], ignore_extra=False
    )
    async def prefix_remove(self, ctx, prefix: Prefix):
        """Removes a prefix from the list of custom prefixes

        You can use this to remove any custom or default prefix, it is the
        opposite of prefix add.
        """

        prefixes = self.bot.get_other_prefixes(ctx.guild)
        prefixes_only = [p[0] for p in self.bot.get_other_prefixes(ctx.guild)]

        try:
            del prefixes[prefixes_only.index(prefix)]
        except ValueError:
            await ctx.auto_react('🚫')
            await ctx.send("That's not one of my prefixes, sorry!")
            return

        try:
            await self.bot.set_guild_prefixes(ctx.guild, prefixes)
        except RuntimeError as e:
            await ctx.auto_react('🚫')
            await ctx.send(e)
        else:
            await ctx.auto_react()

    @is_mod()
    @prefix.command(name='clear')
    async def prefix_clear(self, ctx):
        """Clears all prefixes, custom and default except for direct mentions"""

        await self.bot.set_guild_prefixes(ctx.guild, [])
        await ctx.auto_react()

    @is_mod()
    @prefix.command(name='reset')
    async def prefix_reset(self, ctx):
        """Resets to the default prefix, `-`."""

        await self.bot.set_guild_prefixes(ctx.guild, [['-', False]])
        await ctx.auto_react()

    @commands.command(aliases=['pong'])
    async def ping(self, ctx):
        """What do you think"""

        before = time.monotonic()

        message = f'{"Pong" if ctx.invoked_with == "ping" else "Ping"}! ' \
                  f'{round(self.bot.latency*1000, 2):,}ms of Discord ' \
                  f'WebSocket latency! 🏓'

        m = await ctx.send(message)

        after = time.monotonic()

        await m.edit(content=f'{m.content.strip("! 🏓")}, '
                             f'{round((after-before)*1000, 2)}ms of message '
                             f'latency! 🏓')

    @commands.command(aliases=['fb'])
    @commands.cooldown(rate=1, per=2 * 60, type=commands.BucketType.user)
    async def feedback(self, ctx, *, body: str):
        """PM the owner with feedback, questions and more.

        Feel free to use this to contact me (the owner) about anything and stuff.

        You can use this once every two minutes.
        """

        embed = discord.Embed(
            color=0x2db5e2,
            description=body,
            timestamp=ctx.message.created_at
        )

        me = await self.bot.application_info()
        me = me.owner

        embed.set_author(
            name=ctx.author.name,
            icon_url=ctx.author.avatar_url_as(format='png')
        )

        if ctx.guild is None:
            embed.set_footer(text='DM')
        else:
            embed.add_field(
                name='Server',
                value=f'{ctx.guild.name} (ID: `{ctx.guild.id}`)',
                inline=False
            )

        if ctx.channel is not None:
            embed.add_field(
                name='Channel',
                value=f'{ctx.channel} (ID: `{ctx.channel.id}`)',
                inline=False
            )

        if not isinstance(embed.footer.text, str):
            embed.set_footer(
                text=f'Author ID: {ctx.author.id}'
            )
        else:
            embed.set_footer(
                text=f'{embed.footer.text} | Author ID: {ctx.author.id}'
            )

        await me.send(embed=embed)
        await ctx.auto_react(emoji='✅')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def pm(self, ctx, user_id: int, *, content: str):
        user = self.bot.get_user(user_id)

        content = content + '\n\nThis DM is in response to your recent ' \
                            'feedback. If you want to reply, make sure you ' \
                            'use the `feedback` command again. (One use ' \
                            'every two minutes) '

        # noinspection PyBroadException
        try:
            await user.send(content)
        except:
            await ctx.send(f'Could not PM User (ID: {user_id})')
        else:
            await ctx.auto_react()

    # From
    # https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/meta.py#L163-L191
    # So many levels of meta right here (some modifications)
    @commands.command()
    async def source(self, ctx, *, command: str = None):
        """
        Displays the full source code or the source code for a specific command.
        To display the source code of a subcommand you can separate it by
        periods or spaces, e.g. `prefix.add` or `prefix add` for the create
        subcommand of the tag command.
        """
        source_url = 'https://github.com/perryprog/tor-genius'
        if command is None:
            return await ctx.send(
                embed=discord.Embed(
                    description=f'[perryprog/tor-genius]({source_url})'
                )
            )

        obj = self.bot.get_command(command.replace('.', ' '))
        if obj is None:
            return await ctx.send("I couldn't find that command. Sorry!")

        # since we found the command we're looking for, presumably anyway, let's
        # try to access the code itself
        src = obj.callback.__code__
        lines, first_line_no = inspect.getsourcelines(src)
        if not obj.callback.__module__.startswith('discord'):
            # not a built-in command
            location = os.path.relpath(src.co_filename).replace('\\', '/')
        else:
            location = obj.callback.__module__.replace('.', '/') + '.py'
            source_url = 'https://github.com/Rapptz/discord.py'

        final_url = f'<{source_url}/blob/master/{location}' \
                    f'#L{first_line_no}-L{first_line_no + len(lines) - 1}>'
        await ctx.send(
            embed=discord.Embed(
                description=f'[{location}]({final_url})'
            )
        )

    @commands.command(aliases=['info'])
    @commands.guild_only()
    async def about(self, ctx):
        """Details about this bot"""

        e = discord.Embed(
            description="I'm a bot made by perryprog#9657. I'm specifically "
                        "designed for the [TranscribersOfReddit guild](https:/"
                        "/www.reddit.com/r/TranscribersOfReddit/wiki/index). "
                        "I do, however, have some helpful utilities for things "
                        "outside of ToR.",
            color=ctx.author.color,
            title='ToR Genius'
        )

        e.add_field(name='Server', value='[Join the server!]'
                                         '(https://discord.gg/fhefJb2)')

        e.add_field(
            name='Transcribers Of Reddit',
            value='Transcribers of Reddit is a group of Redditors that are '
                  'making the internet more accessible, one image at a time. '
                  'Read more about them [here]('
                  'https://www.reddit.com/r/TranscribersOfReddit/wiki/index). '
                  'Join the Discord Guild [here.](https://discord.gg/b5DqZXq)'
        )

        e.add_field(
            name='Invite',
            value='[Click here](https://discordapp.com/api/oauth2/authorize?cli'
                  'ent_id=401477146511409183&permissions=8192&scope=bot)'
        )

        # blah blah hard coding is bad blah
        e.set_author(
            name=f'perryprog#9657',
            icon_url='https://images.discordapp.net/avatars/280001404020588544'
                     '/d958e37f81f45a2d18289c64112cfe22.png?size=1024'
        )
        await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(Meta(bot))

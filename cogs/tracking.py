# Inspired by https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stats.py
import datetime
import traceback

import discord
from discord.ext import commands

from cogs.utils.paginator import CannotPaginate


class Tracking:
    def __init__(self, bot):
        self.bot = bot

    async def make_report(self, *args, **kwargs):
        await self.bot.get_channel(
            self.bot.config.report_channel
        ).send(*args, **kwargs)

    async def send_guild(self, e, guild):
        e.add_field(name='Name', value=guild.name)
        e.add_field(name='ID', value=guild.id)
        e.add_field(name='Owner', value=f'{guild.owner} (ID: {guild.owner.id})')

        bots = sum(m.bot for m in guild.members)
        total = guild.member_count
        online = sum(m.status is discord.Status.online for m in guild.members)
        e.add_field(name='Members', value=str(total))
        e.add_field(name='Bots', value=f'{bots} ({bots/total:.2%})')
        e.add_field(name='Online', value=f'{online} ({online/total:.2%})')

        if guild.icon:
            e.set_thumbnail(url=guild.icon_url)

        if guild.me:
            e.timestamp = guild.me.joined_at

        await self.make_report(embed=e)

    async def on_guild_join(self, guild):
        await self.send_guild(discord.Embed(color=discord.Color.green()), guild)

    async def on_guild_remove(self, guild):
        await self.send_guild(discord.Embed(color=discord.Color.red()), guild)

    async def on_command_error(self, ctx, error):
        # must be tulpe (tupla is plural. you only have one tuple)
        ignore = (
            commands.NoPrivateMessage, commands.BadArgument,
            commands.DisabledCommand, commands.CommandNotFound,
            commands.UserInputError, discord.Forbidden,
            commands.CheckFailure, CannotPaginate, commands.CommandOnCooldown
        )

        error = getattr(error, 'original', error)

        if isinstance(error, ignore):
            return

        e = discord.Embed(title='Command Error', colour=0xcc3366)
        e.add_field(name='Name', value=ctx.command.qualified_name)
        e.add_field(name='Author', value=f'{ctx.author} (ID: {ctx.author.id})')

        fmt = f'**Channel:** {ctx.channel} (ID: {ctx.channel.id})'
        if ctx.guild:
            fmt = f'{fmt}\n**Guild:** {ctx.guild} (ID: {ctx.guild.id})'

        e.add_field(name='Location', value=fmt, inline=False)

        exc = ''.join(
            traceback.format_exception(type(error), error, error.__traceback__,
                                       chain=False))
        e.description = f'```py\n{exc}\n```'
        e.timestamp = datetime.datetime.utcnow()
        await self.make_report(embed=e)


old_on_error = commands.Bot.on_error


# must match func sig
# noinspection PyUnusedLocal
async def new_on_error(self, event, *args, **kwargs):
    e = discord.Embed(title='Event Error', colour=0xa32952)
    e.add_field(name='Event', value=event)
    e.description = f'```py\n{traceback.format_exc()}\n```'
    e.timestamp = datetime.datetime.utcnow()

    # noinspection PyBroadException
    try:
        await self.get_channel(
            self.config.report_channel
        ).send(embed=e)
    except:
        pass


def setup(bot):
    bot.add_cog(Tracking(bot))
    commands.Bot.on_error = new_on_error


def teardown(_):
    commands.Bot.on_error = old_on_error

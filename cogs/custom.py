from discord.ext import commands

from cogs.utils.config import Config
from cogs.utils.paginator import Pages


class CommandName(commands.Converter):

    async def convert(self, ctx, argument):
        first_word, _, _ = argument.partition(' ')

        # hacky but whatever. This is because things.
        command = ctx.bot.get_command('custom')
        if first_word in command.all_commands:
            raise commands.BadArgument("That's already a sub command")

        return argument


class CustomCommands:
    def __init__(self, bot):
        self.bot = bot
        self.config = Config('custom_commands.json')

    @staticmethod
    async def __error(ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)

    async def on_ready(self):
        self.reload_globals()

    @commands.group(aliases=['c', 'tag', 't'], invoke_without_command=True)
    async def custom(self, ctx, *, name: CommandName):
        """Basic tagging like thing just for me."""
        if name not in self.config:
            await ctx.send("That custom command doesn't exist")
        else:
            await ctx.send(self.config[name]['text'])

    @custom.command(aliases=['a'])
    @commands.is_owner()
    async def add(self, ctx, name: CommandName, *, content):
        """Add a custom command"""
        if name in self.config:
            return await ctx.send(
                f'There already is a custom command called {name}.'
            )
        await self.config.put(name, {'text': content, 'global': False})
        await ctx.auto_react()

    @custom.command(aliases=['rm', 'del'])
    @commands.is_owner()
    async def delete(self, ctx, name: CommandName):
        """Removes a custom command"""
        if name not in self.config:
            return await ctx.send(f"That custom command doesn't exist")

        if self.config[name]['global']:
            self.bot.remove_command(name)

        await self.config.delete(name)
        await ctx.auto_react()

    @custom.command(aliases=['e'])
    @commands.is_owner()
    async def edit(self, ctx, name: CommandName, *, content):
        """Removes a custom command"""
        if name not in self.config:
            return await ctx.send(f"That custom command doesn't exist")

        is_global = self.config[name]['global']

        await self.config.put(name, {
            'text': content,
            'global': is_global
        })

        self.bot.remove_command(name)
        self.bot.add_command(self.gen_command(name, content))

        await ctx.auto_react()

    @custom.command(aliases=['ls', 'all', 'l'])
    async def list(self, ctx, query=''):
        p = Pages(
            ctx,
            entries=[
                f'{name}: global' if e['global'] else name
                for name, e in self.config
                if query in e['text'] or query in name
            ]
        )

        if not p.entries:
            return await ctx.send('No results found.')
        await p.paginate()

    @custom.command(aliases=['g', 'gt'])
    async def global_toggle(self, ctx, *, name):
        """Toggle if the command is a global (-command_name) vs sub command
        command (-c command_name)"""

        if name not in self.config:
            return await ctx.send(f"That custom command doesn't exist")

        if self.bot.get_command(name):
            possible = self.config.get(name, None)
            if not None and not possible['global']:
                return await ctx.send('That command already exists, so you '
                                      'can\'t make this custom one global.')

        state = self.config[name]['global']
        text = self.config[name]['text']

        await self.config.put(
            name,
            {
                'text': text,
                'global': not state
            }
        )

        if state:
            self.bot.remove_command(name)
        else:
            self.bot.add_command(self.gen_command(name, text))

        await ctx.auto_react()

    @custom.command(aliases=['r', 'reload'])
    async def global_reload(self, ctx):
        """Reload the global commands"""

        self.reload_globals()
        await ctx.auto_react()

    def reload_globals(self):
        for key, value in [(k, v) for k, v in self.config if v['global']]:
            self.bot.remove_command(key)
            self.bot.add_command(self.gen_command(key, value['text']))

    @staticmethod
    def gen_command(name, text):
        async def func(ctx):
            await ctx.send(text)

        return commands.Command(
            name,
            func,
            help='This is a custom, static, command.',
            hidden=True
        )


def setup(bot):
    bot.add_cog(CustomCommands(bot))

import datetime
import traceback
import sys

import disnake

from disnake.ext import commands

from ChannelMonitors import ChannelMonitors

from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

with open("config.yaml", "r") as o:
    config = load(o.read(), Loader=Loader)


bot = commands.Bot(
    intents=disnake.Intents(members=True, guilds=True, guild_messages=True)
)

bot.timestamp = None

bot.monitors = ChannelMonitors(config["DATABASE_FILEPATH"], bot.get_channel)


@bot.event
async def on_ready():
    print(f"Running on {bot.user.name}#{bot.user.discriminator} ({bot.user.id})")
    if not bot.timestamp:
        await bot.monitors.initialize()

        bot.timestamp = (
            datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).timestamp()
        )


@bot.event
async def on_message(message):
    # Wait for bot initialization to complete before accepting inputs
    if not bot.timestamp:
        return

    # Ignore DMs
    if not isinstance(message.channel, disnake.abc.GuildChannel):
        return

    # Ignore bot accounts
    if message.author.bot:
        return

    # Ignore if we cannot affect slowmode
    if not message.channel.permissions_for(message.guild.me).manage_channels:
        return
    # Ignore if user is bypassing slowmode
    if message.channel.permissions_for(message.author).manage_messages:
        return

    await bot.monitors.process_message(message.channel, message.created_at)


def has_manage_guild(ctx):
    return (
        bot.timestamp
        and ctx.guild
        and (
            ctx.guild.owner.id == ctx.user.id
            or ctx.guild.get_member(ctx.user.id).guild_permissions.manage_guild
        )
    )


def generate_permission_warning(channel_id):
    return f"**WARNING:** I do not have permissions to modify <#{channel_id}>.\nPlease grant `MANAGE_CHANNELS` for monitoring to work there."


def generate_channel_settings_display(config, show_monitoring):
    ret = """**Min/Max**: {}/{}
**Cache Size**: {}
**Sensitivity**: {:.3f}
""".format(
        config.slowmode_min,
        config.slowmode_max,
        config.cache_size,
        config.sensitivity,
    )

    if show_monitoring:
        ret = (
            "**Currently Monitoring**: {}\n".format(
                "Yes" if config.monitoring else "No"
            )
            + ret
        )

    return ret


@bot.slash_command()
async def monitor(inter):
    pass


@monitor.sub_command(name="add", description="Start monitoring a channel's activity")
@commands.check(has_manage_guild)
async def monitor_add_channel(
    ctx,
    channel: disnake.TextChannel = commands.Param(
        description="Select a channel to start monitoring"
    ),
):
    try:
        channel_config = await bot.monitors.start_monitoring(channel)
    except ValueError as e:
        await ctx.response.send_message(f"Error: {e}")
        return

    resp = "An unknown error occured"

    if channel_config:
        resp = f"Now monitoring <#{channel.id}>."
        if (
            not channel.guild.get_channel(channel.id)
            .permissions_for(channel.guild.me)
            .manage_channels
        ):
            resp += f"\n\n{generate_permission_warning(channel.id)}"
        resp += f"\n\n{generate_channel_settings_display(channel_config, False)}"

    await ctx.response.send_message(resp)


@monitor.sub_command(name="remove", description="Stop monitoring a channel's activity")
@commands.check(has_manage_guild)
async def monitor_remove_channel(
    ctx,
    channel: disnake.TextChannel = commands.Param(
        description="Select a channel to stop monitoring"
    ),
):
    try:
        success = await bot.monitors.stop_monitoring(channel)
    except ValueError as e:
        await ctx.response.send_message(f"Error: {e}")
        return

    resp = "An unknown error occured"

    if success:
        resp = f"No longer monitoring <#{channel.id}>."

    await ctx.response.send_message(resp)


@monitor.sub_command(name="view", description="View currently monitored channels")
@commands.check(has_manage_guild)
async def monitor_view(ctx):
    channel_ids = await bot.monitors.get_guild_monitors(ctx.guild.id)
    resp = "__**Currently Monitoring**__\n"

    channels = [
        ctx.guild.get_channel(c) for c in channel_ids if ctx.guild.get_channel(c)
    ]

    for c in channels:
        # Add protections for guild leave/join/disconnect desync shenanigans
        try:
            await bot.monitors.start_monitoring(c)
        except ValueError:
            pass

    if not channels:
        resp += "*No channels are currently being monitored*"
    else:
        resp += " ".join(
            [f"<#{c.id}>" for c in sorted(channels, key=lambda x: x.position)]
        )
    await ctx.response.send_message(resp)


@bot.slash_command(name="settings", description="View the settings for a channel")
@commands.check(has_manage_guild)
async def get_channel_settings(
    ctx,
    channel: disnake.TextChannel = commands.Param(
        description="Select a channel to check the settings for"
    ),
):
    channel_config = await bot.monitors.get_channel_config(channel.id)

    if not channel_config:
        await ctx.response.send_message(
            "This channel has no associated settings. Start monitoring the channel to create one!"
        )
        return

    warning = ""

    if (
        not channel.guild.get_channel(channel.id)
        .permissions_for(channel.guild.me)
        .manage_channels
    ):
        warning = f"\n{generate_permission_warning(channel.id)}\n"

    resp = f"__**Settings for <#{channel.id}>:**__\n{warning}\n{generate_channel_settings_display(channel_config, True)}"

    await ctx.response.send_message(resp)


@bot.slash_command(name="set")
async def settings(inter):
    pass


# settings = bot.command_group(
#     name="set",
#     description="Adjust settings for channels",
# )


@settings.sub_command(
    name="bounds", description="Set the minimum and maximum bounds for a channel"
)
@commands.check(has_manage_guild)
async def set_channel_bounds(
    ctx,
    channel: disnake.TextChannel = commands.Param(
        description="Select a channel to configure"
    ),
    minimum: int = commands.Param(
        name="min", description="The minimum number of seconds"
    ),
    maximum: int = commands.Param(
        name="max", description="The maxinum number of seconds"
    ),
):
    # Why do I only validate inputside this can only go well
    if maximum < minimum:
        await ctx.response.send_message("Error: Maximum must be greater than minimum.")
        return
    if maximum > 21600:
        await ctx.response.send_message(
            "Error: Maximum cannot exceed 21600 seconds (6 hours)."
        )
        return

    success = await bot.monitors.update_channel(
        channel, slowmode_min=minimum, slowmode_max=maximum
    )

    resp = "An unknown error occured"

    if success:
        resp = f"The bounds for <#{channel.id}> have been set to **{minimum}**/**{maximum}**."

    await ctx.response.send_message(resp)


@settings.sub_command(name="cachesize", description="Set the cache size for a channel")
@commands.check(has_manage_guild)
async def set_channel_cache_size(
    ctx,
    channel: disnake.TextChannel = commands.Param(
        description="Select a channel to configure"
    ),
    size: int = commands.Param(
        description="The number messages to be cached for this channel"
    ),
):
    if size < 5 or size > 50:
        await ctx.response.send_message("Error: Cache size must be between 5 and 50.")
        return

    success = await bot.monitors.update_channel(channel, cache_size=size)

    resp = "An unknown error occured"

    if success:
        resp = f"The cache size for <#{channel.id}> have been set to **{size}**."

    await ctx.response.send_message(resp)


@settings.sub_command(
    name="sensitivity", description="Set the sensitivity for a channel"
)
@commands.check(has_manage_guild)
async def set_channel_sensitivity(
    ctx,
    channel: disnake.TextChannel = commands.Param(
        description="Select a channel to configure"
    ),
    sensitivity: float = commands.Param(
        description="The sensitivity for this channel (higher is more sensitive)",
    ),
):

    success = await bot.monitors.update_channel(channel, sensitivity=sensitivity)

    resp = "An unknown error occured"

    if success:
        resp = (
            f"The sensitivity for <#{channel.id}> have been set to **{sensitivity}**."
        )

    await ctx.response.send_message(resp)


@bot.slash_command(name="about", description="Get info about this bot")
@commands.check(has_manage_guild)
async def about_message(
    ctx,
):

    await ctx.response.send_message(
        """This bot's purpose is to dynamically adjust slowmode based on chat activity.
Please ensure it has the ability to manage channels and view messages for each channel assigned to it.

Run `/commands` for a list of commands and what they do.

Author: **Roadcrosser**#**3657**"""
    )


@bot.slash_command(name="commands", description="Get a list of commands")
@commands.check(has_manage_guild)
async def commands_message(
    ctx,
):

    await ctx.response.send_message(
        """__**Commands:**__

`/monitor add` - Start monitoring a channel
`/monitor remove` - Stop monitoring a channel
`/monitor view` - View all currently-monitored channels

`/settings` - View settings for a specific channel

`/set bounds` - Set the minimum/maximum slowmode for a channel
`/set cache` - Set the message cache size for a channel
`/set sensitivity` - Set the sensitivity for a channel"""
    )


@about_message.error
@commands_message.error
@monitor_add_channel.error
@monitor_remove_channel.error
@monitor_view.error
@get_channel_settings.error
@set_channel_bounds.error
@set_channel_cache_size.error
@set_channel_sensitivity.error
async def process_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.response.send_message(
            f"Error: You require `MANAGE_GUILD` to use this bot."
        )
        return

    print(
        "".join(traceback.TracebackException.from_exception(error).format()),
        file=sys.stderr,
    )
    await ctx.response.send_message("An error occured. Please alert the maintainer.")


bot.run(config["TOKEN"])

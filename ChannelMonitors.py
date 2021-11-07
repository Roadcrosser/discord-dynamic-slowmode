from MessageQueue import MessageQueue, ChannelConfigObject
from DBInterface import DBInterface


class ChannelMonitors:
    def __init__(self, db_fp, get_discord_channel):
        self.db = DBInterface(db_fp)
        self.get_discord_channel = get_discord_channel
        self.channels = {}

    async def initialize(self):
        channel_data = await self.db.initialize_database()

        channels_initialized = 0
        for c in channel_data:
            if not self.get_discord_channel(c.channel_id):
                continue

            self.add_channel(
                c.channel_id,
                c.slowmode_min,
                c.slowmode_max,
                c.cache_size,
                c.sensitivity,
            )
            channels_initialized += 1

        print(f"Successfully initialized {channels_initialized} channels.")

    async def get_channel_config(self, channel_id):
        ret = await self.db.get_channel_monitor(channel_id)
        if ret:
            ret = ChannelConfigObject.from_db(ret)

        return ret

    async def start_monitoring(self, channel):
        if channel.id in self.channels:
            raise ValueError("Already monitoring this channel.")

        new_channel_config = await self.get_channel_config(channel.id)

        if not new_channel_config:
            new_channel_config = ChannelConfigObject.default(channel)
            await self.db.insert_channel_monitor(new_channel_config.to_db())
        else:
            await self.db.update_channel_monitoring(channel.id, True)

        self.add_channel(*new_channel_config.as_monitor())

        return new_channel_config

    async def stop_monitoring(self, channel):
        if not channel.id in self.channels:
            raise ValueError("Not currently monitoring this channel.")

        self.remove_channel(channel.id)
        await self.db.update_channel_monitoring(channel.id, False)

        return True

    def add_channel(
        self, channel_id, slowmode_min, slowmode_max, cache_size, sensitivity
    ):
        if not channel_id in self.channels:
            self.channels[channel_id] = MessageQueue(
                slowmode_min, slowmode_max, cache_size, sensitivity
            )

    async def update_channel(
        self,
        channel,
        slowmode_min=None,
        slowmode_max=None,
        cache_size=None,
        sensitivity=None,
    ):
        q = self.channels.get(channel.id)
        monitoring = True

        if not q:
            q = MessageQueue.from_config(ChannelConfigObject.default(channel, False))
            monitoring = False

        if slowmode_min != None and slowmode_max != None:
            q.set_bounds(slowmode_min, slowmode_max)
        if cache_size != None:
            q.set_cache_size(cache_size)
        if sensitivity != None:
            q.set_sensitivity(sensitivity)

        await self.db.update_channel_config(q.to_config(channel, monitoring))
        return True

    def remove_channel(self, channel_id):
        self.channels.pop(channel_id, None)

    async def get_guild_monitors(self, guild_id):
        rows = await self.db.get_guild_monitors(guild_id)
        return rows

    async def process_message(self, channel, timestamp):
        q = self.channels.get(channel.id)

        if not q:
            return

        q.add_message(timestamp)

        old_slowmode = channel.slowmode_delay
        new_slowmode = q.calculate_optimal_slowmode()

        if new_slowmode != None and old_slowmode != new_slowmode:
            await channel.edit(slowmode_delay=new_slowmode)

            print(
                f"Updated {channel.guild.name}#{channel.name} slowmode: {old_slowmode} to {new_slowmode}"
            )

class ChannelConfigObject:
    def __init__(
        self,
        channel_id,
        guild_id,
        slowmode_min,
        slowmode_max,
        cache_size,
        sensitivity,
        monitoring,
    ):
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.slowmode_min = slowmode_min
        self.slowmode_max = slowmode_max
        self.cache_size = cache_size
        self.sensitivity = sensitivity
        self.monitoring = monitoring

    @classmethod
    def from_db(cls, row):
        return cls(row[0], row[1], row[2], row[3], row[4], row[5], bool(row[6]))

    @classmethod
    def default(cls, channel, monitoring=True):
        return cls(channel.id, channel.guild.id, 0, 30, 15, 1.0, monitoring)

    def to_db(self):
        return (
            self.channel_id,
            self.guild_id,
            self.slowmode_min,
            self.slowmode_max,
            self.cache_size,
            self.sensitivity,
            int(self.monitoring),
        )

    def as_monitor(self):
        return (
            self.channel_id,
            self.slowmode_min,
            self.slowmode_max,
            self.cache_size,
            self.sensitivity,
        )

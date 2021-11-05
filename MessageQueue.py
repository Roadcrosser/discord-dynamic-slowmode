from ChannelConfigObject import ChannelConfigObject


class MessageQueue:
    def __init__(self, slowmode_min, slowmode_max, cache_size, sensitivity):
        self.slowmode_min = slowmode_min
        self.slowmode_max = slowmode_max
        self.cache_size = cache_size
        self.sensitivity = sensitivity

        self.message_timestamp_queue = []

    @classmethod
    def from_config(cls, config):
        return cls(
            config.slowmode_min,
            config.slowmode_max,
            config.cache_size,
            config.sensitivity,
        )

    def to_config(self, channel, monitoring):
        return ChannelConfigObject(
            channel.id,
            channel.guild.id,
            self.slowmode_min,
            self.slowmode_max,
            self.cache_size,
            self.sensitivity,
            monitoring,
        )

    def set_bounds(self, slowmode_min, slowmode_max):
        self.slowmode_min = slowmode_min
        self.slowmode_max = slowmode_max

    def set_cache_size(self, cache_size):
        self.cache_size = cache_size

    def set_sensitivity(self, sensitivity):
        self.sensitivity = sensitivity

    def add_message(self, timestamp):
        # Add new message timestamp to the queue, pruning if over cache size
        # Exempt checks are done outside current scope before this is called
        self.message_timestamp_queue.append(timestamp)

        while len(self.message_timestamp_queue) > self.cache_size:
            self.message_timestamp_queue.pop(0)

    def calculate_optimal_slowmode(self):
        target_spm = self.sensitivity * 10

        delays = []

        optimal_slowmode = None

        if len(self.message_timestamp_queue) > 1:
            # Get list of delays between messages
            for i in range(len(self.message_timestamp_queue) - 1):
                delays.append(
                    (
                        self.message_timestamp_queue[i + 1]
                        - self.message_timestamp_queue[i]
                    ).total_seconds()
                )

            # Get average seconds per message
            average_spm = sum(delays) / len(delays)

            # Panic if we get a zero somehow
            if average_spm == 0:
                return None

            # Calculate optimal slowmode based on target seconds per message
            optimal_slowmode = target_spm / average_spm
            optimal_slowmode = int(round(optimal_slowmode))

            # Bind to min/max bounds
            if self.slowmode_max:
                optimal_slowmode = min(self.slowmode_max, optimal_slowmode)

            if not self.slowmode_min:
                self.slowmode_min = 0

            optimal_slowmode = max(self.slowmode_min, optimal_slowmode)

        return optimal_slowmode

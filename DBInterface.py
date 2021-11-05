import aiosqlite

from ChannelConfigObject import ChannelConfigObject


class DBInterface:
    def __init__(self, db_fp):
        self.conn = lambda: aiosqlite.connect(db_fp)

    async def initialize_database(self):
        # Create tables if first start and return all channels to monitor
        async with self.conn() as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_monitors(
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    min INTEGER DEFAULT 0,
                    max INTEGER DEFAULT 30,
                    cache_size INTEGER DEFAULT 15,
                    sensitivity DECIMAL DEFAULT 1.0,
                    monitoring INTEGER DEFAULT 1
                );
                """
            )
            await db.commit()

            async with db.execute(
                "SELECT * FROM channel_monitors WHERE monitoring = 1;"
            ) as cursor:
                rows = await cursor.fetchall()

        return [ChannelConfigObject(*row) for row in rows]

    async def get_guild_monitors(self, guild_id):
        async with self.conn() as db:
            cur = await db.execute(
                "SELECT channel_id FROM channel_monitors WHERE monitoring = 1 AND guild_id = ?;",
                (guild_id,),
            )
            row = await cur.fetchall()

        return [r[0] for r in row]

    async def get_channel_monitor(self, channel_id):
        async with self.conn() as db:
            cur = await db.execute(
                "SELECT * FROM channel_monitors WHERE channel_id = ?;",
                (channel_id,),
            )
            row = await cur.fetchone()

        return row

    async def insert_channel_monitor(self, row):
        async with self.conn() as db:
            await db.execute(
                """
                INSERT INTO channel_monitors(channel_id, guild_id, min, max, cache_size, sensitivity, monitoring) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                row,
            )
            await db.commit()

    async def update_channel_monitoring(self, channel_id, monitoring):
        async with self.conn() as db:
            await db.execute(
                """
                UPDATE
                    channel_monitors
                SET
                    monitoring = ?
                WHERE
                    channel_id = ?;
                """,
                (int(monitoring), channel_id),
            )
            await db.commit()

    async def update_channel_config(self, config):
        async with self.conn() as db:
            await db.execute(
                """
                UPDATE
                    channel_monitors
                SET
                    min = ?,
                    max = ?,
                    cache_size = ?,
                    sensitivity = ?
                WHERE
                    channel_id = ?;
                """,
                (
                    config.slowmode_min,
                    config.slowmode_max,
                    config.cache_size,
                    config.sensitivity,
                    config.channel_id,
                ),
            )
            await db.commit()

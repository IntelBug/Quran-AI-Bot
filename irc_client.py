import asyncio
import logging
import time
from config import BOT_OWNER, MESSAGES

class IRCClient:
    def __init__(self, server, port, nick, password, channels, alt_nick=None):
        self.server = server
        self.port = port
        self.nick = nick
        self.password = password
        self.channels = channels
        self.alt_nick = alt_nick or f"{nick}_"
        self.reader = None
        self.writer = None
        self.bot = None  # Reference to the bot instance
        self.connected = False
        self.authenticated = False
        self.flood_warning_detected = False
        self.last_ping_time = time.time()
        self._keep_alive_task = None
        self.current_delay = 1.5  # Initial delay in seconds
        self.max_delay = 5  # Maximum delay in seconds
        self.retry_count = 0
        self.max_reconnect_delay = 300

    async def connect(self):
        try:
            self.reader, self.writer = await asyncio.open_connection(self.server, self.port)
            await self.send_command("CAP LS")
            await self.send_command(f"PASS {self.password}")
            await self.send_command(f"NICK {self.nick}")
            await self.send_command(f"USER {self.nick} 0 * :{self.nick}")
            self.connected = True
            logging.info("Successfully connected to IRC server.")
            await asyncio.sleep(5)  # Delay to avoid flooding
        except Exception as e:
            logging.error(f"Failed to connect to IRC server: {e}")
            self.connected = False
            await self.shutdown()

    async def run(self):
        retry_count = 0
        while True:
            if not self.connected:
                await self.connect()
                delay = min(10 * (2 ** retry_count), self.max_reconnect_delay)
                await asyncio.sleep(delay)  # Wait before retrying
                retry_count += 1

            try:
                while self.connected:
                    data = await self.reader.readline()
                    message = data.decode().strip()
                    if message:  # Only log and process non-empty messages
                        logging.debug(f"Received: {message}")
                        await self.handle_message(message)
            except asyncio.CancelledError:
                logging.info("IRC connection cancelled.")
                break
            except (ConnectionResetError, ConnectionAbortedError) as e:
                logging.error(f"Error in IRC connection: {e}")
                self.connected = False
                await self.shutdown()
            except Exception as e:
                logging.error(f"Unexpected error in IRC connection: {e}")
                self.connected = False
                await self.shutdown()

    async def send_command(self, command):
        if self.writer:
            try:
                self.writer.write(f"{command}\r\n".encode())
                await self.writer.drain()
            except Exception as e:
                logging.error(f"Error sending command: {e}")
                await self.shutdown()

    async def send_message(self, target, message):
        if message:  # Only send non-empty messages
            await self.send_command(f"PRIVMSG {target} :{message}")
            await self.handle_delay()

    async def handle_delay(self):
        """Handle delay with exponential backoff and flood warning handling."""
        if self.flood_warning_detected:
            # Apply a one-time fixed delay of 15 seconds for flood warning
            await asyncio.sleep(15)
            self.flood_warning_detected = False  # Reset the flood warning flag
            self.current_delay = 1.5  # Reset delay to initial value after flood warning
        else:
            # Apply exponential backoff for regular messages
            await asyncio.sleep(self.current_delay)
            self.current_delay = min(self.current_delay * 1.05, self.max_delay)

    async def handle_message(self, message):
        logging.debug(f"Handling message: {message}")
        if message.startswith("PING"):
            ping_value = message.split()[1]
            await self.send_command(f"PONG {ping_value}")
            self.last_ping_time = time.time()
        else:
            parts = message.split()
            if len(parts) > 1:
                if parts[1] == "001":  # RPL_WELCOME
                    self.authenticated = True
                    logging.info(f"Successfully authenticated with nick: {self.nick}")
                    for channel in self.channels:
                        await self.join_channel(channel)
                elif parts[1] == "433":  # ERR_NICKNAMEINUSE
                    logging.error("Nickname is already in use. Attempting to ghost the nick.")
                    await self.send_command(f"NICK {self.alt_nick}")
                    await self.send_command(f"NickServ :RECOVER {self.nick} {self.password}")
                    await asyncio.sleep(2)  # Wait for recovery
                    await self.send_command(f"NickServ :RELEASE {self.nick} {self.password}")
                    await asyncio.sleep(2)  # Wait before changing nick
                    await self.send_command(f"NICK {self.nick}")
                elif parts[1] == "PRIVMSG":
                    prefix = parts[0].lstrip(':')
                    sender_nick = self.parse_nick_from_prefix(prefix)
                    logging.debug(f"Parsed sender_nick: {sender_nick}")
                    target = parts[2].lstrip(':')
                    msg_content = ' '.join(parts[3:]).lstrip(':')

                    logging.debug(f"Parsed PM/msg: {sender_nick} -> {target}: {msg_content}")
                    await self.bot.on_message(sender_nick.strip(), target.strip(), msg_content)
                elif parts[1] == "439":
                    await self.handle_excess_flood(target)

    async def handle_excess_flood(self, target):
        """Handle the Excess Flood warning by slowing down message sending."""
        logging.warning("[WARNING] Excess Flood detected! Slowing down...")
        self.flood_warning_detected = True
        await self.send_message(target, MESSAGES["flood_protection"])

    async def join_channel(self, channel):
        try:
            await self.send_command(f"JOIN {channel}")
            logging.info(f"Joining channel: {channel}")
            await self.send_message(BOT_OWNER, MESSAGES["join_success"].format(channel=channel))  # Send message to owner
        except Exception as e:
            logging.error(f"Error joining channel: {e}")
            await self.send_message(BOT_OWNER, MESSAGES["join_failure"].format(channel=channel, error=str(e)))

    async def part_channel(self, channel):
        try:
            await self.send_command(f"PART {channel}")
            await self.send_message(BOT_OWNER, MESSAGES["part_success"].format(channel=channel))  # Send message to owner
        except Exception as e:
            logging.error(f"Error leaving channel: {e}")
            await self.send_message(BOT_OWNER, MESSAGES["part_failure"].format(channel=channel, error=str(e)))

    async def quit(self):
        try:
            await self.send_command("QUIT")
        except Exception as e:
            logging.error(f"Error sending QUIT command: {e}")
        finally:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
            self.connected = False

    async def shutdown(self):
        if self._keep_alive_task:
            self._keep_alive_task.cancel()
            try:
                await self._keep_alive_task
            except asyncio.CancelledError:
                pass
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.connected = False
        logging.info("IRC client shutdown complete.")

    async def keep_alive(self):
        """Send periodic PING messages to keep the connection alive."""
        while self.connected:
            await asyncio.sleep(60)  # Send PING every 60 seconds
            await self.send_command("PING")

    @staticmethod
    def parse_nick_from_prefix(prefix):
        """Extracts nickname from IRC prefix (e.g., ':Nick!user@host')."""
        nick = prefix.split('!', 1)[0].lstrip(':')  # Remove leading ':'
        logging.debug(f"Parsed nick from prefix: {nick}")
        return nick

    def set_bot(self, bot):
        self.bot = bot

    async def start_keep_alive(self):
        """Start the keep-alive task."""
        self._keep_alive_task = asyncio.create_task(self.keep_alive())

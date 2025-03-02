# -*- coding: utf-8 -*-
import asyncio
import logging
import logging.config
import yaml
import os
import sys
import time

from irc_client import IRCClient
from ai_client import AIClient
from database import Database
from utils import setup_logging
from config import (
    IRC_SERVER, IRC_PORT, BOT_NICK, BOT_PASSWORD, BOT_CHANNELS, BOT_OWNER,
    AI_API_URL, AI_API_KEY, DB_PATH, MESSAGES, HELP_CONTENT, LANGUAGE_TABLE_MAPPING
)

# Load logging configuration
with open('logging_config.yaml', 'r') as f:
    logging_config = yaml.safe_load(f)
    setup_logging(logging_config)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

class QuranIRCBot:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(5)
        self.irc_client = IRCClient(IRC_SERVER, IRC_PORT, BOT_NICK, BOT_PASSWORD, BOT_CHANNELS)
        self.ai_client = AIClient(AI_API_URL, AI_API_KEY)
        self.database = Database(DB_PATH)
        self.commands = {
            '!Quran': self.handle_quran,
            '!stop': self.handle_stop,
            '!help': self.handle_help,
            '!quit': self.handle_quit,
            '!join': self.handle_join,
            '!part': self.handle_part,
            '!counts': self.handle_counts,
            '!msg': self.handle_msg
        }
        self.forward_bot_nick = 'Cheer'
        # Track one active query per user
        self.active_tasks = {}
        self.help_sent = {}
        self.private_query_success = set()
        self.irc_client.set_bot(self)

    async def start(self):
        logging.info("Starting the bot...")
        await self.irc_client.connect()
        await self.irc_client.run()

    async def handle_quran(self, nick, channel, query):
        logging.info(f"Handling !Quran command from {nick} in {channel} with query: {query}")
        # Enforce one active query per user.
        if nick in self.active_tasks:
            logging.warning(f"Existing query detected for {nick}. Sending query_exists message.")
            await self.irc_client.send_message(channel, MESSAGES["query_exists"])
            return

        # Create and store the active query task.
        task = asyncio.create_task(self.process_quran_query(nick, channel, query))
        self.active_tasks[nick] = {"task": task, "cancel_requested": False, "chunks_sent": 0}

        success = False
        try:
            await task
            success = True
            await asyncio.to_thread(self.database.update_user_stats, nick, 0, 1, 0, time.time())
            # Do NOT send completion message here; process_quran_query sends it.
        except asyncio.CancelledError:
            success = False
            logging.info(f"Query for {nick} was cancelled.")
            await self.irc_client.send_message(channel, MESSAGES["stop_success"])
            await asyncio.to_thread(self.database.update_user_stats, nick, 0, 0, 1, time.time())
            raise
        except Exception as e:
            success = False
            logging.error(f"Query failed for {nick}: {str(e)}")
            await self.irc_client.send_message(channel, MESSAGES["no_results_found"])
            await asyncio.to_thread(self.database.update_user_stats, nick, 0, 0, 1, time.time())
        finally:
            # Log the query into the query_history table.
            chunks_sent = self.active_tasks[nick]["chunks_sent"] if nick in self.active_tasks else 0
            await asyncio.to_thread(self.database.log_query, nick, channel, query, success, chunks_sent)
            logging.info(f"Cleaning up resources for {nick}.")
            self.active_tasks.pop(nick, None)

    async def process_quran_query(self, nick, channel, query):
        target = channel
        logging.info(f"Processing query for {nick} in {channel} with query: {query}")
        if not query:
            logging.warning("Empty query for !Quran command.")
            await self.irc_client.send_message(target, MESSAGES["wrong_command"])
            return
        if channel != BOT_NICK:
            await self.irc_client.send_message(target, MESSAGES["query_queued"])
        try:
            async with self.semaphore:
                response = await self.ai_client.query_quran(query)
            logging.info(f"Received AI response: {response}")
            if self._should_cancel(nick):
                logging.info(f"Query for {nick} was cancelled after AI response.")
                raise asyncio.CancelledError()
            if response:
                language = response.get('language', 'arabic')
                is_rtl = response.get('rtl', False)
                ayats_info = sorted(set(response.get('ayats', [])), key=lambda x: (x[0], x[1]))
                logging.info(f"Extracted language: {language}, RTL: {is_rtl}, Ayats: {ayats_info}")
                if ayats_info:
                    formatted_response = self.database.fetch_ayats(ayats_info, language, is_rtl)
                    logging.info(f"Formatted response from database: {formatted_response}")
                    if formatted_response:
                        grouped_ayats = self.group_ayats_by_surah(formatted_response)
                        for surah_name, ayats in grouped_ayats.items():
                            await self.irc_client.send_message(target, surah_name)
                            for ayat in ayats:
                                if self._should_cancel(nick):
                                    logging.info(f"Query for {nick} cancelled during chunking.")
                                    raise asyncio.CancelledError()
                                await self.send_chunked_message(target, ayat, nick)
                                self.active_tasks[nick]["chunks_sent"] += 1
                        await self.irc_client.send_message(target, MESSAGES["completion_message"])
                        if channel == nick and nick not in self.private_query_success:
                            logging.info(f"Sending channel invite to {nick} after successful query.")
                            await self.irc_client.send_message(target, MESSAGES["channel_invite"])
                            self.private_query_success.add(nick)
                    else:
                        logging.warning("Formatted response is empty.")
                        await self.irc_client.send_message(target, MESSAGES["no_results_found"])
                else:
                    logging.warning("No Ayats found in AI response.")
                    await self.irc_client.send_message(target, MESSAGES["no_results_found"])
            else:
                logging.warning("AI response is empty or invalid.")
                await self.irc_client.send_message(target, MESSAGES["no_results_found"])
        except asyncio.TimeoutError:
            logging.error("AI request timed out.")
            await self.irc_client.send_message(target, MESSAGES["api_timeout"])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logging.error(f"Error processing !Quran command: {e}")
            await self.irc_client.send_message(target, MESSAGES["wrong_command"])
        # Note: Active task cleanup is handled by handle_quran.

    def _should_cancel(self, nick):
        logging.debug(f"Checking if query should be cancelled for {nick}.")
        return self.active_tasks.get(nick, {}).get("cancel_requested", False)

    def group_ayats_by_surah(self, formatted_response):
        logging.debug("Grouping ayats by surah.")
        grouped_ayats = {}
        current_surah = None
        for line in formatted_response:
            if line.startswith("Surah"):
                current_surah = line
                grouped_ayats[current_surah] = []
            elif current_surah and line.startswith("Ayat"):
                grouped_ayats[current_surah].append(line)
            elif current_surah and line.startswith("Translation"):
                grouped_ayats[current_surah].append(line)
        return grouped_ayats

    async def handle_stop(self, nick, channel, query):
        logging.info(f"Handling stop command from {nick} in {channel}.")
        target = channel if channel != BOT_NICK else nick
        try:
            if nick in self.active_tasks:
                task_data = self.active_tasks[nick]
                task_data["cancel_requested"] = True
                if not task_data["task"].done():
                    task_data["task"].cancel()
                    await self.irc_client.send_message(target, MESSAGES["stop_success"])
                else:
                    await self.irc_client.send_message(target, MESSAGES["stop_failure"])
            else:
                await self.irc_client.send_message(target, MESSAGES["stop_failure"])
        except Exception as e:
            logging.error(f"Error stopping query for {nick}: {e}")
            await self.irc_client.send_message(target, MESSAGES["stop_failure"])

    async def handle_help(self, nick, channel, query):
        logging.info(f"Handling help command from {nick} in {channel}.")
        content_type = 'private' if nick == channel else 'channel'
        content_lines = HELP_CONTENT.get(content_type, [MESSAGES["wrong_command"]])
        for line in content_lines:
            await self.send_chunked_message(
                target=(nick if content_type == 'private' else channel),
                message=line,
                nick=nick
            )

    async def handle_quit(self, nick, channel, query):
        logging.info(f"Handling quit command from {nick} in {channel}.")
        if self.is_owner(nick) and channel == BOT_OWNER:
            await self.irc_client.send_message(channel, MESSAGES["shutting_down"])
            for task_data in list(self.active_tasks.values()):
                task_data["cancel_requested"] = True
                if not task_data["task"].done():
                    task_data["task"].cancel()
            await self.shutdown()

    async def handle_join(self, nick, channel, query):
        logging.debug(f"Configured owner: {BOT_OWNER}, Command sender: {nick}, Channel: {channel}")
        if self.is_owner(nick) and channel == BOT_OWNER and query:
            logging.info(f"Attempting to join channel: {query}")
            await self.irc_client.join_channel(query)
            await asyncio.to_thread(self.database.update_channel_stats, query, 0, time.time())

    async def handle_part(self, nick, channel, query):
        logging.debug(f"Configured owner: {BOT_OWNER}, Command sender: {nick}, Channel: {channel}")
        if self.is_owner(nick) and channel == BOT_OWNER and query:
            logging.info(f"Attempting to leave channel: {query}")
            await self.irc_client.part_channel(query)
            await asyncio.to_thread(self.database.update_channel_stats, query, 0, time.time())

    async def handle_counts(self, nick, channel, query):
        logging.info(f"Handling counts command from {nick} in {channel}.")
        if self.is_owner(nick) and channel == BOT_OWNER:
            counts = self.database.get_usage_counts()
            await self.irc_client.send_message(nick, f"Usage counts: {counts}")

    async def handle_msg(self, nick, channel, query):
        logging.info(f"Handling msg command from {nick} in {channel} with query: {query}.")
        if self.is_owner(nick) and channel == BOT_OWNER and ' ' in query:
            target, message = query.split(' ', 1)
            await self.send_chunked_message(target, message, nick)

    async def on_message(self, nick, channel, message):
        logging.debug(f"Processing message: nick={nick}, channel={channel}, message={message}")
        await asyncio.to_thread(self.database.update_channel_stats, channel, 1, time.time())
        await asyncio.to_thread(self.database.update_user_stats, nick, 1, 0, 0, time.time())
        if channel == BOT_NICK:
            target = nick
            if nick not in self.help_sent:
                self.help_sent[nick] = True
                await self.handle_help(nick, nick, '')
        else:
            target = channel
            if BOT_NICK in message and nick not in self.help_sent:
                self.help_sent[nick] = True
                await self.handle_help(nick, nick, '')
        words = message.split()
        if words and words[0].startswith('!'):
            command = words[0]
            args = ' '.join(words[1:])
            if command in self.commands:
                await self.commands[command](nick, target, args)
            else:
                logging.info(f"Ignoring non-command message with '!': {message}")

    async def send_chunked_message(self, target, message, nick, chunk_size=350):
        logging.info(f"Sending chunked message to {target}: {message}")
        if not message.strip():
            return
        for i in range(0, len(message), chunk_size):
            await asyncio.sleep(0)
            if self._should_cancel(nick):
                logging.info(f"Cancellation detected in send_chunked_message for {nick}")
                raise asyncio.CancelledError()
            chunk = message[i:i+chunk_size]
            if chunk.strip():
                await self.irc_client.send_message(target, chunk)
                await asyncio.to_thread(self.database.update_channel_stats, target, 1, time.time())

    async def shutdown(self):
        logging.info("Shutting down the bot...")
        await self.irc_client.quit()
        logging.info("Bot shutdown complete.")
        sys.exit(0)

    def is_owner(self, nick):
        logging.debug(f"Checking ownership: received nick='{nick}', configured owner='{BOT_OWNER}'")
        return nick.strip().lower() == BOT_OWNER.strip().lower()

if __name__ == "__main__":
    logging.info("Starting the bot application.")
    bot = QuranIRCBot()
    asyncio.run(bot.start())

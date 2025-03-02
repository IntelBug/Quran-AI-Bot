# config.py code
import os

# IRC Configuration
IRC_SERVER = os.getenv("IRC_SERVER", "irc.dal.net")
IRC_PORT = int(os.getenv("IRC_PORT", 6667))
BOT_NICK = os.getenv("BOT_NICK", "Falah")
ALT_NICK = os.getenv("ALT_NICK", "AL-Falah")
BOT_PASSWORD = os.getenv("BOT_PASSWORD", "786@786")
BOT_CHANNELS = os.getenv("BOT_CHANNELS", "#Margalla").split(",")
BOT_OWNER = os.getenv("BOT_OWNER", "IntelBug")

# AI API Configuration
AI_API_URL = os.getenv("AI_API_URL", "https://api.mistral.ai/v1/chat/completions")
AI_API_KEY = os.getenv("AI_API_KEY", "iQDc4Y877xj2NyOup7IRdkX2vZ5j5pJW")

# Database Configuration
DB_PATH = os.getenv("DB_PATH", "quran_kb.db")

# Messages Configuration
MESSAGES = {
    "no_results_found": "Sorry! No relevant Ayat found for your query. Please try different phrase or words for better results.",
    "api_timeout": "Sorry! Request timed out, please try again.",
    "query_queued": "Your query has been queued. You will receive a response shortly.",
    "completion_message": "The possible result(s) for the query has been processed. It is always the best approach to cross-check from other authentic sources too.",
    "query_exists": "You already have an active query",
    "flood_protection": "To avoid flooding, responses are sent in parts. Please be patient.",
    "shutting_down": "Stay blessed!",
    "wrong_command": "Invalid command. Please use one of the available commands.",
    "private_msg": "Please type !Quran <your question, topic, keywords etc.>.",
    "stop_success": "The remaining result has been stopped.",
    "stop_failure": "Unable to stop result for {target} : {Error}",
    "stopped_mid_process": "Stopped mid-transmission.",
    "existing_query": "You already have an active query.",
    "error_generic": "An error occurred processing your request.",
    "resume_start": "Sorry for the disconnection, remaining result is being continued.",
    "join_success": "Joined {channel}.",
    "join_failure": "Cannot join {channel} : {error}.",
    "join_empty": "Please mention channel name with !join",
    "part_success": "Left {channel}.",
    "part_empty": "Please mention channel name with !part",
    "quit_success": "Shutting down and quiting IRC.",
    "quit_failure": "Cannot shut down and quit.",
    "msg_empty": "Please mention nickname or channel and message after !msg",
    "msg_success": "Message sent to {nick}/{channel}",
    "msg_failure": "Cannot send message to {nickname}/{channel} : {reason}",
    "counts_failure": "Cannot fetch counts {error}",
    "resume_failure": "Cannot resume result for {nickname}/{channel} : {reason}",
    "reconnecting": "Reconnecting to IRC server...",
    "connection_failed": "Connection to IRC server failed. Retrying in 10 seconds...",
    "part_failure": "Cannot leave {channel} : {error}.",
    "channel_invite": "You can also join #Margalla to lead positive discussions!"
}

# Help content for the !help command
HELP_CONTENT = {
    'private': [
        "Assalam-o-Alaikum! I am here to provide very easy and authentic Qur'an Search. Just type !Quran <any Surah name, Ayat content, topic, keywords, or question> to find relevant Surah and Ayaat in 37 languages.",
        "To mention your preferred language e.g. !Quran Surah Al-Fateha in Urdu. You can also use !stop to stop the result. Have your blessed time on IRC :)"
    ],
    'channel': [
        "I am here to provide very easy and authentic Qur'an Search. You can ask about the Qur'anic Ayaat (Verses) based on topic, keywords, Surah name, Ayat content and questions.",
        "- You can just type !Quran <your query> and I will search for Surah and Ayat relevant to your query.",
        "- You can stop me if result is very long or not relevant by entering !stop.",
        "- To display this help message again, enter !help.",
        "I can translate Qur'an in 36 languages. Just mention your preferred language e.g. !Quran Surah Al-Fateha in Urdu. Have your blessed time on IRC :)"
    ]
}

# Mapping of language codes to table names
LANGUAGE_TABLE_MAPPING = {
    'sq': 'albanian',
    'az': 'azeri',
    'bn': 'bangali',
    'bs': 'bosnian',
    'bg': 'bulgarian',
    'zh': 'chinese',
    'cs': 'czech',
    'dv': 'divehi',
    'nl': 'dutch',
    'en': 'english',
    'de': 'german',
    'hi': 'hindi',
    'id': 'indonesian',
    'it': 'italian',
    'ja': 'japanese',
    'ko': 'korean',
    'ku': 'kurdish',
    'ms': 'malay',
    'ml': 'malayalam',
    'no': 'norwegian',
    'pl': 'polish',
    'pt': 'portuguese',
    'ro': 'romanian',
    'ru': 'russian',
    'so': 'somali',
    'es': 'spanish',
    'si': 'sinhala',
    'sw': 'swahili',
    'sv': 'swedish',
    'tg': 'tajik',
    'ta': 'tamil',
    'tt': 'tatar',
    'th': 'thai',
    'tr': 'turkish',
    'ur': 'urdu',
    'ug': 'uyghur',
    'uz': 'uzbek'
}

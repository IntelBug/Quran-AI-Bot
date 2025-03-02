import sqlite3
import logging
import time
from config import LANGUAGE_TABLE_MAPPING

class Database:
    def __init__(self, db_path):
        # Allow multi-threaded access
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS channel_stats (
                channel TEXT PRIMARY KEY,
                join_count INTEGER DEFAULT 0,
                part_count INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                last_activity REAL DEFAULT 0
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                nick TEXT PRIMARY KEY,
                total_commands INTEGER DEFAULT 0,
                successful_queries INTEGER DEFAULT 0,
                failed_queries INTEGER DEFAULT 0,
                last_seen REAL DEFAULT 0
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nick TEXT,
                channel TEXT,
                query TEXT,
                success BOOLEAN,
                chunks_sent INTEGER,
                timestamp REAL
            )
        """)
        self.conn.commit()

    def fetch_ayats(self, surah_ayat_pairs, language='arabic', is_rtl=False):
        logging.info(f"Fetching Ayats for pairs: {surah_ayat_pairs} in language: {language}")
        formatted_response = []
        surah_ayats_map = {}

        for surah_number, ayat_number in surah_ayat_pairs:
            self.cursor.execute("SELECT text, number FROM arabic WHERE surah_id = ? AND number_in_surah = ?",
                                (surah_number, ayat_number))
            arabic_text_result = self.cursor.fetchone()
            if not arabic_text_result:
                logging.warning(f"No Arabic text found for Surah {surah_number}, Ayat {ayat_number}")
                continue
            arabic_text, number = arabic_text_result

            translation_table = LANGUAGE_TABLE_MAPPING.get(language, 'english')
            self.cursor.execute(f"SELECT data FROM {translation_table} WHERE ayah_id = ?", (number,))
            translation_result = self.cursor.fetchone()
            translation = translation_result[0] if translation_result else "Translation not available"

            self.cursor.execute("SELECT name_ar, name_en, name_en_translation, type FROM surahs WHERE id = ?",
                                (surah_number,))
            surah_info_result = self.cursor.fetchone()
            if not surah_info_result:
                logging.warning(f"No Surah information found for Surah {surah_number}")
                continue
            surah_name_ar, surah_name_en, surah_name_en_translation, surah_type = surah_info_result

            if surah_number not in surah_ayats_map:
                surah_ayats_map[surah_number] = {
                    "surah_name_en": surah_name_en,
                    "surah_name_ar": surah_name_ar,
                    "surah_name_en_translation": surah_name_en_translation,
                    "surah_type": surah_type,
                    "ayats": []
                }

            if is_rtl:
                arabic_text = f"\u202B{arabic_text}\u202C"
                translation = f"\u202A{translation}\u202C"

            surah_ayats_map[surah_number]["ayats"].append((ayat_number, arabic_text, translation))

        for surah_number, surah_data in surah_ayats_map.items():
            formatted_response.append(
                f"Surah {surah_data['surah_name_en']} ({surah_data['surah_name_en_translation']}) - {surah_data['surah_type']} - {surah_data['surah_name_ar']}"
            )
            for ayat_number, arabic_text, translation in surah_data["ayats"]:
                formatted_response.append(f"Ayat {ayat_number}: {arabic_text}")
                formatted_response.append(f"Translation: {translation}")

        logging.info(f"Completed fetching and formatting Ayats: {formatted_response}")
        return formatted_response

    def update_user_stats(self, nick, inc_total, inc_success, inc_fail, last_seen):
        self.cursor.execute("""
            INSERT INTO user_stats (nick, total_commands, successful_queries, failed_queries, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(nick) DO UPDATE SET
                total_commands = total_commands + ?,
                successful_queries = successful_queries + ?,
                failed_queries = failed_queries + ?,
                last_seen = ?
        """, (nick, inc_total, inc_success, inc_fail, last_seen,
              inc_total, inc_success, inc_fail, last_seen))
        self.conn.commit()

    def update_channel_stats(self, channel, inc_message, last_activity):
        self.cursor.execute("""
            INSERT INTO channel_stats (channel, message_count, last_activity)
            VALUES (?, ?, ?)
            ON CONFLICT(channel) DO UPDATE SET
                message_count = message_count + ?,
                last_activity = ?
        """, (channel, inc_message, last_activity, inc_message, last_activity))
        self.conn.commit()

    def log_query(self, nick, channel, query, success, chunks_sent):
        self.cursor.execute("""
            INSERT INTO query_history (nick, channel, query, success, chunks_sent, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nick, channel, query, success, chunks_sent, time.time()))
        self.conn.commit()

    def get_usage_counts(self):
        self.cursor.execute("SELECT COUNT(*) FROM query_history")
        total_count = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT nick, COUNT(*) FROM query_history GROUP BY nick")
        user_counts = self.cursor.fetchall()
        self.cursor.execute("SELECT channel, COUNT(*) FROM query_history GROUP BY channel")
        channel_counts = self.cursor.fetchall()
        return {
            "total_count": total_count,
            "user_counts": user_counts,
            "channel_counts": channel_counts
        }

    def close(self):
        if self.conn:
            self.conn.close()

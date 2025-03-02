# ai_client.py code
import aiohttp
import asyncio
import re
import logging

class AIClient:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self.surah_ayat_patterns = [
            r"Surah\s*:\s*(\d+)\s*,\s*Ayat\s*:\s*(\d+)",
            r"(\d+)\s*:\s*(\d+)",
            r"(\d+)\s*:\s*(\d+)\s*-\s*(\d+)",
            r"\((\d+)\s*:\s*(\d+)\)",
            r"\((\d+)\s*:\s*(\d+)\s*-\s*(\d+)\)",
            r"(\d+)\s*-\s*(\d+)"  # Pattern to match ranges like "62:9-11"
        ]

    async def query_quran(self, query):
        payload = {
            "model": "mistral-small-latest",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only Surah and Ayat number(s) of the Ayat(s) relevant to the query in the below format: "
                        "Language: ISO code:Unicode Direction; Surah Number: Ayat Number, Surah Number: Ayat Number, Surah Number: Ayat Number. "
                        "Example: Language: ur:RTL; 108:10, 8:12, 10:20. "
                        "Return all Ayats of a Surah in sequence if the query specifies so. "
                        "Result must contain unique Ayats of a Surah and do not repeat Ayat of the same Surah in a result. "
                        "Must return accurate results and ensure moderation for the criticality of religious information. "
                        "Query and result mapping shall start with Surah name, Ayat content, Ayat meaning and then Tafseer to get a complete context. "
                        "Don't include Ayat content and other information in the response. "
                        "Mention the ISO language code and Right-to-Left flag e.g. RTL or LTR of query used by the user e.g. Language: en:LTR."
                    )
                },
                {"role": "user", "content": query}
            ]
        }

        logging.info(f"Sending structured query to AI: {payload}")

        for attempt in range(10):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.api_url,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                        timeout=10
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            logging.info(f"Received response from AI: {data}")
                            return self.parse_response(data['choices'][0]['message']['content'])
                        else:
                            logging.error(f"AI request failed with status code: {response.status}. Retrying...")
            except aiohttp.ClientError as e:
                logging.error(f"Error during AI request: {e}. Retrying...")

            await asyncio.sleep(2 ** attempt)  # Exponential backoff

        logging.error("Failed to get a valid response after multiple attempts.")
        return None

    def parse_response(self, response):
        logging.info(f"Parsing AI response: {response}")
        language_match = re.search(r"Language:\s*(\w+)(?::(\w+))?;", response)
        language = language_match.group(1) if language_match else 'arabic'
        is_rtl = language_match.group(2) == 'RTL' if language_match else False
        logging.info(f"Extracted language: {language}, RTL: {is_rtl}")

        ayats = []
        for pattern in self.surah_ayat_patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                if len(match) == 2:
                    surah = int(match[0])
                    ayat = int(match[1])
                    ayats.append((surah, ayat))
                    logging.info(f"Extracted Surah:Ayat pair: {surah}:{ayat}")
                elif len(match) == 3:
                    surah = int(match[0])
                    start_ayat = int(match[1])
                    end_ayat = int(match[2])
                    for ayat in range(start_ayat, end_ayat + 1):
                        ayats.append((surah, ayat))
                        logging.info(f"Extracted Surah:Ayat range: {surah}:{start_ayat}-{end_ayat}")

        logging.info(f"All extracted Ayats: {ayats}")
        return {'language': language, 'rtl': is_rtl, 'ayats': ayats}

import logging
from collections import OrderedDict

import httpx

from app.config import settings
from app.rag.retrieval import Retriever

log = logging.getLogger("chatbot")

SYSTEM_PROMPT = """You are a helpful assistant for two real-estate companies: DarGlobal (a luxury property developer) and Wasalt (a Saudi property marketplace).

Rules:
- Answer ONLY from the numbered context excerpts below. Do not use outside knowledge.
- If the context does not contain the answer, say you don't have that information in your sources, and suggest checking darglobal.co.uk or wasalt.sa. Never invent prices, locations, dates or figures.
- Be concise (under 150 words unless asked for more). For property searches, list the best matches with location, size, bedrooms and price.
- Cite sources inline as [1], [2] matching the excerpt numbers.
- Wasalt listing data is a small sample and may be out of date; remind the user to check the live listing when quoting prices or availability. Attribute Wasalt content as "Source: Wasalt.sa".
- Never share personal contact details. Reply in the language the user writes in."""

NO_KEY_MSG = "The server is missing OPENROUTER_API_KEY."
BUSY_MSG = ("The free language models are busy or rate-limited right now. "
            "Please try again in a minute.")


class Chatbot:
    def __init__(self):
        self.retriever = Retriever()
        self.cache: OrderedDict[str, dict] = OrderedDict()

    @staticmethod
    def _context(hits: list[dict]) -> str:
        return "\n\n".join(f"[{i}] ({h['source']}) {h['title']}\nURL: {h['url']}\n{h['text']}"
                           for i, h in enumerate(hits, 1))

    @staticmethod
    def _sources(hits: list[dict]) -> list[dict]:
        seen, out = set(), []
        for h in hits:
            if h["url"] not in seen:
                seen.add(h["url"])
                out.append({"title": h["title"] or h["url"], "url": h["url"], "source": h["source"]})
        return out

    async def _llm(self, messages: list[dict]) -> str | None:
        headers = {"Authorization": f"Bearer {settings.openrouter_api_key}",
                   "HTTP-Referer": "https://example.com", "X-Title": "Real Estate Assistant"}
        async with httpx.AsyncClient(timeout=60) as client:
            for model in settings.models:
                try:
                    r = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers,
                                          json={"model": model, "messages": messages,
                                                "temperature": 0, "max_tokens": 800})
                    if r.status_code != 200:
                        log.warning("%s -> HTTP %s %s", model, r.status_code, r.text[:200])
                        continue
                    text = (r.json()["choices"][0]["message"].get("content") or "").strip()
                    if text:
                        return text
                    log.warning("%s -> empty content", model)
                except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
                    log.warning("%s -> %r", model, e)
        return None

    async def answer(self, question: str, history: list[dict]) -> dict:
        history = history[-settings.max_history_turns * 2:]
        key = question.strip().lower()
        if not history and key in self.cache:
            return self.cache[key]

        # short follow-ups ("what about Jeddah?") need the previous user turn to retrieve well
        q = question
        if history and len(question.split()) < 8:
            prev = [m["content"] for m in history if m["role"] == "user"]
            q = (prev[-1] + " " + question) if prev else question
        hits = self.retriever.search(q)

        if not settings.openrouter_api_key:
            return {"answer": NO_KEY_MSG, "sources": []}
        messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\nContext:\n" + self._context(hits)},
                    *history, {"role": "user", "content": question}]
        text = await self._llm(messages)
        if text is None:
            return {"answer": BUSY_MSG, "sources": []}
        result = {"answer": text, "sources": self._sources(hits)}
        if not history:
            self.cache[key] = result
            if len(self.cache) > 200:
                self.cache.popitem(last=False)
        return result

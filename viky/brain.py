"""L'intelligence de Viky : une IA locale (Ollama) et Claude pour les recherches.

- Questions courantes : l'IA locale répond, gratuitement et hors ligne.
- Recherches complètes, actualité, sujets récents : Claude, avec recherche web.
Si l'une des deux n'est pas disponible, Viky utilise l'autre.
"""

from __future__ import annotations

import json
import os
import urllib.request

SPOKEN_STYLE = {
    "fr": "Tu es Viky, une assistante vocale chaleureuse et précise, un peu comme Jarvis. "
          "Tu réponds toujours en français. Ta réponse sera lue à voix haute : phrases courtes "
          "et naturelles, aucun markdown, aucune liste à puces, aucune adresse web, pas d'émojis. "
          "Sauf demande contraire, réponds en 3 à 6 phrases, en commençant par l'essentiel.",
    "en": "You are Viky, a warm and precise voice assistant, a bit like Jarvis. Always answer "
          "in English. Your answer will be read aloud: short natural sentences, no markdown, "
          "no bullet points, no URLs, no emojis. Unless asked otherwise, answer in 3 to 6 "
          "sentences, starting with the key point.",
}

REPORT_MARKER = "---RAPPORT---"

RESEARCH_TASK = {
    "fr": "Fais une recherche complète et à jour sur le web à propos de : {topic}\n\n"
          "Réponds en deux parties.\n"
          "1. D'abord un résumé à lire à voix haute (6 à 10 phrases, sans markdown).\n"
          f"2. Puis une ligne contenant exactement {REPORT_MARKER} suivie d'un rapport détaillé "
          "en markdown (titres, points clés, chiffres, nuances) qui se termine par la liste des sources.",
    "en": "Do thorough, up-to-date web research on: {topic}\n\n"
          "Answer in two parts.\n"
          "1. First a summary to read aloud (6 to 10 sentences, no markdown).\n"
          f"2. Then a line containing exactly {REPORT_MARKER} followed by a detailed markdown "
          "report (headings, key points, figures, nuances) that ends with the list of sources.",
}

ARTICLE_TASK = {
    "fr": "Voici un article d'actualité intitulé « {title} ». Explique-le-moi à l'oral en 6 à 8 "
          "phrases : ce qui s'est passé, le contexte et pourquoi c'est important.\n\n{text}",
    "en": "Here is a news article titled \"{title}\". Explain it to me out loud in 6 to 8 "
          "sentences: what happened, the context and why it matters.\n\n{text}",
}


class BrainUnavailable(Exception):
    pass


class Brain:
    def __init__(self, claude_model: str = "claude-opus-5-5", claude_key: str | None = None,
                 local_model: str = "qwen2.5:7b", ollama_url: str = "http://localhost:11434",
                 use_claude: bool = True, use_local: bool = True) -> None:
        self.claude_model = claude_model
        self.claude_key = claude_key or os.environ.get("ANTHROPIC_API_KEY")
        self.local_model = local_model
        self.ollama_url = ollama_url.rstrip("/")
        self.use_claude = use_claude and bool(self.claude_key)
        self.use_local = use_local
        self.history: list[dict] = []  # derniers échanges, pour « approfondis »
        self._client = None

    # ------------------------------------------------------------ disponibilité

    def local_available(self) -> bool:
        if not self.use_local:
            return False
        try:
            with urllib.request.urlopen(f"{self.ollama_url}/api/tags", timeout=1.5) as response:
                models = [m["name"] for m in json.loads(response.read()).get("models", [])]
        except Exception:
            return False
        wanted = self.local_model if ":" in self.local_model else f"{self.local_model}:latest"
        return wanted in models

    @property
    def available(self) -> bool:
        return self.use_claude or self.local_available()

    # ------------------------------------------------------------ questions

    def ask(self, question: str, lang: str, deep: bool = False) -> str:
        """Répond à une question. `deep` force Claude avec recherche web."""
        messages = self.history[-8:] + [{"role": "user", "content": question}]
        answer = self._answer(messages, lang, deep)
        self._remember(question, answer)
        return answer

    def follow_up(self, lang: str) -> str:
        prompt = "Approfondis ta dernière réponse." if lang == "fr" else "Go deeper on your last answer."
        return self.ask(prompt, lang, deep=self.use_claude)

    def research(self, topic: str, lang: str) -> tuple[str, str]:
        """Recherche complète. Renvoie (résumé oral, rapport détaillé en markdown)."""
        task = RESEARCH_TASK[lang].format(topic=topic)
        text = self._claude([{"role": "user", "content": task}], lang, web=True, effort="high")
        spoken, _, report = text.partition(REPORT_MARKER)
        spoken = spoken.strip()
        self._remember(topic, spoken)
        return spoken, (report.strip() or spoken)

    def explain_article(self, title: str, text: str, lang: str) -> str:
        task = ARTICLE_TASK[lang].format(title=title, text=text)
        answer = self._answer([{"role": "user", "content": task}], lang, deep=False)
        self._remember(title, answer)
        return answer

    def _remember(self, question: str, answer: str) -> None:
        self.history += [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]
        self.history = self.history[-12:]

    def _answer(self, messages: list[dict], lang: str, deep: bool) -> str:
        if deep and self.use_claude:
            return self._claude(messages, lang, web=True, effort="medium")
        if self.local_available():
            try:
                return self._ollama(messages, lang)
            except Exception:
                if not self.use_claude:
                    raise
        if self.use_claude:
            return self._claude(messages, lang, web=deep, effort="low")
        raise BrainUnavailable

    # ------------------------------------------------------------ moteurs

    def _ollama(self, messages: list[dict], lang: str) -> str:
        body = json.dumps({
            "model": self.local_model, "stream": False,
            "messages": [{"role": "system", "content": SPOKEN_STYLE[lang]}] + messages,
        }).encode()
        request = urllib.request.Request(f"{self.ollama_url}/api/chat", data=body,
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read())["message"]["content"].strip()

    def _claude(self, messages: list[dict], lang: str, web: bool, effort: str) -> str:
        if not self.use_claude:
            raise BrainUnavailable
        import anthropic

        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.claude_key)
        request = {
            "model": self.claude_model,
            "max_tokens": 16000,
            "system": SPOKEN_STYLE[lang],
            "output_config": {"effort": effort},
            "betas": ["server-side-fallback-2026-07-01"],
            "fallbacks": "default",
            "messages": list(messages),
        }
        if web:
            request["tools"] = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 8}]

        # Avec la recherche web, Claude peut mettre son tour en pause : on le relance.
        for _ in range(5):
            response = self._client.beta.messages.create(**request)
            if response.stop_reason != "pause_turn":
                break
            request["messages"] = request["messages"] + [{"role": "assistant", "content": response.content}]

        if response.stop_reason == "refusal":
            return ("Désolée, je ne peux pas répondre à cette question." if lang == "fr"
                    else "Sorry, I can't answer that.")
        return "".join(block.text for block in response.content if block.type == "text").strip()

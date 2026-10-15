"""Météo gratuite et sans inscription (Open-Meteo), à l'endroit où vous êtes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

from .web import get_json

# Codes météo WMO -> description
_CODES = {
    0: ("ciel dégagé", "clear sky"), 1: ("ciel plutôt dégagé", "mostly clear"),
    2: ("partiellement nuageux", "partly cloudy"), 3: ("ciel couvert", "overcast"),
    45: ("brouillard", "fog"), 48: ("brouillard givrant", "freezing fog"),
    51: ("bruine légère", "light drizzle"), 53: ("bruine", "drizzle"), 55: ("forte bruine", "heavy drizzle"),
    56: ("bruine verglaçante", "freezing drizzle"), 57: ("bruine verglaçante", "freezing drizzle"),
    61: ("pluie faible", "light rain"), 63: ("pluie", "rain"), 65: ("forte pluie", "heavy rain"),
    66: ("pluie verglaçante", "freezing rain"), 67: ("forte pluie verglaçante", "heavy freezing rain"),
    71: ("neige faible", "light snow"), 73: ("neige", "snow"), 75: ("forte neige", "heavy snow"),
    77: ("grains de neige", "snow grains"), 80: ("averses", "rain showers"),
    81: ("averses", "rain showers"), 82: ("violentes averses", "violent showers"),
    85: ("averses de neige", "snow showers"), 86: ("fortes averses de neige", "heavy snow showers"),
    95: ("orages", "thunderstorms"), 96: ("orages avec grêle", "thunderstorms with hail"),
    99: ("violents orages avec grêle", "severe thunderstorms with hail"),
}

_DAY_WORDS = {"aujourd hui": 0, "ce soir": 0, "maintenant": 0, "today": 0, "tonight": 0, "now": 0,
              "demain": 1, "tomorrow": 1, "apres demain": 2}


@dataclass
class Place:
    name: str
    latitude: float
    longitude: float


def parse_request(text: str, lang: str) -> tuple[str | None, int]:
    """« quel temps fera-t-il à lyon demain » -> (« lyon », 1)."""
    day = 0
    for words, offset in sorted(_DAY_WORDS.items(), key=lambda item: -len(item[0])):
        if re.search(rf"\b{words}\b", text):
            day = offset
            text = re.sub(rf"\b{words}\b", " ", text)
            break
    text = re.sub(r"\s+", " ", text).strip()
    prepositions = r"(a|au|aux|en|sur|pour|de|du)" if lang == "fr" else r"(in|at|for)"
    match = re.search(rf"\b{prepositions} (?P<city>[a-z][a-z ]*)$", text)
    city = match.group("city").strip() if match else None
    if city in ("la", "le", "l", "the", "", None) or (city and city.split()[0] in ("ce", "cette", "la")):
        city = None
    return city, day


def geocode(city: str, lang: str) -> Place | None:
    data = get_json(f"https://geocoding-api.open-meteo.com/v1/search?name={quote(city)}"
                    f"&count=1&language={lang}&format=json")
    results = data.get("results") or []
    if not results:
        return None
    r = results[0]
    return Place(r["name"], r["latitude"], r["longitude"])


def locate_by_ip() -> Place | None:
    """Position approximative (la ville) d'après la connexion internet."""
    try:
        data = get_json("https://ipapi.co/json/", timeout=5)
        if data.get("latitude") is not None:
            return Place(data.get("city") or "", data["latitude"], data["longitude"])
    except Exception:
        pass
    try:
        data = get_json("http://ip-api.com/json/?fields=status,city,lat,lon", timeout=5)
        if data.get("status") == "success":
            return Place(data.get("city") or "", data["lat"], data["lon"])
    except Exception:
        pass
    return None


def forecast(place: Place) -> dict:
    return get_json(
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={place.latitude}&longitude={place.longitude}"
        "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        "&timezone=auto&forecast_days=3")


def describe(place: Place, data: dict, day: int, lang: str) -> str:
    fr = lang == "fr"
    where = (f"À {place.name}, " if fr else f"In {place.name}, ") if place.name else ""
    daily = data["daily"]
    low, high = round(daily["temperature_2m_min"][day]), round(daily["temperature_2m_max"][day])
    rain = daily.get("precipitation_probability_max", [None] * 3)[day]
    sky = _CODES.get(daily["weather_code"][day], ("", ""))[0 if fr else 1]
    rain_text = ""
    if rain is not None:
        rain_text = f" {rain} % de risque de pluie." if fr else f" {rain}% chance of rain."

    if day == 0:
        current = data["current"]
        now_sky = _CODES.get(current["weather_code"], ("", ""))[0 if fr else 1]
        temp, feels = round(current["temperature_2m"]), round(current["apparent_temperature"])
        if fr:
            feel = f", ressenti {feels}" if abs(feels - temp) >= 2 else ""
            return (f"{where}il fait {temp} degrés{feel}, {now_sky}. "
                    f"Aujourd'hui, entre {low} et {high} degrés.{rain_text}")
        feel = f", feels like {feels}" if abs(feels - temp) >= 2 else ""
        return f"{where}it's {temp} degrees{feel}, {now_sky}. Today between {low} and {high}.{rain_text}"

    when = ("Demain" if day == 1 else "Après-demain") if fr else ("Tomorrow" if day == 1 else "In two days")
    place_text = f" à {place.name}" if fr and place.name else (f" in {place.name}" if place.name else "")
    if fr:
        return f"{when}{place_text} : {sky}, entre {low} et {high} degrés.{rain_text}"
    return f"{when}{place_text}: {sky}, between {low} and {high} degrees.{rain_text}"


class Weather:
    def __init__(self, home_city: str | None = None) -> None:
        self.home_city = home_city
        self._home: Place | None = None

    def home(self, lang: str) -> Place | None:
        if self._home is None:
            self._home = geocode(self.home_city, lang) if self.home_city else locate_by_ip()
        return self._home

    def report(self, text: str, lang: str) -> str | None:
        """Renvoie la phrase météo, ou None si le lieu est introuvable."""
        city, day = parse_request(text, lang)
        place = geocode(city, lang) if city else self.home(lang)
        if place is None:
            return None
        return describe(place, forecast(place), day, lang)

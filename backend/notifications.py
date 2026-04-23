# MIT License
# Copyright (c) 2026 Angshuman Nandy

from __future__ import annotations

import logging

import httpx

from .config import PUSHOVER_TOKEN, PUSHOVER_USER

logger = logging.getLogger(__name__)

_GEO_URL = "http://ip-api.com/json/{ip}?fields=status,country,countryCode,regionName,city,zip,lat,lon,timezone,isp,org,query"


async def geolocate_ip(ip: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(_GEO_URL.format(ip=ip))
            data = r.json()
            if data.get("status") == "success":
                return data
    except Exception as exc:
        logger.warning("IP geolocation failed for %s: %s", ip, exc)
    return {}


async def send_pushover(title: str, message: str) -> None:
    if not PUSHOVER_TOKEN or not PUSHOVER_USER:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                "https://api.pushover.net/1/messages.json",
                data={
                    "token": PUSHOVER_TOKEN,
                    "user": PUSHOVER_USER,
                    "title": title,
                    "message": message,
                },
            )
    except Exception as exc:
        logger.warning("Pushover notification failed: %s", exc)


async def notify_game_started(ip: str, game) -> None:
    geo = await geolocate_ip(ip)

    location_parts = [geo.get("city"), geo.get("regionName"), geo.get("countryCode")]
    location = ", ".join(p for p in location_parts if p) or "Unknown"

    def player_label(p) -> str:
        if p.is_human:
            return "Human"
        if p.llm_config:
            return f"{p.llm_config.provider} / {p.llm_config.model}"
        return "Unknown"

    lines = [f"IP: {ip}", f"Location: {location}"]
    if geo.get("isp"):
        lines.append(f"ISP: {geo['isp']}")
    if geo.get("org") and geo.get("org") != geo.get("isp"):
        lines.append(f"Org: {geo['org']}")
    if geo.get("timezone"):
        lines.append(f"Timezone: {geo['timezone']}")
    if geo.get("lat") and geo.get("lon"):
        lines.append(f"Coords: {geo['lat']}, {geo['lon']}")
    lines.append(f"P1: {player_label(game.player1)}")
    lines.append(f"P2: {player_label(game.player2)}")
    lines.append(f"Board: {game.board_size}x{game.board_size}")

    await send_pushover("LLM-Battleships | New Game", "\n".join(lines))

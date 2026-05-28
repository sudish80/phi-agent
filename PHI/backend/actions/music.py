"""Music control module for J.A.R.V.I.S.

Spotify playback control via Spotipy.
"""

import asyncio
import logging
from typing import Optional

from backend.shared.config import settings

logger = logging.getLogger(__name__)


async def spotify_search(query: str, type: str = "track",
                         limit: int = 5) -> str:
    """Search Spotify for tracks, artists, or albums."""
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
    except ImportError:
        return "Spotify requires spotipy"

    cid = settings.openai_api_key  # reuse or add dedicated SPOTIFY_CLIENT_ID
    secret = settings.anthropic_api_key  # placeholder
    if not cid or not secret:
        return ("Spotify not configured. Add SPOTIFY_CLIENT_ID and "
                "SPOTIFY_CLIENT_SECRET to .env")

    loop = asyncio.get_event_loop()

    def _search():
        try:
            auth = SpotifyClientCredentials(
                client_id=cid, client_secret=secret)
            sp = spotipy.Spotify(auth_manager=auth)
            results = sp.search(q=query, type=type, limit=limit)
            items = results.get(f"{type}s", {}).get("items", [])
            if not items:
                return f"No {type}s found for '{query}'."
            lines = [f"**Spotify results for '{query}'**"]
            for item in items:
                name = item.get("name", "N/A")
                artists = ", ".join(a["name"] for a in item.get("artists", []))
                lines.append(f"  - {name} by {artists}")
            return "\n".join(lines)
        except Exception as e:
            return f"Spotify error: {e}"

    return await loop.run_in_executor(None, _search)


async def spotify_playlist(playlist_id: str, limit: int = 10) -> str:
    """Get tracks from a Spotify playlist."""
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
    except ImportError:
        return "Spotify requires spotipy"

    loop = asyncio.get_event_loop()

    def _fetch():
        try:
            auth = SpotifyClientCredentials()
            sp = spotipy.Spotify(auth_manager=auth)
            results = sp.playlist_tracks(playlist_id, limit=limit)
            items = results.get("items", [])
            if not items:
                return "No tracks found in playlist."
            lines = [f"**Playlist tracks** ({len(items)} tracks)"]
            for item in items:
                track = item.get("track", {})
                name = track.get("name", "N/A")
                artists = ", ".join(a["name"] for a in track.get("artists", []))
                lines.append(f"  - {name} — {artists}")
            return "\n".join(lines)
        except Exception as e:
            return f"Spotify error: {e}"

    return await loop.run_in_executor(None, _fetch)

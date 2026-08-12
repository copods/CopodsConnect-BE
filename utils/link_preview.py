# utils/link_preview.py
"""
Utility for on-the-fly URL metadata extraction.
Usage:
    from utils.link_preview import fetch_link_metadata
    link_metadata = await fetch_link_metadata(caption_text)
    # Returns: [{"url": "https://example.com", "title": "Example Domain"}, ...]
How it works:
    1. Extracts all HTTP/HTTPS URLs from the given text using regex.
    2. Fires async HTTP GET requests to ALL URLs concurrently using asyncio.gather —
       so whether the caption has 1 link or 5, the wait is always equal to the
       slowest single response, not the sum.
    3. Parses HTML with BeautifulSoup4, preferring OpenGraph og:title over the raw
       <title> tag since OG titles are usually cleaner/shorter.
    4. If a URL fails or has no title, that entry still appears with title=None
       so the frontend can fall back to displaying the raw URL as a clickable link.
Usage in create_post (write path):
    - fetch_link_metadata is called BEFORE the AI moderation scan so that
      the fetched titles can be appended to moderation_text and sent to Gemini.
      This closes the loophole where a user could paste a link whose page title
      contains NSFW content that would otherwise bypass text moderation entirely.
    - The fetch runs concurrently with scan_images (independent operation),
      then the combined text (caption + titles) is passed to scan_text.
Usage in get_feed / get_post (read path):
    - fetch_link_metadata is called concurrently for all posts at once using
      asyncio.gather so feed load time is not multiplied by the number of posts.
Future scope (TODO):
    - Persist link metadata (url, title, description, og:image) in a `PostLink`
      DB table at create_post time. This turns the HTTP fetch into a one-time
      operation — all subsequent reads (get_feed, get_post) become cheap DB
      lookups instead of live network calls, eliminating the per-request delay.
      At that point:
        * create_post: still calls fetch_link_metadata once, saves result to DB.
        * get_feed / get_post: reads from post.links join, no HTTP call at all.
        * _serialize_post: can go back to a plain `def` (sync), reading
          link metadata like it reads `media` or `tags` today.
    - Add a short in-memory / Redis TTL cache keyed on URL so repeated
      requests for the same popular link don't hammer the same server.
"""

import asyncio 
import re 
from typing import Optional

import httpx 
from bs4 import BeautifulSoup

# Matches http:// and https:// URLs in plain text. 
_URL_RE = re.compile(r"https?://[^\s<>\"'()]+" , re.IGNORECASE)

# Max seconds to wait for a single URL before giving up. 
# Kept deliberately short - this runs on the critical path of post creation.
_FETCH_TIMEOUT = 2.0

def extract_urls(text:str)-> list[str]:
    """Return a deduplicated , ordered list of HTTP/HTTPS URLs found in *text*."""
    seen: set[str]= set()
    result: list[str] =[]
    for url in _URL_RE.findall(text or ""):
        # Strip trailing punctuations that is almost never part of the URL
        url = url.rstrip(".,;:!?)")
        if url not in seen : 
            seen.add(url)
            result.append(url)
    return result

async def _fetch_title(client: httpx.AsyncClient, url:str)-> Optional[str]:
    """
    Fetch *url* and return the best available page title, or None.
    Title priority:
        1. <meta property="og:title"> — curated by the site, usually cleaner
        2. <title> tag — standard HTML fallback
    """
    try:
        response = await client.get(
            url,
            timeout = _FETCH_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; CopodsConnect/1.0; +https://copdos.co)"
                ),
                "Accept": "text/html, application/xhtml+xml;q=0.9,*/*;q=0.8",
            },
        )
        content_type = response.headers.get("content-type," "")
        if "html" not in content_type:
            return None
        
        soup= BeautifulSoup(response.text,"html.parser")

        # 1) OpenGraph title (preferred)
        og_title = soup.find("meta",property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip() or None
        
        # 2) Standard title (preffered)
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            return title_tag.string.strip() or None
        
        return None
    except Exception:
        # Network error , timeout, redirect loop, parse failure - return None. 
        # The frontend will fall back to displaying the raw URL as a clickable link. 
        return None

async def fetch_link_metadata(text:str) -> list[dict]:
    """
    Extract all URLs from *text* and fetch their page titles concurrently.
    All URL fetches fire at the same time via asyncio.gather, so the total
    wait time equals the slowest single response — not the sum of all responses.
    This means 5 links takes the same time as 1 link.
    Returns a list of dicts in the order URLs appear in the text:
        [{"url": "https://...", "title": "Page Title"}, ...]
    title is None if the fetch failed or the page had no title.
    Returns [] immediately if no URLs are found in the text.
    """
    urls = extract_urls(text)
    if not urls:
        return []
    
    async with httpx.AsyncClient() as client:
        titles = await asyncio.gather(*[_fetch_title(client, url) for url in urls])

        return [{"url": url, "title": title} for url, title in zip(urls, titles)]

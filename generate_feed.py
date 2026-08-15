#!/usr/bin/env python3
"""Build a Futuri-friendly, full-content RSS feed from the Wix blog feed."""

from __future__ import annotations

import html
import json
import mimetypes
import os
import re
import sys
import time
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
HEADERS = {
    "User-Agent": "NewsRadio923-RSS/1.0 (+https://www.newsradio923.com)",
    "Accept": "text/html,application/xhtml+xml,application/rss+xml,application/xml",
}


def cdata(value: str) -> str:
    """ElementTree-compatible placeholder; CDATA is added after serialization."""
    return value or ""


def clean_article_html(url: str) -> tuple[str, str | None]:
    response = requests.get(url, headers=HEADERS, timeout=35)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    viewer = soup.select_one('[data-id="content-viewer"]')
    if not viewer:
        raise ValueError("Wix article body was not found")

    for unwanted in viewer.select("script, style, button, form, noscript"):
        unwanted.decompose()

    # Wix inserts empty bookkeeping divs between real content blocks.
    for node in list(viewer.find_all("div")):
        if node.get("data-hook", "").startswith("rcv-block"):
            node.decompose()

    # Make links and images absolute and remove Wix's presentation-only attributes.
    for tag in viewer.find_all(True):
        if tag.name == "a" and tag.get("href"):
            tag["href"] = urljoin(url, tag["href"])
            tag["target"] = "_blank"
            tag["rel"] = "noopener"
        if tag.name == "img" and tag.get("src"):
            tag["src"] = urljoin(url, tag["src"])
        allowed = {"href", "src", "alt", "title", "target", "rel", "width", "height"}
        for attribute in list(tag.attrs):
            if attribute not in allowed:
                del tag.attrs[attribute]

    article_html = "".join(str(child) for child in viewer.children).strip()
    article_html = re.sub(r"(?:<br\s*/?>\s*){3,}", "<br><br>", article_html)

    og_image = soup.select_one('meta[property="og:image"]')
    image_url = og_image.get("content") if og_image else None
    return article_html, image_url


def text_preview(article_html: str, limit: int = 350) -> str:
    text = BeautifulSoup(article_html, "html.parser").get_text(" ", strip=True)
    if len(text) <= limit:
        return text
    shortened = text[:limit].rsplit(" ", 1)[0]
    return shortened + "…"


def sub(parent: ET.Element, name: str, value: str | None = None, **attrs) -> ET.Element:
    element = ET.SubElement(parent, name, attrs)
    if value is not None:
        element.text = value
    return element


def build() -> Path:
    source = requests.get(CONFIG["source_feed"], headers=HEADERS, timeout=35)
    source.raise_for_status()
    parsed = feedparser.parse(source.content)
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"Could not parse Wix RSS: {parsed.bozo_exception}")

    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:atom": "http://www.w3.org/2005/Atom",
            "xmlns:content": "http://purl.org/rss/1.0/modules/content/",
            "xmlns:dc": "http://purl.org/dc/elements/1.1/",
            "xmlns:media": "http://search.yahoo.com/mrss/",
        },
    )
    channel = sub(rss, "channel")
    sub(channel, "title", CONFIG["feed_title"])
    sub(channel, "link", CONFIG["site_url"])
    sub(channel, "description", CONFIG["feed_description"])
    sub(channel, "language", "en-us")
    sub(channel, "lastBuildDate", format_datetime(datetime.now(timezone.utc)))
    sub(channel, "ttl", "15")

    github_repo = os.getenv("GITHUB_REPOSITORY", "")
    if "/" in github_repo:
        owner, repo = github_repo.split("/", 1)
        output_name = Path(CONFIG["output_file"]).name
        sub(
            channel,
            "atom:link",
            href=f"https://raw.githubusercontent.com/{owner}/{repo}/main/{output_name}",
            rel="self",
            type="application/rss+xml",
        )

    included = 0
    failures: list[str] = []
    for entry in parsed.entries:
        categories = {tag.get("term", "").lower() for tag in entry.get("tags", [])}
        wanted = CONFIG.get("category", "").strip().lower()
        if wanted and wanted not in categories:
            continue
        if included >= int(CONFIG.get("max_items", 20)):
            break

        url = entry.get("link", "").strip()
        if not url:
            continue
        try:
            full_html, page_image = clean_article_html(url)
        except Exception as exc:  # Keep the feed alive if one Wix page changes.
            failures.append(f"{url}: {exc}")
            fallback = entry.get("description", "")
            full_html = f"<p>{html.escape(BeautifulSoup(fallback, 'html.parser').get_text(' ', strip=True))}</p>"
            page_image = None

        full_html += f'<p><a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener"><strong>View this story on NewsRadio923.com</strong></a></p>'
        image_url = None
        image_type = None
        if entry.get("enclosures"):
            image_url = entry.enclosures[0].get("href")
            image_type = entry.enclosures[0].get("type")
        image_url = image_url or page_image
        image_type = image_type or (mimetypes.guess_type(image_url)[0] if image_url else None) or "image/jpeg"

        item = sub(channel, "item")
        sub(item, "title", entry.get("title", "Untitled"))
        sub(item, "link", url)
        sub(item, "guid", entry.get("id", url), isPermaLink="false")
        sub(item, "pubDate", entry.get("published", ""))
        if entry.get("author"):
            sub(item, "dc:creator", entry.author)
        sub(item, "category", CONFIG.get("category", "News"))
        sub(item, "description", text_preview(full_html))
        sub(item, "content:encoded", cdata(full_html))
        if image_url:
            sub(item, "enclosure", url=image_url, length="0", type=image_type)
            sub(item, "media:content", url=image_url, medium="image", type=image_type)
        included += 1
        time.sleep(0.15)

    if not included:
        raise RuntimeError("No matching stories were found; refusing to publish an empty feed")

    xml = ET.tostring(rss, encoding="unicode", xml_declaration=True)
    # RSS readers expect HTML inside these fields; wrap their escaped content in CDATA.
    for tag in ("description", "content:encoded"):
        pattern = rf"<{re.escape(tag)}>(.*?)</{re.escape(tag)}>"
        xml = re.sub(
            pattern,
            lambda match: f"<{tag}><![CDATA[{html.unescape(match.group(1)).replace(']]>', ']]]]><![CDATA[>')}]]></{tag}>",
            xml,
            flags=re.DOTALL,
        )

    output = ROOT / CONFIG["output_file"]
    output.write_text(xml + "\n", encoding="utf-8")
    print(f"Wrote {included} full stories to {output}")
    if failures:
        print("Warnings:", *failures, sep="\n- ", file=sys.stderr)
    return output


if __name__ == "__main__":
    build()

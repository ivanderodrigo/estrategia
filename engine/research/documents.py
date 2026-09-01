"""Small, dependency-free HTML/XML extraction primitives."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin


@dataclass(frozen=True)
class Link:
    url: str
    label: str


@dataclass(frozen=True)
class Document:
    url: str
    title: str
    text: str
    links: tuple[Link, ...]
    content_digest: str


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.links: list[tuple[str, list[str]]] = []
        self._title_depth = 0
        self._ignored_depth = 0
        self._active_link: tuple[str, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        if tag == "title":
            self._title_depth += 1
        if tag == "a":
            href = next((value for key, value in attrs if key.casefold() == "href" and value), None)
            if href:
                self._active_link = (href, [])

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "a" and self._active_link:
            self.links.append(self._active_link)
            self._active_link = None
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        self.parts.append(text)
        if self._title_depth:
            self.title_parts.append(text)
        if self._active_link:
            self._active_link[1].append(text)


def parse_document(raw: str, final_url: str, digest: str) -> Document:
    parser = TextExtractor()
    parser.feed(raw)
    links: list[Link] = []
    seen: set[str] = set()
    for href, label_parts in parser.links:
        target = urldefrag(urljoin(final_url, href))[0]
        if target in seen:
            continue
        seen.add(target)
        links.append(Link(target, " ".join(label_parts)[:180]))
    return Document(
        url=final_url,
        title=" ".join(parser.title_parts)[:240],
        text=" ".join(parser.parts)[:1_500_000],
        links=tuple(links[:300]),
        content_digest=digest,
    )


def sitemap_urls(raw: str) -> list[str]:
    tagged = re.findall(r"<loc>\s*(https?://[^<]+?)\s*</loc>", raw, flags=re.I)
    # ``Document.text`` intentionally strips markup, so accept whitespace-delimited
    # sitemap URLs too.  Trailing punctuation is not part of a URL.
    bare = [url.rstrip(".,;)") for url in re.findall(r"https?://[^\s<>]+", raw, flags=re.I)]
    return list(dict.fromkeys(tagged + bare))[:5_000]

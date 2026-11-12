"""Small, dependency-free HTML/XML extraction primitives."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlsplit


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
        self.brand_image_labels: list[str] = []
        self.manufacturer_section_images: list[str] = []
        self._in_manufacturer_section = False
        self._in_brand_inventory = False
        self.brand_inventory_labels: list[str] = []
        self.links: list[tuple[str, list[str]]] = []
        self._title_depth = 0
        self._ignored_depth = 0
        self._active_link: tuple[str, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        # Some distributors expose their entire vendor linecard as logo images.
        # Preserve visible alt labels only for explicit brand catalogue pages
        # when assembling the document; do not index decorative images globally.
        if tag == "img":
            alt = next((value for key, value in attrs if key.casefold() == "alt" and value), "")
            alt = re.sub(r"\s+", " ", alt).strip()
            if 2 <= len(alt) <= 70 and alt.casefold() not in {
                "logo", "imagen", "image", "photo", "foto", "banner", "icon", "icono",
            }:
                self.brand_image_labels.append(alt)
                if self._in_manufacturer_section:
                    self.manufacturer_section_images.append(alt)
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
        # Depau-style directories enumerate named manufacturers in a bounded
        # first-party "Estas son las marcas..." region, not image logos.
        if re.search(r"(?i)estas son las marcas que forman parte de nuestro cat[aá]logo", text):
            self._in_brand_inventory = True
        elif self._in_brand_inventory:
            if text.casefold() in {"volver", "nuestros clientes opinan", "localización"}:
                self._in_brand_inventory = False
            elif (2 <= len(text) <= 48 and 1 <= len(text.split()) <= 5
                  and text.upper() == text and any(ch.isalpha() for ch in text)):
                self.brand_inventory_labels.append(text)
        if re.search(r"(?i)\b(?:nuestros|nossos|our)\s+fabricantes\s+(?:que|that|para)\b", text):
            self._in_manufacturer_section = True
        elif re.search(r"(?i)\b(?:nuestros|nossos|our)\s+servicios\s+complementarios\b", text):
            self._in_manufacturer_section = False
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
    # Only explicit manufacturer directories (or manufacturer-labelled sections)
    # may turn image alt labels into candidate brand names. Decorative images on
    # general service/news pages are never catalogue evidence.
    page_path = urlsplit(final_url).path.casefold()
    page_title = " ".join(parser.title_parts).casefold()
    catalogue_page = (
        any(tag in page_path for tag in (
            "/fabricant", "/marcas", "/brands", "/vendors", "/line-card",
            "/linecard", "/catalogo-marcas", "/nossas-marcas", "/site/vendor/",
        ))
        or any(label in page_title for label in (
            "portfolio de fabricantes", "catálogo de fabricantes",
            "catalogo de fabricantes", "lista de fabricantes",
        ))
    )
    logo_labels = (
        parser.brand_image_labels if catalogue_page
        else parser.manufacturer_section_images
    )
    if catalogue_page:
        logo_labels = [*logo_labels, *parser.brand_inventory_labels]
    return Document(
        url=final_url,
        title=" ".join(parser.title_parts)[:240],
        text=(
            " ".join(parser.parts)
            + (" Marcas y fabricantes: " + " / ".join(dict.fromkeys(logo_labels[:1000]))
               if logo_labels else "")
        )[:1_500_000],
        links=tuple(links[:1500]),
        content_digest=digest,
    )


def sitemap_urls(raw: str) -> list[str]:
    tagged = re.findall(r"<loc>\s*(https?://[^<]+?)\s*</loc>", raw, flags=re.I)
    # ``Document.text`` intentionally strips markup, so accept whitespace-delimited
    # sitemap URLs too.  Trailing punctuation is not part of a URL.
    bare = [url.rstrip(".,;)") for url in re.findall(r"https?://[^\s<>]+", raw, flags=re.I)]
    return list(dict.fromkeys(tagged + bare))[:5_000]

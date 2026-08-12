"""Small HTML parsers shared by provider and site adapters."""

from __future__ import annotations

from html.parser import HTMLParser


class BasicHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.iframes: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict(attrs)

        if tag == "title":
            self.in_title = True
        elif tag == "iframe":
            src = attrs.get("src") or attrs.get("data-lazy-src")
            if src:
                self.iframes.append(src)

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if not self.in_title:
            return

        value = data.strip()
        if value:
            self.title_parts.append(value)

    @property
    def title(self) -> str | None:
        value = " ".join(self.title_parts).strip()
        return value or None

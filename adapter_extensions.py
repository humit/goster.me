#!/usr/bin/env python3

from __future__ import annotations

import adapters


_ORIGINAL_ILK_OKUL_RESOLVE = adapters.IlkOkulNativeAdapter.resolve


def _resolve_ilk_okul_with_fast_reading(self, url: str):
    """Extend the conservative İlk-Okul native fingerprints.

    Current /1912/hizliokuma/icerik/... pages expose intro, game, result,
    report and transition states as siblings rather than under one stable
    application container.  Preserve the source body so every state remains
    available; the sandbox renderer removes advertising/tracking elements.
    """
    try:
        return _ORIGINAL_ILK_OKUL_RESOLVE(self, url)
    except adapters.NotApplicable:
        pass

    url = adapters.normalized_url(url)

    if not self.match(url):
        raise adapters.NotApplicable()

    final_url, document = adapters.fetch_html(
        url,
        allowed_hosts=self.SOURCE_HOSTS,
    )

    parser = adapters.NativeGameFingerprintParser()
    parser.feed(document)

    required_ids = {
        "sahne1",
        "sahne2",
        "app",
        "sonucsayfasi",
        "app1",
        "sonucsayfasi1",
        "gecisAnimasyon",
        "gecisAnimasyon2",
    }
    required_classes = {
        "ortega",
        "result-card",
        "report-card",
    }

    if not (
        required_ids.issubset(parser.ids)
        and required_classes.issubset(parser.classes)
    ):
        raise adapters.NotApplicable(
            "No supported İlk-Okul native game found."
        )

    return adapters.ResolvedContent(
        kind="native-exercise",
        provider="ilk-okul-native",
        source_url=url,
        title=parser.title,
        content_url=final_url,
        adapter=self.name,
        render_mode="isolate",
        selector="body",
    )


def install() -> None:
    if adapters.IlkOkulNativeAdapter.resolve is _resolve_ilk_okul_with_fast_reading:
        return

    adapters.IlkOkulNativeAdapter.resolve = _resolve_ilk_okul_with_fast_reading


install()

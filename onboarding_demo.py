from __future__ import annotations


DEMO_ROUTE = "/demo/activity"


def render_activity_demo() -> str:
    """Render a fully local before/after onboarding prototype.

    The prototype intentionally does not load or imitate a third-party runtime.
    It demonstrates the product transformation with a generic education-page
    mockup whose activity remains constant while surrounding page chrome is
    hidden in the goster.me state.
    """
    return """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>goster.me — etkileşimli demo</title>
<style>
:root {
    color-scheme: light dark;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; background: Canvas; color: CanvasText; }
.demo-shell { max-width: 880px; margin: 0 auto; padding: 20px; }
.demo-intro { max-width: 650px; margin-bottom: 18px; }
.demo-intro h1 { margin-bottom: 8px; }
.demo-intro p { line-height: 1.55; }
.demo-toggle {
    position: sticky;
    top: 10px;
    z-index: 10;
    display: inline-flex;
    gap: 4px;
    padding: 4px;
    border: 1px solid currentColor;
    border-radius: 999px;
    background: Canvas;
}
.demo-toggle button {
    border: 0;
    border-radius: 999px;
    padding: 9px 14px;
    font: inherit;
    cursor: pointer;
}
.demo-toggle button[aria-pressed="true"] { font-weight: 700; text-decoration: underline; }
.demo-stage { margin-top: 16px; border: 1px solid color-mix(in srgb, currentColor 24%, transparent); border-radius: 18px; overflow: hidden; }
.source-page { min-height: 720px; background: Canvas; }
.source-header { padding: 14px 18px; border-bottom: 1px solid color-mix(in srgb, currentColor 20%, transparent); display: flex; justify-content: space-between; gap: 12px; }
.source-brand { font-weight: 800; }
.source-nav { display: flex; gap: 12px; font-size: .9rem; opacity: .72; }
.source-hero { padding: 26px 18px; background: color-mix(in srgb, CanvasText 7%, Canvas); }
.source-grid { display: grid; grid-template-columns: minmax(0, 1fr) 220px; gap: 18px; padding: 18px; }
.source-copy p, .source-side p { line-height: 1.55; }
.source-card, .source-side { border: 1px solid color-mix(in srgb, currentColor 18%, transparent); border-radius: 14px; padding: 16px; }
.activity-wrap { margin: 32px 0; }
.activity-label { margin: 0 0 8px; font-size: .85rem; opacity: .65; }
.activity {
    min-height: 310px;
    border-radius: 18px;
    border: 2px solid currentColor;
    padding: 24px;
    display: grid;
    place-items: center;
    text-align: center;
    background: color-mix(in srgb, CanvasText 4%, Canvas);
}
.activity-inner { max-width: 420px; }
.activity-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 16px; }
.activity-actions button { font: inherit; padding: 9px 12px; }
.demo-stage[data-mode="clean"] .source-header,
.demo-stage[data-mode="clean"] .source-hero,
.demo-stage[data-mode="clean"] .source-side,
.demo-stage[data-mode="clean"] .source-copy > :not(.activity-wrap) { display: none; }
.demo-stage[data-mode="clean"] .source-grid { display: block; padding: 0; }
.demo-stage[data-mode="clean"] .source-card { border: 0; padding: 0; }
.demo-stage[data-mode="clean"] .activity-wrap { margin: 0; }
.demo-stage[data-mode="clean"] .activity-label { display: none; }
.demo-stage[data-mode="clean"] .activity { min-height: 70vh; border: 0; border-radius: 0; }
.demo-explainer { margin-top: 14px; min-height: 3em; line-height: 1.5; }
.demo-back { display: inline-block; margin-top: 18px; }
@media (max-width: 680px) {
    .demo-shell { padding: 14px; }
    .source-grid { grid-template-columns: 1fr; }
    .source-nav { display: none; }
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; }
}
</style>
</head>
<body>
<main class="demo-shell">
    <section class="demo-intro" aria-labelledby="demo-title">
        <h1 id="demo-title">İçerik aynı. Etrafı değişiyor.</h1>
        <p>
            Aşağıdaki örnekte önce normal bir eğitim sayfasını gör. Sayfayı kaydırıp
            etkinliği bulabilirsin. Sonra <strong>goster.me</strong> görünümüne geç:
            etkinlik aynı kalırken onu çevreleyen sayfa kalabalığı ortadan kalkar.
        </p>
    </section>

    <div class="demo-toggle" role="group" aria-label="Demo görünümü">
        <button type="button" data-demo-mode="source" aria-pressed="true">Göster</button>
        <button type="button" data-demo-mode="clean" aria-pressed="false">goster.me</button>
    </div>

    <section class="demo-stage" data-mode="source" aria-live="polite">
        <div class="source-page">
            <header class="source-header">
                <span class="source-brand">Örnek Eğitim Sitesi</span>
                <nav class="source-nav" aria-label="Örnek site menüsü">
                    <span>Anasayfa</span><span>Etkinlikler</span><span>Testler</span><span>İletişim</span>
                </nav>
            </header>

            <div class="source-hero">
                <strong>Haftanın etkinlikleri</strong>
                <p>Sınıf düzeyine göre etkinlik, test ve çalışma içerikleri.</p>
            </div>

            <div class="source-grid">
                <article class="source-card source-copy">
                    <h2>2. sınıf matematik etkinliği</h2>
                    <p>Bu sayfada etkinliğin öncesinde açıklamalar, bağlantılar ve başka içerikler bulunur.</p>
                    <p>Normal bir ziyaretçi asıl etkinliğe ulaşmak için sayfayı tarar ve aşağı kaydırır.</p>

                    <div class="activity-wrap">
                        <p class="activity-label">Sayfaya gömülü asıl etkinlik</p>
                        <div class="activity" tabindex="0">
                            <div class="activity-inner">
                                <strong>Toplama alıştırması</strong>
                                <p>8 + 7 kaç eder?</p>
                                <div class="activity-actions">
                                    <button type="button">13</button>
                                    <button type="button">15</button>
                                    <button type="button">17</button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <h3>Benzer içerikler</h3>
                    <p>Diğer testler, çalışma kâğıtları, kategori bağlantıları ve sayfa altı içerikleri burada devam eder.</p>
                    <p>Bu alanlar etkinliğin kendisi değildir; yalnızca onu çevreleyen kaynak sayfanın parçalarıdır.</p>
                </article>

                <aside class="source-side" aria-label="Örnek yan içerik">
                    <strong>Popüler içerikler</strong>
                    <p>Türkçe testi</p>
                    <p>Matematik çalışma kâğıdı</p>
                    <p>Haftalık program</p>
                    <hr>
                    <strong>Kategoriler</strong>
                    <p>1. sınıf<br>2. sınıf<br>3. sınıf<br>4. sınıf</p>
                </aside>
            </div>
        </div>
    </section>

    <p class="demo-explainer" data-demo-explainer>
        <strong>Göster:</strong> Etkinlik, kaynak sayfanın menüleri ve diğer içerikleri arasında gömülü.
    </p>
    <a class="demo-back" href="/">← Kendi bağlantını dene</a>
</main>
<script>
(() => {
    const stage = document.querySelector('[data-mode]');
    const explainer = document.querySelector('[data-demo-explainer]');
    const buttons = [...document.querySelectorAll('[data-demo-mode]')];

    function setMode(mode) {
        stage.dataset.mode = mode;
        for (const button of buttons) {
            button.setAttribute('aria-pressed', String(button.dataset.demoMode === mode));
        }
        explainer.innerHTML = mode === 'clean'
            ? '<strong>goster.me:</strong> Aynı etkinlik kaldı; kaynak sayfanın geri kalanı gösterilmiyor.'
            : '<strong>Göster:</strong> Etkinlik, kaynak sayfanın menüleri ve diğer içerikleri arasında gömülü.';
        if (mode === 'clean') {
            stage.scrollIntoView({block: 'start'});
        }
    }

    for (const button of buttons) {
        button.addEventListener('click', () => setMode(button.dataset.demoMode));
    }
})();
</script>
</body>
</html>
"""

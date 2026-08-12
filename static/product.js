(() => {
    const home = document.querySelector(".product-home-minimal");

    if (home) {
        const button = home.querySelector(".url-submit");
        if (button) {
            button.textContent = "→";
            button.setAttribute("aria-label", "Bağlantıyı aç");
            button.setAttribute("title", "Bağlantıyı aç");
        }

        const style = document.createElement("style");
        style.textContent = `
            :root {
                --g-bg: #f4f6f7;
                --g-surface: transparent;
                --g-surface-soft: rgba(29, 41, 57, .045);
                --g-border: #cfd6dc;
                --g-text: #20272d;
                --g-muted: #7d8992;
                --g-accent: #5d6f82;
                --g-accent-hover: #46586b;
                --g-accent-ink: #ffffff;
                --g-focus: rgba(93, 111, 130, .22);
            }

            @media (prefers-color-scheme: dark) {
                :root {
                    --g-bg: #111417;
                    --g-surface: transparent;
                    --g-surface-soft: rgba(225, 232, 237, .05);
                    --g-border: #303840;
                    --g-text: #e8ecef;
                    --g-muted: #87929a;
                    --g-accent: #9baebb;
                    --g-accent-hover: #b1c0ca;
                    --g-accent-ink: #162028;
                    --g-focus: rgba(155, 174, 187, .25);
                }
            }

            .product-home-minimal {
                display: block !important;
                position: relative;
                min-height: 100dvh;
                padding: 0 1.15rem max(1rem, env(safe-area-inset-bottom)) !important;
            }

            .minimal-shell {
                width: 100%;
                min-height: 100dvh;
                transform: none !important;
                display: flex;
                flex-direction: column;
                justify-content: flex-end;
                padding: 0 0 max(8.5rem, 24vh);
            }

            .minimal-wordmark {
                order: 3;
                margin: 1.1rem 0 0 auto !important;
                color: var(--g-muted) !important;
                font-size: .76rem !important;
                font-weight: 540 !important;
                letter-spacing: -.012em !important;
            }

            .product-url-form {
                order: 1;
                grid-template-columns: minmax(0, 1fr) 2.7rem !important;
                gap: 0 !important;
                padding: 0 !important;
                border: 0 !important;
                border-bottom: 1px solid var(--g-border) !important;
                border-radius: 0 !important;
                background: transparent !important;
            }

            .product-url-form input {
                height: 3.2rem !important;
                min-height: 3.2rem !important;
                padding: 0 .05rem !important;
                border-radius: 0 !important;
                background: transparent !important;
                font-size: 1.02rem !important;
                font-weight: 430 !important;
                letter-spacing: -.012em !important;
            }

            .product-url-form input::placeholder {
                color: color-mix(in srgb, var(--g-muted) 88%, var(--g-text)) !important;
                opacity: .9 !important;
            }

            .product-url-form input:focus,
            .product-url-form input:focus-visible {
                background: transparent !important;
                box-shadow: none !important;
            }

            .product-url-form button {
                width: 2.7rem !important;
                min-width: 2.7rem !important;
                height: 3.2rem !important;
                min-height: 3.2rem !important;
                padding: 0 !important;
                border-radius: 0 !important;
                background: transparent !important;
                color: var(--g-accent) !important;
                font-size: 1.25rem !important;
                font-weight: 350 !important;
            }

            .product-url-form button:hover {
                background: var(--g-surface-soft) !important;
            }

            .minimal-links {
                order: 2;
                justify-content: flex-start;
                gap: .95rem !important;
                margin-top: .82rem !important;
                font-size: .7rem !important;
            }

            .minimal-links a {
                color: var(--g-muted) !important;
            }

            @media (min-width: 700px) {
                .minimal-shell {
                    max-width: 34rem;
                    margin: 0 auto;
                    justify-content: center;
                    padding-bottom: 0;
                }
            }
        `;
        document.head.appendChild(style);

        const tag = document.createElement("div");
        tag.textContent = "tool-first · v3";
        tag.setAttribute("aria-hidden", "true");
        Object.assign(tag.style, {
            position: "fixed",
            left: "50%",
            bottom: "max(.55rem, env(safe-area-inset-bottom))",
            transform: "translateX(-50%)",
            color: "var(--g-muted)",
            opacity: ".42",
            fontSize: "10px",
            lineHeight: "1",
            letterSpacing: ".06em",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
            pointerEvents: "none",
            zIndex: "1"
        });
        document.body.appendChild(tag);
    }

    const toast = document.createElement("div");
    toast.className = "toast";
    toast.hidden = true;
    document.body.appendChild(toast);

    let toastTimer = null;

    function showToast(message) {
        toast.textContent = message;
        toast.hidden = false;
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
            toast.hidden = true;
        }, 1500);
    }

    function actionUrl(element) {
        const value = element.dataset.url;
        if (!value) {
            return location.href;
        }
        return new URL(value, location.origin).href;
    }

    function legacyCopy(text) {
        const area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        area.style.pointerEvents = "none";
        document.body.appendChild(area);
        area.select();
        area.setSelectionRange(0, text.length);

        let ok = false;
        try {
            ok = document.execCommand("copy");
        } catch (_) {
            ok = false;
        }

        area.remove();
        return ok;
    }

    async function copyText(text) {
        if (navigator.clipboard && window.isSecureContext) {
            try {
                await navigator.clipboard.writeText(text);
                return true;
            } catch (_) {}
        }
        return legacyCopy(text);
    }

    function analyticsCode(element) {
        const path = new URL(actionUrl(element)).pathname;
        const match = path.match(/^\/([a-z0-9]{4,16})$/);
        return match ? match[1] : null;
    }

    function recordProductEvent(event, element) {
        const code = analyticsCode(element);
        if (!code) return;
        fetch("/api/events", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ event, code }),
            keepalive: true,
            credentials: "same-origin"
        }).catch(() => {});
    }

    async function handleCopy(element) {
        const ok = await copyText(actionUrl(element));
        if (ok) recordProductEvent("copy_click", element);
        showToast(ok ? "Bağlantı kopyalandı" : "Bağlantı kopyalanamadı");
    }

    async function handleShare(element) {
        const url = actionUrl(element);
        const title = element.dataset.title || document.title;

        if (navigator.share) {
            try {
                await navigator.share({ title, url });
                recordProductEvent("share_click", element);
                return;
            } catch (error) {
                if (error && error.name === "AbortError") {
                    return;
                }
            }
        }

        const ok = await copyText(url);
        showToast(ok ? "Paylaşım desteklenmedi; bağlantı kopyalandı" : "Bu tarayıcıda paylaşım kullanılamıyor");
    }

    function closeCompactViewerMenus(except = null) {
        document.querySelectorAll("details.viewer-compact-menu[open]").forEach(menu => {
            if (menu !== except) menu.removeAttribute("open");
        });
    }

    document.addEventListener("click", async event => {
        const compactMenu = event.target.closest("details.viewer-compact-menu");

        // When an open menu owns the transparent full-screen dismiss layer,
        // clicks on that layer target the <details> element itself. Close the
        // menu before the iframe/content receives an accidental interaction.
        if (compactMenu && compactMenu.open && event.target === compactMenu) {
            compactMenu.removeAttribute("open");
            return;
        }

        if (!compactMenu) {
            closeCompactViewerMenus();
        }

        const action = event.target.closest("[data-action]");
        if (!action) return;

        const name = action.dataset.action;
        if (name === "copy") {
            event.preventDefault();
            await handleCopy(action);
            return;
        }
        if (name === "share") {
            event.preventDefault();
            await handleShare(action);
        }
    });

    document.addEventListener("keydown", event => {
        if (event.key !== "Escape") return;
        closeCompactViewerMenus();
    });
})();

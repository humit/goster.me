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
                --g-bg: #f3f4f2;
                --g-surface: transparent;
                --g-surface-soft: rgba(38, 48, 56, .045);
                --g-border: #cfd4d1;
                --g-text: #252b2f;
                --g-muted: #7a8388;
                --g-accent: #667885;
                --g-accent-hover: #52636f;
                --g-accent-ink: #ffffff;
                --g-focus: rgba(102, 120, 133, .2);
            }

            @media (prefers-color-scheme: dark) {
                :root {
                    --g-bg: #111315;
                    --g-surface: transparent;
                    --g-surface-soft: rgba(230, 235, 238, .045);
                    --g-border: #343a3e;
                    --g-text: #e6e9e8;
                    --g-muted: #91999e;
                    --g-accent: #a5b2ba;
                    --g-accent-hover: #bcc5ca;
                    --g-accent-ink: #161c20;
                    --g-focus: rgba(165, 178, 186, .24);
                }
            }

            .product-home-minimal {
                display: block !important;
                position: relative;
                min-height: 100dvh;
                padding:
                    max(.75rem, env(safe-area-inset-top))
                    1.15rem
                    max(1.25rem, env(safe-area-inset-bottom)) !important;
            }

            .minimal-shell {
                width: 100%;
                min-height: calc(100dvh - max(.75rem, env(safe-area-inset-top)) - max(1.25rem, env(safe-area-inset-bottom)));
                transform: none !important;
                display: grid;
                grid-template-rows: 1fr auto auto;
                align-items: end;
            }

            .product-url-form {
                grid-row: 1;
                align-self: end;
                width: 100%;
                margin-bottom: clamp(8rem, 24vh, 12rem) !important;
                display: grid !important;
                grid-template-columns: minmax(0, 1fr) 2.7rem !important;
                gap: 0 !important;
                padding: 0 !important;
                border: 0 !important;
                border-bottom: 1px solid var(--g-border) !important;
                border-radius: 0 !important;
                background: transparent !important;
            }

            .product-url-form input {
                height: 3.05rem !important;
                min-height: 3.05rem !important;
                padding: 0 .05rem !important;
                border-radius: 0 !important;
                background: transparent !important;
                color: var(--g-text) !important;
                font-size: 1.02rem !important;
                font-weight: 430 !important;
                letter-spacing: -.015em !important;
            }

            .product-url-form input::placeholder {
                color: var(--g-muted) !important;
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
                height: 3.05rem !important;
                min-height: 3.05rem !important;
                padding: 0 !important;
                border-radius: 0 !important;
                background: transparent !important;
                color: var(--g-accent) !important;
                font-size: 1.2rem !important;
                font-weight: 350 !important;
                line-height: 1 !important;
            }

            .product-url-form button:hover {
                background: var(--g-surface-soft) !important;
            }

            .minimal-links {
                grid-row: 3;
                margin: 0 !important;
                display: flex;
                align-items: center;
                gap: .95rem !important;
                font-size: .7rem !important;
            }

            .minimal-links a {
                color: var(--g-muted) !important;
                text-decoration: none !important;
            }

            .minimal-wordmark {
                grid-row: 3;
                justify-self: end;
                align-self: center;
                margin: 0 !important;
                color: var(--g-muted) !important;
                font-size: .72rem !important;
                font-weight: 540 !important;
                letter-spacing: -.01em !important;
                opacity: .86;
                pointer-events: none;
            }

            .minimal-shell {
                grid-template-columns: 1fr auto;
                column-gap: 1rem;
            }

            .product-url-form {
                grid-column: 1 / -1;
            }

            .minimal-links {
                grid-column: 1;
            }

            .minimal-wordmark {
                grid-column: 2;
            }

            @media (max-width: 430px) {
                .product-url-form {
                    margin-bottom: clamp(7rem, 21vh, 9.5rem) !important;
                }
            }

            @media (min-width: 700px) {
                .minimal-shell {
                    max-width: 34rem;
                    margin: 0 auto;
                }

                .product-url-form {
                    align-self: center;
                    margin-bottom: 0 !important;
                }
            }
        `;
        document.head.appendChild(style);
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

    async function handleCopy(element) {
        const ok = await copyText(actionUrl(element));
        showToast(ok ? "Bağlantı kopyalandı" : "Bağlantı kopyalanamadı");
    }

    async function handleShare(element) {
        const url = actionUrl(element);
        const title = element.dataset.title || document.title;

        if (navigator.share) {
            try {
                await navigator.share({ title, url });
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

    document.addEventListener("click", async event => {
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
})();

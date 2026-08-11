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
                --g-bg: #f3f0e8;
                --g-surface: transparent;
                --g-surface-soft: rgba(74, 65, 48, .06);
                --g-border: #cfc7b8;
                --g-text: #28251f;
                --g-muted: #7b7468;
                --g-accent: #b86b4b;
                --g-accent-hover: #a85e40;
                --g-accent-ink: #fffaf4;
                --g-focus: rgba(184, 107, 75, .22);
            }

            @media (prefers-color-scheme: dark) {
                :root {
                    --g-bg: #171613;
                    --g-surface: transparent;
                    --g-surface-soft: rgba(244, 236, 220, .055);
                    --g-border: #3a352d;
                    --g-text: #eee8dc;
                    --g-muted: #9c9486;
                    --g-accent: #d58b68;
                    --g-accent-hover: #e19a77;
                    --g-accent-ink: #24150f;
                    --g-focus: rgba(213, 139, 104, .28);
                }
            }

            .product-home-minimal {
                display: flex !important;
                align-items: center;
                justify-content: center;
            }

            .minimal-shell {
                transform: translateY(-3vh) !important;
                max-width: 31rem;
            }

            .minimal-wordmark {
                margin-bottom: 1.2rem !important;
                font-family: Georgia, "Times New Roman", serif !important;
                font-size: 1.55rem !important;
                font-weight: 400 !important;
                letter-spacing: -.025em !important;
            }

            .product-url-form {
                grid-template-columns: minmax(0, 1fr) 2.55rem !important;
                gap: 0 !important;
                padding: 0 !important;
                border: 0 !important;
                border-bottom: 1px solid var(--g-border) !important;
                border-radius: 0 !important;
                background: transparent !important;
            }

            .product-url-form input {
                height: 3rem !important;
                min-height: 3rem !important;
                padding: 0 .1rem !important;
                border-radius: 0 !important;
                font-family: Georgia, "Times New Roman", serif !important;
                font-size: 1rem !important;
            }

            .product-url-form input:focus {
                background: transparent !important;
            }

            .product-url-form input:focus-visible {
                box-shadow: none !important;
            }

            .product-url-form button {
                min-width: 2.55rem !important;
                width: 2.55rem !important;
                height: 3rem !important;
                min-height: 3rem !important;
                padding: 0 !important;
                border-radius: 0 !important;
                background: transparent !important;
                color: var(--g-accent) !important;
                font-size: 1.35rem !important;
                font-weight: 400 !important;
            }

            .product-url-form button:hover {
                background: var(--g-surface-soft) !important;
            }

            .minimal-links {
                margin-top: .8rem !important;
                gap: 1rem !important;
                font-family: Georgia, "Times New Roman", serif !important;
                font-size: .78rem !important;
            }

            @media (max-width: 430px) {
                .minimal-shell {
                    transform: translateY(-9vh) !important;
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

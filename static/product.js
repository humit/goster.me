(() => {
    const home = document.querySelector(".product-home-minimal");

    if (home) {
        const form = home.querySelector(".product-url-form");
        const input = form ? form.querySelector('input[name="url"]') : null;

        if (form && input) {
            // Browser-native type=url messages vary by browser and locale and,
            // on some mobile/desktop browsers, can still appear even with
            // noValidate. Keep the URL keyboard via inputmode=url, but switch
            // constraint validation to text so goster.me fully owns the UX.
            input.type = "text";
            form.noValidate = true;

            const error = document.createElement("p");
            error.className = "url-form-error";
            error.setAttribute("role", "alert");
            error.hidden = true;
            form.insertAdjacentElement("afterend", error);

            function hideUrlError() {
                error.hidden = true;
                error.textContent = "";
                input.removeAttribute("aria-invalid");
            }

            function showUrlError(message) {
                error.textContent = message;
                error.hidden = false;
                input.setAttribute("aria-invalid", "true");
                input.focus();
            }

            function normalizedHttpUrl(value) {
                const normalized = value.trim();
                if (!normalized) return null;

                try {
                    const parsed = new URL(normalized);
                    if (
                        (parsed.protocol !== "http:" && parsed.protocol !== "https:")
                        || !parsed.hostname
                    ) {
                        return null;
                    }
                } catch (_) {
                    return null;
                }

                return normalized;
            }

            input.addEventListener("input", hideUrlError);
            input.addEventListener("paste", () => {
                // Let the browser perform the paste first, then normalize the
                // common whitespace copied with URLs from messages/documents.
                setTimeout(() => {
                    input.value = input.value.trim();
                    hideUrlError();
                }, 0);
            });

            form.addEventListener("submit", event => {
                const raw = input.value;
                const normalized = normalizedHttpUrl(raw);

                if (!raw.trim()) {
                    event.preventDefault();
                    showUrlError("Bir bağlantı yapıştırın.");
                    return;
                }

                if (!normalized) {
                    event.preventDefault();
                    showUrlError(
                        "Geçerli bir web bağlantısı yapıştırın (http:// veya https:// ile başlamalı)."
                    );
                    return;
                }

                input.value = normalized;
                hideUrlError();
            });
        }

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

    function shareMessage(title, url) {
        return `${title}\n${url}\n\n[ dikkat dağıtıcı öğelerden arındırılmış içerik - www.goster.me ]`;
    }

    async function handleShare(element) {
        const url = actionUrl(element);
        const title = element.dataset.title || document.title;
        const text = shareMessage(title, url);

        if (navigator.share) {
            try {
                await navigator.share({ text });
                recordProductEvent("share_click", element);
                return;
            } catch (error) {
                if (error && error.name === "AbortError") {
                    return;
                }
            }
        }

        const ok = await copyText(text);
        showToast(ok ? "Paylaşım metni kopyalandı" : "Bu tarayıcıda paylaşım kullanılamıyor");
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

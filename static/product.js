(() => {
    const home = document.querySelector(".product-home-minimal");
    if (home) {
        const tag = document.createElement("div");
        tag.textContent = "base · v1";
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
            } catch (_) {
                // Fall through for browsers / policies that expose the API
                // but reject the write.
            }
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
        showToast(
            ok
                ? "Paylaşım desteklenmedi; bağlantı kopyalandı"
                : "Bu tarayıcıda paylaşım kullanılamıyor"
        );
    }

    document.addEventListener("click", async event => {
        const action = event.target.closest("[data-action]");
        if (!action) {
            return;
        }

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

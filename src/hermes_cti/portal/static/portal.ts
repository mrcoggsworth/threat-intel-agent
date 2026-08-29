/** Progressive enhancement: dialog lifecycle, backdrop dismissal, keyboard shortcuts, history popstate, theme switching, and clipboard copying. */
(function () {
  const validThemes = [
    "traditional-light",
    "traditional-dark",
    "cyberpunk",
    "synthwave",
    "tokyo-night",
    "darcula",
    "monokai",
    "synthwave-metal",
    "matrix"
  ];

  function applySavedTheme(): void {
    try {
      const saved = localStorage.getItem("hermes-theme");
      if (saved && validThemes.includes(saved)) {
        document.documentElement.setAttribute("data-theme", saved);
      }
    } catch {
      // Ignore localStorage access errors
    }
  }

  // Apply theme immediately on script execution
  applySavedTheme();

  const shell = document.querySelector<HTMLElement>("#report-dialog");
  let returnFocus: HTMLElement | null = null;

  function closeDialog(): void {
    if (!shell) return;
    shell.hidden = true;
    shell.setAttribute("aria-hidden", "true");
    shell.replaceChildren();
    if (returnFocus) {
      returnFocus.focus();
      returnFocus = null;
    }
  }

  // Expose global helpers for coordination with portal-enhance
  (window as unknown as Record<string, unknown>).__hermesCloseDialog = closeDialog;
  (window as unknown as Record<string, unknown>).__hermesSetReturnFocus = function (el: HTMLElement | null) {
    returnFocus = el;
  };

  // Initialize theme selector
  function initThemeSelector(): void {
    const selector = document.querySelector<HTMLSelectElement>("#theme-selector");
    if (!selector) return;

    try {
      const saved = localStorage.getItem("hermes-theme") || "traditional-light";
      if (validThemes.includes(saved)) {
        selector.value = saved;
        document.documentElement.setAttribute("data-theme", saved);
      }
    } catch {
      // Ignore
    }

    selector.addEventListener("change", () => {
      const theme = selector.value;
      document.documentElement.setAttribute("data-theme", theme);
      try {
        localStorage.setItem("hermes-theme", theme);
      } catch {
        // Ignore
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initThemeSelector);
  } else {
    initThemeSelector();
  }

  // Copy text to clipboard with fallback
  async function copyText(text: string): Promise<boolean> {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch {
      // Fallback below
    }

    try {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(textarea);
      return ok;
    } catch {
      return false;
    }
  }

  document.addEventListener("click", async (event: MouseEvent) => {
    const target = event.target as HTMLElement | null;
    if (!target) return;

    // Handle copy-to-clipboard button
    const copyBtn = target.closest<HTMLButtonElement>("[data-copy-target]");
    if (copyBtn) {
      event.preventDefault();
      const card = copyBtn.closest(".detection, .hunt-query-card, [data-copy-container]");
      const codeEl = card ? card.querySelector("pre code, pre, code") : null;
      const textToCopy = codeEl ? (codeEl.textContent || "") : "";

      if (!textToCopy) return;

      const success = await copyText(textToCopy);
      if (success) {
        const labelEl = copyBtn.querySelector<HTMLElement>(".copy-label");
        const prevLabel = labelEl ? labelEl.textContent : "Copy";
        const prevClass = copyBtn.className;

        if (labelEl) labelEl.textContent = "Copied!";
        copyBtn.classList.add("bg-emerald-800", "text-emerald-200", "border-emerald-600");

        setTimeout(() => {
          if (labelEl) labelEl.textContent = prevLabel;
          copyBtn.className = prevClass;
        }, 2000);
      }
      return;
    }

    // Handle dialog close button and backdrop
    if (target.closest("[data-dialog-close]") || target.classList.contains("dialog-backdrop")) {
      event.preventDefault();
      closeDialog();
      if (window.location.search.includes("ioc=") || window.location.search.includes("attack=") || window.location.pathname.match(/\/(hunt|remediation|detections)$/)) {
        history.back();
      }
    }
  });

  document.addEventListener("keydown", (event: KeyboardEvent) => {
    if (event.key === "Escape" && shell && !shell.hidden) {
      closeDialog();
      if (window.location.search.includes("ioc=") || window.location.search.includes("attack=") || window.location.pathname.match(/\/(hunt|remediation|detections)$/)) {
        history.back();
      }
    }
  });

  window.addEventListener("popstate", () => {
    if (shell && !shell.hidden) {
      closeDialog();
    }
  });
})();

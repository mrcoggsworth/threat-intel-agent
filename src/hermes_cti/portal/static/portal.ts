/** Progressive enhancement: dialog lifecycle, backdrop dismissal, keyboard shortcuts, history popstate, and theme switching. */
(function () {
  const validThemes = [
    "traditional-light",
    "traditional-dark",
    "cyberpunk",
    "synthwave",
    "tokyo-night",
    "darcula",
    "monokai",
    "synthwave-metal"
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

  document.addEventListener("click", (event: MouseEvent) => {
    const target = event.target as HTMLElement | null;
    if (!target) return;

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

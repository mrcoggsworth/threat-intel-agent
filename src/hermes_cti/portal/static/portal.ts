/** Progressive enhancement: dialog lifecycle, backdrop dismissal, keyboard shortcuts, and history popstate. */
(function () {
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

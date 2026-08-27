/** Progressive enhancement only: dialog focus, history, and HTMX-compatible links. */
const dialogShell = document.querySelector<HTMLElement>("#report-dialog");
let returnFocus: HTMLElement | null = null;
let historyPushed = false;

(window as any)._setModalHistoryPushed = (pushed: boolean) => {
  historyPushed = pushed;
};

function closeDialog(): void {
  if (!dialogShell) return;
  dialogShell.hidden = true;
  dialogShell.setAttribute("aria-hidden", "true");
  dialogShell.replaceChildren();
  returnFocus?.focus();
  returnFocus = null;
  if (historyPushed) {
    historyPushed = false;
    history.back();
  }
}

function openDialog(link: HTMLElement): void {
  if (!dialogShell) return;
  returnFocus = link;
  dialogShell.hidden = false;
  dialogShell.setAttribute("aria-hidden", "false");
  const noHistory = link.getAttribute("data-no-history") === "true";
  const href = link.getAttribute("href");
  if (!noHistory && href && href !== window.location.href && !href.startsWith("javascript:")) {
    historyPushed = true;
    history.pushState({ report: href }, "", href);
  }
  dialogShell.querySelector<HTMLElement>("[data-dialog]")?.focus();
}

document.addEventListener("click", (event) => {
  const target = event.target as HTMLElement;
  const link = target.closest<HTMLElement>("[data-report-link]");
  if (link && dialogShell && !dialogShell.hidden) return;
  if (link && dialogShell) openDialog(link);
  if (target.closest("[data-dialog-close]")) {
    event.preventDefault();
    closeDialog();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && dialogShell && !dialogShell.hidden) {
    closeDialog();
  }
});

window.addEventListener("popstate", () => {
  if (dialogShell && !location.pathname.startsWith("/reports/")) closeDialog();
});

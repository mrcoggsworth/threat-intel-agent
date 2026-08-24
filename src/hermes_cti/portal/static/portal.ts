/** Progressive enhancement only: dialog focus, history, and HTMX-compatible links. */
const dialogShell = document.querySelector<HTMLElement>("#report-dialog");
let returnFocus: HTMLElement | null = null;

function closeDialog(): void {
  if (!dialogShell) return;
  dialogShell.hidden = true;
  dialogShell.setAttribute("aria-hidden", "true");
  dialogShell.replaceChildren();
  returnFocus?.focus();
  returnFocus = null;
}

function openDialog(link: HTMLElement): void {
  if (!dialogShell) return;
  returnFocus = link;
  dialogShell.hidden = false;
  dialogShell.setAttribute("aria-hidden", "false");
  history.pushState({ report: link.getAttribute("href") }, "", link.getAttribute("href") ?? "");
  dialogShell.querySelector<HTMLElement>("[data-dialog]")?.focus();
}

document.addEventListener("click", (event) => {
  const target = event.target as HTMLElement;
  const link = target.closest<HTMLElement>("[data-report-link]");
  if (link && dialogShell && !dialogShell.hidden) return;
  if (link && dialogShell) openDialog(link);
  if (target.closest("[data-dialog-close], [data-dialog-backdrop]")) {
    event.preventDefault();
    closeDialog();
    history.back();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && dialogShell && !dialogShell.hidden) {
    closeDialog();
    history.back();
  }
});

window.addEventListener("popstate", () => {
  if (dialogShell && !location.pathname.startsWith("/reports/")) closeDialog();
});

/** Small fetch adapter for HTMX attributes when no external runtime is installed. */
document.addEventListener("click", (event) => {
  const target = event.target as HTMLElement;
  const shell = document.querySelector<HTMLElement>("#report-dialog");
  const link = target.closest<HTMLAnchorElement>("[data-report-link]");
  const url = link?.getAttribute("data-hx-get");
  if (!shell || !link || !url || !shell.hidden) return;
  event.preventDefault();
  fetch(url, { headers: { "HX-Request": "true" } })
    .then((response) => response.ok ? response.text() : Promise.reject(new Error("modal request failed")))
    .then((html) => {
      shell.innerHTML = html;
      shell.hidden = false;
      shell.setAttribute("aria-hidden", "false");
      history.pushState({ report: link.href }, "", link.href);
      shell.querySelector<HTMLElement>("[data-dialog]")?.focus();
    })
    .catch(() => window.location.assign(link.href));
});

document.addEventListener("click", (event) => {
  const target = event.target as HTMLElement;
  const shell = document.querySelector<HTMLElement>("#report-dialog");
  if (!shell) return;
  if (target.closest("[data-dialog-close]")) {
    shell.hidden = true;
    shell.setAttribute("aria-hidden", "true");
  }
});

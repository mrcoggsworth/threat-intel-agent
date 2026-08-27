/* Minimal HTMX-compatible enhancement for deployments without a bundled HTMX runtime. */
(function () {
  var shell = document.querySelector("#report-dialog");
  if (!shell) return;

  document.addEventListener("click", function (event) {
    var target = event.target;
    var link = target.closest("[data-report-link]");
    if (!link || !link.getAttribute("data-hx-get")) return;
    event.preventDefault();
    fetch(link.getAttribute("data-hx-get"), { headers: { "HX-Request": "true" } })
      .then(function (response) {
        if (!response.ok) throw new Error("modal request failed: " + response.status);
        return response.text();
      })
      .then(function (html) {
        shell.innerHTML = html;
        shell.hidden = false;
        shell.setAttribute("aria-hidden", "false");
        var noHistory = link.getAttribute("data-no-history") === "true";
        if (!noHistory && link.href && link.href !== window.location.href && !link.href.startsWith("javascript:")) {
          history.pushState({ report: link.href }, "", link.href);
        }
        var dialog = shell.querySelector("[data-dialog]");
        if (dialog) dialog.focus();
      })
      .catch(function (err) {
        console.error("Modal load error:", err);
        if (link.href && link.href !== window.location.href && !link.href.startsWith("javascript:")) {
          window.location.assign(link.href);
        }
      });
  });

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (target.closest("[data-dialog-close]")) {
      shell.hidden = true;
      shell.setAttribute("aria-hidden", "true");
    }
  });
}());

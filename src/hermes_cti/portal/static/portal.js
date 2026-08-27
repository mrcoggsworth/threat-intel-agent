/* Small progressive enhancement module; canonical pages remain usable without it. */
(function () {
  var shell = document.querySelector("#report-dialog");
  var returnFocus = null;
  function closeDialog() {
    if (!shell) return;
    shell.hidden = true;
    shell.setAttribute("aria-hidden", "true");
    shell.replaceChildren();
    if (returnFocus) returnFocus.focus();
    returnFocus = null;
  }
  function openDialog(link) {
    if (!shell) return;
    returnFocus = link;
    shell.hidden = false;
    shell.setAttribute("aria-hidden", "false");
    var href = link.getAttribute("href");
    if (href && href !== window.location.href && !href.startsWith("javascript:")) {
      history.pushState({ report: href }, "", href);
    }
    var dialog = shell.querySelector("[data-dialog]");
    if (dialog) dialog.focus();
  }
  document.addEventListener("click", function (event) {
    var target = event.target;
    var link = target.closest("[data-report-link]");
    if (link && shell && !shell.hidden) return;
    if (link && shell) openDialog(link);
    if (target.closest("[data-dialog-close]") || target.classList.contains("dialog-backdrop")) {
      event.preventDefault();
      closeDialog();
      history.back();
    }
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && shell && !shell.hidden) {
      closeDialog();
      history.back();
    }
  });
  window.addEventListener("popstate", function () {
    if (shell && !shell.hidden) closeDialog();
  });
}());

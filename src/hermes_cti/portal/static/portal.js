/* Small progressive enhancement module; canonical pages remain usable without it. */
(function () {
  var shell = document.querySelector("#report-dialog");
  var returnFocus = null;
  var historyPushed = false;
  window._setModalHistoryPushed = function (pushed) { historyPushed = pushed; };
  function closeDialog() {
    if (!shell) return;
    shell.hidden = true;
    shell.setAttribute("aria-hidden", "true");
    shell.replaceChildren();
    if (returnFocus) returnFocus.focus();
    returnFocus = null;
    if (historyPushed) {
      historyPushed = false;
      history.back();
    }
  }
  document.addEventListener("click", function (event) {
    var target = event.target;
    var link = target.closest("[data-report-link]");
    if (link && shell) { returnFocus = link; }
    if (target.closest("[data-dialog-close]")) {
      event.preventDefault();
      closeDialog();
    }
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && shell && !shell.hidden) {
      closeDialog();
    }
  });
  window.addEventListener("popstate", function () {
    if (shell && !location.pathname.startsWith("/reports/")) closeDialog();
  });
}());

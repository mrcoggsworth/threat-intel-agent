/* Progressive enhancement: dialog lifecycle, backdrop dismissal, keyboard shortcuts, and history popstate. */
(function () {
  var shell = document.querySelector("#report-dialog");
  var returnFocus = null;

  function closeDialog() {
    if (!shell) return;
    shell.hidden = true;
    shell.setAttribute("aria-hidden", "true");
    shell.replaceChildren();
    if (returnFocus) {
      returnFocus.focus();
      returnFocus = null;
    }
  }

  window.__hermesCloseDialog = closeDialog;
  window.__hermesSetReturnFocus = function (el) {
    returnFocus = el;
  };

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target) return;

    if (target.closest("[data-dialog-close]") || target.classList.contains("dialog-backdrop")) {
      event.preventDefault();
      closeDialog();
      if (window.location.search.includes("ioc=") || window.location.search.includes("attack=") || window.location.pathname.match(/\/(hunt|remediation|detections)$/)) {
        history.back();
      }
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && shell && !shell.hidden) {
      closeDialog();
      if (window.location.search.includes("ioc=") || window.location.search.includes("attack=") || window.location.pathname.match(/\/(hunt|remediation|detections)$/)) {
        history.back();
      }
    }
  });

  window.addEventListener("popstate", function () {
    if (shell && !shell.hidden) {
      closeDialog();
    }
  });
}());

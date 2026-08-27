/* Progressive enhancement: dialog lifecycle, backdrop dismissal, keyboard shortcuts, history popstate, and theme switching. */
(function () {
  var validThemes = [
    "traditional-light",
    "traditional-dark",
    "cyberpunk",
    "synthwave",
    "tokyo-night",
    "darcula",
    "monokai",
    "synthwave-metal"
  ];

  function applySavedTheme() {
    try {
      var saved = localStorage.getItem("hermes-theme");
      if (saved && validThemes.indexOf(saved) !== -1) {
        document.documentElement.setAttribute("data-theme", saved);
      }
    } catch (e) {
      // Ignore
    }
  }

  applySavedTheme();

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

  // Initialize theme selector
  function initThemeSelector() {
    var selector = document.querySelector("#theme-selector");
    if (!selector) return;

    try {
      var saved = localStorage.getItem("hermes-theme") || "traditional-light";
      if (validThemes.indexOf(saved) !== -1) {
        selector.value = saved;
        document.documentElement.setAttribute("data-theme", saved);
      }
    } catch (e) {
      // Ignore
    }

    selector.addEventListener("change", function () {
      var theme = selector.value;
      document.documentElement.setAttribute("data-theme", theme);
      try {
        localStorage.setItem("hermes-theme", theme);
      } catch (e) {
        // Ignore
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initThemeSelector);
  } else {
    initThemeSelector();
  }

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
})();

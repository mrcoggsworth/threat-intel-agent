/* Progressive enhancement: dialog lifecycle, backdrop dismissal, keyboard shortcuts, history popstate, theme switching, and clipboard copying. */
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

  // Copy text to clipboard with fallback
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(
        function () {
          return true;
        },
        function () {
          return false;
        }
      );
    }

    try {
      var textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      var ok = document.execCommand("copy");
      document.body.removeChild(textarea);
      return Promise.resolve(ok);
    } catch (e) {
      return Promise.resolve(false);
    }
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target) return;

    // Handle copy-to-clipboard button
    var copyBtn = target.closest("[data-copy-target]");
    if (copyBtn) {
      event.preventDefault();
      var card = copyBtn.closest(".detection");
      var codeEl = card ? card.querySelector("pre code") : null;
      var textToCopy = codeEl ? codeEl.textContent || "" : "";

      if (!textToCopy) return;

      copyText(textToCopy).then(function (success) {
        if (success) {
          var labelEl = copyBtn.querySelector(".copy-label");
          var prevLabel = labelEl ? labelEl.textContent : "Copy";
          var prevClass = copyBtn.className;

          if (labelEl) labelEl.textContent = "Copied!";
          copyBtn.classList.add("bg-emerald-800", "text-emerald-200", "border-emerald-600");

          setTimeout(function () {
            if (labelEl) labelEl.textContent = prevLabel;
            copyBtn.className = prevClass;
          }, 2000);
        }
      });
      return;
    }

    // Handle dialog close button and backdrop
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

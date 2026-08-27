/* HTMX-compatible progressive modal enhancement with live enrichment loading feedback. */
(function () {
  var shell = document.querySelector("#report-dialog");
  if (!shell) return;

  function buildLoadingSkeleton(title, subtitle, detailMsg) {
    return [
      '<div class="dialog-backdrop" data-dialog-close></div>',
      '<section class="dialog" role="dialog" aria-modal="true" aria-labelledby="loading-modal-title" tabindex="-1" data-dialog>',
      '  <button class="dialog-close" type="button" data-dialog-close aria-label="Close dialog">×</button>',
      '  <div class="dialog-body space-y-5 pr-6">',
      '    <div class="border-b border-slate-200 pb-3">',
      '      <div class="flex items-center gap-2">',
      '        <span class="inline-block w-2 h-2 rounded-full bg-sky-500 animate-pulse"></span>',
      '        <span class="text-xs font-bold uppercase tracking-wider text-sky-700">' + subtitle + '</span>',
      '      </div>',
      '      <h2 id="loading-modal-title" class="text-lg sm:text-xl font-bold tracking-tight text-slate-900 mt-2 font-mono break-all select-all">' + title + '</h2>',
      '    </div>',
      '    <div class="p-6 rounded-xl border border-slate-200 bg-slate-50 flex flex-col items-center justify-center text-center space-y-3">',
      '      <svg class="animate-spin h-7 w-7 text-sky-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">',
      '        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>',
      '        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>',
      '      </svg>',
      '      <p class="text-xs font-semibold text-slate-700">' + detailMsg + '</p>',
      '      <p class="text-[11px] text-slate-500">Live intelligence enrichment in progress</p>',
      '    </div>',
      '  </div>',
      '</section>'
    ].join('\n');
  }

  function buildErrorSkeleton(errorMsg) {
    return [
      '<div class="dialog-backdrop" data-dialog-close></div>',
      '<section class="dialog" role="dialog" aria-modal="true" tabindex="-1" data-dialog>',
      '  <button class="dialog-close" type="button" data-dialog-close aria-label="Close dialog">×</button>',
      '  <div class="dialog-body space-y-4 pr-6">',
      '    <div class="border-b border-rose-200 pb-2">',
      '      <span class="text-xs font-bold uppercase tracking-wider text-rose-700">Enrichment Notice</span>',
      '      <h2 class="text-lg font-bold text-slate-900 mt-1">Unable to Load Indicator Data</h2>',
      '    </div>',
      '    <p class="text-sm text-slate-600">' + errorMsg + '</p>',
      '    <div class="flex items-center gap-3 pt-2">',
      '      <button type="button" class="px-3 py-1.5 rounded-lg bg-sky-700 text-white text-xs font-semibold hover:bg-sky-800 cursor-pointer" data-dialog-close>Close</button>',
      '    </div>',
      '  </div>',
      '</section>'
    ].join('\n');
  }

  function loadModal(link, url) {
    var isIoc = url.indexOf("ioc-modal") !== -1;
    var iocVal = link.getAttribute("data-ioc-value") || link.textContent.trim() || "Indicator";
    var subtitle = isIoc ? "Enriching Indicator" : "Loading Report Component";
    var detailMsg = isIoc
      ? "Querying VirusTotal, AbuseIPDB, and AlienVault OTX..."
      : "Fetching section content...";

    // Show instant loading skeleton
    shell.innerHTML = buildLoadingSkeleton(iocVal, subtitle, detailMsg);
    shell.hidden = false;
    shell.setAttribute("aria-hidden", "false");

    if (typeof window.__hermesSetReturnFocus === "function") {
      window.__hermesSetReturnFocus(link);
    }

    var href = link.getAttribute("href");
    if (href && href !== window.location.href && !href.startsWith("javascript:")) {
      history.pushState({ report: href }, "", href);
    }

    fetch(url, { headers: { "HX-Request": "true" } })
      .then(function (response) {
        if (!response.ok) throw new Error("Modal request failed: " + response.status);
        return response.text();
      })
      .then(function (html) {
        shell.innerHTML = html;
        var dialog = shell.querySelector("[data-dialog]");
        if (dialog) dialog.focus();
      })
      .catch(function (err) {
        console.error("Modal load error:", err);
        shell.innerHTML = buildErrorSkeleton(
          "We could not retrieve live data for this indicator. Please verify your connection or try again later."
        );
      });
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target) return;

    var link = target.closest("[data-report-link]");
    if (!link) return;

    var url = link.getAttribute("data-hx-get");
    if (!url) return;

    event.preventDefault();
    loadModal(link, url);
  });

  // Handle URL query parameters on initial page load (e.g. ?ioc=198.51.100.22)
  window.addEventListener("DOMContentLoaded", function () {
    var params = new URLSearchParams(window.location.search);
    var iocParam = params.get("ioc");
    if (iocParam) {
      var match = document.querySelector('[data-ioc-value="' + CSS.escape(iocParam) + '"]') ||
                  document.querySelector('[data-report-link][href*="ioc=' + encodeURIComponent(iocParam) + '"]');
      if (match) {
        var url = match.getAttribute("data-hx-get");
        if (url) {
          loadModal(match, url);
        }
      }
    }
  });
}());

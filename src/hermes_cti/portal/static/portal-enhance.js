/* HTMX-compatible progressive modal enhancement with live enrichment & CTI analyst loading feedback. */
(function () {
  var shell = document.querySelector("#report-dialog");
  if (!shell) return;

  var sillyAnalystQuotes = [
    "Consulting the cyber threat intelligence tea leaves...",
    "Asking the SOC hamster to sprint faster on the wheel...",
    "Cross-referencing packet dust with reality...",
    "De-obfuscating dark web whisper networks...",
    "Checking under the digital couch cushions for IOCs...",
    "Bribing the firewall for extra telemetry...",
    "Untangling PowerShell scriptblock spaghetti...",
    "Teaching the AI model how to spot suspicious rundll32 invocations...",
    "Brewing a fresh pot of incident response coffee...",
    "Reticulating threat splines and behavior trees...",
    "Interrogating the SIEM logs until they confess...",
    "Decoding base64 hieroglyphics into actionable intel...",
    "Aligning defensive shields with MITRE ATT&CK vectors...",
    "Triangulating anomalous beaconing from the ether...",
    "Correlating kernel callbacks with adversary tradecraft...",
    "Polishing the threat matrix for maximum defense...",
    "Summoning the VirusTotal and AlienVault oracles...",
    "Pivoting on malware hashes in the digital wild...",
    "De-fanging suspicious infrastructure in the containment vat...",
    "Calibrating threat score confidence algorithms..."
  ];

  var quoteInterval = null;

  function stopQuoteRotation() {
    if (quoteInterval !== null) {
      clearInterval(quoteInterval);
      quoteInterval = null;
    }
  }

  function buildLoadingSkeleton(title, subtitle, detailMsg, bottomTag) {
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
      '    <div class="p-6 rounded-xl border border-sky-200 bg-sky-50 flex flex-col items-center justify-center text-center space-y-3 shadow-xs">',
      '      <div class="relative flex items-center justify-center my-1">',
      '        <span class="text-3xl animate-pulse">🧠</span>',
      '      </div>',
      '      <p id="dynamic-loading-quote" class="text-xs font-semibold text-slate-900 italic transition-opacity duration-200 min-h-[2rem] flex items-center justify-center px-4 leading-relaxed">' + detailMsg + '</p>',
      '      <div class="flex items-center gap-2 text-[11px] text-slate-500 font-mono pt-1">',
      '        <span class="inline-block w-2 h-2 rounded-full bg-sky-500 animate-ping"></span>',
      '        <span>' + bottomTag + '</span>',
      '      </div>',
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
      '      <span class="text-xs font-bold uppercase tracking-wider text-rose-700">Notice</span>',
      '      <h2 class="text-lg font-bold text-slate-900 mt-1">Unable to Load Requested Data</h2>',
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
    stopQuoteRotation();

    var isIoc = url.indexOf("ioc-modal") !== -1;
    var isEvidence = url.indexOf("evidence") !== -1;
    var isAttack = url.indexOf("attack-modal") !== -1;

    var title =
      link.getAttribute("data-evidence-id") ||
      link.getAttribute("data-ioc-value") ||
      link.textContent.trim() ||
      "Item";
    var subtitle = "Loading Report Component";
    var bottomTag = "Hermes CTI Intelligence Platform";
    var initialQuote =
      sillyAnalystQuotes[Math.floor(Math.random() * sillyAnalystQuotes.length)];

    if (isEvidence) {
      var evId = link.getAttribute("data-evidence-id") || title;
      var shortId = evId.length > 12 ? evId.substring(0, 8) + "…" : evId;
      title = "Evidence Claim (" + shortId + ")";
      subtitle = "Analyzing Evidence with CTI Analyst";
      bottomTag = "🧠 Hermes CTI Analyst Synthesis Engine active";
    } else if (isIoc) {
      var iocVal = link.getAttribute("data-ioc-value") || title;
      var iocType = link.getAttribute("data-ioc-type") || "IOC";
      title = iocVal + " (" + iocType.toUpperCase() + ")";
      subtitle = "Enriching Indicator with Live CTI Feeds";
      bottomTag = "Live VirusTotal, AbuseIPDB & OTX enrichment active";
    } else if (isAttack) {
      subtitle = "Mapping MITRE ATT&CK Technique";
      bottomTag = "ATT&CK Enterprise Matrix correlation active";
    }

    // Show instant loading skeleton with funny sayings
    shell.innerHTML = buildLoadingSkeleton(
      title,
      subtitle,
      initialQuote,
      bottomTag
    );
    shell.hidden = false;
    shell.setAttribute("aria-hidden", "false");

    var quoteIdx = Math.floor(Math.random() * sillyAnalystQuotes.length);
    quoteInterval = window.setInterval(function () {
      var quoteEl = document.getElementById("dynamic-loading-quote");
      if (quoteEl) {
        quoteIdx = (quoteIdx + 1) % sillyAnalystQuotes.length;
        quoteEl.style.opacity = "0";
        setTimeout(function () {
          if (quoteEl) {
            quoteEl.textContent = sillyAnalystQuotes[quoteIdx];
            quoteEl.style.opacity = "1";
          }
        }, 150);
      }
    }, 1500);

    if (typeof window.__hermesSetReturnFocus === "function") {
      window.__hermesSetReturnFocus(link);
    }

    var href = link.getAttribute("href");
    if (
      href &&
      href !== window.location.href &&
      !href.startsWith("javascript:")
    ) {
      history.pushState({ report: href }, "", href);
    }

    fetch(url, { headers: { "HX-Request": "true" } })
      .then(function (response) {
        if (!response.ok)
          throw new Error("Modal request failed: " + response.status);
        return response.text();
      })
      .then(function (html) {
        stopQuoteRotation();
        shell.innerHTML = html;
        var dialog = shell.querySelector("[data-dialog]");
        if (dialog) dialog.focus();
      })
      .catch(function (err) {
        stopQuoteRotation();
        console.error("Modal load error:", err);
        shell.innerHTML = buildErrorSkeleton(
          "We could not retrieve data for this item. Please verify your connection or try again."
        );
      });
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target) return;

    if (
      target.closest("[data-dialog-close]") ||
      target.classList.contains("dialog-backdrop")
    ) {
      stopQuoteRotation();
    }

    var link = target.closest("[data-report-link]");
    if (!link) return;

    var url = link.getAttribute("data-hx-get");
    if (!url) return;

    event.preventDefault();
    loadModal(link, url);
  });

  // Handle URL query parameters on initial page load (e.g. ?ioc=198.51.100.22 or ?evidence=UUID)
  window.addEventListener("DOMContentLoaded", function () {
    var params = new URLSearchParams(window.location.search);
    var iocParam = params.get("ioc");
    var evParam = params.get("evidence") || params.get("evidence_id");

    if (iocParam) {
      var matchIoc =
        document.querySelector(
          '[data-ioc-value="' + CSS.escape(iocParam) + '"]'
        ) ||
        document.querySelector(
          '[data-report-link][href*="ioc=' + encodeURIComponent(iocParam) + '"]'
        );
      if (matchIoc) {
        var urlIoc = matchIoc.getAttribute("data-hx-get");
        if (urlIoc) {
          loadModal(matchIoc, urlIoc);
          return;
        }
      }
    }

    if (evParam) {
      var matchEv =
        document.querySelector(
          '[data-evidence-id="' + CSS.escape(evParam) + '"]'
        ) ||
        document.querySelector(
          '[data-report-link][href*="evidence/' +
            encodeURIComponent(evParam) +
            '"]'
        ) ||
        document.querySelector(
          '[data-report-link][href*="evidence=' +
            encodeURIComponent(evParam) +
            '"]'
        );
      if (matchEv) {
        var urlEv = matchEv.getAttribute("data-hx-get");
        if (urlEv) {
          loadModal(matchEv, urlEv);
        }
      }
    }
  });
})();

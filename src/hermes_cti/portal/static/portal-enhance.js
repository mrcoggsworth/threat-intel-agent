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
    "Summoning the VirusTotal, AbuseIPDB and AlienVault oracles...",
    "Pivoting on malware hashes across threat landscape...",
    "De-fanging suspicious infrastructure in the containment vat...",
    "Translating threat actor forum chatter...",
    "Calibrating threat score confidence algorithms...",
    "Scouring memory dumps for hidden reflective DLLs...",
    "Consulting the MITRE ATT&CK knowledge matrix...",
    "Filtering out benign background noise from the enterprise matrix..."
  ];

  var quoteInterval = null;

  function stopQuoteRotation() {
    if (quoteInterval !== null) {
      clearInterval(quoteInterval);
      quoteInterval = null;
    }
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatStructuredContent(container) {
    if (!container) return;
    var candidates = container.querySelectorAll("p, li, div.dialog-body div");
    for (var i = 0; i < candidates.length; i++) {
      var el = candidates[i];
      if (el.children.length > 0 || el.classList.contains("structured-formatted")) continue;
      var text = (el.textContent || "").trim();

      if (
        (text.startsWith("{") && text.endsWith("}")) ||
        (text.startsWith("[") && text.endsWith("]"))
      ) {
        try {
          var parsed = JSON.parse(text);
          var pretty = JSON.stringify(parsed, null, 2);
          el.classList.add("structured-formatted");
          el.innerHTML = '<pre class="structured-code-block font-mono"><code>' + escapeHtml(pretty) + '</code></pre>';
          continue;
        } catch (e) {
          // continue
        }
      }

      var isQuery =
        /^(SELECT\s+.+\s+FROM\s+|DeviceProcessEvents\s+\||index=\w+\s+sourcetype=)/i.test(text) ||
        (text.indexOf(" | where ") !== -1 || text.indexOf(" | project ") !== -1 || text.indexOf(" | summarize ") !== -1);
      if (isQuery && text.length > 25) {
        el.classList.add("structured-formatted");
        el.innerHTML = '<pre class="structured-code-block font-mono"><code>' + escapeHtml(text) + '</code></pre>';
      }
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
      '    <div class="p-5 sm:p-6 rounded-xl border border-slate-200 bg-white flex flex-col items-center justify-center text-center space-y-4 shadow-xs">',
      '      <!-- Terminal Progress Bar -->',
      '      <div class="w-full max-w-md mx-auto space-y-2 text-left font-mono">',
      '        <div class="flex items-center justify-between text-[11px] text-sky-700 font-semibold tracking-wide">',
      '          <span class="flex items-center gap-1.5">',
      '            <span class="inline-block w-2 h-2 rounded-xs bg-sky-500 animate-pulse"></span>',
      '            <span>hermes@cti-cluster:~$ ingest --stream</span>',
      '          </span>',
      '          <span class="text-[10px] text-slate-500 font-mono animate-pulse">CONNECTING...</span>',
      '        </div>',
      '        <div class="w-full h-4 rounded-md terminal-progress-track p-0.5 shadow-inner">',
      '          <div class="h-full rounded-xs terminal-progress-fill"></div>',
      '        </div>',
      '        <div class="flex items-center justify-between text-[10px] text-slate-400 font-mono">',
      '          <span>[■■■■■■■■■■■■■■░░░░░░]</span>',
      '          <span>TELEMETRY_STREAM</span>',
      '        </div>',
      '      </div>',
      '      <div class="w-full max-w-lg mx-auto p-4 rounded-xl border border-sky-200 bg-sky-50 flex flex-col items-center justify-center text-center space-y-2 shadow-2xs">',
      '        <span class="text-[11px] font-bold uppercase tracking-wider text-sky-700 font-mono">Hermes Analyst Synthesis</span>',
      '        <p id="dynamic-loading-quote" class="text-sm font-semibold text-slate-900 italic transition-opacity duration-300 min-h-[2.5rem] flex items-center justify-center px-4 leading-relaxed">' + detailMsg + '</p>',
      '        <div class="flex items-center gap-1.5 pt-1">',
      '          <span class="inline-block w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></span>',
      '          <span class="inline-block w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></span>',
      '          <span class="inline-block w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></span>',
      '        </div>',
      '      </div>',
      '      <div class="flex items-center justify-center gap-2 pt-1 text-xs text-slate-500 font-mono">',
      '        <span class="inline-flex items-center px-3 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200 text-[11px] font-semibold tracking-wide">',
      '          ' + bottomTag + '',
      '        </span>',
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

    var isIoc = url.indexOf("ioc-modal") !== -1 || url.indexOf("type=") !== -1 || url.indexOf("value=") !== -1;
    var isEvidence = url.indexOf("evidence") !== -1;
    var isAttack = url.indexOf("attack-modal") !== -1 || url.indexOf("attack_id=") !== -1 || url.indexOf("techniques/") !== -1;

    var title =
      link.getAttribute("data-evidence-id") ||
      link.getAttribute("data-ioc-value") ||
      link.getAttribute("data-attack-id") ||
      link.textContent.replace("🔍", "").trim() ||
      "Intelligence Record";
    var subtitle = "Loading CTI Intelligence Module";
    var bottomTag = "Hermes Threat Intelligence Platform";
    var initialQuote =
      sillyAnalystQuotes[Math.floor(Math.random() * sillyAnalystQuotes.length)];

    if (isEvidence) {
      var evId = link.getAttribute("data-evidence-id") || title;
      var shortId = evId.length > 12 ? evId.substring(0, 8) + "…" : evId;
      title = "Evidence Claim (" + shortId + ")";
      subtitle = "CTI Analyst Synthesis & Provenance";
      bottomTag = "Hermes Evidence & Provenance Ledger";
    } else if (isIoc) {
      var iocVal = link.getAttribute("data-ioc-value") || title;
      var iocType = (link.getAttribute("data-ioc-type") || "IOC").toUpperCase();
      title = iocVal + " (" + iocType + ")";
      subtitle = "Enriching Indicator with Live CTI Feeds";
      bottomTag = "Live VirusTotal · AbuseIPDB · AlienVault OTX";
    } else if (isAttack) {
      var attackId = link.getAttribute("data-attack-id") || title;
      title = "MITRE ATT&CK " + attackId;
      subtitle = "Mapping ATT&CK Enterprise Technique";
      bottomTag = "ATT&CK Enterprise Matrix Correlation";
    }

    // Show instant Claude-style loading skeleton with funny sayings
    shell.innerHTML = buildLoadingSkeleton(
      title,
      subtitle,
      initialQuote,
      bottomTag
    );
    shell.hidden = false;
    shell.setAttribute("aria-hidden", "false");

    var quoteIdx = Math.floor(Math.random() * sillyAnalystQuotes.length);
    // Hold each saying for 3500ms (previous 1500ms + 2000ms)
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
        }, 250);
      }
    }, 3500);

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
        formatStructuredContent(shell);
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

  // Handle URL query parameters on initial page load (e.g. ?ioc=..., ?attack=..., ?evidence=...)
  window.addEventListener("DOMContentLoaded", function () {
    var params = new URLSearchParams(window.location.search);
    var iocParam = params.get("ioc");
    var evParam = params.get("evidence") || params.get("evidence_id");
    var attackParam = params.get("attack") || params.get("attack_id");

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

    if (attackParam) {
      var matchAttack =
        document.querySelector(
          '[data-attack-id="' + CSS.escape(attackParam) + '"]'
        ) ||
        document.querySelector(
          '[data-report-link][href*="attack=' + encodeURIComponent(attackParam) + '"]'
        ) ||
        document.querySelector(
          '[data-report-link][data-hx-get*="attack_id=' + encodeURIComponent(attackParam) + '"]'
        );
      if (matchAttack) {
        var urlAttack = matchAttack.getAttribute("data-hx-get");
        if (urlAttack) {
          loadModal(matchAttack, urlAttack);
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

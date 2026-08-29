/** HTMX-compatible progressive modal enhancement with live enrichment & CTI analyst loading feedback. */
(function () {
  const shell = document.querySelector<HTMLElement>("#report-dialog");
  if (!shell) return;

  const sillyAnalystQuotes: string[] = [
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

  let quoteInterval: number | null = null;

  function stopQuoteRotation(): void {
    if (quoteInterval !== null) {
      clearInterval(quoteInterval);
      quoteInterval = null;
    }
  }

  function formatStructuredContent(container: HTMLElement): void {
    if (!container) return;
    // Auto-detect JSON, SQL queries, or structured blocks in text nodes / lists
    const candidates = container.querySelectorAll<HTMLElement>("p, li, div.dialog-body div");
    candidates.forEach((el) => {
      // Don't format containers with child elements or existing code blocks
      if (el.children.length > 0 || el.classList.contains("structured-formatted")) return;
      const text = el.textContent?.trim() || "";
      
      // JSON detection
      if (
        (text.startsWith("{") && text.endsWith("}")) ||
        (text.startsWith("[") && text.endsWith("]"))
      ) {
        try {
          const parsed = JSON.parse(text);
          const pretty = JSON.stringify(parsed, null, 2);
          el.classList.add("structured-formatted");
          el.innerHTML = `<pre class="structured-code-block font-mono"><code>${escapeHtml(pretty)}</code></pre>`;
          return;
        } catch {
          // not valid JSON, proceed
        }
      }

      // SQL / KQL / SPL detection (multi-line queries or distinct keywords)
      const isQuery =
        /^(SELECT\s+.+\s+FROM\s+|DeviceProcessEvents\s+\||index=\w+\s+sourcetype=)/i.test(text) ||
        (text.includes(" | where ") || text.includes(" | project ") || text.includes(" | summarize "));
      if (isQuery && text.length > 25) {
        el.classList.add("structured-formatted");
        el.innerHTML = `<pre class="structured-code-block font-mono"><code>${escapeHtml(text)}</code></pre>`;
        return;
      }
    });
  }

  function escapeHtml(str: string): string {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function buildLoadingSkeleton(
    title: string,
    subtitle: string,
    detailMsg: string,
    bottomTag: string
  ): string {
    return `
      <div class="dialog-backdrop" data-dialog-close></div>
      <section class="dialog" role="dialog" aria-modal="true" aria-labelledby="loading-modal-title" tabindex="-1" data-dialog>
        <button class="dialog-close" type="button" data-dialog-close aria-label="Close dialog">×</button>
        <div class="dialog-body space-y-5 pr-6">
          <div class="border-b border-slate-200 pb-3">
            <div class="flex items-center gap-2">
              <span class="inline-block w-2 h-2 rounded-full bg-sky-500 animate-pulse"></span>
              <span class="text-xs font-bold uppercase tracking-wider text-sky-700">${subtitle}</span>
            </div>
            <h2 id="loading-modal-title" class="text-lg sm:text-xl font-bold tracking-tight text-slate-900 mt-2 font-mono break-all select-all">${title}</h2>
          </div>

          <div class="p-6 rounded-xl border border-slate-200 bg-white flex flex-col items-center justify-center text-center space-y-4 shadow-xs">
            <div class="relative flex items-center justify-center w-12 h-12 my-1" style="-webkit-transform: translateZ(0); transform: translateZ(0);">
              <svg class="animate-spin w-10 h-10 text-sky-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"></circle>
                <path class="opacity-80" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
                <span class="w-2.5 h-2.5 rounded-full bg-sky-500 animate-pulse"></span>
              </div>
            </div>

            <div class="w-full max-w-lg mx-auto p-4 rounded-xl border border-sky-200 bg-sky-50 flex flex-col items-center justify-center text-center space-y-2 shadow-2xs">
              <span class="text-[11px] font-bold uppercase tracking-wider text-sky-700 font-mono">Hermes Analyst Synthesis</span>
              <p id="dynamic-loading-quote" class="text-sm font-semibold text-slate-900 italic transition-opacity duration-300 min-h-[2.5rem] flex items-center justify-center px-4 leading-relaxed">${detailMsg}</p>
              <div class="flex items-center gap-1.5 pt-1">
                <span class="inline-block w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></span>
                <span class="inline-block w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></span>
                <span class="inline-block w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></span>
              </div>
            </div>

            <div class="flex items-center justify-center gap-2 pt-1 text-xs text-slate-500 font-mono">
              <span class="inline-flex items-center px-3 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200 text-[11px] font-semibold tracking-wide">
                ${bottomTag}
              </span>
            </div>
          </div>
        </div>
      </section>
    `;
  }

  function buildErrorSkeleton(errorMsg: string): string {
    return `
      <div class="dialog-backdrop" data-dialog-close></div>
      <section class="dialog" role="dialog" aria-modal="true" tabindex="-1" data-dialog>
        <button class="dialog-close" type="button" data-dialog-close aria-label="Close dialog">×</button>
        <div class="dialog-body space-y-4 pr-6">
          <div class="border-b border-rose-200 pb-2">
            <span class="text-xs font-bold uppercase tracking-wider text-rose-700">Notice</span>
            <h2 class="text-lg font-bold text-slate-900 mt-1">Unable to Load Requested Data</h2>
          </div>
          <p class="text-sm text-slate-600">${errorMsg}</p>
          <div class="flex items-center gap-3 pt-2">
            <button type="button" class="px-3 py-1.5 rounded-lg bg-sky-700 text-white text-xs font-semibold hover:bg-sky-800 cursor-pointer" data-dialog-close>Close</button>
          </div>
        </div>
      </section>
    `;
  }

  function loadModal(link: HTMLElement, url: string): void {
    stopQuoteRotation();

    const isIoc = url.includes("ioc-modal") || url.includes("type=") || url.includes("value=");
    const isEvidence = url.includes("evidence");
    const isAttack = url.includes("attack-modal") || url.includes("attack_id=") || url.includes("techniques/");

    let title =
      link.getAttribute("data-evidence-id") ||
      link.getAttribute("data-ioc-value") ||
      link.getAttribute("data-attack-id") ||
      link.textContent?.trim().replace("🔍", "").trim() ||
      "Intelligence Record";
    let subtitle = "Loading CTI Intelligence Module";
    let bottomTag = "Hermes Threat Intelligence Platform";
    const initialQuote =
      sillyAnalystQuotes[Math.floor(Math.random() * sillyAnalystQuotes.length)];

    if (isEvidence) {
      const evId = link.getAttribute("data-evidence-id") || title;
      const shortId = evId.length > 12 ? evId.substring(0, 8) + "…" : evId;
      title = `Evidence Claim (${shortId})`;
      subtitle = "CTI Analyst Synthesis & Provenance";
      bottomTag = "Hermes Evidence & Provenance Ledger";
    } else if (isIoc) {
      const iocVal = link.getAttribute("data-ioc-value") || title;
      const iocType = (link.getAttribute("data-ioc-type") || "IOC").toUpperCase();
      title = `${iocVal} (${iocType})`;
      subtitle = "Enriching Indicator with Live CTI Feeds";
      bottomTag = "Live VirusTotal · AbuseIPDB · AlienVault OTX";
    } else if (isAttack) {
      const attackId = link.getAttribute("data-attack-id") || title;
      title = `MITRE ATT&CK ${attackId}`;
      subtitle = "Mapping ATT&CK Enterprise Technique";
      bottomTag = "ATT&CK Enterprise Matrix Correlation";
    }

    // Show instant Claude-style loading skeleton with funny sayings
    shell!.innerHTML = buildLoadingSkeleton(
      title,
      subtitle,
      initialQuote,
      bottomTag
    );
    shell!.hidden = false;
    shell!.setAttribute("aria-hidden", "false");

    let quoteIdx = Math.floor(Math.random() * sillyAnalystQuotes.length);
    // Hold each saying for 3500ms (previous 1500ms + 2000ms)
    quoteInterval = window.setInterval(() => {
      const quoteEl = document.getElementById("dynamic-loading-quote");
      if (quoteEl) {
        quoteIdx = (quoteIdx + 1) % sillyAnalystQuotes.length;
        quoteEl.style.opacity = "0";
        setTimeout(() => {
          if (quoteEl) {
            quoteEl.textContent = sillyAnalystQuotes[quoteIdx];
            quoteEl.style.opacity = "1";
          }
        }, 250);
      }
    }, 3500);

    if (
      typeof (
        window as unknown as Record<string, (el: HTMLElement) => void>
      ).__hermesSetReturnFocus === "function"
    ) {
      (
        window as unknown as Record<string, (el: HTMLElement) => void>
      ).__hermesSetReturnFocus(link);
    }

    const href = link.getAttribute("href");
    if (
      href &&
      href !== window.location.href &&
      !href.startsWith("javascript:")
    ) {
      history.pushState({ report: href }, "", href);
    }

    fetch(url, { headers: { "HX-Request": "true" } })
      .then((response) => {
        if (!response.ok)
          throw new Error("Modal request failed: " + response.status);
        return response.text();
      })
      .then((html) => {
        stopQuoteRotation();
        shell!.innerHTML = html;
        formatStructuredContent(shell!);
        shell!.querySelector<HTMLElement>("[data-dialog]")?.focus();
      })
      .catch((err) => {
        stopQuoteRotation();
        console.error("Modal load error:", err);
        shell!.innerHTML = buildErrorSkeleton(
          "We could not retrieve data for this item. Please verify your connection or try again."
        );
      });
  }

  document.addEventListener("click", (event: MouseEvent) => {
    const target = event.target as HTMLElement | null;
    if (!target) return;

    if (
      target.closest("[data-dialog-close]") ||
      target.classList.contains("dialog-backdrop")
    ) {
      stopQuoteRotation();
    }

    const link = target.closest<HTMLElement>("[data-report-link]");
    if (!link) return;

    const url = link.getAttribute("data-hx-get");
    if (!url) return;

    event.preventDefault();
    loadModal(link, url);
  });

  // Handle URL query parameters on initial page load (e.g. ?ioc=..., ?attack=..., ?evidence=...)
  window.addEventListener("DOMContentLoaded", () => {
    const params = new URLSearchParams(window.location.search);
    const iocParam = params.get("ioc");
    const evParam = params.get("evidence") || params.get("evidence_id");
    const attackParam = params.get("attack") || params.get("attack_id");

    if (iocParam) {
      const match =
        document.querySelector<HTMLElement>(
          `[data-ioc-value="${CSS.escape(iocParam)}"]`
        ) ||
        document.querySelector<HTMLElement>(
          `[data-report-link][href*="ioc=${encodeURIComponent(iocParam)}"]`
        );
      if (match) {
        const url = match.getAttribute("data-hx-get");
        if (url) {
          loadModal(match, url);
          return;
        }
      }
    }

    if (attackParam) {
      const match =
        document.querySelector<HTMLElement>(
          `[data-attack-id="${CSS.escape(attackParam)}"]`
        ) ||
        document.querySelector<HTMLElement>(
          `[data-report-link][href*="attack=${encodeURIComponent(attackParam)}"]`
        ) ||
        document.querySelector<HTMLElement>(
          `[data-report-link][data-hx-get*="attack_id=${encodeURIComponent(attackParam)}"]`
        );
      if (match) {
        const url = match.getAttribute("data-hx-get");
        if (url) {
          loadModal(match, url);
          return;
        }
      }
    }

    if (evParam) {
      const match =
        document.querySelector<HTMLElement>(
          `[data-evidence-id="${CSS.escape(evParam)}"]`
        ) ||
        document.querySelector<HTMLElement>(
          `[data-report-link][href*="evidence/${encodeURIComponent(evParam)}"]`
        ) ||
        document.querySelector<HTMLElement>(
          `[data-report-link][href*="evidence=${encodeURIComponent(evParam)}"]`
        );
      if (match) {
        const url = match.getAttribute("data-hx-get");
        if (url) {
          loadModal(match, url);
        }
      }
    }
  });
})();


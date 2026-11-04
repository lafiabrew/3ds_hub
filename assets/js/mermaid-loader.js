/* GitHub Pages emits Mermaid fences as code. Render without hiding failed source. */
(() => {
  "use strict";
  const loader = document.currentScript;
  const sourceURL = loader && loader.dataset.mermaidSrc;
  const integrity = loader && loader.dataset.mermaidIntegrity;

  function unavailable(pre, message) {
    const notice = document.createElement("p");
    notice.className = "pages-mermaid-fallback";
    notice.setAttribute("role", "status");
    notice.textContent = message;
    pre.before(notice);
  }

  async function render() {
    // Support both current Primer output and Rouge's nested language wrapper.
    const blocks = Array.from(document.querySelectorAll(
      "pre > code.language-mermaid, .language-mermaid pre > code"
    )).filter(code => !code.dataset.pagesMermaid);
    if (!blocks.length) return;
    for (const code of blocks) code.dataset.pagesMermaid = "pending"; // Do not download the library on ordinary text pages.
    try {
      if (!sourceURL || !integrity) throw new Error("Missing renderer configuration");
      await new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = sourceURL;
        script.integrity = integrity;
        script.crossOrigin = "anonymous";
        const timer = setTimeout(() => {
          script.remove();
          reject(new Error("Renderer load timed out"));
        }, 15000);
        script.onload = () => { clearTimeout(timer); resolve(); };
        script.onerror = () => {
          clearTimeout(timer);
          script.remove();
          reject(new Error("Renderer unavailable"));
        };
        document.head.append(script);
      });
      const mermaid = window.mermaid;
      if (!mermaid || typeof mermaid.render !== "function") throw new Error("Invalid renderer");
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        secure: ["secure", "securityLevel", "startOnLoad", "maxTextSize", "suppressErrorRendering", "maxEdges"],
        suppressErrorRendering: true,
        flowchart: { htmlLabels: false },
        theme: "default"
      });
      for (const [index, code] of blocks.entries()) {
        const pre = code.parentElement;
        const text = code.textContent.trim();
        try {
          if (!await mermaid.parse(text, { suppressErrors: true })) throw new Error("Invalid diagram");
          const result = await mermaid.render("pages-mermaid-" + index, text);
          const viewport = document.createElement("div");
          viewport.className = "pages-mermaid-viewport";
          viewport.tabIndex = 0;
          viewport.setAttribute("aria-label", "Diagram; scroll horizontally if needed");
          // Mermaid's strict renderer sanitizes SVG; do not bind source click handlers.
          viewport.innerHTML = result.svg;
          const svg = viewport.querySelector("svg");
          if (!svg) throw new Error("Missing diagram output");
          const box = svg.viewBox.baseVal;
          if (box.width > 0) svg.setAttribute("width", String(box.width));
          const figure = document.createElement("figure");
          figure.className = "pages-mermaid";
          const details = document.createElement("details");
          const summary = document.createElement("summary");
          summary.textContent = "View Mermaid source";
          details.append(summary);
          figure.append(viewport, details);
          pre.replaceWith(figure);
          details.append(pre); // Preserve the actual original code, even after success.
        } catch (_error) {
          unavailable(pre, "This diagram could not be rendered. Its source is preserved below.");
        }
      }
    } catch (_error) {
      for (const code of blocks) {
        unavailable(code.parentElement, "Diagram renderer unavailable. Its source is preserved below.");
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render, { once: true });
  } else {
    render();
  }
})();

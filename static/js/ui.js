/**
 * Shared warm UI helpers: escaping, cozy Toast notifications, empty states, and file validation.
 */

export function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

export function showToast(message, tone = "info", linkHref = null, linkLabel = null) {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "fixed bottom-5 right-5 z-50 flex flex-col gap-3 max-w-sm w-full pointer-events-none px-4 sm:px-0";
    document.body.appendChild(container);
  }

  const styles = {
    success: {
      wrap: "bg-white border border-[#c08552]/40 border-l-4 border-l-[#c08552] text-[#4b2e2b]",
      badge: "bg-[#c08552] text-white",
      icon: "✓",
    },
    warning: {
      wrap: "bg-[#fff8f0] border border-[#8c5a3c]/40 border-l-4 border-l-[#8c5a3c] text-[#4b2e2b]",
      badge: "bg-[#8c5a3c] text-white",
      icon: "!",
    },
    error: {
      wrap: "bg-white border border-rose-300 border-l-4 border-l-rose-700 text-[#4b2e2b]",
      badge: "bg-rose-700 text-white",
      icon: "✕",
    },
    info: {
      wrap: "bg-white border border-[#8c5a3c]/25 border-l-4 border-l-[#8c5a3c] text-[#4b2e2b]",
      badge: "bg-[#4b2e2b] text-[#fff8f0]",
      icon: "i",
    },
  };

  const theme = styles[tone] || styles.info;
  const toast = document.createElement("div");
  toast.className = `pointer-events-auto rounded-2xl shadow-xl shadow-[#8c5a3c]/15 px-4 py-3.5 text-sm font-medium transition-all duration-300 flex items-center gap-3 ${theme.wrap}`;

  const iconEl = document.createElement("span");
  iconEl.className = `w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${theme.badge}`;
  iconEl.textContent = theme.icon;

  const textEl = document.createElement("span");
  textEl.className = "flex-1 leading-snug";
  textEl.textContent = message;

  toast.appendChild(iconEl);
  toast.appendChild(textEl);

  if (linkHref) {
    const link = document.createElement("a");
    link.href = linkHref;
    link.className = "text-xs font-bold text-[#c08552] hover:text-[#8c5a3c] underline shrink-0";
    link.textContent = linkLabel || "Open";
    toast.appendChild(link);
  }

  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add("opacity-0", "translate-y-2");
    setTimeout(() => toast.remove(), 300);
  }, 4200);
}

export function renderEmptyState({ title, subtitle, iconSvg = "" }) {
  const defaultIcon = `
    <svg class="w-6 h-6 text-[#8c5a3c]" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
    </svg>`;
  return `
    <div class="flex flex-col items-center justify-center text-center py-8 px-4 rounded-2xl bg-[#fff8f0]/70 border border-dashed border-[#8c5a3c]/25">
      <div class="w-12 h-12 rounded-2xl bg-[#c08552]/15 flex items-center justify-center mb-3">
        ${iconSvg || defaultIcon}
      </div>
      <p class="text-sm font-bold text-[#4b2e2b]">${escapeHtml(title)}</p>
      ${subtitle ? `<p class="text-xs text-[#8c5a3c] mt-1 max-w-xs leading-relaxed">${escapeHtml(subtitle)}</p>` : ""}
    </div>`;
}

export function validateUploadFile(file, allowedExtensions, label = "file") {
  if (!file) {
    showToast(`Please select a ${label} before submitting.`, "warning");
    return false;
  }
  if (file.size === 0) {
    showToast(`The selected ${label} is empty (0 bytes).`, "error");
    return false;
  }
  const lowerName = (file.name || "").toLowerCase();
  const matches = allowedExtensions.some((ext) => lowerName.endsWith(ext));
  if (!matches) {
    showToast(
      `Unsupported ${label} format. Allowed: ${allowedExtensions.join(", ")}`,
      "error"
    );
    return false;
  }
  return true;
}

export function renderSafeMarkdown(md) {
  const escaped = escapeHtml(md || "");
  return escaped
    .split("\n")
    .map((line) => {
      const formatted = line
        .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-[#4b2e2b]">$1</strong>')
        .replace(
          /`([^`]+)`/g,
          '<code class="px-1.5 py-0.5 rounded-md bg-[#fff8f0] border border-[#8c5a3c]/20 font-mono text-xs text-[#8c5a3c]">$1</code>'
        );
      if (formatted.startsWith("### ")) {
        return `<h3 class="text-base font-bold text-[#4b2e2b] mt-3 mb-1">${formatted.slice(4)}</h3>`;
      }
      if (formatted.startsWith("- ")) {
        return `<li class="ml-4 list-disc text-[#4b2e2b]/90">${formatted.slice(2)}</li>`;
      }
      if (!formatted.trim()) return `<div class="h-1"></div>`;
      return `<p class="text-[#4b2e2b]/90">${formatted}</p>`;
    })
    .join("");
}

// Shared React (via CDN, buildless) + htm binding + Stitch design-system widgets.
import React, { useState, useEffect, useRef, useMemo } from "https://esm.sh/react@18.2.0";
import { createRoot } from "https://esm.sh/react-dom@18.2.0/client";
import htm from "https://esm.sh/htm@3.1.1";

export const html = htm.bind(React.createElement);
export { React, useState, useEffect, useRef, useMemo, createRoot };

// Material Symbols icon. `fill` renders the filled variant.
export const Icon = ({ name, className = "", fill = false, style = {} }) =>
  html`<span
    class="material-symbols-outlined ${className}"
    style=${{ ...(fill ? { fontVariationSettings: "'FILL' 1" } : {}), ...style }}
    >${name}</span
  >`;

export const Spinner = ({ className = "" }) =>
  html`<span class="material-symbols-outlined animate-spin ${className}">progress_activity</span>`;

// Labeled input (Stitch field style).
export const Field = ({ label, hint, ...props }) => html`
  <label class="flex flex-col gap-2">
    ${label && html`<span class="text-body-md text-text-secondary text-sm">${label}</span>`}
    <input
      ...${props}
      class="w-full bg-surface-1 border border-border-light rounded-[16px] px-4 py-3 text-text-primary
             placeholder:text-text-muted focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary
             transition-all ${props.class || ""}"
    />
    ${hint && html`<span class="text-xs text-text-muted">${hint}</span>`}
  </label>
`;

// Button variants: primary (white CTA), gold, ghost, danger.
export const Btn = ({ variant = "primary", className = "", children, loading, ...props }) => {
  const base =
    "rounded-xl font-bold flex items-center justify-center gap-2 transition-transform active:scale-[0.97] disabled:opacity-60";
  const styles = {
    primary: "bg-text-primary text-background py-4",
    gold: "bg-primary text-on-primary py-4 shadow-[0_4px_20px_rgba(239,178,0,0.3)]",
    ghost: "border border-border-light text-text-primary py-3 hover:bg-surface-2",
    dashedGold: "border-2 border-dashed border-primary/40 bg-primary/5 text-primary py-4",
    danger: "bg-danger/10 text-danger py-3",
  };
  return html`<button ...${props} disabled=${props.disabled || loading}
    class="${base} ${styles[variant]} ${className}">
    ${loading ? html`<${Spinner} />` : children}
  </button>`;
};

// Fixed top app bar (glassmorphic).
export const AppBar = ({ title, left, right }) => html`
  <header class="fixed top-0 inset-x-0 max-w-[480px] mx-auto h-16 z-40 px-gutter px-5
                 bg-background/80 backdrop-blur-xl border-b border-border-light flex items-center justify-between">
    <div class="w-10 flex justify-start">${left || ""}</div>
    <h1 class="text-headline-sm text-lg font-bold">${title}</h1>
    <div class="w-10 flex justify-end">${right || ""}</div>
  </header>
`;

// Linear progress bar for the onboarding flow.
export const ProgressBar = ({ step, total }) => html`
  <div class="w-full h-1.5 bg-surface-2 rounded-full overflow-hidden">
    <div class="h-full bg-primary rounded-full transition-all duration-300"
         style=${{ width: `${Math.round((step / total) * 100)}%` }}></div>
  </div>
`;

// Bottom tab nav for the dashboard. tabs: [{key, label, icon}].
export const BottomNav = ({ tabs, active, onSelect }) => html`
  <nav class="fixed bottom-0 inset-x-0 max-w-[480px] mx-auto h-20 z-40 flex flex-row-reverse justify-around items-center
              px-2 bg-surface/70 backdrop-blur-2xl border-t border-border-light">
    ${tabs.map(
      (t) => html`<button
        key=${t.key}
        onClick=${() => onSelect(t.key)}
        class="flex flex-col items-center justify-center flex-1 py-2 ${active === t.key
          ? "text-primary"
          : "text-text-muted"}"
      >
        <${Icon} name=${t.icon} fill=${active === t.key} />
        <span class="text-[10px] leading-none mt-1 ${active === t.key ? "font-bold" : ""}">${t.label}</span>
      </button>`
    )}
  </nav>
`;

// Floating action button (gold).
export const FAB = ({ onClick, icon = "add" }) => html`
  <button onClick=${onClick}
    class="fixed bottom-28 left-6 max-[520px]:left-6 w-14 h-14 z-40 bg-primary text-on-primary rounded-full
           shadow-[0_0_20px_rgba(239,178,0,0.4)] flex items-center justify-center hover:scale-105 active:scale-95 transition-transform">
    <${Icon} name=${icon} className="text-[28px]" />
  </button>
`;

// Centered modal sheet (for add/edit forms). Returns null when not open.
export const Modal = ({ open, onClose, title, children }) =>
  !open
    ? null
    : html`<div class="fixed inset-0 z-50 bg-black/60 flex items-end sm:items-center justify-center" onClick=${onClose}>
        <div class="w-full max-w-[480px] bg-surface-container border border-border-light rounded-t-3xl sm:rounded-3xl p-5"
             onClick=${(e) => e.stopPropagation()}>
          <div class="flex justify-between items-center mb-5">
            <h2 class="text-headline-md text-xl font-bold">${title}</h2>
            <button onClick=${onClose} class="text-text-muted"><${Icon} name="close" /></button>
          </div>
          ${children}
        </div>
      </div>`;

// Build a wa.me deep link from an Israeli phone number + prefilled text.
// Returns null when no usable number is present.
export function waLink(phone, text = "") {
  let d = String(phone || "").replace(/\D/g, "");
  if (!d) return null;
  if (d.startsWith("0")) d = "972" + d.slice(1); // 05X… -> +9725X…
  else if (d.length === 9) d = "972" + d; // 9 digits, no leading 0
  return `https://wa.me/${d}?text=${encodeURIComponent(text)}`;
}

// Lightweight transient toast.
export function toast(msg) {
  const el = document.createElement("div");
  el.textContent = msg;
  el.className =
    "fixed bottom-24 left-1/2 -translate-x-1/2 z-[100] bg-surface-3 border border-border-light " +
    "text-text-primary px-4 py-2 rounded-full text-sm shadow-lg";
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2200);
}

export const fmtTime = (iso) =>
  new Date(iso).toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" });
export const fmtDate = (iso) =>
  new Date(iso).toLocaleDateString("he-IL", { weekday: "short", day: "numeric", month: "short" });
export const ymd = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

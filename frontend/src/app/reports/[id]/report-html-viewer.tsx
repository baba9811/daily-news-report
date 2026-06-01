"use client";

import { useState } from "react";

const LANG_LABELS: Record<string, string> = {
  ko: "한국어",
  en: "English",
  ja: "日本語",
  zh: "中文",
};

interface ReportHtmlViewerProps {
  reportId: number;
  /** Available languages, ordered with the primary (generated) language first. */
  languages?: string[];
}

export default function ReportHtmlViewer({
  reportId,
  languages = [],
}: ReportHtmlViewerProps) {
  const [height, setHeight] = useState(600);
  const primary = languages[0] ?? "";
  const [lang, setLang] = useState(primary);

  function handleLoad(e: React.SyntheticEvent<HTMLIFrameElement>) {
    try {
      const body = e.currentTarget.contentDocument?.body;
      if (body) {
        setHeight(Math.max(600, body.scrollHeight + 40));
      }
    } catch {
      // Cross-origin, keep default height
    }
  }

  const src =
    lang && lang !== primary
      ? `/api/reports/${reportId}/html?lang=${encodeURIComponent(lang)}`
      : `/api/reports/${reportId}/html`;

  return (
    <div>
      {languages.length > 1 && (
        <div
          role="group"
          aria-label="Report language"
          className="mb-3 inline-flex overflow-hidden rounded-lg border border-[var(--border-color)]"
        >
          {languages.map((code) => {
            const active = code === lang;
            return (
              <button
                key={code}
                type="button"
                onClick={() => setLang(code)}
                aria-pressed={active}
                className={
                  "px-3 py-1.5 text-xs font-medium transition-colors " +
                  (active
                    ? "bg-blue-500/20 text-blue-300"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]")
                }
              >
                {LANG_LABELS[code] ?? code.toUpperCase()}
              </button>
            );
          })}
        </div>
      )}
      <iframe
        key={lang}
        src={src}
        className="w-full rounded-lg border border-[var(--border-color)]"
        style={{ height: `${height}px` }}
        onLoad={handleLoad}
        title="Report HTML"
      />
    </div>
  );
}

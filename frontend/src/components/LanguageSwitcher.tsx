"use client";

import { useI18n, type Lang } from "@/lib/i18n";

const OPTIONS: Array<{ value: Lang; label: string }> = [
  { value: "uk", label: "УКР" },
  { value: "en", label: "ENG" },
];

export function LanguageSwitcher() {
  const { lang, setLang } = useI18n();
  return (
    <div className="lang-switch" role="group" aria-label="Language / Мова">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          className={`ghost sm${lang === o.value ? " current" : ""}`}
          onClick={() => setLang(o.value)}
          aria-pressed={lang === o.value}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

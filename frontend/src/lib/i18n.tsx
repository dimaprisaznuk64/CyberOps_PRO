"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

/**
 * Проста локалізація UI без зовнішньої бібліотеки: дві мови, плаский словник
 * і React-контекст.
 *
 * next-intl тягне за собою сегментацію маршрутів на `[locale]`, middleware і
 * серверні залежності — для двох мов і клієнтського рендеру це надлишково.
 * Натомість тут `en` типізований як `Record<keyof typeof uk, string>`: забути
 * переклад якогось ключа не дасть компілятор, а не користувач.
 */

export type Lang = "uk" | "en";

const STORAGE_KEY = "cyberops.lang";

const uk = {
  "common.loading": "Завантаження…",
  "common.error": "Помилка",
  "common.dash": "—",
  "common.id": "ID",
  "common.type": "Тип",
  "common.status": "Статус",
  "common.risk": "Ризик",
  "common.select": "— виберіть —",
  "common.all": "всі",
  "common.save": "Зберегти",
  "common.cancel": "Скасувати",
  "common.close": "Закрити",
  "common.edit": "Редагувати",
  "common.delete": "Видалити",
  "common.view": "Показати",
  "common.create": "Створити",
  "common.noData": "Немає даних",

  "nav.dashboard": "Панель",
  "nav.assets": "Активи",
  "nav.scans": "Скани",
  "nav.findings": "Знахідки",
  "nav.reports": "Звіти",
  "nav.notifications": "Сповіщення",
  "nav.settings": "Налаштування",
  "nav.logout": "Вийти",

  "login.title": "Вхід",
  "login.username": "Username",
  "login.password": "Password",
  "login.submit": "Увійти",
  "login.busy": "Вхід…",
  "login.noAccount": "Немає акаунта?",
  "login.registerLink": "Зареєструватися",
  "login.error": "Помилка входу",

  "register.title": "Реєстрація",
  "register.username": "Username (мін. 3)",
  "register.password": "Password (мін. 8)",
  "register.email": "Email (необовʼязково)",
  "register.submit": "Створити акаунт",
  "register.busy": "Реєстрація…",
  "register.error": "Помилка реєстрації",
  "register.note":
    "Новий акаунт отримує роль user. Підняття до analyst або admin робить адміністратор.",
  "register.haveAccount": "Вже є акаунт?",
  "register.loginLink": "Увійти",

  "home.redirecting": "Перенаправлення…",

  "dashboard.title": "Dashboard",
  "dashboard.assets": "Активи",
  "dashboard.unread": "Непрочитані сповіщення",
  "dashboard.highRisk": "Скани з високим ризиком",
  "dashboard.systemStatus": "Статус системи",
  "dashboard.recentScans": "Останні сканування",
  "dashboard.noScans": "Поки немає сканувань",
  "dashboard.realtime": "Активність у реальному часі",
  "dashboard.wsHint": "Підключіться до WS — події зʼявляться тут",
  "dashboard.quickActions": "Швидкі дії",
  "dashboard.manageAssets": "Керувати assets",
  "dashboard.createScan": "Створити сканування",
  "dashboard.viewFindings": "Переглянути findings",
  "dashboard.reports": "Звіти",

  "assets.title": "Assets",
  "assets.new": "Новий актив",
  "assets.edit": "Редагувати #{id}",
  "assets.name": "Назва",
  "assets.host": "Host",
  "assets.hostPlaceholder": "192.168.1.100 / example.com / vulnerable-api",
  "assets.kind": "Тип",
  "assets.docker": "Docker container (optional)",
  "assets.description": "Опис",
  "assets.saveChanges": "Зберегти зміни",
  "assets.create": "Створити",
  "assets.list": "Список ({count})",
  "assets.sort": "Сортування",
  "assets.sortRisk": "за ризиком",
  "assets.sortName": "за назвою",
  "assets.sortId": "за ID",
  "assets.none": "Немає активів",
  "assets.colName": "Назва",
  "assets.colDocker": "Docker",
  "assets.colHistory": "Історія",
  "assets.colScans": "Скани",
  "assets.colActions": "Дії",
  "assets.notScanned": "не скановано",
  "assets.max": "макс {score} ({level})",
  "assets.last": "останній: {date}",
  "assets.confirmDelete": "Видалити актив?",

  "scans.title": "Scans",
  "scans.new": "Нове сканування",
  "scans.asset": "Актив (ціль)",
  "scans.type": "Тип сканування",
  "scans.ports": "Порти (optional)",
  "scans.portsPlaceholder": "22,80,443  або 1-1000",
  "scans.submit": "Запустити сканування",
  "scans.submitting": "Запуск…",
  "scans.history": "Історія ({count})",
  "scans.none": "Немає сканувань",
  "scans.colStart": "Старт",
  "scans.colFinish": "Фініш",

  "scanDetail.title": "Сканування #{id}",
  "scanDetail.status": "Статус",
  "scanDetail.services": "Сервіси",
  "scanDetail.riskScore": "Risk score",
  "scanDetail.riskLevel": "Risk level",
  "scanDetail.command": "Команда",
  "scanDetail.servicesCount": "Сервіси ({count})",
  "scanDetail.findingsBySeverity": "Findings по серйозності",
  "scanDetail.noFindings": "Немає findings",
  "scanDetail.findings": "Findings ({count})",
  "scanDetail.colPort": "Порт",
  "scanDetail.colProtocol": "Протокол",
  "scanDetail.colService": "Сервіс",
  "scanDetail.colProduct": "Продукт",
  "scanDetail.colVersion": "Версія",
  "scanDetail.colSeverity": "Серйозність",
  "scanDetail.colTitle": "Назва",
  "scanDetail.colRecommendation": "Рекомендація",

  "findings.title": "Findings",
  "findings.severity": "Серйозність",
  "findings.all": "всі",
  "findings.scanId": "Scan ID",
  "findings.scanPlaceholder": "filter by scan",
  "findings.list": "Знахідки ({count})",
  "findings.none": "Немає знахідок",
  "findings.colScan": "Scan",
  "findings.colTitle": "Назва",

  "reports.title": "Reports",
  "reports.new": "Новий звіт",
  "reports.name": "Назва",
  "reports.type": "Тип",
  "reports.scan": "Scan",
  "reports.asset": "Asset",
  "reports.generate": "Згенерувати",
  "reports.list": "Звіти ({count})",
  "reports.none": "Немає звітів",
  "reports.colName": "Назва",
  "reports.colCreated": "Створено",
  "reports.colExport": "Експорт",
  "reports.colDetails": "Деталі",
  "reports.exportFailed": "Export failed: HTTP {status}",
  "reports.details": "Деталі #{id}: {title}",

  "notifications.title": "Notifications",
  "notifications.allChannels": "Усі канали",
  "notifications.unreadOnly": "Тільки непрочитані",
  "notifications.markAll": "Прочитати всі",
  "notifications.none": "Немає сповіщень",
  "notifications.errorPrefix": " — помилка: ",
  "notifications.retry": "Повторити",
  "notifications.markRead": "Прочитано",
  "notifications.retryQueued": "Повторну доставку поставлено в чергу",

  "settings.title": "Settings",
  "settings.profile": "Профіль",
  "settings.user": "Користувач",
  "settings.role": "Роль",
  "settings.logout": "Вийти",
  "settings.changePassword": "Зміна пароля",
  "settings.oldPassword": "Поточний пароль",
  "settings.newPassword": "Новий пароль (мін. 8)",
  "settings.savePassword": "Змінити пароль",
  "settings.savingPassword": "Зберігаємо…",
  "settings.passwordChanged": "Пароль змінено",
  "settings.channels": "Канали сповіщень",
  "settings.telegramChat": "Telegram chat id",
  "settings.minSeverity": "Мінімальний рівень",
  "settings.disabledOnServer": "(вимкнено на сервері)",
  "settings.save": "Зберегти",
  "settings.prefsSaved": "Налаштування сповіщень збережено",
  "settings.testEmail": "Тест Email",
  "settings.testTelegram": "Тест Telegram",
  "settings.sending": "Надсилаємо…",
  "settings.testSent": "Тестове повідомлення надіслано в {channel}",
  "settings.effectivePrefix": "Дієвий поріг: ",
  "settings.effectiveMiddle": ". Серверний поріг ",
  "settings.effectiveSuffix":
    " — нижче нього не надсилаємо, тож ваш вибір спрацює лише якщо він суворіший.",
  "settings.hint.info": "усі сповіщення",
  "settings.hint.low": "від низького ризику",
  "settings.hint.medium": "від середнього ризику",
  "settings.hint.high": "лише високий і критичний",
  "settings.hint.critical": "лише критичний",

  "raw.title": "Сирий Nmap-архів",
  "raw.notAvailable": "Сирого Nmap-звіту немає",
  "raw.notAvailableStatus": " (статус сканування: {status})",
  "raw.notAvailableTail": ". Архів зʼявляється після завершення сканування.",
  "raw.nmap": "Nmap",
  "raw.unknown": "невідомо",
  "raw.size": "Розмір",
  "raw.hosts": "Хостів",
  "raw.portsCount": "{count} портів",
  "raw.stats": "up {up} / down {down} з {total}",
  "raw.downloadXml": "⬇ Завантажити .xml",
  "raw.downloading": "Завантаження…",
  "raw.xmlShown": "XML показано",
  "raw.showXml": "Показати сирий XML",
  "raw.truncated": "XML завеликий для сторінки — повний файл лише у .xml",
  "raw.loadingArchive": "Завантаження архіву…",
  "raw.file": "Файл: ",
  "raw.hostnameUnknown": "hostname не визначено",
  "raw.osFingerprint": "OS-відпечаток",
  "raw.family": "Сімейство",
  "raw.accuracy": "Точність",
  "raw.hostScripts": "Хост-скрипти:",
  "raw.colPort": "Порт",
  "raw.colService": "Сервіс",
  "raw.downloadFailed": "Не вдалося завантажити файл",
  "raw.bytes.b": "Б",
  "raw.bytes.kb": "КБ",
  "raw.bytes.mb": "МБ",

  "ai.button": "🤖 AI explain",
  "ai.analyzing": "Аналіз…",
  "ai.title": "AI пояснення ({provider})",
  "ai.found": "Що знайдено:",
  "ai.impact": "Вплив:",
  "ai.risk": "Ризик:",
  "ai.remediation": "Як виправити:",

  "pill.skipped": "пропущено",
} as const;

const en: Record<keyof typeof uk, string> = {
  "common.loading": "Loading…",
  "common.error": "Error",
  "common.dash": "—",
  "common.id": "ID",
  "common.type": "Type",
  "common.status": "Status",
  "common.risk": "Risk",
  "common.select": "— select —",
  "common.all": "all",
  "common.save": "Save",
  "common.cancel": "Cancel",
  "common.close": "Close",
  "common.edit": "Edit",
  "common.delete": "Delete",
  "common.view": "View",
  "common.create": "Create",
  "common.noData": "No data",

  "nav.dashboard": "Dashboard",
  "nav.assets": "Assets",
  "nav.scans": "Scans",
  "nav.findings": "Findings",
  "nav.reports": "Reports",
  "nav.notifications": "Notifications",
  "nav.settings": "Settings",
  "nav.logout": "Logout",

  "login.title": "Sign in",
  "login.username": "Username",
  "login.password": "Password",
  "login.submit": "Sign in",
  "login.busy": "Signing in…",
  "login.noAccount": "No account?",
  "login.registerLink": "Sign up",
  "login.error": "Login failed",

  "register.title": "Sign up",
  "register.username": "Username (min. 3)",
  "register.password": "Password (min. 8)",
  "register.email": "Email (optional)",
  "register.submit": "Create account",
  "register.busy": "Signing up…",
  "register.error": "Registration failed",
  "register.note":
    "A new account gets the user role. Promotion to analyst or admin is done by an administrator.",
  "register.haveAccount": "Already have an account?",
  "register.loginLink": "Sign in",

  "home.redirecting": "Redirecting…",

  "dashboard.title": "Dashboard",
  "dashboard.assets": "Assets",
  "dashboard.unread": "Unread notifications",
  "dashboard.highRisk": "High-risk scans",
  "dashboard.systemStatus": "System status",
  "dashboard.recentScans": "Recent scans",
  "dashboard.noScans": "No scans yet",
  "dashboard.realtime": "Real-time activity",
  "dashboard.wsHint": "Connect to WS — events will appear here",
  "dashboard.quickActions": "Quick actions",
  "dashboard.manageAssets": "Manage assets",
  "dashboard.createScan": "Create scan",
  "dashboard.viewFindings": "View findings",
  "dashboard.reports": "Reports",

  "assets.title": "Assets",
  "assets.new": "New asset",
  "assets.edit": "Edit #{id}",
  "assets.name": "Name",
  "assets.host": "Host",
  "assets.hostPlaceholder": "192.168.1.100 / example.com / vulnerable-api",
  "assets.kind": "Type",
  "assets.docker": "Docker container (optional)",
  "assets.description": "Description",
  "assets.saveChanges": "Save changes",
  "assets.create": "Create",
  "assets.list": "List ({count})",
  "assets.sort": "Sort",
  "assets.sortRisk": "by risk",
  "assets.sortName": "by name",
  "assets.sortId": "by ID",
  "assets.none": "No assets",
  "assets.colName": "Name",
  "assets.colDocker": "Docker",
  "assets.colHistory": "History",
  "assets.colScans": "Scans",
  "assets.colActions": "Actions",
  "assets.notScanned": "not scanned",
  "assets.max": "max {score} ({level})",
  "assets.last": "last: {date}",
  "assets.confirmDelete": "Delete this asset?",

  "scans.title": "Scans",
  "scans.new": "New scan",
  "scans.asset": "Asset (target)",
  "scans.type": "Scan type",
  "scans.ports": "Ports (optional)",
  "scans.portsPlaceholder": "22,80,443 or 1-1000",
  "scans.submit": "Start scan",
  "scans.submitting": "Starting…",
  "scans.history": "History ({count})",
  "scans.none": "No scans",
  "scans.colStart": "Start",
  "scans.colFinish": "Finish",

  "scanDetail.title": "Scan #{id}",
  "scanDetail.status": "Status",
  "scanDetail.services": "Services",
  "scanDetail.riskScore": "Risk score",
  "scanDetail.riskLevel": "Risk level",
  "scanDetail.command": "Command",
  "scanDetail.servicesCount": "Services ({count})",
  "scanDetail.findingsBySeverity": "Findings by severity",
  "scanDetail.noFindings": "No findings",
  "scanDetail.findings": "Findings ({count})",
  "scanDetail.colPort": "Port",
  "scanDetail.colProtocol": "Protocol",
  "scanDetail.colService": "Service",
  "scanDetail.colProduct": "Product",
  "scanDetail.colVersion": "Version",
  "scanDetail.colSeverity": "Severity",
  "scanDetail.colTitle": "Name",
  "scanDetail.colRecommendation": "Recommendation",

  "findings.title": "Findings",
  "findings.severity": "Severity",
  "findings.all": "all",
  "findings.scanId": "Scan ID",
  "findings.scanPlaceholder": "filter by scan",
  "findings.list": "Findings ({count})",
  "findings.none": "No findings",
  "findings.colScan": "Scan",
  "findings.colTitle": "Name",

  "reports.title": "Reports",
  "reports.new": "New report",
  "reports.name": "Name",
  "reports.type": "Type",
  "reports.scan": "Scan",
  "reports.asset": "Asset",
  "reports.generate": "Generate",
  "reports.list": "Reports ({count})",
  "reports.none": "No reports",
  "reports.colName": "Name",
  "reports.colCreated": "Created",
  "reports.colExport": "Export",
  "reports.colDetails": "Details",
  "reports.exportFailed": "Export failed: HTTP {status}",
  "reports.details": "Details #{id}: {title}",

  "notifications.title": "Notifications",
  "notifications.allChannels": "All channels",
  "notifications.unreadOnly": "Unread only",
  "notifications.markAll": "Mark all read",
  "notifications.none": "No notifications",
  "notifications.errorPrefix": " — error: ",
  "notifications.retry": "Retry",
  "notifications.markRead": "Read",
  "notifications.retryQueued": "Retry queued",

  "settings.title": "Settings",
  "settings.profile": "Profile",
  "settings.user": "User",
  "settings.role": "Role",
  "settings.logout": "Log out",
  "settings.changePassword": "Change password",
  "settings.oldPassword": "Current password",
  "settings.newPassword": "New password (min. 8)",
  "settings.savePassword": "Change password",
  "settings.savingPassword": "Saving…",
  "settings.passwordChanged": "Password changed",
  "settings.channels": "Notification channels",
  "settings.telegramChat": "Telegram chat id",
  "settings.minSeverity": "Minimum level",
  "settings.disabledOnServer": "(disabled on server)",
  "settings.save": "Save",
  "settings.prefsSaved": "Notification settings saved",
  "settings.testEmail": "Test Email",
  "settings.testTelegram": "Test Telegram",
  "settings.sending": "Sending…",
  "settings.testSent": "Test message sent to {channel}",
  "settings.effectivePrefix": "Effective threshold: ",
  "settings.effectiveMiddle": ". Server threshold ",
  "settings.effectiveSuffix":
    " — we never send below it, so your choice only applies if it is stricter.",
  "settings.hint.info": "all notifications",
  "settings.hint.low": "low risk and above",
  "settings.hint.medium": "medium risk and above",
  "settings.hint.high": "high and critical only",
  "settings.hint.critical": "critical only",

  "raw.title": "Raw Nmap archive",
  "raw.notAvailable": "No raw Nmap report",
  "raw.notAvailableStatus": " (scan status: {status})",
  "raw.notAvailableTail": ". The archive appears after the scan finishes.",
  "raw.nmap": "Nmap",
  "raw.unknown": "unknown",
  "raw.size": "Size",
  "raw.hosts": "Hosts",
  "raw.portsCount": "{count} ports",
  "raw.stats": "up {up} / down {down} of {total}",
  "raw.downloadXml": "⬇ Download .xml",
  "raw.downloading": "Downloading…",
  "raw.xmlShown": "XML shown",
  "raw.showXml": "Show raw XML",
  "raw.truncated": "XML is too large for the page — full file only in .xml",
  "raw.loadingArchive": "Loading archive…",
  "raw.file": "File: ",
  "raw.hostnameUnknown": "hostname not determined",
  "raw.osFingerprint": "OS fingerprint",
  "raw.family": "Family",
  "raw.accuracy": "Accuracy",
  "raw.hostScripts": "Host scripts:",
  "raw.colPort": "Port",
  "raw.colService": "Service",
  "raw.downloadFailed": "Failed to download file",
  "raw.bytes.b": "B",
  "raw.bytes.kb": "KB",
  "raw.bytes.mb": "MB",

  "ai.button": "🤖 AI explain",
  "ai.analyzing": "Analyzing…",
  "ai.title": "AI explanation ({provider})",
  "ai.found": "What was found:",
  "ai.impact": "Impact:",
  "ai.risk": "Risk:",
  "ai.remediation": "How to fix:",

  "pill.skipped": "skipped",
};

export type TKey = keyof typeof uk;

type Params = Record<string, string | number>;

const DICTS: Record<Lang, Record<TKey, string>> = { uk, en };

const LOCALES: Record<Lang, string> = { uk: "uk-UA", en: "en-US" };

function format(template: string, params?: Params): string {
  if (!params) return template;
  let out = template;
  for (const [key, value] of Object.entries(params)) {
    out = out.replaceAll(`{${key}}`, String(value));
  }
  return out;
}

interface I18nState {
  lang: Lang;
  /** Локаль для toLocaleString — щоб дати не лишалися українськими в англ. UI. */
  locale: string;
  setLang: (lang: Lang) => void;
  t: (key: TKey, params?: Params) => string;
}

const I18nContext = createContext<I18nState | null>(null);

function readSavedLang(): Lang {
  if (typeof window === "undefined") return "uk";
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return saved === "en" || saved === "uk" ? saved : "uk";
  } catch {
    return "uk";
  }
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  // Початковий стан однаковий на сервері й клієнті ("uk"), а збережений вибір
  // підхоплюється в ефекті — інакше SSR і гідратація розійшлися б у розмітці.
  const [lang, setLangState] = useState<Lang>("uk");

  useEffect(() => {
    setLangState(readSavedLang());
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // приватний режим або вимкнений localStorage — мова просто не збережеться
    }
  }, []);

  const t = useCallback(
    (key: TKey, params?: Params) => format(DICTS[lang][key] ?? key, params),
    [lang]
  );

  const value = useMemo(
    () => ({ lang, locale: LOCALES[lang], setLang, t }),
    [lang, setLang, t]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nState {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}

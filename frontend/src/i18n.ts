import { createI18n } from "vue-i18n";
import zh from "./locales/zh";
import en from "./locales/en";
const saved = localStorage.getItem("combuddy-lang");
const locale = saved || (navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en");
export const i18n = createI18n({ legacy: false, locale, fallbackLocale: "zh", messages: { zh, en } });
export function setLocale(l: "zh" | "en") { localStorage.setItem("combuddy-lang", l); i18n.global.locale.value = l; }

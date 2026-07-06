import { cpSync, mkdirSync, readdirSync, rmSync } from "node:fs";
const SRC = "node_modules/primevue/resources/themes";
const DST = "public/themes";
const PALETTES = ["green", "blue", "cyan", "purple", "amber"];
const MODES = ["light", "dark"];
rmSync(DST, { recursive: true, force: true });
mkdirSync(`${DST}/fonts`, { recursive: true });
// 共享一套字体(所有 aura 主题字体相同,文件名一致)
const fdir = `${SRC}/aura-dark-green/fonts`;
for (const f of readdirSync(fdir)) cpSync(`${fdir}/${f}`, `${DST}/fonts/${f}`);
// 扁平拷贝 10 个 theme.css → public/themes/{name}.css(内部 ./fonts/ 解析到共享 fonts)
for (const m of MODES) for (const p of PALETTES) {
  const name = `aura-${m}-${p}`;
  cpSync(`${SRC}/${name}/theme.css`, `${DST}/${name}.css`);
}
console.log("copied 10 aura themes + shared fonts → public/themes");

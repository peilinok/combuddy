# combuddy 品牌指南

**combuddy** = Comfy(UI) + buddy —— 你的 ComfyUI 依赖管家。

- 中文标语：你的 ComfyUI 依赖管家
- 英文标语：Your ComfyUI model librarian
- 描述句：A local-first dependency manager for ComfyUI models and workflows

## 色板

取自产品 Aura green 主题（`combuddy/web/themes/aura-*-green.css`），保证 logo 与 UI 同源。

| 角色 | Hex |
|---|---|
| Emerald 500（主色） | `#10b981` |
| Emerald 600 | `#0e9d6e` |
| Emerald 700 | `#047857` |
| Emerald 400（暗底 mark） | `#34d399` |
| Emerald 300（高亮） | `#6ee7b7` |
| 墨底 | `#0a0a0a` |
| 纸白 | `#ffffff` |

App 图标 / favicon 标准配色：emerald `#10b981` 圆角实底 + 白色 mark。

## Logo

设计：三个依赖节点串成一条对勾路径 —— 既是依赖图，又是「已解析 / 安全清理」。几何母版（viewBox `0 0 100 100`）：路径 `M27 53 L44 69 L74 30`，节点 `(27,53)`、`(44,69)`、`(74,30)`。

| 文件 | 何时用 |
|---|---|
| `branding/logo-mark.svg` | 需自定义颜色时（`currentColor`） |
| `branding/logo-mark-emerald.svg` | 亮底 |
| `branding/logo-mark-white.svg` | emerald / 暗底 |
| `branding/favicon.svg` | 网站 / 应用图标（自带 emerald 圆底） |
| `branding/logo-lockup-light.svg` / `-dark.svg` | logo + 字标 + 标语的横向组合 |
| `branding/banner-light.svg` / `-dark.svg` | README 横幅源 |
| `branding/social-card.svg` | GitHub 社交卡片源 |

派生落地：`packaging/icons/combuddy.icns`（macOS）、`packaging/icons/combuddy.ico`（Windows）、`frontend/public/favicon.svg`（→ 构建进 `combuddy/web/`）、`.github/images/banner-*.png` 与 `social-card.png`。

## 使用规则

- **留白**：mark 四周留白 ≥ 一个节点直径。
- **最小尺寸**：mark 16px；横向锁定组合高度 ≥ 24px（更小只用 mark）。
- **字标**：全小写 `combuddy`，`com` 用墨色 / 浅色，`buddy` 用 emerald。
- **不要**：拉伸变形、改主色、加阴影 / 外描边、放在低对比度背景上、旋转。

## 字体

字标与标语使用几何无衬线（`system-ui` / Inter 栈）。中文回落到系统字体（macOS PingFang 等）。

## 标语候选（备用）

- 功能三问：在用没用、缺没缺、能不能删，一目了然 / Know what's used, find what's missing, clean the rest
- 行动利落：理清模型，找回缺失，放心清理 / Map, resolve, and clean — all local

## 资源再生成

**App 图标（.icns / .ico）** —— 改 `packaging/gen_icons.py` 的几何后：

```bash
pip install pillow           # dev-only，非项目依赖
python packaging/gen_icons.py
```

**前端 favicon** —— 改 `branding/favicon.svg` 后：

```bash
cp branding/favicon.svg frontend/public/favicon.svg
cd frontend && npm run build   # 产出 combuddy/web/favicon.svg
```

**Banner / 社交卡片 PNG** —— 改 `branding/*.svg` 后，用 Chrome headless 按原尺寸重截（2× 高清）：

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
  --default-background-color=00000000 --window-size=1280,360 \
  --screenshot="$PWD/.github/images/banner-light.png" "file://$PWD/branding/banner-light.svg"
# banner-dark 同上；social-card 改 --window-size=1280,640
```

> 注意：GitHub README 不渲染 `raw.githubusercontent.com` 上的 SVG，故 banner / 卡片以 PNG 提交、SVG 仅作源文件。

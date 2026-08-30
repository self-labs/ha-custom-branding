[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?logo=home-assistant&logoColor=white)](https://hacs.xyz/) [![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-41BDF5?logo=home-assistant&logoColor=white)](https://www.home-assistant.io/) [![License: MIT](https://img.shields.io/badge/license-MIT-blue)](./LICENSE)

# 🎨 Custom Branding

Put your own mark on a Home Assistant install: browser tab, **login screen**, loading logo, footer and the icon of the app installed on the phone.

Everything is configured from the interface, and nothing has to be copied back after a `docker pull`.

## Why this exists

Home Assistant has no white-label option. The workarounds people usually reach for all fall short:

| Approach                           | Problem                                                                              |
| :--------------------------------- | :----------------------------------------------------------------------------------- |
| Replace files inside the container | Lost on every image update, and the path carries the Python version                  |
| JS module via `extra_module_url`   | Never loaded on `/auth/authorize`, so the login screen keeps the Home Assistant logo |
| `thomasloven/hass-favicon`         | Marked DEPRECATED by its own author since 2021                                       |
| Browser Mod favicon                | Great for the tab, but explicitly does not touch the manifest icons                  |
| Reverse proxy rewrites             | Works, but couples the proxy config to the Home Assistant deployment                 |

This integration takes a different route: it **registers one static route per file** over `/static/icons/*` and `/static/images/*`. aiohttp resolves by longest matching prefix, so a route for `/static/icons/favicon.ico` wins over the frontend's own `/static` directory resource, regardless of registration order. The login screen asks for that exact URL, so it gets your icon without anything being patched.

## What it covers

| Surface                                     | How                                      | Needs opt-in? |
| :------------------------------------------ | :--------------------------------------- | :------------ |
| Browser tab icon                            | Static route                             | No            |
| Login screen icon and artwork               | Static route                             | No            |
| Onboarding icon                             | Static route                             | No            |
| Loading logo                                | Static route                             | No            |
| Open Home Foundation footer                 | Static route                             | No            |
| Windows tiles, Safari pinned tab            | Static route                             | No            |
| Installed app (PWA) name and icons          | `add_manifest_json_key`                  | No            |
| Browser tab **title** and app name metadata | ES module, loaded by the integration     | No            |
| **Login and onboarding page titles**        | File rewrite inside the frontend package | **Yes**       |

Only the last row touches anything inside the container, it is off by default, it keeps a backup, and it reapplies itself on every start so an image update does not undo it.

> [!NOTE]
> The Home Assistant logo shown **inside** the app (the one in the sidebar header) is inline SVG compiled into the JavaScript bundle. No static file, no route, no way to swap it short of rebuilding the frontend.

## Install

### HACS (recommended)

1. HACS → three-dot menu → **Custom repositories**.
2. URL: `https://github.com/self-labs/ha-custom-branding`, type **Integration** → **ADD**.
3. Open the entry and click **Download**.
4. Restart Home Assistant.

### Manual

Copy `custom_components/custom_branding/` into your `config/custom_components/` and restart.

## Set up

### 1. Prepare the artwork

Create a folder inside the configuration directory, `config/custom_branding/` by default, and put the files there using **the exact names below**. Everything is optional: whatever is missing simply keeps the Home Assistant original.

```text
config/custom_branding/
├── favicon.ico                    # tab, login, onboarding
├── favicon-16x16.png
├── favicon-32x32.png
├── favicon-192x192.png            # login screen artwork + PWA
├── favicon-384x384.png            # PWA
├── favicon-512x512.png            # PWA
├── favicon-1024x1024.png          # PWA
├── favicon-apple-180x180.png      # iOS home screen, opaque background
├── mask-icon.svg                  # Safari pinned tab, monochrome SVG
├── login-icon.svg                 # OPTIONAL, takes over the login screen slot
├── maskable_icon-48x48.png        # Android adaptive icon
├── maskable_icon-72x72.png
├── maskable_icon-96x96.png
├── maskable_icon-128x128.png
├── maskable_icon-192x192.png
├── maskable_icon-384x384.png
├── maskable_icon-512x512.png
├── logo-loading.svg               # logo on the loading screen
├── footer-light.svg               # footer, light theme
└── footer-dark.svg                # footer, dark theme
```

The bare minimum that looks finished: `favicon.ico`, `favicon-192x192.png`, `favicon-512x512.png`, `maskable_icon-512x512.png` and `logo-loading.svg`.

### Following the light and dark theme

Three of these are drawn straight onto the Home Assistant background, which is `#fafafa` in the light theme and `#111111` in the dark one. No single colour clears 3:1 against both, so a fixed-colour asset is guaranteed to look wrong in one of them, and an opaque background turns into a bright square floating in the dark theme.

**An SVG can follow the theme**, because a browser applies the CSS inside an SVG loaded through `img`, media queries included:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">
  <style><![CDATA[
    path { fill: #293a44; }
    @media (prefers-color-scheme: dark) { path { fill: #e3e0d9; } }
  ]]></style>
  <path d="..."/>
</svg>
```

The `CDATA` is not optional: an SVG served as `image/svg+xml` is parsed as strict XML, so a bare `<` or `&` anywhere in that CSS breaks the whole file.

| Slot | Rendered at | Theme-aware how |
| :--- | :--- | :--- |
| Login and onboarding | 56x56 square | `login-icon.svg`, media query inside the file |
| Loading screen | 96x96 square | `logo-loading.svg`, media query inside the file |
| Footer | 237x24 | Two files: Home Assistant picks with `picture` + `prefers-color-scheme` |

**`login-icon.svg` is the odd one.** That slot is a PNG in the frontend markup, and a PNG cannot carry a media query. aiohttp picks the `Content-Type` from the file on disk rather than from the URL, so when this file exists the integration serves it at `/static/icons/favicon-192x192.png` and the browser receives `image/svg+xml` and renders it as SVG. The PWA manifest keeps pointing at the real PNG, since an app icon has to be a bitmap.

Both square slots are square: a wordmark dropped in there renders letterboxed and tiny (a 3:1 logo in a 96x96 box comes out 96x30). Use the compact mark for those two and the wordmark for the footer.

Generating them from a square logo, with ImageMagick 7:

```bash
for s in 16 32 192 384 512 1024; do
  magick logo.png -resize ${s}x${s} -background none -gravity center \
    -extent ${s}x${s} favicon-${s}x${s}.png
done
magick favicon-32x32.png favicon-16x16.png favicon.ico

# Apple touch: opaque background, iOS paints any alpha channel black
magick logo.png -resize 180x180 -background "#FFFFFF" -gravity center \
  -extent 180x180 -alpha remove -alpha off favicon-apple-180x180.png

# Maskable: the glyph must fit the central 80% circle, and no transparency
for s in 48 72 96 128 192 384 512; do
  inner=$(( s * 72 / 100 ))
  magick logo.png -resize ${inner}x${inner} -background "#FFFFFF" \
    -gravity center -extent ${s}x${s} -alpha remove -alpha off \
    maskable_icon-${s}x${s}.png
done
```

### 2. Add the integration

**Settings → Devices & services → Add integration → Custom Branding**, then fill in:

| Field                            | Meaning                                                                  |
| :------------------------------- | :----------------------------------------------------------------------- |
| **Brand name**                   | Replaces "Home Assistant" in the tab title and in the installed app name |
| **Asset folder**                 | Path relative to the configuration directory. Default `custom_branding`  |
| **Rewrite the login page title** | Off by default. See below                                                |

Restart Home Assistant once more, so the static routes are registered.

### 3. Clear the cache, once

The service worker caches `/static/**` **first and forever**: it has no expiry.

- A browser that has **never** opened this Home Assistant gets the new artwork immediately.
- A browser that already opened it keeps the old icons until you clear the site data (DevTools → Application → Clear storage, or `Ctrl + F5` plus a hard reload).

This matters exactly once, right after setup. Deliveries to a new client are unaffected.

## The login page title

The login and onboarding screens are plain static HTML with a hardcoded `<title>Home Assistant</title>`, served by exact-match routes. There is no template hook and they cannot be shadowed by a route, so the title is the one thing that requires rewriting the file inside the `home-assistant-frontend` package.

If you turn the option on, the integration:

1. Takes a backup next to the original (`authorize.html.custom_branding-orig`).
2. Rewrites the title and marks the file.
3. **Regenerates the `.gz` and `.br` twins.** This step is what most attempts miss: aiohttp serves the pre-compressed sidecar with priority, so patching only the plain file means every real browser keeps receiving the original page.
4. Repeats all of it on every start, so a `docker pull` that wipes `site-packages` is picked back up automatically.

Turning the option off, or calling `custom_branding.restore`, puts the originals back.

> [!WARNING]
> `onboarding.html` is served with `Cache-Control: public, max-age=2678400` (31 days). A browser that already loaded that screen may keep the old one for a while. It runs once per install, so this rarely matters, but do the setup before handing the machine over.

## Actions

| Action                    | What it does                                                                            |
| :------------------------ | :-------------------------------------------------------------------------------------- |
| `custom_branding.apply`   | Re-reads the asset folder and reapplies everything. Use after replacing an icon on disk |
| `custom_branding.restore` | Puts the original login and onboarding pages back                                       |

> [!NOTE]
> Adding a file that was **not** there when Home Assistant started still needs a restart: aiohttp has no public API to add a route after the fact without conflicts. Replacing a file that already exists takes effect immediately.

## Trademark

The Home Assistant name and logo, and the Open Home Foundation marks, belong to their owners. Replacing the artwork on an installation you operate is a local change; **redistributing** a modified Home Assistant under a different name is a separate question, governed by their trademark policy. Check it before shipping a rebranded product.

## Compatibility

Requires **Home Assistant 2024.12 or newer**. Two independent floors: `async_register_static_paths` (2024.7, which replaced the older blocking `register_static_path`) and the framework-provided `OptionsFlow.config_entry` property (2024.12), which is what lets the options flow have an empty constructor. The higher of the two wins.

Tested against the interfaces of the 2026.x frontend. If a future release renames the icon files, the integration logs a warning and leaves the originals in place rather than serving something broken.

## License

MIT. See [LICENSE](./LICENSE).

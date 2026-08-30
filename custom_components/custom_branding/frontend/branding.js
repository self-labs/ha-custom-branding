/**
 * Custom Branding: browser tab title and app-name metadata.
 *
 * Loaded automatically by the integration through frontend.add_extra_js_url,
 * so there is nothing to add to configuration.yaml.
 *
 * The icons are NOT handled here. They are served by static routes that
 * override /static/icons/* and /static/images/*, which is why the login screen
 * and the loading logo get the brand too, even though this module never runs
 * on those pages.
 *
 * What this module is for: Home Assistant rewrites document.title on every
 * panel change, in the form "Panel – Home Assistant", with the product name
 * hardcoded in the bundle. Setting the title once would only last until the
 * first click.
 */

const BRAND =
  new URL(import.meta.url).searchParams.get("brand") || "Home Assistant";
const HA_NAME = "Home Assistant";

const setMeta = (name, content) => {
  let el = document.head.querySelector(`meta[name="${name}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute("name", name);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
};

const applyMeta = () => {
  // The label under the icon on the iOS home screen and on Windows tiles.
  setMeta("apple-mobile-web-app-title", BRAND);
  setMeta("application-name", BRAND);
  // Safari's smart banner pushing the Companion App on the App Store.
  document.head
    .querySelectorAll('meta[name="apple-itunes-app"]')
    .forEach((el) => el.remove());
};

const applyTitle = () => {
  const current = document.title;
  if (!current || !current.includes(HA_NAME)) return;
  const next = current.split(HA_NAME).join(BRAND);
  if (next !== current) document.title = next;
};

if (BRAND !== HA_NAME) {
  applyMeta();
  applyTitle();

  const titleEl = document.querySelector("title");
  if (titleEl) {
    new MutationObserver(applyTitle).observe(titleEl, {
      childList: true,
      characterData: true,
      subtree: true,
    });
  }

  // The frontend re-adds its own metas after some navigations.
  new MutationObserver((records) => {
    const touched = records.some((r) =>
      [...r.addedNodes].some(
        (n) =>
          n.nodeName === "META" &&
          ["apple-mobile-web-app-title", "application-name", "apple-itunes-app"].includes(
            n.getAttribute("name")
          )
      )
    );
    if (touched) applyMeta();
    applyTitle();
  }).observe(document.head, { childList: true });

  document.addEventListener("visibilitychange", applyTitle);
}

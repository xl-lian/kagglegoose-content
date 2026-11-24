// Apply the saved appearance before the stylesheet paints the first frame.
(() => {
  const key = "kagglegoose.theme";
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  const browserColor = document.querySelector('meta[name="theme-color"]');
  let preference = "system";

  function apply(value) {
    preference = value === "dark" || value === "light" ? value : "system";
    const dark = preference === "system" ? system.matches : preference === "dark";
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    browserColor.content = dark ? "#101713" : "#f6f8f4";
    const picker = document.getElementById("theme");
    if (picker) picker.value = preference;
  }

  try {
    preference = localStorage.getItem(key);
  } catch {}
  apply(preference);
  system.addEventListener("change", () => apply(preference));
  window.addEventListener("storage", (event) => {
    if (event.key === key || event.key === null) apply(event.newValue);
  });
  document.addEventListener("DOMContentLoaded", () => {
    const picker = document.getElementById("theme");
    picker.value = preference;
    picker.addEventListener("change", () => {
      apply(picker.value);
      try {
        localStorage.setItem(key, preference);
      } catch {}
    });
  });
})();

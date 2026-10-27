const root = document.documentElement;
const toggle = document.getElementById("theme-toggle");
const systemDark = matchMedia("(prefers-color-scheme: dark)");

function savedTheme() {
  try {
    return localStorage.getItem("theme");
  } catch (e) {
    return null;
  }
}

function applyTheme(theme) {
  root.dataset.bsTheme = theme;
  const next = theme === "dark" ? "light" : "dark";
  toggle.querySelector(".icon-moon").classList.toggle("d-none", next !== "dark");
  toggle.querySelector(".icon-sun").classList.toggle("d-none", next === "dark");
  toggle.setAttribute("aria-label", `Switch to ${next} mode`);
  toggle.title = `Switch to ${next} mode`;
  document.querySelectorAll("img[data-chart]").forEach((img) => {
    const src = img.dataset.chart + theme + ".svg";
    if (img.getAttribute("src") !== src) img.src = src;
  });
  document.querySelectorAll("a[data-chart-link]").forEach((a) => {
    a.href = a.dataset.chartLink + theme + ".svg";
  });
}

applyTheme(root.dataset.bsTheme);

toggle.addEventListener("click", () => {
  const theme = root.dataset.bsTheme === "dark" ? "light" : "dark";
  try {
    localStorage.setItem("theme", theme);
  } catch (e) {}
  applyTheme(theme);
});

systemDark.addEventListener("change", (e) => {
  if (!savedTheme()) applyTheme(e.matches ? "dark" : "light");
});

const tocLinks = [...document.querySelectorAll("#toc .nav-link")];
const headings = tocLinks.map((link) => document.getElementById(link.hash.slice(1)));

function markCurrentSection() {
  let current = 0;
  headings.forEach((h, i) => {
    if (h.getBoundingClientRect().top < 120) current = i;
  });
  tocLinks.forEach((link, i) => {
    link.classList.toggle("active", i === current);
    if (i === current) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  });
}

addEventListener("scroll", markCurrentSection, { passive: true });

const backToTop = document.getElementById("back-to-top");

function toggleBackToTop() {
  backToTop.classList.toggle("visible", scrollY > 600);
}

addEventListener("scroll", toggleBackToTop, { passive: true });
toggleBackToTop();
markCurrentSection();

document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => new bootstrap.Tooltip(el));

const copyButton = document.getElementById("copy-citation");
if (copyButton) {
  copyButton.addEventListener("click", async () => {
    const status = document.getElementById("copy-status");
    try {
      await navigator.clipboard.writeText(document.getElementById("citation-text").innerText);
      status.textContent = "Copied";
    } catch (e) {
      status.textContent = "Couldn't copy. Select the text instead.";
    }
  });
}

const printButton = document.getElementById("print-report");
if (printButton) {
  printButton.addEventListener("click", () => {
    location.href = "./#print";
  });
}

if (location.hash === "#print") {
  addEventListener("load", () => {
    history.replaceState(null, "", location.pathname);
    print();
  });
}

document.addEventListener("show.bs.collapse", (e) => {
  const button = document.querySelector(`[data-bs-target="#${e.target.id}"]`);
  button.textContent = button.dataset.hideText;
});
document.addEventListener("hide.bs.collapse", (e) => {
  const button = document.querySelector(`[data-bs-target="#${e.target.id}"]`);
  button.textContent = button.dataset.showText;
});

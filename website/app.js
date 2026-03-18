const nav = document.getElementById("site-nav");
const navLinks = document.getElementById("nav-links");
const mobileToggle = document.querySelector(".mobile-toggle");
const themeToggle = document.querySelector("[data-theme-toggle]");
const revealItems = [...document.querySelectorAll(".reveal")];

const applyTheme = (theme) => {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("synthesis-theme", theme);
};

const storedTheme = localStorage.getItem("synthesis-theme");
if (storedTheme === "light" || storedTheme === "dark") {
  applyTheme(storedTheme);
}

themeToggle?.addEventListener("click", () => {
  const current = document.documentElement.getAttribute("data-theme");
  applyTheme(current === "dark" ? "light" : "dark");
});

mobileToggle?.addEventListener("click", () => {
  const isOpen = navLinks?.classList.toggle("is-open");
  mobileToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
});

document.querySelectorAll(".nav-links a").forEach((link) => {
  link.addEventListener("click", () => {
    navLinks?.classList.remove("is-open");
    mobileToggle?.setAttribute("aria-expanded", "false");
  });
});

const syncScrolledNav = () => {
  if (!nav) {
    return;
  }

  nav.classList.toggle("is-scrolled", window.scrollY > 12);
};

window.addEventListener("scroll", syncScrolledNav, { passive: true });
syncScrolledNav();

const showItem = (element) => {
  element.classList.add("is-visible");
};

if ("IntersectionObserver" in window) {
  const revealObserver = new IntersectionObserver(
    (entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }

        showItem(entry.target);
        observer.unobserve(entry.target);
      });
    },
    {
      threshold: 0.16,
      rootMargin: "0px 0px -40px 0px",
    },
  );

  revealItems.forEach((item, index) => {
    item.style.setProperty("--reveal-delay", `${Math.min(index * 45, 240)}ms`);
    revealObserver.observe(item);
  });
} else {
  revealItems.forEach(showItem);
}

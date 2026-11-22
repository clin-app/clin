// Menu "tutte le sezioni": si chiude dopo la scelta, con Esc o cliccando fuori.
const more = document.querySelector(".nav-more");
if (more) {
  more.querySelectorAll(".nav-menu a").forEach((a) => a.addEventListener("click", () => { more.open = false; }));
  document.addEventListener("click", (e) => { if (more.open && !more.contains(e.target)) more.open = false; });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") more.open = false; });
}

function ready(fn) {
  if (document.readyState !== "loading") {
    fn();
  } else {
    document.addEventListener("DOMContentLoaded", fn);
  }
}

ready(() => {
  const tabs = document.querySelectorAll(".tab");
  const panels = {
    programs: document.getElementById("tab-programs"),
    unified: document.getElementById("tab-unified"),
    cutoffs: document.getElementById("tab-cutoffs"),
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      Object.values(panels).forEach((p) => p.classList.remove("active"));
      const key = tab.dataset.tab;
      if (panels[key]) {
        panels[key].classList.add("active");
      }
    });
  });

  const table = document.getElementById("programTable");
  if (!table) return;

  const headers = table.querySelectorAll("th[data-sort]");
  const tbody = table.querySelector("tbody");

  headers.forEach((header, index) => {
    header.addEventListener("click", () => {
      const current = header.dataset.direction || "desc";
      const nextDirection = current === "asc" ? "desc" : "asc";
      headers.forEach((h) => delete h.dataset.direction);
      header.dataset.direction = nextDirection;

      const rows = Array.from(tbody.querySelectorAll("tr"));
      rows.sort((a, b) => {
        const av = a.children[index].textContent.trim();
        const bv = b.children[index].textContent.trim();
        const an = Number(av);
        const bn = Number(bv);
        const numeric = !Number.isNaN(an) && !Number.isNaN(bn);
        if (numeric) {
          return nextDirection === "asc" ? an - bn : bn - an;
        }
        return nextDirection === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      });
      rows.forEach((r) => tbody.appendChild(r));
    });
  });

  const searchInput = document.getElementById("searchInput");
  const consentFilter = document.getElementById("consentFilter");
  const priorityFilter = document.getElementById("priorityFilter");

  function applyFilters() {
    const query = (searchInput.value || "").trim();
    const consent = consentFilter.value;
    const priority = priorityFilter.value;
    const rows = Array.from(tbody.querySelectorAll("tr"));

    rows.forEach((row) => {
      const applicant = row.dataset.applicant || "";
      const rowConsent = row.dataset.consent || "";
      const rowPriority = row.dataset.priority || "";

      let visible = true;
      if (query && !applicant.includes(query)) visible = false;
      if (consent !== "all" && rowConsent !== consent) visible = false;
      if (priority !== "all" && rowPriority !== priority) visible = false;

      row.style.display = visible ? "" : "none";
    });
  }

  [searchInput, consentFilter, priorityFilter].forEach((el) => {
    if (el) el.addEventListener("input", applyFilters);
    if (el) el.addEventListener("change", applyFilters);
  });
});
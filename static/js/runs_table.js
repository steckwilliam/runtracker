(function () {
    const table = document.getElementById("runsTable");
    if (!table) {
        return;
    }

    const tbody = document.getElementById("runsTableBody");
    const pageSizeSelect = document.getElementById("runsPageSize");
    const prevBtn = document.getElementById("runsPrevPage");
    const nextBtn = document.getElementById("runsNextPage");
    const pageIndicator = document.getElementById("runsPageIndicator");
    const sortButtons = table.querySelectorAll(".runs-table__sort");

    const NUMERIC_SORT_KEYS = new Set(["distance", "pace", "time", "weather", "starttime"]);

    const DEFAULT_SORT_DIR = {
        date: "desc",
        starttime: "asc",
        run: "asc",
        distance: "desc",
        pace: "asc",
        time: "desc",
        weather: "desc",
    };

    let rows = Array.from(tbody.querySelectorAll("tr"));
    let currentPage = 1;
    let pageSize = 10;
    let sortKey = "date";
    let sortDir = "desc";

    function getSortValue(row, key) {
        switch (key) {
            case "date":
                return row.getAttribute("data-sort-date") || "";
            case "starttime":
                return parseInt(row.getAttribute("data-sort-starttime"), 10) || -1;
            case "run":
                return (row.getAttribute("data-sort-run") || "").toLowerCase();
            case "distance":
                return parseFloat(row.getAttribute("data-sort-distance")) || 0;
            case "pace":
                return parseInt(row.getAttribute("data-sort-pace"), 10) || 0;
            case "time":
                return parseInt(row.getAttribute("data-sort-time"), 10) || 0;
            case "weather":
                return parseInt(row.getAttribute("data-sort-weather"), 10) || -1;
            default:
                return "";
        }
    }

    function compareRows(a, b) {
        const aVal = getSortValue(a, sortKey);
        const bVal = getSortValue(b, sortKey);
        let result = 0;

        if (NUMERIC_SORT_KEYS.has(sortKey)) {
            result = aVal - bVal;
        } else if (sortKey === "date") {
            result = String(aVal).localeCompare(String(bVal));
        } else {
            result = String(aVal).localeCompare(String(bVal));
        }

        return sortDir === "asc" ? result : -result;
    }

    function sortRows() {
        rows.sort(compareRows);
        rows.forEach((row) => tbody.appendChild(row));
    }

    function getTotalPages() {
        if (pageSize === "all") {
            return 1;
        }
        return Math.max(1, Math.ceil(rows.length / pageSize));
    }

    function renderPage() {
        const totalPages = getTotalPages();
        if (currentPage > totalPages) {
            currentPage = totalPages;
        }

        const size = pageSize === "all" ? rows.length : pageSize;
        const start = (currentPage - 1) * size;
        const end = start + size;

        rows.forEach((row, index) => {
            const visible = pageSize === "all" || (index >= start && index < end);
            row.classList.toggle("d-none", !visible);
        });

        pageIndicator.textContent = "Page " + currentPage + " of " + totalPages;
        prevBtn.disabled = currentPage <= 1;
        nextBtn.disabled = currentPage >= totalPages || rows.length === 0;
    }

    function updateSortIndicators() {
        sortButtons.forEach((button) => {
            const upArrow = button.querySelector(".runs-table__sort-arrow--up");
            const downArrow = button.querySelector(".runs-table__sort-arrow--down");
            const key = button.dataset.sortKey;
            const isActive = key === sortKey;

            button.classList.toggle("runs-table__sort--active", isActive);
            button.setAttribute(
                "aria-sort",
                isActive ? (sortDir === "asc" ? "ascending" : "descending") : "none"
            );

            upArrow.classList.toggle(
                "runs-table__sort-arrow--highlight",
                isActive && sortDir === "asc"
            );
            downArrow.classList.toggle(
                "runs-table__sort-arrow--highlight",
                isActive && sortDir === "desc"
            );
        });
    }

    sortButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const key = button.dataset.sortKey;
            if (key === sortKey) {
                sortDir = sortDir === "asc" ? "desc" : "asc";
            } else {
                sortKey = key;
                sortDir = DEFAULT_SORT_DIR[key] || "asc";
            }
            sortRows();
            currentPage = 1;
            updateSortIndicators();
            renderPage();
        });
    });

    pageSizeSelect.addEventListener("change", () => {
        pageSize = pageSizeSelect.value === "all" ? "all" : parseInt(pageSizeSelect.value, 10);
        currentPage = 1;
        renderPage();
    });

    prevBtn.addEventListener("click", () => {
        if (currentPage > 1) {
            currentPage -= 1;
            renderPage();
        }
    });

    nextBtn.addEventListener("click", () => {
        if (currentPage < getTotalPages()) {
            currentPage += 1;
            renderPage();
        }
    });

    sortRows();
    updateSortIndicators();
    renderPage();
})();

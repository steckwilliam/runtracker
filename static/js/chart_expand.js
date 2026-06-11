(function (global) {
    const registry = {};
    let modalEl = null;
    let modalChart = null;
    let escapeHandler = null;

    function cloneChartData(data) {
        return JSON.parse(JSON.stringify(data));
    }

    function modalOptions(options) {
        const next = {
            ...options,
            responsive: true,
            maintainAspectRatio: false,
            plugins: options.plugins ? { ...options.plugins } : {},
            scales: {},
        };

        if (options.scales) {
            Object.keys(options.scales).forEach(function (scaleKey) {
                const scale = options.scales[scaleKey] || {};
                const ticks = scale.ticks || {};
                next.scales[scaleKey] = {
                    ...scale,
                    ticks: {
                        ...ticks,
                        font: {
                            ...(ticks.font || {}),
                            size: 13,
                        },
                    },
                };
                if (scale.title) {
                    next.scales[scaleKey].title = {
                        ...scale.title,
                        font: {
                            ...(scale.title.font || {}),
                            size: 13,
                        },
                    };
                }
            });
        }

        return next;
    }

    function ensureModal() {
        if (modalEl) {
            return;
        }

        modalEl = document.createElement("div");
        modalEl.className = "chart-modal";
        modalEl.hidden = true;
        modalEl.innerHTML =
            '<div class="chart-modal__backdrop" data-chart-modal-close></div>' +
            '<div class="chart-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="chartModalTitle">' +
            '  <div class="chart-modal__header">' +
            '    <h2 class="chart-modal__title" id="chartModalTitle"></h2>' +
            '    <button type="button" class="chart-modal__close" aria-label="Close expanded chart" data-chart-modal-close>&times;</button>' +
            "  </div>" +
            '  <div class="chart-modal__body">' +
            '    <div class="chart-modal__canvas-wrap">' +
            '      <canvas id="chartModalCanvas" aria-label="Expanded chart"></canvas>' +
            "    </div>" +
            "  </div>" +
            "</div>";

        document.body.appendChild(modalEl);

        modalEl.querySelectorAll("[data-chart-modal-close]").forEach(function (el) {
            el.addEventListener("click", closeModal);
        });

        modalEl.querySelector(".chart-modal__dialog").addEventListener("click", function (event) {
            event.stopPropagation();
        });

        escapeHandler = function (event) {
            if (event.key === "Escape" && modalEl && !modalEl.hidden) {
                closeModal();
            }
        };
        document.addEventListener("keydown", escapeHandler);
    }

    function openModal(chartId) {
        const entry = registry[chartId];
        if (!entry || window.matchMedia("(max-width: 767px)").matches) {
            return;
        }

        ensureModal();
        closeModal();

        modalEl.hidden = false;
        modalEl.classList.add("is-open");
        document.body.classList.add("chart-modal-open");
        modalEl.querySelector("#chartModalTitle").textContent = entry.title;

        const canvas = document.getElementById("chartModalCanvas");
        modalChart = new Chart(canvas, {
            type: entry.type,
            data: cloneChartData(entry.data),
            options: modalOptions(entry.options),
        });

        modalEl.querySelector(".chart-modal__close").focus();
    }

    function closeModal() {
        if (modalChart) {
            modalChart.destroy();
            modalChart = null;
        }
        if (modalEl) {
            modalEl.classList.remove("is-open");
            modalEl.hidden = true;
        }
        document.body.classList.remove("chart-modal-open");
    }

    function registerChart(canvasId, title, config) {
        registry[canvasId] = {
            title: title,
            type: config.type,
            data: config.data,
            options: config.options,
        };
    }

    function createChart(canvasId, title, config) {
        registerChart(canvasId, title, config);
        return new Chart(document.getElementById(canvasId), config);
    }

    function init() {
        document.querySelectorAll(".chart-expand-btn[data-chart-id]").forEach(function (button) {
            button.addEventListener("click", function () {
                openModal(button.getAttribute("data-chart-id"));
            });
        });
    }

    global.ChartExpand = {
        registerChart: registerChart,
        createChart: createChart,
        init: init,
    };
})(window);

// Dashboard charts (REQ-FEED-002). Data comes from the json_script element "chart-data";
// this file is static so the 'self' CSP needs no inline scripts.
(function () {
  "use strict";

  var source = document.getElementById("chart-data");
  if (!source || typeof Chart === "undefined") {
    return;
  }
  var data = JSON.parse(source.textContent);

  // One colour per phase, in phase order; repeats if admins add more phases. Validated for
  // colour-blind separation (REQ-UI-003); red stays out, since it means High impact and the brand.
  var palette = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"];
  function colour(index) {
    return palette[index % palette.length];
  }

  // Quiet axes and text in ink colours, so the bars carry the colour (REQ-UI-003).
  Chart.defaults.font.family = '"Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = "#6b6f76";
  Chart.defaults.borderColor = "#eef0f2";
  Chart.defaults.plugins.legend.position = "bottom";
  Chart.defaults.plugins.legend.labels.boxWidth = 10;
  Chart.defaults.plugins.legend.labels.boxHeight = 10;
  Chart.defaults.plugins.tooltip.backgroundColor = "#1d1d1f";

  var byMonth = document.getElementById("chart-by-month");
  if (byMonth) {
    new Chart(byMonth, {
      type: "bar",
      data: {
        labels: data.months,
        datasets: data.series.map(function (series, index) {
          // A 2px white edge separates stacked segments.
          return {
            label: series.label,
            data: series.data,
            backgroundColor: colour(index),
            borderColor: "#fff",
            borderWidth: { top: 2 },
            maxBarThickness: 28
          };
        })
      },
      options: {
        responsive: true,
        aspectRatio: 1.4,
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } }
        },
        plugins: {
          tooltip: {
            callbacks: {
              label: function (item) {
                return item.dataset.label + ", " + item.label + ": " + item.formattedValue;
              }
            }
          }
        }
      }
    });
  }

  var byPhase = document.getElementById("chart-by-phase");
  if (byPhase) {
    var codes = data.series.map(function (series) { return series.code; });
    new Chart(byPhase, {
      type: "bar",
      data: {
        labels: data.totals.map(function (total) { return total.label; }),
        datasets: [{
          label: "Lessons",
          data: data.totals.map(function (total) { return total.count; }),
          backgroundColor: data.totals.map(function (total) { return colour(codes.indexOf(total.code)); }),
          borderRadius: 4,
          maxBarThickness: 22
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        aspectRatio: 1.6,
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0 } },
          y: { grid: { display: false } }
        },
        plugins: { legend: { display: false } }
      }
    });
  }
})();

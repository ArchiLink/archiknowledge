// Dashboard charts (REQ-FEED-002). Data comes from the json_script element "chart-data";
// this file is static so the 'self' CSP needs no inline scripts.
(function () {
  "use strict";

  var source = document.getElementById("chart-data");
  if (!source || typeof Chart === "undefined") {
    return;
  }
  var data = JSON.parse(source.textContent);

  // One colour per phase, in phase order; repeats if admins add more phases.
  var palette = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#76b7b2", "#b07aa1", "#edc948", "#9c755f"];
  function colour(index) {
    return palette[index % palette.length];
  }

  var byMonth = document.getElementById("chart-by-month");
  if (byMonth) {
    new Chart(byMonth, {
      type: "bar",
      data: {
        labels: data.months,
        datasets: data.series.map(function (series, index) {
          return { label: series.label, data: series.data, backgroundColor: colour(index) };
        })
      },
      options: {
        responsive: true,
        scales: {
          x: { stacked: true },
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
          backgroundColor: data.totals.map(function (total) { return colour(codes.indexOf(total.code)); })
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
        plugins: { legend: { display: false } }
      }
    });
  }
})();

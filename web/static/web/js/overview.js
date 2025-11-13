// static/web/js/overview.js
// Overview frontend: final fixed version

const $ = (s) => document.querySelector(s);
const fmt = (v) => (v == null ? "—" : Number(v).toLocaleString("vi-VN"));
const toCurrency = (v) => (v == null ? "—" : Number(v).toLocaleString("vi-VN") + " ₫");

let chartRegion = null;
let chartMain = null;
let chartProductGroup = null;
let chartTop5 = null; // now has its own canvas FIXED

document.addEventListener("DOMContentLoaded", () => {
  const btnFilter = document.getElementById("btn-filter");
  const btnExport = document.getElementById("btn-export");

  if (btnFilter) btnFilter.addEventListener("click", fetchOverview);
  if (btnExport) btnExport.addEventListener("click", downloadOverview);

  fetchOverview();
});

// -----------------------
async function fetchOverview() {
  const btnFilter = document.getElementById("btn-filter");
  try {
    if (btnFilter) {
      btnFilter.dataset.old = btnFilter.textContent;
      btnFilter.textContent = "⏳ Đang thống kê...";
      btnFilter.disabled = true;
    }

    const region = $("#f-region")?.value || "ALL";
    const product = $("#f-product")?.value || "ALL";

    const url = `/api/overview/?region=${encodeURIComponent(region)}&product=${encodeURIComponent(product)}`;
    const res = await fetch(url, { method: "GET", headers: { "Accept":"application/json" } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const payload = await res.json();
    if (!payload) throw new Error("Payload rỗng");

    const dataRows = payload.data || [];
    const timeObj = payload.time || { labels: [], revenue: [], profit: [] };
    const top5 = payload.top5 || { labels: [], values: [] };
    const kpis = payload.kpis || {};

    updateKPIs(kpis);
    renderMainTimeChart(timeObj);
    renderRegionChart(dataRows);
    renderProductGroupChart(dataRows); // FIXED: correct product group
    renderTop5(top5); // FIXED: separate chart canvas

  } catch (err) {
    console.error("❌ Lỗi fetchOverview:", err);
    alert("Không thể tải dữ liệu báo cáo! " + (err.message || ""));
  } finally {
    if (btnFilter) {
      btnFilter.textContent = btnFilter.dataset.old || "Lọc";
      btnFilter.disabled = false;
    }
  }
}

// -----------------------
function updateKPIs(kpis) {
  $("#kpi-revenue").textContent = kpis?.revenue != null ? fmt(kpis.revenue) : "—";
  $("#kpi-cost").textContent = kpis?.cost != null ? fmt(kpis.cost) : "—";
  $("#kpi-profit").textContent = kpis?.profit != null ? fmt(kpis.profit) : "—";
  $("#kpi-profit-rate").textContent = kpis?.profit_pct != null ? kpis.profit_pct + "%" : "—";
}

// -----------------------
function renderMainTimeChart(timeObj) {
  const ctx = $("#chart-rev-profit")?.getContext("2d");
  if (!ctx) return;

  const labels = timeObj.labels || [];
  const rev = (timeObj.revenue || []).map(v => v ?? null);
  const profit = (timeObj.profit || []).map(v => v ?? null);

  if (chartMain) chartMain.destroy();
  chartMain = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Doanh thu",
          data: rev,
          borderColor: "#0b5ed7",
          backgroundColor: "rgba(11,94,215,0.08)",
          fill: true,
          tension: 0.22
        },
        {
          label: "Lợi nhuận",
          data: profit,
          borderColor: "#ff7a00",
          backgroundColor: "rgba(255,122,0,0.08)",
          fill: true,
          tension: 0.22
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" } }
    }
  });
}

// -----------------------
function renderRegionChart(rows) {
  const ctx = $("#chart-region")?.getContext("2d");
  if (!ctx) return;

  const map = {};
  rows.forEach(r => {
    const reg = r.region || "Unknown";
    if (reg === "Unknown") return;
    if (!map[reg]) map[reg] = { rev: 0, profit: 0 };
    map[reg].rev += Number(r.revenue || 0);
    map[reg].profit += Number(r.profit || 0);
  });

  const labels = Object.keys(map);
  const revs = labels.map(l => map[l].rev);
  const profits = labels.map(l => map[l].profit);

  if (chartRegion) chartRegion.destroy();
  chartRegion = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Doanh thu", data: revs, backgroundColor: "rgba(11,94,215,0.7)" },
        { label: "Lợi nhuận", data: profits, backgroundColor: "rgba(255,122,0,0.7)" }
      ]
    },
    options: {
      responsive: true,
      plugins: { legend: { position: "bottom" } }
    }
  });
}

// -----------------------
// FIXED: Product chart must use product_group, not product name
// -----------------------
// -----------------------
// FIXED AGAIN: dùng đúng field API trả về: r.product
// -----------------------
function renderProductGroupChart(rows) {
  const ctx = $("#chart-product-group")?.getContext("2d");
  if (!ctx) return;

  const map = {};
  rows.forEach(r => {
    const pg = r.product || "Unknown";   // <-- FIX: API field là 'product'
    if (pg === "Unknown") return;
    if (!map[pg]) map[pg] = 0;
    map[pg] += Number(r.revenue || 0);
  });

  const labels = Object.keys(map);
  const values = labels.map(l => map[l]);

  const zipped = labels.map((l,i)=>({label:l,value:values[i]}));
  zipped.sort((a,b)=>b.value-a.value);

  const top = zipped.slice(0,12);

  if (chartProductGroup) chartProductGroup.destroy();
  chartProductGroup = new Chart(ctx, {
    type: "pie",
    data: {
      labels: top.map(x => x.label),
      datasets: [{
          data: top.map(x => x.value),
          // BỔ SUNG MÀU NỀN CHO BIỂU ĐỒ TRÒN
          backgroundColor: [
              '#0b5ed7',
              '#ff7a00',
              '#20c997',
              '#6f42c1',
              '#dc3545',
              '#fd7e14',
              '#0dcaf0',
              '#e83e8c',
              '#6610f2',
              '#198754',
              '#adb5bd',
              '#343a40'
          ]
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { position: "right" } }
    }
  });
}

// -----------------------
// FIXED: Top uses its own canvas now
// -----------------------
function renderTop5(top) {
  const labelsRaw = top.labels || [];
  const valsRaw = top.values || [];

  const pairs = [];
  for (let i = 0; i < labelsRaw.length; i++) {
    const lab = labelsRaw[i] || "Unknown";
    if (lab === "Unknown") continue;
    pairs.push({ label: lab, value: Number(valsRaw[i] || 0) });
  }

  pairs.sort((a,b)=>b.value-a.value);
  const topPairs = pairs.slice(0,5);

  const ol = $("#top5-ol");
  if (ol) {
    ol.innerHTML = "";
    if (topPairs.length === 0) {
      for (let i=0;i<5;i++) ol.insertAdjacentHTML("beforeend", `<li>—</li>`);
    } else {
      topPairs.forEach((p,idx)=>{
        ol.insertAdjacentHTML(
          "beforeend",
          `<li><strong>${idx+1}.</strong> ${p.label} — <span style="color:#0b5ed7">${toCurrency(p.value)}</span></li>`
        );
      });
    }
  }

  const ctx = $("#chart-top5")?.getContext("2d"); // FIXED CANVAS
  if (!ctx) return;

  if (chartTop5) chartTop5.destroy();

  if (topPairs.length > 0) {
    chartTop5 = new Chart(ctx, {
      type: "bar",
      data: {
        labels: topPairs.map(p=>p.label),
        datasets: [{
          data: topPairs.map(p=>p.value),
          backgroundColor: "rgba(11,94,215,0.7)"
        }]
      },
      options: {
        indexAxis: "y",
        plugins: { legend: { display:false } }
      }
    });
  }
}

async function downloadOverview() {
  try {
    const region = $("#f-region")?.value || "ALL";
    const product = $("#f-product")?.value || "ALL";

    const res = await fetch("/api/download_overview/", {
      method: "POST",
      headers: { "Content-Type":"application/json" },
      body: JSON.stringify({ region, product })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "overview.csv";
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert("Không thể tải báo cáo");
  }
}
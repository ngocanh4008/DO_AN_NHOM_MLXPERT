// =======================================================
// OVERVIEW DASHBOARD – FULL VERSION (PNG ICON FIXED)
// =======================================================

const $ = (s) => document.querySelector(s);
const fmt = (v) => (v == null ? "—" : Number(v).toLocaleString("vi-VN"));
const toCurrency = (v) => (v == null ? "—" : Number(v).toLocaleString("vi-VN") + " ₫");

let chartRegion = null;
let chartMain = null;
let chartProductGroup = null;
let chartTop5 = null;

// =======================================================
// INIT
// =======================================================
document.addEventListener("DOMContentLoaded", () => {
    const btnFilter = $("#btn-filter");
    const btnExport = $("#btn-export");

    if (btnFilter) btnFilter.addEventListener("click", fetchOverview);
    if (btnExport) btnExport.addEventListener("click", downloadOverview);

    fetchOverview();
});

// =======================================================
// FETCH OVERVIEW (CÓ ICON PNG LOADING)
// =======================================================
async function fetchOverview() {
    const btnFilter = $("#btn-filter");

    try {
        if (btnFilter) {
            const iconLoading = btnFilter.dataset.iconLoading;
            btnFilter.innerHTML = `
                <img src="${iconLoading}" class="btn-icon">
                Đang thống kê...
            `;
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
        renderProductGroupChart(dataRows);
        renderTop5(top5);

    } catch (err) {
        console.error("❌ Lỗi fetchOverview:", err);
        alert("Không thể tải dữ liệu báo cáo! " + (err.message || ""));
    } finally {
        if (btnFilter) {
           btnFilter.textContent = "Lọc";
            btnFilter.disabled = false;
        }
    }
}

// =======================================================
// UPDATE KPIs
// =======================================================
function updateKPIs(kpis) {
    $("#kpi-revenue").textContent = kpis?.revenue != null ? fmt(kpis.revenue) : "—";
    $("#kpi-cost").textContent = kpis?.cost != null ? fmt(kpis.cost) : "—";
    $("#kpi-profit").textContent = kpis?.profit != null ? fmt(kpis.profit) : "—";
    $("#kpi-profit-rate").textContent = kpis?.profit_pct != null ? kpis.profit_pct + "%" : "—";
}

// =======================================================
// MAIN LINE CHART
// =======================================================
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

// =======================================================
// REGION CHART
// =======================================================
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

// =======================================================
// PRODUCT GROUP CHART
// =======================================================
function renderProductGroupChart(rows) {
    const ctx = $("#chart-product-group")?.getContext("2d");
    if (!ctx) return;

    const map = {};
    rows.forEach(r => {
        const pg = r.product || "Unknown";
        if (pg === "Unknown") return;
        if (!map[pg]) map[pg] = 0;
        map[pg] += Number(r.revenue || 0);
    });

    const labels = Object.keys(map);
    const values = labels.map(l => map[l]);

    const sorted = labels.map((l,i)=>({label:l,value:values[i]})).sort((a,b)=>b.value-a.value);
    const top = sorted.slice(0,12);

    if (chartProductGroup) chartProductGroup.destroy();
    chartProductGroup = new Chart(ctx, {
        type: "pie",
        data: {
            labels: top.map(x => x.label),
            datasets: [{
                data: top.map(x => x.value),
                backgroundColor: [
                    '#0b5ed7','#ff7a00','#20c997','#6f42c1','#dc3545','#fd7e14',
                    '#0dcaf0','#e83e8c','#6610f2','#198754','#adb5bd','#343a40'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: "right" } }
        }
    });
}

// =======================================================
// TOP 5 CHART + LIST
// =======================================================
function renderTop5(top) {
    const labelsRaw = top.labels || [];
    const valsRaw = top.values || [];

    // Gom lại thành list
    const pairs = labelsRaw.map((lab, i) => ({
        label: lab || "—",
        value: Number(valsRaw[i] || 0)
    }));

    // Sort giảm dần
    pairs.sort((a, b) => b.value - a.value);

    // Lấy tối đa 5
    const topPairs = pairs.slice(0, 5);

    const ol = $("#top5-ol");
    const note = $("#top5-note"); // element ghi chú (m thêm ID này vào HTML)

    if (ol) {
        ol.innerHTML = "";

        // Render danh sách
        topPairs.forEach((p) => {
            ol.insertAdjacentHTML(
                "beforeend",
                `<li>
                    ${p.label} — 
                    <span style="color:#0b5ed7">${toCurrency(p.value)}</span>
                </li>`
            );
        });

        // ❗ Giải thích nếu < 5 sản phẩm
        if (note) {
            if (topPairs.length < 5) {
                note.textContent = `Chỉ tìm thấy ${topPairs.length} sản phẩm phù hợp với điều kiện lọc hiện tại.`;
                note.style.display = "block";
            } else {
                note.style.display = "none";
            }
        }
    }

    // Biểu đồ
    const ctx = $("#chart-top5")?.getContext("2d");
    if (!ctx) return;

    if (chartTop5) chartTop5.destroy();

    chartTop5 = new Chart(ctx, {
        type: "bar",
        data: {
            labels: topPairs.map(p => p.label),
            datasets: [{
                data: topPairs.map(p => p.value),
                backgroundColor: "rgba(11,94,215,0.7)"
            }]
        },
        options: {
            indexAxis: "y",
            plugins: { legend: { display: false } }
        }
    });
}


// =======================================================
// EXPORT OVERVIEW (Không đổi, chỉ giữ nguyên icon riêng của export)
// =======================================================
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

        const disposition = res.headers.get('Content-Disposition');
        let filename = 'Bao_cao_tong_quan.xlsx';

        if (disposition) {
            const filenameMatch = disposition.match(/filename="(.+?)"/);
            if (filenameMatch && filenameMatch[1]) filename = filenameMatch[1];
        }

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);

    } catch (err) {
        console.error("Lỗi tải báo cáo:", err);
        alert("Không thể tải báo cáo!");
    }
}

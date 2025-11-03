// web/static/web/js/price.js
const $ = (sel) => document.querySelector(sel);

document.addEventListener("DOMContentLoaded", () => {
  const slider = $("#discount_rate");
  const promoLabel = $("#promo_label");
  slider.addEventListener("input", () => promoLabel.textContent = slider.value + "%");

  $("#run_btn").addEventListener("click", async () => {
    await runPredict();
    drawCharts(); // vẽ 3 biểu đồ sau khi chạy
  });

  async function runPredict() {
    const payload = getPayload();
    const res = await fetch("/predict/", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error);

    $("#kq_sold").textContent   = data.predicted_sales.toLocaleString("vi-VN");
    $("#kq_rev").textContent    = data.predicted_revenue.toLocaleString("vi-VN");
    $("#kq_profit").textContent = data.predicted_profit.toLocaleString("vi-VN");
    $("#kq_margin").textContent = `${data.margin_rate.toFixed(2)}%`;

    $("#ai_text").textContent = genAIText(data, payload);
  }

  function getPayload() {
    return {
      product_group_enc: Number($("#product_group").value),
      brand_name_enc: Number($("#brand_name").value),
      region_enc: Number($("#region_name").value),
      net_price: Number($("#net_price").value),
      discount_rate: Number($("#discount_rate").value),
      promo_on: $("#promo_on").checked
    };
  }

  function genAIText(data, payload) {
    const { predicted_sales, predicted_revenue, predicted_profit, margin_rate } = data;
    const d = payload.discount_rate, p = payload.net_price, promo = payload.promo_on;

    let txt = "";
    if (d >= 40) {
      txt = `Khuyến mãi ${d}% đang rất cao, giúp kích cầu mạnh nhưng biên lợi nhuận chỉ còn ${margin_rate.toFixed(1)}%. 
             Cân nhắc giảm về 25–35% để tối ưu lợi nhuận.`;
    } else if (d <= 10) {
      txt = `Khuyến mãi thấp (${d}%) khiến nhu cầu tăng chậm. 
             Nên thử tăng nhẹ để cải thiện sản lượng.`;
    } else {
      txt = `Cấu hình hiện tại (giá ${p.toLocaleString()}đ, KM ${d}%) đang ở mức cân bằng giữa doanh thu và lợi nhuận.`;
    }
    txt += `\n➡️ Dự kiến ${predicted_sales.toLocaleString()} sp/tuần, doanh thu ${predicted_revenue.toLocaleString()}đ, lợi nhuận ${predicted_profit.toLocaleString()}đ.`;
    return txt;
  }

  // ========== CHARTS ==========
  async function drawCharts() {
    const payload = getPayload();
    await drawPriceChart(payload);
    await drawDiscountChart(payload);
    await drawRegionChart(payload);
  }

  async function drawPriceChart(payload) {
    const res = await fetch("/simulate_series/", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, mode: "price" })
    });
    const data = await res.json();
    if (!data.ok) return;

    const x = data.series.map(d => d.x);
    const y1 = data.series.map(d => d.revenue);
    const y2 = data.series.map(d => d.sold);
    const y3 = data.series.map(d => d.profit);

    const fig = [
      { x, y: y1, type: "scatter", name: "Doanh thu", line: { color: "blue" } },
      { x, y: y2, type: "scatter", name: "Sản lượng", line: { color: "green" } },
      { x, y: y3, type: "scatter", name: "Lợi nhuận", line: { color: "orange" } },
    ];
    Plotly.newPlot("chart_main", fig, {
      title: "Biến động theo Giá bán",
      xaxis: { title: "Giá bán (đ)" },
      yaxis: { title: "Giá trị" }
    });
  }

  async function drawDiscountChart(payload) {
    const res = await fetch("/simulate_series/", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, mode: "discount" })
    });
    const data = await res.json();
    if (!data.ok) return;

    const x = data.series.map(d => d.x);
    const y = data.series.map(d => d.sold);

    Plotly.newPlot("chart_growth", [{
      x, y, type: "scatter", fill: "tozeroy", line: { color: "purple" }
    }], {
      title: "Độ nhạy sản lượng theo khuyến mãi",
      xaxis: { title: "Mức khuyến mãi (%)" },
      yaxis: { title: "Sản lượng dự đoán" }
    });
  }

  async function drawRegionChart(payload) {
    const res = await fetch("/simulate_series/", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, mode: "region" })

    });
    const data = await res.json();
    if (!data.ok) return;

    const regionLabels = ["KVCA","KVMB","KVMN","KVMT","KVMTR","KVTN","Khác"];
    const x = data.series.map(d => regionLabels[d.x] || d.x);
    const y = data.series.map(d => d.sold);

    Plotly.newPlot("chart_top_regions", [{
      x, y, type: "bar", marker: { color: "teal" }
    }], {
      title: "Phản ứng vùng miền với khuyến mãi",
      xaxis: { title: "Vùng" },
      yaxis: { title: "Sản lượng dự đoán" }
    });
  }
});

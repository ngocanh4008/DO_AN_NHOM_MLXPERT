// =======================================================
// REPORT MANAGEMENT DASHBOARD SCRIPT (Hoàn chỉnh)
// =======================================================

// Utility function
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// Global state
let filterState = {
    page: 1,
    pageSize: 5, // 5 hàng/trang
    search: '',
    time: 'all', // today, 3_days, 7_days, 30_days, 90_days, 1_year, all
    type: 'all', // Báo cáo tổng quan, Dự báo nhu cầu, ...
    creator: '',
};

// Dropdown options
const TIME_OPTIONS = {
    'all': 'Tất cả thời gian',
    'today': 'Hôm nay',
    '3_days': '3 ngày qua',
    '7_days': '7 ngày qua',
    '30_days': '30 ngày qua',
    '90_days': '90 ngày qua',
    '1_year': '1 năm qua',
};

const TYPE_OPTIONS = [
    'all',
    'Báo cáo tổng quan',
    'Dự báo nhu cầu',
    'Mô phỏng giá và khuyến mãi',
    'Khuyến nghị'
];

document.addEventListener("DOMContentLoaded", () => {
    // Initial load
    fetchReports();

    // 1️⃣ Search live
    const searchInput = $("#search_input");
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            filterState.search = e.target.value.trim();
            filterState.page = 1;
            fetchReports();
        });
    }

    // 2️⃣ Dropdown filters
    setupDropdowns();

    // 3️⃣ Pagination click
    const paginationContainer = $("#pagination_container");
    if (paginationContainer) {
        paginationContainer.addEventListener('click', (e) => {
            const target = e.target.closest('.page-btn');
            if (target) handlePaginationClick(target);
        });
    }
});

// =======================================================
// Setup dropdown filters (direct dropdown, no prompt)
// =======================================================
function setupDropdowns() {
    // Time filter
    const timeFilter = document.querySelector('.dropdown-filter[data-filter="time"] select');
    if (timeFilter) {
        for (const key in TIME_OPTIONS) {
            const option = document.createElement('option');
            option.value = key;
            option.textContent = TIME_OPTIONS[key];
            timeFilter.appendChild(option);
        }
        timeFilter.value = filterState.time;
        timeFilter.addEventListener('change', (e) => {
            filterState.time = e.target.value;
            filterState.page = 1;
            fetchReports();
        });
    }

    // Type filter
    const typeFilter = document.querySelector('.dropdown-filter[data-filter="type"] select');
    if (typeFilter) {
        TYPE_OPTIONS.forEach(type => {
            const option = document.createElement('option');
            option.value = type;
            option.textContent = type === 'all' ? 'Tất cả' : type;
            typeFilter.appendChild(option);
        });
        typeFilter.value = filterState.type;
        typeFilter.addEventListener('change', (e) => {
            filterState.type = e.target.value;
            filterState.page = 1;
            fetchReports();
        });
    }

    // Creator filter
    const creatorFilter = document.querySelector('.dropdown-filter[data-filter="creator"] input');
    if (creatorFilter) {
        creatorFilter.addEventListener('input', (e) => {
            filterState.creator = e.target.value.trim();
            filterState.page = 1;
            fetchReports();
        });
    }
}

// =======================================================
// Fetch reports from backend / mock
// =======================================================
async function fetchReports() {
    const tableBody = $("#report_table_body");
    const paginationContainer = $("#pagination_container");
    tableBody.innerHTML = `<tr><td colspan="7" class="text-center py-4">Đang tải dữ liệu...</td></tr>`;
    paginationContainer.innerHTML = '';

    try {
        // Nếu chưa có backend, dùng mock
        const data = generateMockReports(filterState);

        renderTable(data.reports, data.currentPage);
        renderPagination(data.totalPages, data.currentPage);

    } catch (error) {
        console.error(error);
        tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-red-600 py-4">🚫 Lỗi tải dữ liệu</td></tr>`;
    }
}

// =======================================================
// Render table
// =======================================================
function renderTable(reports, currentPage) {
    const tableBody = $("#report_table_body");
    const downloadIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`;
    const trashIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`;

    tableBody.innerHTML = '';
    if (!reports.length) {
        tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4">Không tìm thấy báo cáo nào.</td></tr>';
        return;
    }

    reports.forEach((report, index) => {
        const stt = (currentPage - 1) * filterState.pageSize + index + 1;
        const row = document.createElement('tr');
        row.innerHTML = `
            <td data-label="STT">${stt}</td>
            <td data-label="Tên báo cáo"><a href="#">${report.name}</a></td>
            <td data-label="Loại báo cáo">${report.type}</td>
            <td data-label="Người tạo">${report.creator}</td>
            <td data-label="Ngày tạo">${report.date}</td>
            <td data-label="Kích thước tệp">${report.size}</td>
            <td data-label="Hành động">
                <button onclick="downloadReport('${report.id}', '${report.name}')">${downloadIcon}</button>
                <button class="delete" onclick="deleteReport('${report.id}', '${report.name}')">${trashIcon}</button>
            </td>
        `;
        tableBody.appendChild(row);
    });
}

// =======================================================
// Pagination
// =======================================================
function handlePaginationClick(target) {
    const page = target.getAttribute('data-page');
    const totalPages = parseInt($("#pagination_container").getAttribute('data-total-pages') || 1);

    if (page === 'prev') filterState.page = Math.max(1, filterState.page - 1);
    else if (page === 'next') filterState.page = Math.min(totalPages, filterState.page + 1);
    else filterState.page = parseInt(page);

    fetchReports();
}

function renderPagination(totalPages, currentPage) {
    const container = $("#pagination_container");
    container.setAttribute('data-total-pages', totalPages);
    container.innerHTML = '';

    const prevBtn = createPageButton("«", 'prev', currentPage > 1);
    container.appendChild(prevBtn);

    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, currentPage + 2);
    if (currentPage <= 3) endPage = Math.min(totalPages, 5);
    else if (currentPage > totalPages - 2) startPage = Math.max(1, totalPages - 4);

    for (let i = startPage; i <= endPage; i++) {
        container.appendChild(createPageButton(i, i, true, i === currentPage));
    }

    const nextBtn = createPageButton("»", 'next', currentPage < totalPages);
    container.appendChild(nextBtn);
}

function createPageButton(text, pageValue, isEnabled, isActive = false) {
    const btn = document.createElement('button');
    btn.textContent = text;
    btn.className = 'page-btn';
    btn.setAttribute('data-page', pageValue);
    if (!isEnabled) btn.disabled = true;
    if (isActive) btn.classList.add('active');
    return btn;
}

// =======================================================
// Actions: download / delete
// =======================================================
function downloadReport(id, name) {
    alert(`Đang tải xuống báo cáo "${name}" (PDF)...`);
    console.log("Download report ID:", id);
    // Thực tế: window.location.href = `/api/download_report/${id}`
}

function deleteReport(id, name) {
    if (confirm(`Xóa lịch sử báo cáo "${name}" khỏi database?`)) {
        alert(`Báo cáo "${name}" đã xóa (giả lập).`);
        console.log("Deleted report ID:", id);
        fetchReports();
        // Thực tế: fetch(`/api/reports/${id}`, { method: 'DELETE' }).then(fetchReports)
    }
}

// =======================================================
// Mock data (frontend test)
// =======================================================
function generateMockReports(state) {
    const MOCK_DATA = [];
    const TOTAL = 35;
    const TYPES = ['Báo cáo tổng quan', 'Dự báo nhu cầu', 'Mô phỏng giá và khuyến mãi', 'Khuyến nghị'];
    const today = new Date();

    for (let i = 1; i <= TOTAL; i++) {
        const d = new Date(today);
        d.setDate(today.getDate() - i);
        MOCK_DATA.push({
            id: i,
            name: `Báo cáo Phân tích ${i}`,
            type: TYPES[i % TYPES.length],
            creator: (i % 3 === 0) ? 'Admin' : `User_${i % 5}`,
            date: `${d.getDate().toString().padStart(2,'0')}/${(d.getMonth()+1).toString().padStart(2,'0')}/2025`,
            size: `${(i % 100) + 1} KB`
        });
    }

    // Filter search/type/creator
    let filtered = MOCK_DATA.filter(r => {
        const matchSearch = !state.search || r.name.toLowerCase().includes(state.search.toLowerCase()) || r.creator.toLowerCase().includes(state.search.toLowerCase());
        const matchType = state.type === 'all' || r.type === state.type;
        const matchCreator = !state.creator || r.creator.toLowerCase().includes(state.creator.toLowerCase());

        // Filter time
        if (state.time !== 'all') {
            const reportDate = new Date(r.date.split('/').reverse().join('-'));
            const now = new Date();
            let valid = false;
            switch(state.time) {
                case 'today':
                    valid = reportDate.toDateString() === now.toDateString();
                    break;
                case '3_days':
                    valid = (now - reportDate) / (1000*60*60*24) <= 3;
                    break;
                case '7_days':
                    valid = (now - reportDate) / (1000*60*60*24) <= 7;
                    break;
                case '30_days':
                    valid = (now - reportDate) / (1000*60*60*24) <= 30;
                    break;
                case '90_days':
                    valid = (now - reportDate) / (1000*60*60*24) <= 90;
                    break;
                case '1_year':
                    valid = (now - reportDate) / (1000*60*60*24) <= 365;
                    break;
            }
            return matchSearch && matchType && matchCreator && valid;
        }
        return matchSearch && matchType && matchCreator;
    });

    const totalPages = Math.ceil(filtered.length / state.pageSize);
    const start = (state.page - 1) * state.pageSize;
    const end = start + state.pageSize;
    const paginated = filtered.slice(start, end);

    return {
        ok: true,
        reports: paginated,
        totalPages: totalPages,
        currentPage: state.page
    };
}

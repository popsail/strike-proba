const UPDATE_INTERVAL_MS = 13 * 60 * 1000; // 10 min update cycle + 3 min margin
const DATA_REFRESH_INTERVAL_MS = 60 * 1000; // Check for new data every minute

let lastData = null;
let countdownInterval = null;

async function fetchData() {
    try {
        const response = await fetch('data.json?' + Date.now());
        if (!response.ok) throw new Error('Failed to fetch data');
        return await response.json();
    } catch (error) {
        console.error('Error fetching data:', error);
        return null;
    }
}

function getRiskClass(risk) {
    if (risk < 25) return 'risk-low';
    if (risk < 50) return 'risk-medium';
    if (risk < 75) return 'risk-high';
    return 'risk-critical';
}

function getAlertLevel(risk) {
    if (risk < 20) return { level: 'LOW', class: 'level-low' };
    if (risk < 40) return { level: 'GUARDED', class: 'level-guarded' };
    if (risk < 60) return { level: 'ELEVATED', class: 'level-elevated' };
    if (risk < 80) return { level: 'HIGH', class: 'level-high' };
    return { level: 'SEVERE', class: 'level-severe' };
}

function updateGauge(risk) {
    const gaugeFill = document.getElementById('gauge-fill');
    const totalRiskEl = document.getElementById('total-risk');

    const maxOffset = 251.2;
    const offset = maxOffset - (risk / 100) * maxOffset;

    gaugeFill.style.strokeDashoffset = offset;
    gaugeFill.className = 'gauge-fill ' + getRiskClass(risk);
    totalRiskEl.textContent = risk;
}

function updateAlertLevel(risk) {
    const alertEl = document.getElementById('alert-level');
    const alert = getAlertLevel(risk);
    alertEl.textContent = alert.level;
    alertEl.className = 'alert-value ' + alert.class;
}

function updateSignalCard(key, data) {
    const riskEl = document.getElementById(`${key}-risk`);
    const detailEl = document.getElementById(`${key}-detail`);
    const cardEl = document.getElementById(`card-${key}`);

    if (riskEl) riskEl.textContent = data.risk;
    if (detailEl) detailEl.textContent = data.detail;
    if (cardEl) {
        cardEl.className = 'signal-card ' + getRiskClass(data.risk);
    }

    if (data.history) {
        drawSparkline(`${key}-sparkline`, data.history, data.risk);
    }
}

function drawSparkline(canvasId, history, currentRisk) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const padding = 5;

    ctx.clearRect(0, 0, width, height);

    if (!history || history.length < 2) return;

    const max = Math.max(...history, 100);
    const min = Math.min(...history, 0);
    const range = max - min || 1;

    const stepX = (width - 2 * padding) / (history.length - 1);

    ctx.beginPath();
    ctx.strokeStyle = getComputedStyle(document.documentElement)
        .getPropertyValue(currentRisk < 25 ? '--accent-green' :
                         currentRisk < 50 ? '--accent-yellow' :
                         currentRisk < 75 ? '--accent-orange' : '--accent-red').trim() || '#00ff88';
    ctx.lineWidth = 2;

    history.forEach((value, i) => {
        const x = padding + i * stepX;
        const y = height - padding - ((value - min) / range) * (height - 2 * padding);

        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });

    ctx.stroke();

    // Draw end dot
    const lastX = padding + (history.length - 1) * stepX;
    const lastY = height - padding - ((history[history.length - 1] - min) / range) * (height - 2 * padding);
    ctx.beginPath();
    ctx.arc(lastX, lastY, 3, 0, 2 * Math.PI);
    ctx.fillStyle = ctx.strokeStyle;
    ctx.fill();
}

function drawTrendChart(history) {
    const canvas = document.getElementById('trend-chart');
    if (!canvas || !history || history.length < 2) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const padding = { top: 20, right: 20, bottom: 30, left: 50 };

    ctx.clearRect(0, 0, width, height);

    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Draw grid
    ctx.strokeStyle = '#2a2a3a';
    ctx.lineWidth = 1;

    for (let i = 0; i <= 4; i++) {
        const y = padding.top + (chartHeight / 4) * i;
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(width - padding.right, y);
        ctx.stroke();

        ctx.fillStyle = '#606070';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText((100 - i * 25) + '%', padding.left - 10, y + 4);
    }

    // Draw risk line
    const risks = history.map(h => h.risk);
    const stepX = chartWidth / (history.length - 1);

    ctx.beginPath();
    ctx.strokeStyle = '#0088ff';
    ctx.lineWidth = 2;

    history.forEach((point, i) => {
        const x = padding.left + i * stepX;
        const y = padding.top + chartHeight - (point.risk / 100) * chartHeight;

        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });

    ctx.stroke();

    // Draw pinned points
    history.forEach((point, i) => {
        if (point.pinned) {
            const x = padding.left + i * stepX;
            const y = padding.top + chartHeight - (point.risk / 100) * chartHeight;
            ctx.beginPath();
            ctx.arc(x, y, 4, 0, 2 * Math.PI);
            ctx.fillStyle = '#0088ff';
            ctx.fill();
        }
    });

    // Draw time labels
    ctx.fillStyle = '#606070';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';

    const labelCount = Math.min(6, history.length);
    const labelStep = Math.floor(history.length / labelCount);

    for (let i = 0; i < history.length; i += labelStep) {
        const point = history[i];
        if (point.timestamp) {
            const date = new Date(point.timestamp);
            const label = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const x = padding.left + i * stepX;
            ctx.fillText(label, x, height - 10);
        }
    }
}

function formatTimeAgo(isoString) {
    // Append Z if no timezone to force UTC parsing
    const dateStr = isoString.includes('Z') || isoString.includes('+') ? isoString : isoString + 'Z';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'just now';
    if (diffMins === 1) return '1 minute ago';
    if (diffMins < 60) return `${diffMins} minutes ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours === 1) return '1 hour ago';
    if (diffHours < 24) return `${diffHours} hours ago`;

    return date.toLocaleString();
}

function updateCountdown(lastUpdated) {
    const countdownEl = document.getElementById('countdown');
    const lastUpdatedEl = document.getElementById('last-updated');

    if (!lastUpdated) {
        countdownEl.textContent = '--:--';
        lastUpdatedEl.textContent = '--';
        return;
    }

    // Append Z if no timezone to force UTC parsing
    const dateStr = lastUpdated.includes('Z') || lastUpdated.includes('+') ? lastUpdated : lastUpdated + 'Z';
    const lastUpdate = new Date(dateStr);
    const nextUpdate = new Date(lastUpdate.getTime() + UPDATE_INTERVAL_MS);

    lastUpdatedEl.textContent = formatTimeAgo(lastUpdated);

    if (countdownInterval) {
        clearInterval(countdownInterval);
    }

    function tick() {
        const now = new Date();
        const remaining = nextUpdate - now;

        if (remaining <= 0) {
            countdownEl.textContent = '00:00';
            return;
        }

        const mins = Math.floor(remaining / 60000);
        const secs = Math.floor((remaining % 60000) / 1000);
        countdownEl.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }

    tick();
    countdownInterval = setInterval(tick, 1000);
}

function renderData(data) {
    if (!data) return;

    lastData = data;

    // Update main gauge
    if (data.total_risk) {
        updateGauge(data.total_risk.risk);
        updateAlertLevel(data.total_risk.risk);

        if (data.total_risk.history) {
            drawTrendChart(data.total_risk.history);
        }
    }

    // Update signal cards
    if (data.news) updateSignalCard('news', data.news);
    if (data.aviation) updateSignalCard('aviation', data.aviation);
    if (data.tanker) updateSignalCard('tanker', data.tanker);
    if (data.pentagon) updateSignalCard('pentagon', data.pentagon);
    if (data.polymarket) updateSignalCard('polymarket', data.polymarket);
    if (data.weather) updateSignalCard('weather', data.weather);

    // Update countdown
    updateCountdown(data.last_updated);
}

async function init() {
    const data = await fetchData();
    renderData(data);

    // Refresh data periodically
    setInterval(async () => {
        const newData = await fetchData();
        if (newData && JSON.stringify(newData) !== JSON.stringify(lastData)) {
            renderData(newData);
        }
    }, DATA_REFRESH_INTERVAL_MS);
}

// Handle window resize for charts
window.addEventListener('resize', () => {
    if (lastData) {
        renderData(lastData);
    }
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', init);

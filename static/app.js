// Soil Sensor Web App - Frontend Logic

let sensorSets = {};
let activeSet = 0;
let sensorReadings = [];
let defaultReadings = [];
let pollInterval;
let graphSensorIndex = 0;
let latestHistory = { hour: [], day: [], week: [], month: [], year: [] };
let latestValues = [];
let graphRange = 'day';
let selectedGraphSensors = [];
let uiTheme = 'retro';
let operationMode = 'continuous';
let sensorPollInterval = 10;
let analysisMemory = [];
let timelineEntries = [];

const GRAPH_COLOR_PALETTE = [
    '#00FF00', '#FF00FF', '#00FFFF', '#FFFF00', '#FF8800',
    '#66FF66', '#FF6666', '#66CCFF', '#FF66FF', '#FFFFFF'
];

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    loadGraphPreferences();
    await loadSettings();
    renderSetSelector();
    renderSensorGrid();
    renderSensorConfigForm();
    renderGraphSelector();
    renderGraphLegend();
    startPolling();
    setupEventListeners();
});

function getGraphSelectionStorageKey() {
    return `soilSensorGraphSelections_set_${activeSet}`;
}

function loadGraphPreferences() {
    const savedRange = localStorage.getItem('soilSensorGraphRange') || 'day';
    graphRange = ['hour', 'day', 'week', 'month', 'year'].includes(savedRange) ? savedRange : 'day';
}

function loadSelectedGraphSensors() {
    try {
        const saved = JSON.parse(localStorage.getItem(getGraphSelectionStorageKey()) || '[]');
        selectedGraphSensors = Array.isArray(saved) ? saved.filter(Number.isInteger) : [];
    } catch {
        selectedGraphSensors = [];
    }
}

function saveSelectedGraphSensors() {
    localStorage.setItem(getGraphSelectionStorageKey(), JSON.stringify(selectedGraphSensors));
}

function getSensorColor(sensorName, index) {
    const key = `soilSensorGraphColor_${sensorName}`;
    const savedColor = localStorage.getItem(key);
    if (savedColor) {
        return savedColor;
    }

    const fallback = GRAPH_COLOR_PALETTE[index % GRAPH_COLOR_PALETTE.length];
    localStorage.setItem(key, fallback);
    return fallback;
}

function setSensorColor(sensorName, color) {
    localStorage.setItem(`soilSensorGraphColor_${sensorName}`, color);
}

function applyTheme(themeName) {
    uiTheme = ['retro', 'garden', 'speakeasy', 'studio54'].includes(themeName) ? themeName : 'retro';
    document.body.dataset.theme = uiTheme;

    const selector = document.getElementById('themeSelect');
    if (selector) {
        selector.value = uiTheme;
    }
}

// Load settings from server
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const data = await response.json();
        sensorSets = data.sensor_sets;
        activeSet = data.active_set;
        sensorReadings = data.readings;
        defaultReadings = data.default_readings;
        applyTheme(data.ui_theme || 'retro');
        operationMode = ['analysis', 'continuous'].includes(data.operation_mode) ? data.operation_mode : 'continuous';
        sensorPollInterval = Number.isFinite(Number(data.sensor_poll_interval)) ? Number(data.sensor_poll_interval) : 10;
        if (graphSensorIndex >= sensorReadings.length) {
            graphSensorIndex = 0;
        }
        loadSelectedGraphSensors();
        const validIndexes = selectedGraphSensors.filter(index => index >= 0 && index < sensorReadings.length);
        if (validIndexes.length === 0 && sensorReadings.length > 0) {
            selectedGraphSensors = sensorReadings.slice(0, Math.min(3, sensorReadings.length)).map((_, index) => index);
            saveSelectedGraphSensors();
        } else {
            selectedGraphSensors = validIndexes;
        }
        updateModeControls();
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

function updateModeControls() {
    const selector = document.getElementById('modeSelector');
    const button = document.getElementById('runAnalysisBtn');
    const modalSelector = document.getElementById('modalModeSelect');
    const pollSelector = document.getElementById('pollIntervalSelect');

    if (selector) {
        selector.value = operationMode;
    }

    if (modalSelector) {
        modalSelector.value = operationMode;
    }

    if (pollSelector) {
        pollSelector.value = String(sensorPollInterval);
    }

    if (button) {
        const analysisActive = operationMode === 'analysis';
        button.disabled = !analysisActive;
        button.textContent = analysisActive ? '▶ RUN ANALYSIS' : '● AUTO RUNNING';
    }
}

function renderGraphSelector() {
    const selector = document.getElementById('graphSensorSelect');
    if (!selector) return;

    selector.innerHTML = '';

    sensorReadings.forEach((reading, index) => {
        const option = document.createElement('option');
        option.value = index;
        option.textContent = `${reading.name} ${reading.unit ? `(${reading.unit})` : ''}`.trim();
        if (index === graphSensorIndex) option.selected = true;
        selector.appendChild(option);
    });

    const rangeSelect = document.getElementById('graphRangeSelect');
    if (rangeSelect) {
        rangeSelect.value = graphRange;
    }
}

function renderGraphLegend() {
    const legend = document.getElementById('graphLegend');
    if (!legend) return;

    if (!sensorReadings.length) {
        legend.innerHTML = '<p>⏳ No enabled sensors...</p>';
        return;
    }

    legend.innerHTML = '';

    sensorReadings.forEach((reading, index) => {
        const item = document.createElement('label');
        item.className = 'graph-legend-item';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = selectedGraphSensors.includes(index);
        checkbox.dataset.index = index;

        const colorInput = document.createElement('input');
        colorInput.type = 'color';
        colorInput.value = getSensorColor(reading.name, index);
        colorInput.dataset.name = reading.name;
        colorInput.className = 'graph-color-picker';

        const swatch = document.createElement('span');
        swatch.className = 'graph-legend-swatch';
        swatch.style.backgroundColor = colorInput.value;

        const text = document.createElement('span');
        text.className = 'graph-legend-text';
        text.textContent = `${reading.name}${reading.unit ? ` (${reading.unit})` : ''}`;

        checkbox.addEventListener('change', () => {
            const numericIndex = parseInt(checkbox.dataset.index, 10);
            if (checkbox.checked) {
                if (!selectedGraphSensors.includes(numericIndex)) {
                    selectedGraphSensors.push(numericIndex);
                    selectedGraphSensors.sort((a, b) => a - b);
                }
            } else {
                selectedGraphSensors = selectedGraphSensors.filter(itemIndex => itemIndex !== numericIndex);
                if (graphSensorIndex === numericIndex && selectedGraphSensors.length > 0) {
                    graphSensorIndex = selectedGraphSensors[0];
                    renderGraphSelector();
                }
            }
            saveSelectedGraphSensors();
            renderGraph(latestHistory, latestValues);
        });

        colorInput.addEventListener('input', () => {
            swatch.style.backgroundColor = colorInput.value;
            setSensorColor(reading.name, colorInput.value);
            renderGraph(latestHistory, latestValues);
        });

        item.appendChild(checkbox);
        item.appendChild(colorInput);
        item.appendChild(swatch);
        item.appendChild(text);
        legend.appendChild(item);
    });
}

// Render set selector dropdown
function renderSetSelector() {
    const selector = document.getElementById('setSelector');
    selector.innerHTML = '';
    for (let i = 0; i < 10; i++) {
        const option = document.createElement('option');
        option.value = i;
        option.textContent = sensorSets[i]?.name || `Set ${i + 1}`;
        if (i === activeSet) option.selected = true;
        selector.appendChild(option);
    }
}

// Render sensor grid cards
function renderSensorGrid() {
    const grid = document.getElementById('sensorGrid');
    grid.innerHTML = '';
    
    if (sensorReadings.length === 0) {
        grid.innerHTML = '<p>No sensors enabled</p>';
        return;
    }
    
    sensorReadings.forEach(reading => {
        const card = document.createElement('div');
        card.className = 'sensor-card';
        card.innerHTML = `
            <div class="sensor-card-name">${reading.name}</div>
            <div class="sensor-card-value" data-sensor="${reading.name}">--</div>
            <div class="sensor-card-unit">${reading.unit}</div>
            <div class="sensor-card-range">[${reading.min}–${reading.max}]</div>
        `;
        grid.appendChild(card);
    });
}

// Render sensor configuration form
function renderSensorConfigForm() {
    const form = document.getElementById('sensorConfigForm');
    form.innerHTML = '';
    
    const setName = sensorSets[activeSet]?.name || `Set ${activeSet + 1}`;
    const setLabel = document.getElementById('settingsActiveSetLabel');

    if (setLabel) {
        setLabel.textContent = `SET ${activeSet + 1} — ${setName.toUpperCase()}`;
    }

    document.getElementById('setNameInput').value = setName;
    document.getElementById('themeSelect').value = uiTheme;
    document.getElementById('modalModeSelect').value = operationMode;
    document.getElementById('pollIntervalSelect').value = String(sensorPollInterval);
    
    defaultReadings.forEach((reading, index) => {
        const names = sensorSets[activeSet]?.names || [];
        const enabled = sensorSets[activeSet]?.enabled || [];
        
        const row = document.createElement('div');
        row.className = 'sensor-config-row';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = enabled[index] || false;
        checkbox.dataset.index = index;
        
        const label = document.createElement('label');
        label.textContent = `S${index + 1}:`;
        
        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = reading.name;
        input.value = names[index] || reading.name;
        input.dataset.index = index;
        
        const unit = document.createElement('span');
        unit.textContent = `[${reading.unit}]`;
        
        row.appendChild(checkbox);
        row.appendChild(label);
        row.appendChild(input);
        row.appendChild(unit);
        
        form.appendChild(row);
    });
}

// Start polling sensor data
function startPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }

    // Poll immediately
    updateSensorData();

    if (operationMode === 'continuous') {
        pollInterval = setInterval(updateSensorData, sensorPollInterval * 1000);
    }
}

// Update sensor data from API
async function updateSensorData() {
    try {
        const response = await fetch('/api/data');
        const data = await response.json();
        const previousPollInterval = sensorPollInterval;
        operationMode = ['analysis', 'continuous'].includes(data.operation_mode) ? data.operation_mode : operationMode;
        sensorPollInterval = Number.isFinite(Number(data.sensor_poll_interval)) ? Number(data.sensor_poll_interval) : sensorPollInterval;
        updateModeControls();

        if (operationMode === 'continuous' && previousPollInterval !== sensorPollInterval) {
            startPolling();
            return;
        }
        
        // Update status bar
        document.getElementById('statusBar').textContent = data.status;
        
        // Update sensor cards
        data.values.forEach(value => {
            const cardValue = document.querySelector(`[data-sensor="${value.name}"]`);
            if (cardValue) {
                const formattedValue = typeof value.value === 'number' 
                    ? (value.value % 1 !== 0 ? value.value.toFixed(1) : value.value.toFixed(0))
                    : '--';
                cardValue.textContent = formattedValue;
                
                const card = cardValue.closest('.sensor-card');
                if (value.status === 'warning') {
                    cardValue.classList.add('warning');
                    card.classList.add('warning');
                } else {
                    cardValue.classList.remove('warning');
                    card.classList.remove('warning');
                }
            }
        });
        
        // Update crop recommendations
        analysisMemory = Array.isArray(data.analysis_memory) ? data.analysis_memory : [];
        timelineEntries = Array.isArray(data.timeline_entries) ? data.timeline_entries : [];

        if ((data.crops && data.crops.length > 0) || data.npk_analysis || timelineEntries.length > 0 || analysisMemory.length > 0 || operationMode === 'analysis') {
            renderCrops(data.crops || [], data.npk_analysis || null, analysisMemory, operationMode, timelineEntries);
        } else {
            document.getElementById('cropsContent').innerHTML = '<p>⏳ Awaiting sensor data...</p>';
        }

        latestHistory = data.history_ranges || { hour: [], day: [], week: [], month: [], year: [] };
        latestValues = data.values || [];

        // Update graph
        const activeHistory = Array.isArray(latestHistory[graphRange]) ? latestHistory[graphRange] : [];
        if (activeHistory.length > 0) {
            renderGraph(latestHistory, latestValues);
        } else {
            document.getElementById('graphContent').innerHTML = '<p>⏳ No graph data yet...</p>';
            document.getElementById('graphStats').textContent = 'Awaiting samples...';
        }
    } catch (error) {
        console.error('Error updating sensor data:', error);
        document.getElementById('statusBar').textContent = '✗ Connection Error';
    }
}

// Render crop recommendations
function formatAnalysisTimestamp(timestamp) {
    const parsed = new Date(timestamp);
    if (Number.isNaN(parsed.getTime())) {
        return timestamp || 'Unknown time';
    }

    return parsed.toLocaleString();
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function renderAnalysisMemory(entries, mode) {
    const safeEntries = Array.isArray(entries) ? entries : [];
    if (!safeEntries.length) {
        const emptyLabel = mode === 'analysis'
            ? 'No saved analysis runs yet. Press RUN ANALYSIS to store the next capture.'
            : 'No saved analysis runs for this set yet.';

        return `
            <section class="crops-section analysis-memory-section">
                <h3>🧠 ANALYSIS MEMORY</h3>
                <p class="crops-placeholder">${emptyLabel}</p>
            </section>
        `;
    }

    return `
        <section class="crops-section analysis-memory-section">
            <h3>🧠 ANALYSIS MEMORY</h3>
            <div class="analysis-memory-list">
                ${safeEntries.map(entry => {
                    const topCrop = Array.isArray(entry.crops) && entry.crops.length > 0 ? entry.crops[0] : null;
                    const ratio = entry.npk_analysis && Array.isArray(entry.npk_analysis.ratio_to_peak)
                        ? entry.npk_analysis.ratio_to_peak.map(value => Number(value).toFixed(2)).join(' : ')
                        : 'No NPK ratio saved';
                    const readingChips = Array.isArray(entry.values)
                        ? entry.values.map(reading => {
                            const formattedValue = typeof reading.value === 'number'
                                ? `${formatGraphNumber(reading.value)}${reading.unit ? ` ${reading.unit}` : ''}`
                                : '--';
                            return `<span class="analysis-chip">${reading.name}: ${formattedValue}</span>`;
                        }).join('')
                        : '';

                    return `
                        <article class="analysis-memory-item">
                            <div class="analysis-memory-head">
                                <div class="analysis-memory-time">${formatAnalysisTimestamp(entry.created_at)}</div>
                                <div class="analysis-memory-set">${entry.set_name}</div>
                            </div>
                            <div class="analysis-memory-summary">
                                <span>Stored NPK ratio ${ratio}</span>
                                <span>${topCrop ? `Best crop ${topCrop.icon} ${topCrop.name} (${topCrop.score.toFixed(0)}%)` : 'No crop ranking saved'}</span>
                            </div>
                            <div class="analysis-chip-list">${readingChips}</div>
                        </article>
                    `;
                }).join('')}
            </div>
        </section>
    `;
}

function renderTimelineEntries(entries, mode) {
    const safeEntries = Array.isArray(entries) ? entries : [];
    if (!safeEntries.length) {
        return `
            <section class="crops-section timeline-section">
                <h3>📔 PLANT DIARY & READING TIMELINE</h3>
                <p class="crops-placeholder">${mode === 'analysis' ? 'Run an analysis or add a diary note to begin the timeline.' : 'Awaiting saved readings or diary notes...'}</p>
            </section>
        `;
    }

    return `
        <section class="crops-section timeline-section">
            <h3>📔 PLANT DIARY & READING TIMELINE</h3>
            <div class="timeline-list">
                ${safeEntries.map(entry => {
                    const topCrop = Array.isArray(entry.crops) && entry.crops.length > 0 ? entry.crops[0] : null;
                    const ratio = entry.npk_analysis && Array.isArray(entry.npk_analysis.ratio_to_peak)
                        ? entry.npk_analysis.ratio_to_peak.map(value => Number(value).toFixed(2)).join(' : ')
                        : null;
                    const readings = Array.isArray(entry.values) ? entry.values.slice(0, 6) : [];
                    const readingChips = readings.map(reading => {
                        const formattedValue = typeof reading.value === 'number'
                            ? `${formatGraphNumber(reading.value)}${reading.unit ? ` ${reading.unit}` : ''}`
                            : '--';
                        return `<span class="analysis-chip">${reading.name}: ${formattedValue}</span>`;
                    }).join('');
                    const entryLabel = entry.entry_type === 'note' ? 'NOTE' : (entry.mode === 'analysis' ? 'ANALYSIS READING' : 'CONTINUOUS READING');
                    const entryIcon = entry.entry_type === 'note' ? '📝' : (entry.mode === 'analysis' ? '🔬' : '📡');
                    return `
                        <article class="timeline-item timeline-item-${entry.entry_type}">
                            <div class="timeline-item-head">
                                <div class="timeline-item-title">${entryIcon} ${entryLabel}</div>
                                <div class="timeline-item-time">${formatAnalysisTimestamp(entry.created_at)}</div>
                            </div>
                            <div class="timeline-item-meta">${entry.set_name} · ${entry.mode.toUpperCase()}</div>
                            ${entry.note_text ? `<div class="timeline-note-text">${escapeHtml(entry.note_text)}</div>` : ''}
                            ${(ratio || topCrop) ? `
                                <div class="timeline-item-summary">
                                    ${ratio ? `<span>NPK ${ratio}</span>` : ''}
                                    ${topCrop ? `<span>Best crop ${topCrop.icon} ${topCrop.name} (${topCrop.score.toFixed(0)}%)</span>` : ''}
                                </div>
                            ` : ''}
                            ${readingChips ? `<div class="analysis-chip-list">${readingChips}</div>` : ''}
                        </article>
                    `;
                }).join('')}
            </div>
        </section>
    `;
}

function renderCrops(crops, npkAnalysis, memoryEntries, mode, entries) {
    const cropItems = crops.map(crop => {
        const symbol = crop.score >= 80 ? '✓✓✓' : crop.score >= 60 ? '✓✓' : crop.score >= 40 ? '✓' : '△';
        const profitability = (crop.yield * crop.value) / 1000;
        return `
            <div class="crop-item">
                <div class="crop-item-main">
                    <span class="crop-rank">${crop.rank}.</span>
                    <span class="crop-icon">${crop.icon}</span>
                    <span class="crop-name">${crop.name}</span>
                    <span class="crop-score">${symbol} ${crop.score.toFixed(0)}%</span>
                </div>
                <div class="crop-item-meta">
                    Yield ${crop.yield.toFixed(0)} t/ha · Value €${profitability.toFixed(1)}k/ha
                </div>
            </div>
        `;
    }).join('');

    const npkSection = npkAnalysis ? `
        <section class="crops-section npk-section">
            <h3>⚗ NPK RATIO VS COMMERCIAL FERTILIZERS</h3>
            <div class="npk-summary">
                <div class="npk-reading">N ${npkAnalysis.values.nitrogen}</div>
                <div class="npk-reading">P ${npkAnalysis.values.phosphorus}</div>
                <div class="npk-reading">K ${npkAnalysis.values.potassium}</div>
            </div>
            <div class="npk-ratio-line">
                Relative ratio: ${npkAnalysis.ratio_to_peak[0].toFixed(2)} : ${npkAnalysis.ratio_to_peak[1].toFixed(2)} : ${npkAnalysis.ratio_to_peak[2].toFixed(2)}
            </div>
            <div class="npk-bars">
                <div class="npk-bar-row">
                    <span class="npk-bar-label">N</span>
                    <div class="npk-bar-track"><div class="npk-bar-fill npk-bar-n" style="width: ${npkAnalysis.shares.nitrogen}%"></div></div>
                    <span class="npk-bar-value">${npkAnalysis.shares.nitrogen}%</span>
                </div>
                <div class="npk-bar-row">
                    <span class="npk-bar-label">P</span>
                    <div class="npk-bar-track"><div class="npk-bar-fill npk-bar-p" style="width: ${npkAnalysis.shares.phosphorus}%"></div></div>
                    <span class="npk-bar-value">${npkAnalysis.shares.phosphorus}%</span>
                </div>
                <div class="npk-bar-row">
                    <span class="npk-bar-label">K</span>
                    <div class="npk-bar-track"><div class="npk-bar-fill npk-bar-k" style="width: ${npkAnalysis.shares.potassium}%"></div></div>
                    <span class="npk-bar-value">${npkAnalysis.shares.potassium}%</span>
                </div>
            </div>
            <div class="npk-note">${npkAnalysis.comparison_note}</div>
            <div class="fertilizer-list">
                ${npkAnalysis.closest_matches.map(match => `
                    <div class="fertilizer-item">
                        <div class="fertilizer-title">${match.label} · ${match.name}</div>
                        <div class="fertilizer-meta">Best for ${match.use} · difference ${match.distance.toFixed(3)}</div>
                    </div>
                `).join('')}
            </div>
        </section>
    ` : '';

    const cropsSection = crops.length > 0 ? `
        <section class="crops-section">
            <h3>TOP CROPS FOR YOUR SOIL</h3>
            <div class="crop-list">${cropItems}</div>
        </section>
    ` : '<section class="crops-section"><h3>TOP CROPS FOR YOUR SOIL</h3><p class="crops-placeholder">⏳ Awaiting crop recommendation data...</p></section>';

    const memorySection = renderAnalysisMemory(memoryEntries, mode);
    const timelineSection = renderTimelineEntries(entries, mode);

    document.getElementById('cropsContent').innerHTML = `${npkSection}${timelineSection}${memorySection}${cropsSection}`;
}

function formatGraphNumber(value) {
    return value % 1 !== 0 ? value.toFixed(1) : value.toFixed(0);
}

function getHistoryForSelectedRange(historyRanges) {
    if (!historyRanges || typeof historyRanges !== 'object') {
        return [];
    }

    const selectedHistory = historyRanges[graphRange];
    return Array.isArray(selectedHistory) ? selectedHistory : [];
}

function renderGraph(historyRanges, values) {
    const graphContent = document.getElementById('graphContent');
    const graphStats = document.getElementById('graphStats');
    const history = getHistoryForSelectedRange(historyRanges);

    if (!values.length) {
        graphContent.innerHTML = '<p>⏳ No enabled sensors...</p>';
        graphStats.textContent = 'Awaiting samples...';
        return;
    }

    if (graphSensorIndex >= values.length) {
        graphSensorIndex = 0;
        renderGraphSelector();
    }

    if (!history.length) {
        graphContent.innerHTML = `<p>⏳ No ${graphRange} graph data yet...</p>`;
        graphStats.textContent = `Awaiting ${graphRange} samples...`;
        return;
    }

    const visibleIndexes = selectedGraphSensors.filter(index => index >= 0 && index < values.length);
    const indexesToRender = visibleIndexes.length > 0 ? visibleIndexes : [graphSensorIndex];
    const historyWindow = history;
    const series = indexesToRender.map(index => {
        const reading = values[index];
        const color = getSensorColor(reading.name, index);
        const points = historyWindow.map((entry, sampleIndex) => ({
            index: sampleIndex,
            time: entry.label || '',
            value: Array.isArray(entry.values) ? entry.values[index] : null
        })).filter(point => typeof point.value === 'number' && !Number.isNaN(point.value));

        return { index, reading, color, points };
    }).filter(seriesItem => seriesItem.points.length > 0);

    if (!series.length) {
        graphContent.innerHTML = '<p>⏳ Selected sensors have no graphable samples yet...</p>';
        graphStats.textContent = 'No numeric samples available for selected series';
        return;
    }

    const width = 760;
    const height = 320;
    const left = 56;
    const right = 18;
    const top = 20;
    const bottom = 48;
    const plotWidth = width - left - right;
    const plotHeight = height - top - bottom;

    const allPoints = series.flatMap(seriesItem => seriesItem.points);
    const rawMin = Math.min(...allPoints.map(point => point.value));
    const rawMax = Math.max(...allPoints.map(point => point.value));
    const padding = rawMin === rawMax ? Math.max(1, Math.abs(rawMin) * 0.1 || 1) : (rawMax - rawMin) * 0.12;
    const minValue = rawMin - padding;
    const maxValue = rawMax + padding;
    const range = maxValue - minValue || 1;

    const pointToSvg = (point) => {
        const xDenominator = Math.max(historyWindow.length - 1, 1);
        const x = left + (point.index / xDenominator) * plotWidth;
        const y = top + ((maxValue - point.value) / range) * plotHeight;
        return { x, y };
    };

    const yTicks = Array.from({ length: 5 }, (_, index) => {
        const value = maxValue - (range / 4) * index;
        const y = top + (plotHeight / 4) * index;
        return { value, y };
    });

    const xLabels = historyWindow.map((entry, index) => {
        const xDenominator = Math.max(historyWindow.length - 1, 1);
        const x = left + (index / xDenominator) * plotWidth;
        return { x, time: entry.label || '' };
    });

    const maxVisibleLabels = graphRange === 'hour' ? 6 : graphRange === 'day' ? 8 : 7;
    const labelStep = Math.max(1, Math.ceil(historyWindow.length / maxVisibleLabels));

    graphContent.innerHTML = `
        <svg class="graph-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-label="Multi-sensor graph">
            <rect x="0" y="0" width="${width}" height="${height}" class="graph-bg"></rect>
            ${yTicks.map(tick => `
                <line x1="${left}" y1="${tick.y}" x2="${width - right}" y2="${tick.y}" class="graph-grid"></line>
                <text x="${left - 8}" y="${tick.y + 4}" class="graph-axis-label" text-anchor="end">${formatGraphNumber(tick.value)}</text>
            `).join('')}
            <line x1="${left}" y1="${top}" x2="${left}" y2="${height - bottom}" class="graph-axis"></line>
            <line x1="${left}" y1="${height - bottom}" x2="${width - right}" y2="${height - bottom}" class="graph-axis"></line>
            ${series.map(seriesItem => {
                const svgPoints = seriesItem.points.map(pointToSvg);
                const linePath = svgPoints.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' ');
                const lastPoint = svgPoints[svgPoints.length - 1];
                const lastValue = seriesItem.points[seriesItem.points.length - 1].value;
                return `
                    <path d="${linePath}" class="graph-line" style="stroke: ${seriesItem.color}"></path>
                    ${svgPoints.map(point => `
                        <circle cx="${point.x}" cy="${point.y}" r="3.5" class="graph-point" style="fill: ${seriesItem.color}"></circle>
                    `).join('')}
                    <text x="${lastPoint.x + 8}" y="${lastPoint.y + 4}" class="graph-point-label" style="fill: ${seriesItem.color}">${seriesItem.reading.name} ${formatGraphNumber(lastValue)}</text>
                `;
            }).join('')}
            ${xLabels.map((label, index) => {
                if (historyWindow.length > maxVisibleLabels && index !== 0 && index !== historyWindow.length - 1 && index % labelStep !== 0) {
                    return '';
                }
                return `<text x="${label.x}" y="${height - bottom + 20}" class="graph-axis-label" text-anchor="middle">${label.time}</text>`;
            }).join('')}
        </svg>
    `;

    graphStats.innerHTML = series.map(seriesItem => {
        const numericValues = seriesItem.points.map(point => point.value);
        const average = numericValues.reduce((sum, value) => sum + value, 0) / numericValues.length;
        const latestValue = numericValues[numericValues.length - 1];
        const min = Math.min(...numericValues);
        const max = Math.max(...numericValues);
        return `<span class="graph-stat-item" style="border-color: ${seriesItem.color}; color: ${seriesItem.color}">${seriesItem.reading.name}${seriesItem.reading.unit ? ` (${seriesItem.reading.unit})` : ''} | ${graphRange.toUpperCase()} | MIN ${formatGraphNumber(min)} | AVG ${formatGraphNumber(average)} | MAX ${formatGraphNumber(max)} | LAST ${formatGraphNumber(latestValue)}</span>`;
    }).join('');
}

// Setup event listeners
function setupEventListeners() {
    // Settings button
    document.getElementById('settingsBtn').addEventListener('click', openSettings);
    document.getElementById('closeSettings').addEventListener('click', closeSettings);
    document.getElementById('closeSettingsBtn').addEventListener('click', closeSettings);
    
    // Save config button
    document.getElementById('saveSensorBtn').addEventListener('click', saveConfig);
    document.getElementById('resetSensorBtn').addEventListener('click', resetDefaults);

    document.getElementById('graphSensorSelect').addEventListener('change', (e) => {
        graphSensorIndex = parseInt(e.target.value, 10) || 0;
        if (!selectedGraphSensors.includes(graphSensorIndex)) {
            selectedGraphSensors.push(graphSensorIndex);
            selectedGraphSensors.sort((a, b) => a - b);
            saveSelectedGraphSensors();
            renderGraphLegend();
        }
        renderGraph(latestHistory, latestValues);
    });

    document.getElementById('graphRangeSelect').addEventListener('change', (e) => {
        graphRange = ['hour', 'day', 'week', 'month', 'year'].includes(e.target.value) ? e.target.value : 'day';
        localStorage.setItem('soilSensorGraphRange', graphRange);
        renderGraph(latestHistory, latestValues);
    });

    document.getElementById('modeSelector').addEventListener('change', async (e) => {
        await switchOperationMode(e.target.value);
    });

    document.getElementById('runAnalysisBtn').addEventListener('click', async () => {
        await runManualAnalysis();
    });

    document.getElementById('saveDiaryNoteBtn').addEventListener('click', async () => {
        await saveDiaryNote();
    });

    document.getElementById('diaryNoteInput').addEventListener('keydown', async (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            event.preventDefault();
            await saveDiaryNote();
        }
    });
    
    // Set selector
    document.getElementById('setSelector').addEventListener('change', async (e) => {
        const setId = parseInt(e.target.value);
        try {
            const response = await fetch(`/api/set/${setId}`, { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                activeSet = setId;
                await loadSettings();
                latestHistory = { hour: [], day: [], week: [], month: [], year: [] };
                latestValues = sensorReadings;
                renderSetSelector();
                renderSensorGrid();
                renderSensorConfigForm();
                renderGraphSelector();
                renderGraphLegend();
                renderGraph(latestHistory, sensorReadings);
            }
        } catch (error) {
            console.error('Error switching set:', error);
        }
    });
    
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            
            // Deactivate all tabs and buttons
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            
            // Activate selected tab and button
            document.getElementById(`${tabName}-tab`).classList.add('active');
            btn.classList.add('active');
        });
    });
}

async function switchOperationMode(mode) {
    const nextMode = ['analysis', 'continuous'].includes(mode) ? mode : 'continuous';

    try {
        const response = await fetch('/api/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ operation_mode: nextMode })
        });

        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'mode switch failed');
        }

        operationMode = data.operation_mode;
        updateModeControls();
        startPolling();
        await updateSensorData();
    } catch (error) {
        console.error('Error switching mode:', error);
        alert('Error switching mode');
        updateModeControls();
    }
}

async function runManualAnalysis() {
    if (operationMode !== 'analysis') {
        return;
    }

    const button = document.getElementById('runAnalysisBtn');
    button.disabled = true;
    button.textContent = '⏳ RUNNING...';

    try {
        const response = await fetch('/api/analyze', { method: 'POST' });
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'analysis failed');
        }
        await updateSensorData();
    } catch (error) {
        console.error('Error running analysis:', error);
        alert('Error running analysis');
    } finally {
        updateModeControls();
    }
}

async function saveDiaryNote() {
    const input = document.getElementById('diaryNoteInput');
    const button = document.getElementById('saveDiaryNoteBtn');
    const note = input.value.trim();

    if (!note) {
        input.focus();
        return;
    }

    button.disabled = true;
    button.textContent = '⏳ SAVING...';

    try {
        const response = await fetch('/api/timeline/note', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note })
        });
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'note save failed');
        }

        input.value = '';
        timelineEntries = Array.isArray(data.timeline_entries) ? data.timeline_entries : timelineEntries;
        await updateSensorData();
    } catch (error) {
        console.error('Error saving diary note:', error);
        alert('Error saving diary note');
    } finally {
        button.disabled = false;
        button.textContent = '📝 SAVE NOTE';
    }
}

// Open settings modal
function openSettings() {
    document.getElementById('settingsModal').classList.remove('hidden');
    renderSensorConfigForm();
}

// Close settings modal
function closeSettings() {
    document.getElementById('settingsModal').classList.add('hidden');
}

// Save configuration
async function saveConfig() {
    const setName = document.getElementById('setNameInput').value.trim() || `Set ${activeSet + 1}`;
    const selectedTheme = document.getElementById('themeSelect').value;
    const selectedMode = document.getElementById('modalModeSelect').value;
    const selectedPollInterval = Number(document.getElementById('pollIntervalSelect').value) || sensorPollInterval;
    
    const names = [];
    const enabled = [];
    
    document.querySelectorAll('.sensor-config-row').forEach(row => {
        const checkbox = row.querySelector('input[type="checkbox"]');
        const input = row.querySelector('input[type="text"]');
        
        enabled.push(checkbox ? checkbox.checked : false);
        names.push(input ? input.value.trim() : '');
    });
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                set_name: setName,
                names,
                enabled,
                ui_theme: selectedTheme,
                operation_mode: selectedMode,
                sensor_poll_interval: selectedPollInterval
            })
        });
        
        const data = await response.json();
        if (data.success) {
            applyTheme(selectedTheme);
            operationMode = ['analysis', 'continuous'].includes(selectedMode) ? selectedMode : operationMode;
            sensorPollInterval = selectedPollInterval;
            updateModeControls();
            await loadSettings();
            latestHistory = { hour: [], day: [], week: [], month: [], year: [] };
            latestValues = sensorReadings;
            renderSetSelector();
            renderSensorGrid();
            renderGraphSelector();
            renderGraphLegend();
            renderGraph(latestHistory, sensorReadings);
            startPolling();
            closeSettings();
        }
    } catch (error) {
        console.error('Error saving config:', error);
        alert('Error saving configuration');
    }
}

// Reset to defaults
function resetDefaults() {
    document.querySelectorAll('.sensor-config-row input[type="text"]').forEach((input, index) => {
        const defaultName = defaultReadings[index]?.name || '';
        input.value = defaultName;
    });
    
    document.querySelectorAll('.sensor-config-row input[type="checkbox"]').forEach(checkbox => {
        checkbox.checked = true;
    });
}

// Close modal by clicking outside
window.addEventListener('click', (e) => {
    const modal = document.getElementById('settingsModal');
    if (e.target === modal) {
        closeSettings();
    }
});

// Soil Sensor Web App - Frontend Logic

let sensorSets = {};
let activeSet = 0;
let sensorReadings = [];
let defaultReadings = [];
let pollInterval;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await loadSettings();
    renderSetSelector();
    renderSensorGrid();
    renderSensorConfigForm();
    startPolling();
    setupEventListeners();
});

// Load settings from server
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const data = await response.json();
        sensorSets = data.sensor_sets;
        activeSet = data.active_set;
        sensorReadings = data.readings;
        defaultReadings = data.default_readings;
    } catch (error) {
        console.error('Error loading settings:', error);
    }
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
    document.getElementById('setNameInput').value = setName;
    
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
    // Poll immediately
    updateSensorData();
    // Then every 2 seconds
    pollInterval = setInterval(updateSensorData, 2000);
}

// Update sensor data from API
async function updateSensorData() {
    try {
        const response = await fetch('/api/data');
        const data = await response.json();
        
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
        if (data.crops && data.crops.length > 0) {
            renderCrops(data.crops);
        } else {
            document.getElementById('cropsContent').innerHTML = '<p>⏳ Awaiting sensor data...</p>';
        }
        
        // Update history
        if (data.history && data.history.length > 0) {
            renderHistory(data.history, data.values);
        } else {
            document.getElementById('historyContent').innerHTML = '<p>⏳ No readings yet...</p>';
        }
    } catch (error) {
        console.error('Error updating sensor data:', error);
        document.getElementById('statusBar').textContent = '✗ Connection Error';
    }
}

// Render crop recommendations
function renderCrops(crops) {
    let html = 'TOP CROPS FOR YOUR SOIL:\n';
    html += '─'.repeat(50) + '\n\n';
    
    crops.forEach(crop => {
        const symbol = crop.score >= 80 ? '✓✓✓' : crop.score >= 60 ? '✓✓' : crop.score >= 40 ? '✓' : '△';
        const profitability = (crop.yield * crop.value) / 1000;
        
        html += `${crop.rank}. ${crop.icon} ${crop.name.toUpperCase().padEnd(15)} ${symbol}  [${crop.score.toFixed(0)}%]\n`;
        html += `   Yield: ${crop.yield.toFixed(0)}t/ha | Value: €${profitability.toFixed(1)}k/ha\n\n`;
    });
    
    document.getElementById('cropsContent').textContent = html;
}

// Render history
function renderHistory(history, values) {
    let html = `READINGS: ${history.length}/10\n`;
    html += '─'.repeat(65) + '\n\n';
    
    // Show each reading
    history.forEach((entry, idx) => {
        const timestamp = entry[entry.length - 1]; // Last element is timestamp
        html += `${idx + 1}. [${timestamp}]\n`;
        
        values.forEach((reading, i) => {
            if (i !== -1 && entry[i] !== undefined) {
                const val = entry[i];
                const formattedVal = typeof val === 'number'
                    ? (val % 1 !== 0 ? val.toFixed(1) : val.toFixed(0))
                    : val;
                html += `   ${reading.name.padEnd(12)} ${formattedVal} ${reading.unit}\n`;
            }
        });
        html += '\n';
    });
    
    // Calculate statistics
    if (history.length > 0) {
        html += '─'.repeat(65) + '\n';
        html += 'STATISTICS (Min / Avg / Max):\n';
        html += '─'.repeat(65) + '\n';
        
        values.forEach((reading, i) => {
            const vals = history.map(h => h[i]).filter(v => v !== undefined);
            if (vals.length > 0) {
                const min = Math.min(...vals);
                const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
                const max = Math.max(...vals);
                
                const minStr = min % 1 !== 0 ? min.toFixed(1) : min.toFixed(0);
                const avgStr = avg % 1 !== 0 ? avg.toFixed(1) : avg.toFixed(0);
                const maxStr = max % 1 !== 0 ? max.toFixed(1) : max.toFixed(0);
                
                html += `${reading.name.padEnd(14)} ${minStr} / ${avgStr} / ${maxStr} ${reading.unit}\n`;
            }
        });
    }
    
    document.getElementById('historyContent').textContent = html;
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
    
    // Set selector
    document.getElementById('setSelector').addEventListener('change', async (e) => {
        const setId = parseInt(e.target.value);
        try {
            const response = await fetch(`/api/set/${setId}`, { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                activeSet = setId;
                await loadSettings();
                renderSetSelector();
                renderSensorGrid();
                renderSensorConfigForm();
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
            body: JSON.stringify({ set_name: setName, names, enabled })
        });
        
        const data = await response.json();
        if (data.success) {
            await loadSettings();
            renderSetSelector();
            renderSensorGrid();
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

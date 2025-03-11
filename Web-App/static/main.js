// DOM elements
const commandArea = document.getElementById('command-area');
const systemCommandArea = document.getElementById('system-command-area');
const responseArea = document.getElementById('response-area');
const systemResponseArea = document.getElementById('system-response-area');
const sendBtn = document.getElementById('send-btn');
const systemSendBtn = document.getElementById('system-send-btn');
const clearCommandBtn = document.getElementById('clear-command-btn');
const systemClearCommandBtn = document.getElementById('system-clear-command-btn');
const clearResponseBtn = document.getElementById('clear-response-btn');
const systemClearResponseBtn = document.getElementById('system-clear-response-btn');
const authenticateBtn = document.getElementById('authenticate-btn');
const connectionStatus = document.getElementById('connection-status');
const gatewayInfo = document.getElementById('gateway-info');
const lastAuthTime = document.getElementById('last-auth-time');
const historyPanel = document.getElementById('history-panel');
const gatewayIpInput = document.getElementById('gateway-ip');
const gatewayPortInput = document.getElementById('gateway-port');
const saveGatewayConfigBtn = document.getElementById('save-gateway-config');
const selectedDeviceSelect = document.getElementById('selected-device');
const functionSelect = document.getElementById('function-select');
const functionValueInput = document.getElementById('function-value');
const applyTemplateBtn = document.getElementById('apply-template');
const discoverBtn = document.getElementById('discover-btn');
const deviceTypeFilter = document.getElementById('device-type-filter');
const refreshDevicesBtn = document.getElementById('refresh-devices-btn');
const deviceRangeStart = document.getElementById('device-range-start');
const deviceRangeEnd = document.getElementById('device-range-end');
const discoverBasestation = document.getElementById('discover-basestation');
const discoverCamera = document.getElementById('discover-camera');
const discoverOcp = document.getElementById('discover-ocp');
const discoveredDevicesList = document.getElementById('discovered-devices-list');
const foundDevicesCount = document.getElementById('found-devices-count');
const discoveryStatus = document.getElementById('discovery-status');

// Global state
let discoveredDevices = [];

// XML templates
const templates = {
    'function-value-change': function(deviceId, functionId, value) {
        return `<?xml version="2.0" encoding="UTF-8"?>
<function-value-change>
  <device>
    <deviceid>${deviceId}</deviceid>
    <function id="${functionId}">
      <value>${value}</value>
    </function>
  </device>
</function-value-change>`;
    },
    'function-value-request': function(deviceId, functionId) {
        return `<?xml version="2.0" encoding="UTF-8"?>
<function-value-request>
  <device>
    <deviceid>${deviceId}</deviceid>
    <function id="${functionId}">
    </function>
  </device>
</function-value-request>`;
    },
    'device-discovery': function(deviceType, deviceNumber) {
        return `<?xml version="2.0" encoding="UTF-8"?>
<function-value-request>
  <device>
    <type>${deviceType}</type>
    <n>${deviceNumber}</n>
  </device>
</function-value-request>`;
    }
};

// This checks the IP address used
function isValidIpAddress(ip) {
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipRegex.test(ip)) return false;
    const parts = ip.split('.');
    return parts.every(part => parseInt(part) >= 0 && parseInt(part) <= 255);
}

// Load the config from the gateway_config.csv file
async function loadGatewayConfig() {
    try {
        const response = await fetch('/api/gateway_config');
        const config = await response.json();
        gatewayIpInput.value = config.ip;
        gatewayPortInput.value = config.port;
    } catch (error) {
        console.error('Error loading gateway config:', error);
    }
}

// Save the IP/Port to the config file (gateway_config.csv)
async function saveGatewayConfig() {
    try {
        const ip = gatewayIpInput.value.trim();
        const port = parseInt(gatewayPortInput.value);

        // IP
        if (!isValidIpAddress(ip)) {
            alert('Please enter a valid IP address (e.g. 192.168.1.100)');
            return;
        }

        // port
        if (isNaN(port) || port < 1 || port > 65535) {
            alert('Please enter a valid port number (1-65535)');
            return;
        }

        // disables the button while saving
        saveGatewayConfigBtn.disabled = true;
        saveGatewayConfigBtn.textContent = 'Saving...';
        
        const response = await fetch('/api/gateway_config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                ip: gatewayIpInput.value,
                port: parseInt(gatewayPortInput.value)
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Update the connection status
            updateStatus();
            saveGatewayConfigBtn.textContent = 'Saved!';
            setTimeout(() => {
                saveGatewayConfigBtn.textContent = 'Save Configuration';
                saveGatewayConfigBtn.disabled = false;
            }, 2000);
        } else {
            alert('Failed to save configuration: ' + (result.message || 'Unknown error'));
            saveGatewayConfigBtn.textContent = 'Save Configuration';
            saveGatewayConfigBtn.disabled = false;
        }
    } catch (error) {
        console.error('Error saving gateway config:', error);
        alert('Error saving gateway configuration');
        saveGatewayConfigBtn.textContent = 'Save Configuration';
        saveGatewayConfigBtn.disabled = false;
    }
}

// load the GV xml templates 
async function loadFunctionTemplates() {
    try {
        const response = await fetch('/api/function_templates');
        const data = await response.json();
        
        if (data.success) {
            functionSelect.innerHTML = '<option value="">-- Select a function --</option>';
            
            data.functions.forEach(func => {
                const option = document.createElement('option');
                option.value = JSON.stringify(func);
                option.textContent = `${func.name} - ${func.description}`;
                functionSelect.appendChild(option);
            });
            
            functionSelect.disabled = false;
            functionValueInput.disabled = false;
        }
    } catch (error) {
        console.error('Error loading function templates:', error);
    }
}

// update 'device select'
function updateDeviceSelect(devices) {
    selectedDeviceSelect.innerHTML = '<option value="">-- Select a device --</option>';
    
    if (devices && devices.length > 0) {
        devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.deviceId;
            option.textContent = `${device.type} ${device.name}`;
            option.dataset.deviceType = device.type;
            selectedDeviceSelect.appendChild(option);
        });
    }
}

// check device type (Basestatuion, Camera, OCP) and load relevent functions
async function loadDeviceFunctions(deviceType) {
    try {
        const response = await fetch(`/api/functions?type=${deviceType}`);
        const result = await response.json();
        
        if (result.success) {
            functionSelect.innerHTML = '<option value="">-- Select a function --</option>';
            
            if (result.functions && result.functions.length > 0) {
                result.functions.forEach(func => {
                    const option = document.createElement('option');
                    option.value = JSON.stringify(func);
                    option.textContent = `${func.name} - ${func.description}`;
                    functionSelect.appendChild(option);
                });
                
                functionSelect.disabled = false;
                functionValueInput.disabled = false;
            } else {
                functionSelect.disabled = true;
                functionValueInput.disabled = true;
            }
        } else {
            console.error('Error loading functions:', result.error);
        }
    } catch (error) {
        console.error('Error loading functions:', error);
    }
}

// parse the contents of the dicovery url
async function discoverDevices() {
    const startNum = parseInt(deviceRangeStart.value);
    const endNum = parseInt(deviceRangeEnd.value);
    
    if (startNum > endNum) {
        alert('Start number must be less than or equal to end number');
        return null;
    }
    
    const deviceTypes = [];
    if (discoverBasestation.checked) deviceTypes.push('Basestation');
    if (discoverCamera.checked) deviceTypes.push('Camera');
    if (discoverOcp.checked) deviceTypes.push('OCP');
    
    if (deviceTypes.length === 0) {
        alert('Please select at least one device type');
        return;
    }
    
    try {
        const response = await fetch('/api/discover', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                startNum: startNum,
                endNum: endNum,
                deviceTypes: deviceTypes
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            discoveredDevices = result.devices;
            updateDeviceSelect(result.devices);
            updateDiscoveredDevicesList(result.devices);
            return result.devices;
        } else {
            alert('Failed to discover devices: ' + result.error);
        }
    } catch (error) {
        console.error('Error discovering devices:', error);
        alert('Error discovering devices');
    }
    
    return null;
}

// update device list
function updateDiscoveredDevicesList(devices = discoveredDevices, filter = 'all') {
    discoveredDevicesList.innerHTML = '';
    
    if (!devices || devices.length === 0) {
        discoveredDevicesList.innerHTML = '<div class="list-group-item text-muted">No devices discovered</div>';
        foundDevicesCount.textContent = '0';
        return;
    }
    
    const filteredDevices = filter === 'all' ? 
        devices : 
        devices.filter(device => device.type === filter);
    
    foundDevicesCount.textContent = filteredDevices.length.toString();
    
    filteredDevices.forEach(device => {
        const item = document.createElement('div');
        item.className = 'list-group-item';
        
        const deviceName = device.name;
        const deviceType = device.type;
        const deviceId = device.deviceId;
        
        item.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <h6 class="mb-1">${deviceName} (${deviceType})</h6>
                    <small class="text-muted">ID: ${deviceId}</small>
                </div>
                <button class="btn btn-outline-primary btn-sm select-device" data-device-id="${deviceId}">Select</button>
            </div>
        `;
        
        const selectBtn = item.querySelector('.select-device');
        selectBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const deviceInfo = devices.find(d => d.deviceId === deviceId);
            if (deviceInfo) {
                selectedDeviceSelect.value = deviceId;
                selectedDeviceSelect.dispatchEvent(new Event('change'));
            }
        });
        
        discoveredDevicesList.appendChild(item);
    });
}

// update the status
function updateStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            gatewayInfo.textContent = `${data.gateway_ip}:${data.gateway_port}`;
            lastAuthTime.textContent = data.last_auth_time || 'Never';
            
            if (data.connected) {
                connectionStatus.innerHTML = `
                    <span class="status-indicator status-connected"></span>
                    Connected
                `;
            } else {
                connectionStatus.innerHTML = `
                    <span class="status-indicator status-disconnected"></span>
                    Disconnected
                `;
            }
        })
        .catch(error => {
            console.error('Error fetching status:', error);
        });
}

// update the history
function updateHistory() {
    fetch('/api/history')
        .then(response => response.json())
        .then(data => {
            const historyPanels = document.querySelectorAll('.history-panel');
            historyPanels.forEach(panel => {
                panel.innerHTML = '';
                
                data.reverse().forEach(item => {
                    const historyItem = document.createElement('div');
                    historyItem.className = 'history-item';
                    
                    // Create a preview of the command
                    const commandPreview = item.command.split('\n')[0] + 
                        (item.command.split('\n').length > 1 ? '...' : '');

                    historyItem.innerHTML = `
                        <div class="d-flex align-items-center">
                            <span class="timestamp">${item.timestamp}</span>
                            <span class="command-preview">${commandPreview}</span>
                        </div>
                    `;
                    
                    historyItem.addEventListener('click', () => {
                        // 'system' tab
                        const systemTab = document.querySelector('#system-tab');
                        if (systemTab) {
                            const tabInstance = new bootstrap.Tab(systemTab);
                            tabInstance.show();
                        }
                        
                        // load command
                        const systemCommandArea = document.querySelector('#system-command-area');
                        if (systemCommandArea) {
                            systemCommandArea.value = item.command;
                        }
                        
                        // load response
                        const systemResponseArea = document.querySelector('#system-response-area');
                        if (systemResponseArea) {
                            const responseContent = systemResponseArea.querySelector('.response-content');
                            if (responseContent) {
                                responseContent.textContent = item.response || 'No response';
                                responseContent.style.display = 'block';
                            }
                        }
                    });
                    
                    panel.appendChild(historyItem);
                });
            });
        })
        .catch(error => {
            console.error('Error fetching history:', error);
        });
}

// send command to GV
function sendCommand(cmdArea, respArea) {
    const command = cmdArea.value.trim();
    
    if (!command) {
        alert('Please enter a command');
        return;
    }
    
    //  clear old response messages
    const responseContent = respArea.querySelector('.response-content');
    responseContent.textContent = '';
    
    fetch('/api/send_command', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ command })
    })
        .then(response => response.json())
        .then(data => {
            responseContent.textContent = data.response || 'No response';
            responseContent.style.display = 'block';
            updateHistory();
            updateStatus();
        })
        .catch(error => {
            console.error('Error sending command:', error);
            responseContent.textContent = `Error: ${error.message}`;
            responseContent.style.display = 'block';
        });
}

// Authenticate
function authenticate() {
    authenticateBtn.disabled = true;
    authenticateBtn.textContent = 'Authenticating...';
    
    fetch('/api/authenticate', {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                lastAuthTime.textContent = data.last_auth_time || 'Never';
            }
            updateStatus();
            updateHistory();
        })
        .catch(error => {
            console.error('Error authenticating:', error);
        })
        .finally(() => {
            authenticateBtn.disabled = false;
            authenticateBtn.textContent = 'Authenticate Now';
        });
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Initialize
    loadGatewayConfig();
    loadFunctionTemplates();
    updateStatus();
    updateHistory();
    
    // Event listener for Save Configuration button
    saveGatewayConfigBtn.addEventListener('click', saveGatewayConfig);
    
    // Event listener for command type toggle
    document.querySelectorAll('input[name="command-type"]').forEach(radio => {
        radio.addEventListener('change', (event) => {
            const functionValueContainer = document.getElementById('function-value-container');
            functionValueContainer.style.display = event.target.value === 'change' ? 'block' : 'none';
        });
    });
    
    // Event listener for device selection
    selectedDeviceSelect.addEventListener('change', (event) => {
        const option = event.target.options[event.target.selectedIndex];
        if (option && option.dataset.deviceType) {
            loadDeviceFunctions(option.dataset.deviceType);
        }
    });
    
    // Event listener for Apply Template button
    applyTemplateBtn.addEventListener('click', () => {
        const deviceId = selectedDeviceSelect.value;
        if (!deviceId) {
            alert('Please select a device');
            return;
        }

        const selectedFunctionValue = functionSelect.value;
        if (!selectedFunctionValue) {
            alert('Please select a function');
            return;
        }

        const selectedFunction = JSON.parse(selectedFunctionValue);
        if (!selectedFunction.id) {
            alert('Invalid function selected');
            return;
        }

        const commandType = document.querySelector('input[name="command-type"]:checked').value;
        let command;

        if (commandType === 'change') {
            const value = functionValueInput.value.trim();
            if (!value) {
                alert('Please enter a function value');
                return;
            }
            command = templates['function-value-change'](deviceId, selectedFunction.id, value);
        } else {
            command = templates['function-value-request'](deviceId, selectedFunction.id);
        }

        // Find the active tab's command area
        const activeTab = document.querySelector('.tab-pane.active');
        if (activeTab) {
            const cmdArea = activeTab.querySelector('.command-area');
            if (cmdArea) {
                cmdArea.value = command;
            }
        }
    });
    
    // Event listeners for device discovery
    discoverBtn.addEventListener('click', discoverDevices);
    deviceTypeFilter.addEventListener('change', () => updateDiscoveredDevicesList());
    refreshDevicesBtn.addEventListener('click', discoverDevices);
    
    // Event listeners for command buttons
    sendBtn.addEventListener('click', () => sendCommand(commandArea, responseArea));
    systemSendBtn.addEventListener('click', () => sendCommand(systemCommandArea, systemResponseArea));
    clearCommandBtn.addEventListener('click', () => commandArea.value = '');
    systemClearCommandBtn.addEventListener('click', () => systemCommandArea.value = '');
    clearResponseBtn.addEventListener('click', () => {
        const responseContent = responseArea.querySelector('.response-content');
        if (responseContent) {
            responseContent.textContent = '';
            responseContent.style.display = 'none';
        }
    });
    systemClearResponseBtn.addEventListener('click', () => {
        const responseContent = systemResponseArea.querySelector('.response-content');
        if (responseContent) {
            responseContent.textContent = '';
            responseContent.style.display = 'none';
        }
    });
    authenticateBtn.addEventListener('click', authenticate);
});

// Update all the things
setInterval(updateStatus, 5000);
setInterval(updateHistory, 10000);

// script.js

// DOM Elements
const connectionStep = document.getElementById('connection-step');
const configurationStep = document.getElementById('configuration-step');
const mcpStep = document.getElementById('mcp-step');
const resultsStep = document.getElementById('results-step');
const connectionStatus = document.getElementById('connectionStatus');
const benchmarkCaseSelect = document.getElementById('benchmarkCase');
const mcpServersContainer = document.getElementById('mcpServersContainer');
const resultsContainer = document.getElementById('resultsContainer');

// Backend server URL (same domain)
const BACKEND_URL = window.location.origin;

// MCP Functions - in real implementation, this would come from backend
let mcpFunctions = [];

// Initialize the UI
async function initUI() {
    populateBenchmarkCases();

    document
        .getElementById('testConnectionBtn')
        .addEventListener('click', testConnection);

    await loadMCPFunctions();
}

// Populate benchmark case dropdown
function populateBenchmarkCases() {
    benchmarkCaseSelect.innerHTML = '';
    const cases = [
        { id: 'fix-bug', name: 'Fix Bug' },
        { id: 'refactor', name: 'Refactor Code' },
        { id: 'optimize', name: 'Optimize Performance' },
        { id: 'add-unit-test', name: 'Add Unit Test' }
    ];
    
    cases.forEach(caseItem => {
        const option = document.createElement('option');
        option.value = caseItem.id;
        option.textContent = caseItem.name;
        benchmarkCaseSelect.appendChild(option);
    });
}

async function loadMCPFunctions() {
    try {
        mcpServersContainer.innerHTML = '<p>Loading MCP tools...</p>';

        const response = await fetch(
            `${BACKEND_URL}/api/mcp/tools`
        );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const result = await response.json();

        if (!result.success) {
            throw new Error(
                result.error || 'Failed to load MCP tools'
            );
        }

        mcpFunctions = result.tools.map(tool => ({
            id: tool.name,
            name: tool.name,
            description: tool.description || '',
            inputSchema: tool.inputSchema,
            enabled: true
        }));

        console.log(
            `Loaded ${mcpFunctions.length} MCP tools`
        );

        populateMCPFunctions();

    } catch (error) {
        console.error(
            'Failed to load MCP tools:',
            error
        );

        mcpServersContainer.innerHTML = `
            <div class="error">
                Failed to load MCP tools:
                ${error.message}
            </div>
        `;
    }
}

// Populate MCP functions
function populateMCPFunctions() {
    mcpServersContainer.innerHTML = '';

    const mcpServerDiv = document.createElement('div');

    mcpServerDiv.className = 'mcp-server';

    const title = document.createElement('h3');
    title.textContent = `DiscoPoP MCP (${mcpFunctions.length} tools)`;

    mcpServerDiv.appendChild(title);

    mcpFunctions.forEach(func => {
        const functionDiv = document.createElement('div');

        functionDiv.className = 'mcp-function';

        functionDiv.innerHTML = `
            <input
                type="checkbox"
                id="${func.id}"
                ${func.enabled ? 'checked' : ''}
            >

            <label for="${func.id}">
                <strong>${func.name}</strong>
                ${
                    func.description
                        ? `<small>${func.description}</small>`
                        : ''
                }
            </label>
        `;

        mcpServerDiv.appendChild(functionDiv);
    });

    mcpServersContainer.appendChild(mcpServerDiv);
}

// Test connection to LLM
async function testConnection() {
    const serverUrl = document.getElementById('serverUrl').value;
    const apiKey = document.getElementById('apiKey').value;
    const model = document.getElementById('model').value;
    
    if (!serverUrl || !apiKey || !model) {
        connectionStatus.textContent = 'Please fill in all fields';
        connectionStatus.className = 'disconnected';
        return;
    }
    
    // Show loading state
    connectionStatus.textContent = 'Testing connection...';
    connectionStatus.className = 'disconnected';
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/connect`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                serverUrl,
                apiKey,
                model
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            connectionStatus.textContent = 'Connected successfully!';
            connectionStatus.className = 'connected';
            showConfigurationStep();
        } else {
            connectionStatus.textContent = 'Connection failed: ' + (result.message || result.error || 'Unknown error');
            connectionStatus.className = 'disconnected';
        }
    } catch (error) {
        connectionStatus.textContent = 'Connection error: ' + error.message;
        connectionStatus.className = 'disconnected';
        console.error('Connection error:', error);
    }
}

// Show configuration step
function showConfigurationStep() {
    connectionStep.classList.remove('active');
    configurationStep.classList.add('active');
}

// Show MCP step
function showMCPStep() {
    configurationStep.classList.remove('active');
    mcpStep.classList.add('active');
}

// Run benchmark
async function runBenchmark() {
    // Collect form data
    const benchmarkCase = benchmarkCaseSelect.value;
    const runsCount = document.getElementById('runsCount').value;
    const maxSteps = document.getElementById('maxSteps').value;
    
    // Collect MCP function selections
    const selectedFunctions = [];
    document.querySelectorAll('#mcpServersContainer input[type="checkbox"]:checked').forEach(checkbox => {
        selectedFunctions.push(checkbox.id);
    });
    
    try {
        // Send benchmark request to backend
        const response = await fetch(`${BACKEND_URL}/api/run_benchmark`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                benchmarkCase,
                runs: parseInt(runsCount),
                maxSteps: parseInt(maxSteps),
                mcpFunctions: selectedFunctions
            })
        });
        
        const results = await response.json();
        
        if (results.error) {
            throw new Error(results.error);
        }
        
        // Display results
        displayResults(results);
        
    } catch (error) {
        console.error('Benchmark error:', error);
        resultsContainer.innerHTML = `<div class="error">Error running benchmark: ${error.message}</div>`;
    }
}

// Display benchmark results
function displayResults(results) {
    mcpStep.classList.remove('active');
    resultsStep.classList.add('active');
    
    // Format the results
    const resultsHTML = `
        <h3>Benchmark Results</h3>
        
        <div class="results-summary">
            <h4>Performance Comparison</h4>
            <p><strong>Selected Benchmark Case:</strong> ${results.configuration?.benchmark_case || 'N/A'}</p>
            <p><strong>Runs:</strong> ${results.configuration?.runs || 'N/A'}</p>
            <p><strong>Max MCP Steps:</strong> ${results.configuration?.max_steps || 'N/A'}</p>
        </div>
        
        <h4>Token Usage</h4>
        <table class="results-table">
            <thead>
                <tr>
                    <th>Mode</th>
                    <th>Input Tokens</th>
                    <th>Output Tokens</th>
                    <th>Total Tokens</th>
                    <th>Correctness</th>
                    <th>Latency (s)</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Direct</td>
                    <td>${results.results?.direct?.input_tokens?.toLocaleString() || '0'}</td>
                    <td>${results.results?.direct?.output_tokens?.toLocaleString() || '0'}</td>
                    <td>${results.results?.direct?.total_tokens?.toLocaleString() || '0'}</td>
                    <td>${results.results?.direct?.correctness || '0'}%</td>
                    <td>${results.results?.direct?.latency?.toFixed(1) || '0.0'}</td>
                </tr>
                <tr>
                    <td>Full DP</td>
                    <td>${results.results?.full_discopop?.input_tokens?.toLocaleString() || '0'}</td>
                    <td>${results.results?.full_discopop?.output_tokens?.toLocaleString() || '0'}</td>
                    <td>${results.results?.full_discopop?.total_tokens?.toLocaleString() || '0'}</td>
                    <td>${results.results?.full_discopop?.correctness || '0'}%</td>
                    <td>${results.results?.full_discopop?.latency?.toFixed(1) || '0.0'}</td>
                </tr>
                <tr>
                    <td>MCP</td>
                    <td>${results.results?.mcp?.input_tokens?.toLocaleString() || '0'}</td>
                    <td>${results.results?.mcp?.output_tokens?.toLocaleString() || '0'}</td>
                    <td>${results.results?.mcp?.total_tokens?.toLocaleString() || '0'}</td>
                    <td>${results.results?.mcp?.correctness || '0'}%</td>
                    <td>${results.results?.mcp?.latency?.toFixed(1) || '0.0'}</td>
                </tr>
            </tbody>
        </table>
        
        <h4>Token Reduction</h4>
        <p><strong>Input Token Reduction:</strong> ${results.results?.reduction?.input_tokens?.toFixed(1) || '0'}%</p>
        <p><strong>Output Token Reduction:</strong> ${results.results?.reduction?.output_tokens?.toFixed(1) || '0'}%</p>
        <p><strong>Total Token Reduction:</strong> ${results.results?.reduction?.total_tokens?.toFixed(1) || '0'}%</p>
        
        <h4>Additional Information</h4>
        <p><strong>Model:</strong> ${results.model || 'N/A'}</p>
        <p><strong>Timestamp:</strong> ${results.generated_at || 'N/A'}</p>
    `;
    
    resultsContainer.innerHTML = resultsHTML;
}

// Restart benchmark
function restartBenchmark() {
    resultsStep.classList.remove('active');
    connectionStep.classList.add('active');
    connectionStatus.textContent = '';
    connectionStatus.className = '';
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', initUI);
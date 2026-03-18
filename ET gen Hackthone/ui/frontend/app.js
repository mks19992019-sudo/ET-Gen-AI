/* ========== CONFIGURATION ========== */
const CONFIG = {
  BASE_URL: "http://localhost:8000",
  WS_URL: "ws://localhost:8000/ws/agent-live"
};

/* ========== STATE MANAGEMENT ========== */
const state = {
  currentPage: 'dashboard',
  agentStatus: 'IDLE',
  agentRunId: null,
  teams: [],
  employees: [],
  signals: [],
  hiringDecisions: [],
  auditTrail: [],
  jobDescriptions: [],
  webSocketConnected: false,
  pendingApprovalId: null,
  pendingRejectId: null,
  currentJdId: null,
  auditFilterDate: 'all',
  auditFilterAgent: ''
};

let webSocket = null;
let statusPolling = null;
let wsReconnectAttempts = 0;

/* ========== INITIALIZATION ========== */
document.addEventListener('DOMContentLoaded', () => {
  initializeNavigation();
  connectWebSocket();
  startStatusPolling();
  loadDashboard();
});

/* ========== NAVIGATION ========== */
// Initialize sidebar navigation click handlers
function initializeNavigation() {
  document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const page = link.dataset.page;
      navigateTo(page);
    });
  });

  // Run Agent button
  document.getElementById('runAgentBtn').addEventListener('click', runAgent);

  // Clear logs button
  document.getElementById('clearLogsBtn').addEventListener('click', clearLogs);

  // Export audit button
  document.getElementById('exportAuditBtn').addEventListener('click', exportAudit);

  // Audit filters
  document.getElementById('auditFilterDate').addEventListener('change', (e) => {
    state.auditFilterDate = e.target.value;
    renderAuditTrail();
  });

  document.getElementById('auditFilterAgent').addEventListener('change', (e) => {
    state.auditFilterAgent = e.target.value;
    renderAuditTrail();
  });
}

// Navigate to a page by hiding all and showing target
function navigateTo(page) {
  state.currentPage = page;

  // Update sidebar active state
  document.querySelectorAll('.nav-link').forEach(link => {
    link.classList.remove('active');
  });
  document.querySelector(`[data-page="${page}"]`).classList.add('active');

  // Hide all pages
  document.querySelectorAll('.page').forEach(p => {
    p.classList.remove('active');
  });

  // Show target page
  document.getElementById(page).classList.add('active');

  // Load page-specific data
  switch(page) {
    case 'dashboard':
      loadDashboard();
      break;
    case 'live-log':
      // Live log auto-updates via WebSocket
      break;
    case 'hiring-decisions':
      loadHiringDecisions();
      break;
    case 'job-descriptions':
      loadJobDescriptions();
      break;
    case 'audit-trail':
      loadAuditTrail();
      break;
    case 'workforce-data':
      loadWorkforceData();
      break;
  }
}

/* ========== API FUNCTIONS ========== */

// GET /api/teams
// Returns: list of all teams with headcount, min_required, avg_hours, status
// Used for: Teams Monitored count in stat card + Teams table in Workforce page
async function fetchTeams() {
  try {
    const response = await fetch(`${CONFIG.BASE_URL}/api/teams`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.teams = data;
    return data;
  } catch (error) {
    console.error('Error fetching teams:', error);
    showErrorToast('Failed to load teams data');
    return [];
  }
}

// GET /api/employees
// Returns: list of all employees with name, role, department, status, hours_per_week, joined_date
// Used for: Total Employees count in stat card + Recent changes table in Workforce page
async function fetchEmployees() {
  try {
    const response = await fetch(`${CONFIG.BASE_URL}/api/employees`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.employees = data;
    return data;
  } catch (error) {
    console.error('Error fetching employees:', error);
    showErrorToast('Failed to load employees data');
    return [];
  }
}

// GET /api/signals
// Returns: list of signal scores per team — overload %, exits count, capacity_gap %, attrition count, skill_gap bool
// Used for: Signal Health cards on Dashboard with colored status badges
async function fetchSignals() {
  try {
    const response = await fetch(`${CONFIG.BASE_URL}/api/signals`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.signals = data;
    return data;
  } catch (error) {
    console.error('Error fetching signals:', error);
    showErrorToast('Failed to load signals data');
    return [];
  }
}

// GET /api/agent/status
// Returns: {status: "IDLE" | "RUNNING" | "COMPLETED", last_run: timestamp, current_step: string}
// Used for: Agent status indicator top right of dashboard + spinner when RUNNING
async function fetchAgentStatus() {
  try {
    const response = await fetch(`${CONFIG.BASE_URL}/api/agent/status`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    updateAgentStatus(data.status);
    return data;
  } catch (error) {
    console.error('Error fetching agent status:', error);
    return null;
  }
}

// GET /api/hiring/decisions
// Returns: list of hiring decisions — id, date, department, role, urgency, reason, status
// Used for: Hiring Decisions table with approve/reject buttons for PENDING ones
async function fetchHiringDecisions() {
  try {
    const response = await fetch(`${CONFIG.BASE_URL}/api/hiring/decisions`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.hiringDecisions = data;
    return data;
  } catch (error) {
    console.error('Error fetching hiring decisions:', error);
    showErrorToast('Failed to load hiring decisions');
    return [];
  }
}

// POST /api/hiring/approve
// Body: {decision_id: int}
// Returns: {success: true, message: string}
// Used for: When HR clicks Approve button — refreshes hiring decisions table after success
async function approveHiringDecision(decisionId) {
  try {
    const response = await fetch(`${CONFIG.BASE_URL}/api/hiring/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision_id: decisionId })
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    showSuccessToast('Decision approved successfully');
    await loadHiringDecisions();
    return data;
  } catch (error) {
    console.error('Error approving decision:', error);
    showErrorToast('Failed to approve decision');
    return null;
  }
}

// POST /api/hiring/reject
// Body: {decision_id: int, reason: string}
// Returns: {success: true, message: string}
// Used for: When HR clicks Reject button with reason — refreshes table after success
async function rejectHiringDecision(decisionId, reason) {
  try {
    const response = await fetch(`${CONFIG.BASE_URL}/api/hiring/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision_id: decisionId, reason })
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    showSuccessToast('Decision rejected successfully');
    await loadHiringDecisions();
    return data;
  } catch (error) {
    console.error('Error rejecting decision:', error);
    showErrorToast('Failed to reject decision');
    return null;
  }
}

// GET /api/jd/{id}
// Returns: {id, role, department, urgency, date, status, jd_text}
// Used for: "View JD" modal — shows full JD text when HR clicks View button
async function fetchJobDescription(id) {
  try {
    const response = await fetch(`${CONFIG.BASE_URL}/api/jd/${id}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching job description:', error);
    showErrorToast('Failed to load job description');
    return null;
  }
}

// POST /api/jd/{id}/approve
// Body: {} (id in URL)
// Returns: {success: true, message: string}
// Used for: HR approves JD — triggers LinkedIn posting, updates card status
async function approveJobDescription(id) {
  try {
    const response = await fetch(`${CONFIG.BASE_URL}/api/jd/${id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    showSuccessToast('Job Description approved and posted to LinkedIn');
    await loadJobDescriptions();
    closeModal('viewJdModal');
    return data;
  } catch (error) {
    console.error('Error approving JD:', error);
    showErrorToast('Failed to approve job description');
    return null;
  }
}

// POST /api/agent/run
// Body: {} (no body needed)
// Returns: {success: true, run_id: string}
// Used for: "Run Agent Now" button — starts full LangGraph pipeline manually
// After calling this, connect to WebSocket to stream live logs
async function runAgent() {
  try {
    const response = await fetch(`${CONFIG.BASE_URL}/api/agent/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.agentRunId = data.run_id;
    updateAgentStatus('RUNNING');
    showSuccessToast('Agent pipeline started');
    // Switch to live log page
    navigateTo('live-log');
    return data;
  } catch (error) {
    console.error('Error running agent:', error);
    showErrorToast('Failed to start agent pipeline');
    return null;
  }
}

// GET /api/audit
// Returns: list of audit entries — id, timestamp, agent_name, action, outcome
// Used for: Audit Trail timeline — all agent decisions ever made with color coding
async function fetchAuditTrail() {
  try {
    const response = await fetch(`${CONFIG.BASE_URL}/api/audit`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.auditTrail = data;
    return data;
  } catch (error) {
    console.error('Error fetching audit trail:', error);
    showErrorToast('Failed to load audit trail');
    return [];
  }
}

/* ========== PAGE RENDERING FUNCTIONS ========== */

// Load and render dashboard
async function loadDashboard() {
  try {
    // Show loading state
    showLoadingSpinner('signalsContainer');

    // Fetch all dashboard data in parallel
    const [teams, employees, signals] = await Promise.all([
      fetchTeams(),
      fetchEmployees(),
      fetchSignals()
    ]);

    // Update stat cards
    document.getElementById('totalEmployees').textContent = employees.length || '0';
    document.getElementById('teamsMonitored').textContent = teams.length || '0';

    // Count open hiring requests (assuming they're in hiringDecisions with PENDING status)
    const openRequests = state.hiringDecisions.filter(d => d.status === 'PENDING HR APPROVAL').length;
    document.getElementById('openHiringRequests').textContent = openRequests || '0';

    // Count jobs posted this month (assuming they're in jobDescriptions with POSTED status)
    const postedThisMonth = state.jobDescriptions.filter(jd => jd.status === 'POSTED TO LINKEDIN').length;
    document.getElementById('jobsPostedMonth').textContent = postedThisMonth || '0';

    // Render signal cards
    renderSignalCards(signals);

  } catch (error) {
    console.error('Error loading dashboard:', error);
    showErrorState('signalsContainer');
  }
}

// Render signal cards with animated cards
function renderSignalCards(signals) {
  const container = document.getElementById('signalsContainer');
  
  if (!signals || signals.length === 0) {
    container.innerHTML = '<div class="error-state">No signal data available</div>';
    return;
  }

  container.innerHTML = signals.map(signal => `
    <div class="signal-card">
      <div class="signal-header">
        <div class="signal-team">${signal.team_name || 'Unknown Team'}</div>
        <div class="signal-badge ${getStatusBadgeClass(signal.status)}">${signal.status}</div>
      </div>

      <div class="signal-item">
        <div class="signal-name">Overload Signal</div>
        <div class="signal-bar-container">
          <div class="signal-bar" style="width: ${signal.overload_percentage || 0}%"></div>
        </div>
        <div class="signal-value">${signal.overload_percentage || 0}%</div>
      </div>

      <div class="signal-item">
        <div class="signal-name">Recent Exits</div>
        <div class="signal-value">${signal.recent_exits_count || 0} employees</div>
      </div>

      <div class="signal-item">
        <div class="signal-name">Project Capacity Gap</div>
        <div class="signal-bar-container">
          <div class="signal-bar" style="width: ${signal.capacity_gap_percentage || 0}%"></div>
        </div>
        <div class="signal-value">${signal.capacity_gap_percentage || 0}%</div>
      </div>

      <div class="signal-item">
        <div class="signal-name">Attrition Pattern (90 days)</div>
        <div class="signal-value">${signal.attrition_count || 0} exits</div>
      </div>

      <div class="signal-item">
        <div class="signal-name">Skill Gap</div>
        <div class="signal-badge-item">${signal.skill_gap ? 'Yes - Gap Detected' : 'No'}</div>
      </div>
    </div>
  `).join('');
}

// Get status badge styling class
function getStatusBadgeClass(status) {
  if (!status) return 'badge-normal';
  const upper = status.toUpperCase();
  if (upper.includes('CRITICAL')) return 'badge-critical';
  if (upper.includes('WARNING')) return 'badge-warning';
  return 'badge-normal';
}

// Load and render hiring decisions table
async function loadHiringDecisions() {
  try {
    const decisions = await fetchHiringDecisions();
    renderHiringDecisionsTable(decisions);
  } catch (error) {
    console.error('Error loading hiring decisions:', error);
    showErrorState('hiringDecisionsTableBody');
  }
}

// Render hiring decisions table rows
function renderHiringDecisionsTable(decisions) {
  const tbody = document.getElementById('hiringDecisionsTableBody');

  if (!decisions || decisions.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 24px;">No hiring decisions yet</td></tr>';
    return;
  }

  tbody.innerHTML = decisions.map(decision => `
    <tr>
      <td>${formatDate(decision.date)}</td>
      <td>${decision.department || '-'}</td>
      <td>${decision.role || '-'}</td>
      <td><span class="urgency-badge ${getUrgencyClass(decision.urgency)}">${decision.urgency}</span></td>
      <td>${decision.reason || '-'}</td>
      <td><span class="status-badge ${getStatusClass(decision.status)}">${decision.status}</span></td>
      <td>
        ${decision.status === 'PENDING HR APPROVAL' ? `
          <div class="action-buttons">
            <button class="btn btn-success btn-small" onclick="openApproveModal(${decision.id})">✓ Approve</button>
            <button class="btn btn-danger btn-small" onclick="openRejectModal(${decision.id})">✗ Reject</button>
          </div>
        ` : '-'}
      </td>
    </tr>
  `).join('');
}

// Load and render job descriptions
async function loadJobDescriptions() {
  try {
    showLoadingSpinner('jobDescriptionsContainer');
    
    // Fetch from API - assuming there's an endpoint
    const response = await fetch(`${CONFIG.BASE_URL}/api/jd`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const jds = await response.json();
    state.jobDescriptions = jds;
    
    renderJobDescriptions(jds);
  } catch (error) {
    console.error('Error loading job descriptions:', error);
    showErrorState('jobDescriptionsContainer');
  }
}

// Render job description cards
function renderJobDescriptions(jds) {
  const container = document.getElementById('jobDescriptionsContainer');

  if (!jds || jds.length === 0) {
    container.innerHTML = '<div class="error-state">No job descriptions available</div>';
    return;
  }

  container.innerHTML = jds.map(jd => `
    <div class="card">
      <div class="card-title">${jd.role || 'Unknown Role'}</div>
      <div class="card-meta">
        <div>${jd.department || 'Unknown Department'}</div>
        <div><span class="urgency-badge ${getUrgencyClass(jd.urgency)}">${jd.urgency}</span></div>
        <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">${formatDate(jd.date)}</div>
      </div>
      <div class="card-meta">
        ${jd.status === 'POSTED TO LINKEDIN' ? '<span style="color: var(--status-success);">✓ Live on LinkedIn</span>' : `<span class="status-badge ${getStatusClass(jd.status)}">${jd.status}</span>`}
      </div>
      <div class="card-footer">
        <button class="btn btn-primary btn-small" onclick="openViewJdModal(${jd.id})">View JD</button>
        ${jd.status === 'PENDING REVIEW' ? `<button class="btn btn-success btn-small" onclick="setCurrentJdForApproval(${jd.id})">Approve</button>` : ''}
      </div>
    </div>
  `).join('');
}

// Load and render audit trail
async function loadAuditTrail() {
  try {
    showLoadingSpinner('auditTrailContainer');
    const entries = await fetchAuditTrail();
    
    // Populate agent filter dropdown
    const agents = [...new Set(entries.map(e => e.agent_name))];
    const agentSelect = document.getElementById('auditFilterAgent');
    agentSelect.innerHTML = '<option value="">All Agents</option>' + 
      agents.map(agent => `<option value="${agent}">${agent}</option>`).join('');
    
    renderAuditTrail();
  } catch (error) {
    console.error('Error loading audit trail:', error);
    showErrorState('auditTrailContainer');
  }
}

// Render audit trail with filtering
function renderAuditTrail() {
  const container = document.getElementById('auditTrailContainer');
  let entries = [...state.auditTrail];

  // Apply date filter
  if (state.auditFilterDate === 'today') {
    const today = new Date().toDateString();
    entries = entries.filter(e => new Date(e.timestamp).toDateString() === today);
  } else if (state.auditFilterDate === 'week') {
    const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    entries = entries.filter(e => new Date(e.timestamp) > weekAgo);
  }

  // Apply agent filter
  if (state.auditFilterAgent) {
    entries = entries.filter(e => e.agent_name === state.auditFilterAgent);
  }

  if (entries.length === 0) {
    container.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-secondary);">No audit entries match filters</div>';
    return;
  }

  container.innerHTML = entries.map(entry => `
    <div class="audit-entry">
      <div class="audit-header">
        <div>
          <div class="audit-agent">${entry.agent_name || 'System'}</div>
          <div class="audit-time">${formatDateTime(entry.timestamp)}</div>
        </div>
      </div>
      <div class="audit-action">${entry.action || 'No action'}</div>
      <div class="audit-outcome ${entry.outcome?.includes('success') || entry.outcome?.includes('Success') ? 'outcome-success' : 'outcome-error'}">${entry.outcome || 'Unknown'}</div>
    </div>
  `).join('');
}

// Load and render workforce data
async function loadWorkforceData() {
  try {
    const [teams, employees] = await Promise.all([
      fetchTeams(),
      fetchEmployees()
    ]);

    renderTeamsTable(teams);
    renderEmployeeChangesTable(employees);
  } catch (error) {
    console.error('Error loading workforce data:', error);
    showErrorState('teamsTableBody');
    showErrorState('employeeChangesTableBody');
  }
}

// Render teams table
function renderTeamsTable(teams) {
  const tbody = document.getElementById('teamsTableBody');

  if (!teams || teams.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 24px;">No teams available</td></tr>';
    return;
  }

  tbody.innerHTML = teams.map(team => `
    <tr>
      <td>${team.name || '-'}</td>
      <td>${team.department || '-'}</td>
      <td>${team.headcount || 0}</td>
      <td>${team.min_required || 0}</td>
      <td>${team.avg_hours_per_week || 0}</td>
      <td><span class="status-badge ${getStatusClass(team.status)}">${team.status || 'Unknown'}</span></td>
    </tr>
  `).join('');
}

// Render employee changes table
function renderEmployeeChangesTable(employees) {
  const tbody = document.getElementById('employeeChangesTableBody');

  if (!employees || employees.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 24px;">No recent changes</td></tr>';
    return;
  }

  // Show only recent changes (last 10)
  const recent = employees.slice(0, 10);
  tbody.innerHTML = recent.map(emp => `
    <tr>
      <td>${emp.name || '-'}</td>
      <td>${emp.role || '-'}</td>
      <td>${emp.department || '-'}</td>
      <td>${emp.status || '-'}</td>
      <td>${formatDate(emp.joined_date)}</td>
    </tr>
  `).join('');
}

/* ========== MODAL FUNCTIONS ========== */

// Open modal to view job description
async function openViewJdModal(id) {
  state.currentJdId = id;
  const jd = await fetchJobDescription(id);
  
  if (!jd) return;

  document.getElementById('jdModalTitle').textContent = jd.role || 'Job Description';
  document.getElementById('jdModalBody').textContent = jd.jd_text || 'No description available';
  
  // Show approve button only if PENDING REVIEW
  const approveBtn = document.getElementById('approveJdBtn');
  approveBtn.style.display = jd.status === 'PENDING REVIEW' ? 'inline-flex' : 'none';
  approveBtn.onclick = () => approveJobDescriptionModal(id);

  openModal('viewJdModal');
}

// Approve JD from modal
async function approveJobDescriptionModal(id) {
  await approveJobDescription(id);
}

// Set current JD for approval and open modal
function setCurrentJdForApproval(id) {
  openViewJdModal(id);
}

// Open approve decision modal
function openApproveModal(decisionId) {
  state.pendingApprovalId = decisionId;
  document.getElementById('confirmApproveBtn').onclick = () => {
    approveHiringDecision(decisionId);
    closeModal('approveDecisionModal');
  };
  openModal('approveDecisionModal');
}

// Open reject decision modal
function openRejectModal(decisionId) {
  state.pendingRejectId = decisionId;
  document.getElementById('rejectReasonInput').value = '';
  document.getElementById('confirmRejectBtn').onclick = () => {
    const reason = document.getElementById('rejectReasonInput').value.trim();
    if (!reason) {
      showWarningToast('Please enter a reason');
      return;
    }
    rejectHiringDecision(decisionId, reason);
    closeModal('rejectDecisionModal');
  };
  openModal('rejectDecisionModal');
}

// Open modal by ID
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  modal.classList.add('active');
}

// Close modal by ID
function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  modal.classList.remove('active');
}

// Close modal on background click
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal') && e.target.classList.contains('active')) {
    e.target.classList.remove('active');
  }
});

/* ========== WEBSOCKET ========== */

// Connect to WebSocket for live agent logs
function connectWebSocket() {
  try {
    webSocket = new WebSocket(CONFIG.WS_URL);
    
    webSocket.onopen = () => {
      console.log('WebSocket connected');
      state.webSocketConnected = true;
      updateConnectionStatus(true);
      wsReconnectAttempts = 0;
    };

    webSocket.onmessage = (event) => {
      const logEntry = JSON.parse(event.data);
      addLiveLogEntry(logEntry);
    };

    webSocket.onerror = (error) => {
      console.error('WebSocket error:', error);
      showErrorToast('WebSocket connection error');
    };

    webSocket.onclose = () => {
      console.log('WebSocket disconnected');
      state.webSocketConnected = false;
      updateConnectionStatus(false);
      // Try to reconnect after 5 seconds
      setTimeout(() => {
        if (wsReconnectAttempts < 5) {
          wsReconnectAttempts++;
          connectWebSocket();
        }
      }, 5000);
    };
  } catch (error) {
    console.error('Error connecting WebSocket:', error);
  }
}

// Update connection status indicator
function updateConnectionStatus(connected) {
  const statusLabel = document.querySelector('.connection-status .status-label');
  const statusDot = document.querySelector('.connection-status .status-dot');
  
  if (connected) {
    statusLabel.textContent = 'Connected';
    statusDot.classList.remove('disconnected');
  } else {
    statusLabel.textContent = 'Reconnecting...';
    statusDot.classList.add('disconnected');
  }
}

// Add log entry to live logs container
function addLiveLogEntry(logEntry) {
  const container = document.getElementById('liveLogsContainer');
  
  // Remove placeholder if present
  const placeholder = container.querySelector('.log-placeholder');
  if (placeholder) placeholder.remove();

  // Determine status color class
  let statusClass = 'log-status-info';
  if (logEntry.status === 'SUCCESS') statusClass = 'log-status-success';
  else if (logEntry.status === 'ERROR') statusClass = 'log-status-error';
  else if (logEntry.status === 'WARNING') statusClass = 'log-status-warning';
  else if (logEntry.status === 'CLAUDE') statusClass = 'log-status-claude';

  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerHTML = `
    <div class="log-timestamp">${formatDateTime(logEntry.timestamp)}</div>
    <div class="log-content">
      <div class="log-agent">${logEntry.agent || 'Agent'}</div>
      <div class="log-message">${logEntry.action || 'No action'}</div>
    </div>
    <div class="log-status ${statusClass}">${logEntry.status}</div>
  `;
  
  container.appendChild(entry);
  
  // Auto scroll to latest
  container.scrollTop = container.scrollHeight;

  // Check if agent completed
  if (logEntry.status === 'COMPLETED') {
    updateAgentStatus('COMPLETED');
    showSuccessToast('✓ Pipeline Complete');
  }
}

// Clear all logs
function clearLogs() {
  const container = document.getElementById('liveLogsContainer');
  container.innerHTML = '<div class="log-placeholder">Logs cleared. Waiting for new entries...</div>';
}

/* ========== AGENT STATUS ========== */

// Update agent status indicator
function updateAgentStatus(status) {
  state.agentStatus = status;
  const indicator = document.getElementById('agentStatus');
  const dot = indicator.querySelector('.status-indicator');
  const text = indicator.querySelector('.status-text');

  text.textContent = status;
  dot.className = 'status-indicator';

  if (status === 'RUNNING') {
    dot.classList.add('status-running');
  } else if (status === 'COMPLETED') {
    dot.classList.add('status-completed');
  } else {
    dot.classList.add('status-idle');
  }
}

// Poll agent status every 5 seconds
function startStatusPolling() {
  statusPolling = setInterval(async () => {
    const status = await fetchAgentStatus();
    if (status && status.status === 'COMPLETED' && state.agentStatus !== 'COMPLETED') {
      showSuccessToast('Agent pipeline completed');
    }
  }, 5000);
}

/* ========== TOAST NOTIFICATIONS ========== */

// Show success toast
function showSuccessToast(message) {
  showToast(message, 'success', '✓');
}

// Show error toast
function showErrorToast(message) {
  showToast(message, 'error', '✕');
}

// Show warning toast
function showWarningToast(message) {
  showToast(message, 'warning', '⚠');
}

// Show toast notification
function showToast(message, type = 'success', icon = '✓') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <div class="toast-icon">${icon}</div>
    <div class="toast-message">${message}</div>
  `;
  
  container.appendChild(toast);
  
  // Auto dismiss after 3 seconds
  setTimeout(() => {
    toast.style.animation = 'fadeOut 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

/* ========== UTILITY FUNCTIONS ========== */

// Format date string
function formatDate(dateString) {
  if (!dateString) return '-';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

// Format date and time
function formatDateTime(dateString) {
  if (!dateString) return '-';
  const date = new Date(dateString);
  return date.toLocaleString('en-US', { 
    year: 'numeric', 
    month: 'short', 
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

// Get urgency badge class
function getUrgencyClass(urgency) {
  if (!urgency) return '';
  const upper = urgency.toUpperCase();
  if (upper.includes('CRITICAL')) return 'urgency-critical';
  if (upper.includes('HIGH')) return 'urgency-high';
  return 'urgency-medium';
}

// Get status badge class
function getStatusClass(status) {
  if (!status) return '';
  const upper = status.toUpperCase();
  if (upper.includes('PENDING')) return 'status-pending';
  if (upper.includes('APPROVED')) return 'status-approved';
  if (upper.includes('REJECTED')) return 'status-rejected';
  if (upper.includes('GENERATED')) return 'status-generated';
  if (upper.includes('POSTED')) return 'status-posted';
  return '';
}

// Show loading spinner
function showLoadingSpinner(containerId) {
  const container = document.getElementById(containerId);
  container.innerHTML = '<div class="loading-spinner"></div>';
}

// Show error state
function showErrorState(containerId) {
  const container = document.getElementById(containerId);
  container.innerHTML = '<div class="error-state">Failed to load data. Backend may not be running.</div>';
}

// Export audit trail (demo)
function exportAudit() {
  showSuccessToast('Audit trail exported');
  // In real app, this would download a CSV or JSON file
}

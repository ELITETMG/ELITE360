let token = localStorage.getItem('ftth_token');
let currentUser = null;
let map = null;
let draw = null;
let projects = [];
let mapboxToken = '';
let measureMode = false;
let measurePoints = [];
let currentHoveredId = null;
let moveEndTimer = null;
let selectMode = false;
let selectedTaskIds = new Set();

const API = '';

const STATUS_COLORS = {
    not_started: '#94A3B8',
    in_progress: '#3B82F6',
    submitted: '#F59E0B',
    approved: '#10B981',
    billed: '#8B5CF6',
    rework: '#EF4444',
    failed_inspection: '#DC2626'
};

async function api(path, options = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(API + path, { ...options, headers });
    if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Request failed');
    }
    return res.json();
}

function toggleNavCategory(header) {
    const category = header.closest('.nav-category');
    category.classList.toggle('collapsed');
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    try {
        const data = await api('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password })
        });
        token = data.access_token;
        localStorage.setItem('ftth_token', token);
        await loadApp();
    } catch (err) {
        document.getElementById('login-error').textContent = err.message;
    }
});

async function loadApp() {
    try {
        currentUser = await api('/api/auth/me');
        const configData = await fetch('/api/config').then(r => r.json());
        mapboxToken = configData.mapbox_token;
        document.getElementById('user-name').textContent = currentUser.full_name;
        document.getElementById('user-role').textContent = currentUser.role || 'user';
        document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('main-screen').classList.remove('hidden');
        navigateTo('dashboard');
    } catch {
        logout();
    }
}

function logout() {
    token = null;
    currentUser = null;
    localStorage.removeItem('ftth_token');
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('main-screen').classList.add('hidden');
}

document.getElementById('logout-btn').addEventListener('click', logout);

document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        navigateTo(link.dataset.page);
    });
});

function navigateTo(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.getElementById(`page-${page}`).classList.remove('hidden');
    const activeLink = document.querySelector(`[data-page="${page}"]`);
    if (activeLink) activeLink.classList.add('active');

    const parentCategory = activeLink ? activeLink.closest('.nav-category') : null;
    if (parentCategory) {
        parentCategory.classList.remove('collapsed');
    }

    const contentEl = document.querySelector('.content');
    if (page === 'map') {
        contentEl.style.padding = '0';
        contentEl.style.overflow = 'hidden';
    } else {
        contentEl.style.padding = '';
        contentEl.style.overflow = '';
    }

    switch (page) {
        case 'dashboard': loadDashboard(); break;
        case 'projects': loadProjects(); break;
        case 'map':
            loadProjectSelects();
            setTimeout(() => {
                initMap();
                if (map) map.resize();
            }, 50);
            break;
        case 'tasks': loadProjectSelects(); setTimeout(() => loadTaskRecommendations(), 500); break;
        case 'task-types': loadTaskTypes(); break;
        case 'inspections': loadInspectionsPage(); break;
        case 'reports': loadReportsPage(); break;
        case 'budget': populateEnterpriseSelects(); loadBudget(); break;
        case 'materials': loadMaterials(); break;
        case 'documents': populateEnterpriseSelects(); loadDocuments(); break;
        case 'activity': populateEnterpriseSelects(); loadActivities(); break;
        case 'integrations': populateEnterpriseSelects(); loadIntegrations(); break;
        case 'admin': loadAdminPanel(); break;
        case 'billing': loadBillingPage(); break;
        case 'dispatch': loadDispatchBoard(); break;
        case 'assets': loadAssetsPage(); break;
        case 'fleet': loadFleetPage(); break;
        case 'safety': loadSafetyPage(); break;
        case 'hr': loadHRPage(); break;
    }
}

async function loadDashboard() {
    try {
        const stats = await api('/api/dashboard/stats');
        const pct = stats.total_planned_qty > 0
            ? Math.round((stats.total_actual_qty / stats.total_planned_qty) * 100) : 0;

        document.getElementById('stats-grid').innerHTML = `
            <div class="stat-card">
                <div class="stat-label">Total Projects</div>
                <div class="stat-value">${stats.total_projects}</div>
            </div>
            <div class="stat-card success">
                <div class="stat-label">Active Projects</div>
                <div class="stat-value">${stats.active_projects}</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-label">Total Tasks</div>
                <div class="stat-value">${stats.total_tasks}</div>
            </div>
            <div class="stat-card purple">
                <div class="stat-label">Completed Tasks</div>
                <div class="stat-value">${stats.completed_tasks}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">In Progress</div>
                <div class="stat-value">${stats.in_progress_tasks}</div>
            </div>
            <div class="stat-card success">
                <div class="stat-label">Overall Progress</div>
                <div class="stat-value">${pct}%</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-label">Planned Qty</div>
                <div class="stat-value">${formatNumber(stats.total_planned_qty)}</div>
            </div>
            <div class="stat-card danger">
                <div class="stat-label">Actual Qty</div>
                <div class="stat-value">${formatNumber(stats.total_actual_qty)}</div>
            </div>
        `;

        projects = await api('/api/projects');
        document.getElementById('recent-projects').innerHTML = projects.length
            ? projects.slice(0, 5).map(p => `
                <div class="project-card" onclick="navigateTo('map'); setTimeout(() => { document.getElementById('map-project-select').value='${p.id}'; loadMapData(); }, 300);">
                    <div class="project-card-header">
                        <h4>${esc(p.name)}</h4>
                        <span class="status-badge status-${p.status}">${p.status}</span>
                    </div>
                    <p>${esc(p.description || 'No description')}</p>
                    <div class="progress-bar"><div class="progress-fill" style="width:${p.task_count ? Math.round((p.completed_count/p.task_count)*100) : 0}%"></div></div>
                    <div class="progress-text"><span>${p.completed_count || 0} / ${p.task_count || 0} tasks</span><span>${p.executing_org_name || ''}</span></div>
                </div>
            `).join('')
            : '<div class="empty-state"><p>No projects yet</p></div>';

        loadDashboardKPIs();
        loadAIInsights();
        loadDailyBriefing();
    } catch (err) {
        console.error('Dashboard error:', err);
    }
}

async function loadProjects() {
    try {
        projects = await api('/api/projects');
        document.getElementById('projects-list').innerHTML = projects.length
            ? projects.map(p => `
                <div class="project-card">
                    <div class="project-card-header">
                        <h4>${esc(p.name)}</h4>
                        <span class="status-badge status-${p.status}">${p.status}</span>
                    </div>
                    <p>${esc(p.description || 'No description')}</p>
                    <div class="progress-bar"><div class="progress-fill" style="width:${p.task_count ? Math.round((p.completed_count/p.task_count)*100) : 0}%"></div></div>
                    <div class="progress-text"><span>${p.completed_count || 0} / ${p.task_count || 0} tasks</span></div>
                </div>
            `).join('')
            : '<div class="empty-state"><p>No projects yet. Create one to get started.</p></div>';
    } catch (err) {
        console.error('Projects error:', err);
    }
}

async function loadProjectSelects() {
    if (!projects.length) projects = await api('/api/projects');
    const opts = '<option value="">Select Project</option>' +
        projects.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('');
    const mapSel = document.getElementById('map-project-select');
    const taskSel = document.getElementById('task-project-select');
    if (mapSel) mapSel.innerHTML = opts;
    if (taskSel) taskSel.innerHTML = opts;

    if (projects.length === 1) {
        if (mapSel) { mapSel.value = projects[0].id; loadMapData(); }
        if (taskSel) { taskSel.value = projects[0].id; loadTasks(); }
    }
}

function initMap() {
    if (map) { map.resize(); return; }
    if (!mapboxToken) { console.error('No Mapbox token'); return; }

    mapboxgl.accessToken = mapboxToken;
    map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/satellite-streets-v12',
        center: [-97.7431, 30.2672],
        zoom: 14,
        attributionControl: true,
        pitch: 0,
        bearing: 0
    });

    map.addControl(new mapboxgl.NavigationControl(), 'top-right');
    map.addControl(new mapboxgl.ScaleControl({ unit: 'imperial' }), 'bottom-left');

    const geocoder = new MapboxGeocoder({
        accessToken: mapboxToken,
        mapboxgl: mapboxgl,
        placeholder: 'Search address...',
        marker: true,
        collapsed: true
    });
    map.addControl(geocoder, 'top-left');

    draw = new MapboxDraw({
        displayControlsDefault: false,
        controls: {
            polygon: true,
            line_string: true,
            point: true,
            trash: true
        },
        styles: [
            { id: 'draw-line', type: 'line', filter: ['all', ['==', '$type', 'LineString'], ['!=', 'mode', 'static']],
              paint: { 'line-color': '#FF6B6B', 'line-width': 3, 'line-dasharray': [2, 2] } },
            { id: 'draw-polygon-fill', type: 'fill', filter: ['all', ['==', '$type', 'Polygon'], ['!=', 'mode', 'static']],
              paint: { 'fill-color': '#FF6B6B', 'fill-opacity': 0.15 } },
            { id: 'draw-polygon-stroke', type: 'line', filter: ['all', ['==', '$type', 'Polygon'], ['!=', 'mode', 'static']],
              paint: { 'line-color': '#FF6B6B', 'line-width': 2, 'line-dasharray': [2, 2] } },
            { id: 'draw-point', type: 'circle', filter: ['all', ['==', '$type', 'Point'], ['==', 'meta', 'feature'], ['!=', 'mode', 'static']],
              paint: { 'circle-radius': 6, 'circle-color': '#FF6B6B' } },
            { id: 'draw-vertex', type: 'circle', filter: ['all', ['==', '$type', 'Point'], ['==', 'meta', 'vertex']],
              paint: { 'circle-radius': 4, 'circle-color': '#FF6B6B' } },
            { id: 'draw-midpoint', type: 'circle', filter: ['all', ['==', '$type', 'Point'], ['==', 'meta', 'midpoint']],
              paint: { 'circle-radius': 3, 'circle-color': '#FF6B6B' } },
        ]
    });
    map.addControl(draw, 'top-right');

    map.on('load', () => {
        addMapSources();
        addMapLayers();
        setupMapInteractions();
    });

    map.on('draw.create', onDrawUpdate);
    map.on('draw.update', onDrawUpdate);
    map.on('draw.delete', () => {
        document.getElementById('measurement-result').classList.add('hidden');
    });

    map.on('moveend', () => {
        if (moveEndTimer) clearTimeout(moveEndTimer);
        moveEndTimer = setTimeout(() => {
            const projectId = document.getElementById('map-project-select').value;
            if (projectId) loadMapData(true);
        }, 400);
    });

    if (projects.length === 1) {
        document.getElementById('map-project-select').value = projects[0].id;
        loadMapData();
    }
}

function addMapSources() {
    const emptyGeoJSON = { type: 'FeatureCollection', features: [] };
    map.addSource('spans', { type: 'geojson', data: emptyGeoJSON });
    map.addSource('nodes', { type: 'geojson', data: emptyGeoJSON });
    map.addSource('drops', { type: 'geojson', data: emptyGeoJSON });
    map.addSource('zones', { type: 'geojson', data: emptyGeoJSON });
}

function addMapLayers() {
    map.addLayer({
        id: 'zones-fill',
        type: 'fill',
        source: 'zones',
        paint: {
            'fill-color': ['coalesce', ['get', 'style_color'], ['get', 'status_color']],
            'fill-opacity': ['coalesce', ['get', 'style_opacity'], 0.15]
        }
    });
    map.addLayer({
        id: 'zones-outline',
        type: 'line',
        source: 'zones',
        paint: {
            'line-color': ['coalesce', ['get', 'style_color'], ['get', 'status_color']],
            'line-width': ['coalesce', ['get', 'style_width'], 2],
            'line-dasharray': [3, 2]
        }
    });

    map.addLayer({
        id: 'spans-casing',
        type: 'line',
        source: 'spans',
        paint: {
            'line-color': '#000000',
            'line-width': [
                'case',
                ['boolean', ['feature-state', 'hover'], false], 9,
                6
            ],
            'line-opacity': 0.35
        },
        layout: { 'line-cap': 'round', 'line-join': 'round' }
    });

    map.addLayer({
        id: 'spans-line',
        type: 'line',
        source: 'spans',
        paint: {
            'line-color': ['coalesce', ['get', 'style_color'], ['get', 'status_color']],
            'line-width': [
                'case',
                ['boolean', ['feature-state', 'hover'], false],
                ['*', ['coalesce', ['get', 'style_width'], 4], 1.5],
                ['coalesce', ['get', 'style_width'], 4]
            ],
            'line-opacity': ['coalesce', ['get', 'style_opacity'], 0.95]
        },
        layout: { 'line-cap': 'round', 'line-join': 'round' }
    });

    map.addLayer({
        id: 'spans-highlight',
        type: 'line',
        source: 'spans',
        filter: ['==', ['get', 'id'], ''],
        paint: {
            'line-color': '#FFFFFF',
            'line-width': 9,
            'line-opacity': 0.5
        },
        layout: { 'line-cap': 'round', 'line-join': 'round' }
    });

    map.addLayer({
        id: 'spans-label',
        type: 'symbol',
        source: 'spans',
        layout: {
            'symbol-placement': 'line-center',
            'text-field': ['get', 'name'],
            'text-size': 11,
            'text-max-angle': 30,
            'text-optional': true,
            'text-allow-overlap': false,
            'text-font': ['DIN Pro Medium', 'Arial Unicode MS Regular']
        },
        paint: {
            'text-color': '#FFFFFF',
            'text-halo-color': 'rgba(0,0,0,0.8)',
            'text-halo-width': 2
        },
        minzoom: 15
    });

    map.addLayer({
        id: 'nodes-outer',
        type: 'circle',
        source: 'nodes',
        paint: {
            'circle-radius': [
                'case',
                ['boolean', ['feature-state', 'hover'], false], 13,
                10
            ],
            'circle-color': 'rgba(0,0,0,0.3)',
            'circle-blur': 0.5
        }
    });

    map.addLayer({
        id: 'nodes-circle',
        type: 'circle',
        source: 'nodes',
        paint: {
            'circle-radius': [
                'case',
                ['boolean', ['feature-state', 'hover'], false], 10,
                7
            ],
            'circle-color': ['coalesce', ['get', 'style_color'], ['get', 'status_color']],
            'circle-stroke-color': '#FFFFFF',
            'circle-stroke-width': 2.5,
            'circle-opacity': ['coalesce', ['get', 'style_opacity'], 0.95]
        }
    });

    map.addLayer({
        id: 'nodes-label',
        type: 'symbol',
        source: 'nodes',
        layout: {
            'text-field': ['get', 'name'],
            'text-size': 12,
            'text-offset': [0, 1.6],
            'text-anchor': 'top',
            'text-optional': true,
            'text-font': ['DIN Pro Medium', 'Arial Unicode MS Regular']
        },
        paint: {
            'text-color': '#FFFFFF',
            'text-halo-color': 'rgba(0,0,0,0.8)',
            'text-halo-width': 2
        },
        minzoom: 14
    });

    map.addLayer({
        id: 'drops-circle',
        type: 'circle',
        source: 'drops',
        paint: {
            'circle-radius': [
                'case',
                ['boolean', ['feature-state', 'hover'], false], 8,
                5
            ],
            'circle-color': ['coalesce', ['get', 'style_color'], ['get', 'status_color']],
            'circle-stroke-color': '#FFFFFF',
            'circle-stroke-width': 1.5,
            'circle-opacity': ['coalesce', ['get', 'style_opacity'], 0.9]
        }
    });

    map.addLayer({
        id: 'drops-label',
        type: 'symbol',
        source: 'drops',
        layout: {
            'text-field': ['get', 'name'],
            'text-size': 10,
            'text-offset': [0, 1.3],
            'text-anchor': 'top',
            'text-optional': true,
            'text-font': ['DIN Pro Medium', 'Arial Unicode MS Regular']
        },
        paint: {
            'text-color': '#FFFFFF',
            'text-halo-color': 'rgba(0,0,0,0.8)',
            'text-halo-width': 1.5
        },
        minzoom: 15
    });
}

function setupMapInteractions() {
    const interactiveLayers = ['spans-line', 'nodes-circle', 'drops-circle', 'zones-fill'];

    interactiveLayers.forEach(layerId => {
        map.on('click', layerId, (e) => {
            if (measureMode) return;
            const feature = e.features[0];
            if (!feature) return;
            if (selectMode) {
                toggleTaskSelection(feature.properties.id);
                return;
            }
            openSidePanel(feature.properties);
        });

        map.on('mouseenter', layerId, (e) => {
            map.getCanvas().style.cursor = 'pointer';
            const feature = e.features[0];
            if (feature) showHoverPopup(e, feature.properties);
        });

        map.on('mousemove', layerId, (e) => {
            const feature = e.features[0];
            if (feature) {
                showHoverPopup(e, feature.properties);
                if (feature.id !== currentHoveredId) {
                    if (currentHoveredId !== null) {
                        try { map.setFeatureState({ source: getSourceForLayer(layerId), id: currentHoveredId }, { hover: false }); } catch(ex) {}
                    }
                    currentHoveredId = feature.id;
                    try { map.setFeatureState({ source: getSourceForLayer(layerId), id: currentHoveredId }, { hover: true }); } catch(ex) {}

                    if (layerId === 'spans-line') {
                        map.setFilter('spans-highlight', ['==', ['get', 'id'], feature.properties.id]);
                    }
                }
            }
        });

        map.on('mouseleave', layerId, () => {
            map.getCanvas().style.cursor = '';
            document.getElementById('map-hover-popup').classList.add('hidden');
            if (currentHoveredId !== null) {
                try { map.setFeatureState({ source: getSourceForLayer(layerId), id: currentHoveredId }, { hover: false }); } catch(ex) {}
                currentHoveredId = null;
            }
            if (layerId === 'spans-line') {
                map.setFilter('spans-highlight', ['==', ['get', 'id'], '']);
            }
        });
    });
}

function getSourceForLayer(layerId) {
    if (layerId.startsWith('spans')) return 'spans';
    if (layerId.startsWith('nodes')) return 'nodes';
    if (layerId.startsWith('drops')) return 'drops';
    if (layerId.startsWith('zones')) return 'zones';
    return 'spans';
}

function showHoverPopup(e, props) {
    const popup = document.getElementById('map-hover-popup');
    const planned = props.planned_qty ? formatNumber(props.planned_qty) + ' ' + (props.unit || '') : 'N/A';
    const actual = formatNumber(props.actual_qty || 0) + ' ' + (props.unit || '');
    const remaining = formatNumber(props.remaining_qty || 0) + ' ' + (props.unit || '');

    popup.innerHTML = `
        <strong>${esc(props.name)}</strong>
        <div class="hover-row"><span>Status:</span> <span class="status-dot" style="background:${props.status_color}"></span>${props.status.replace('_', ' ')}</div>
        <div class="hover-row"><span>Planned:</span> ${planned}</div>
        <div class="hover-row"><span>Completed:</span> ${actual}</div>
        <div class="hover-row"><span>Remaining:</span> ${remaining}</div>
        <div class="hover-progress"><div class="hover-progress-fill" style="width:${props.progress_pct || 0}%"></div></div>
    `;
    popup.classList.remove('hidden');

    const mapRect = document.getElementById('map').getBoundingClientRect();
    const x = e.point.x + 15;
    const y = e.point.y - 10;
    popup.style.left = (x + popup.offsetWidth > mapRect.width - 10) ? (x - popup.offsetWidth - 30) + 'px' : x + 'px';
    popup.style.top = y + 'px';
}

function openSidePanel(props) {
    const panel = document.getElementById('side-panel');
    document.getElementById('panel-title').textContent = props.name;

    const statusLabel = (props.status || '').replace(/_/g, ' ');
    const planned = props.planned_qty ? formatNumber(props.planned_qty) + ' ' + (props.unit || '') : 'N/A';
    const actual = formatNumber(props.actual_qty || 0) + ' ' + (props.unit || '');
    const remaining = formatNumber(props.remaining_qty || 0) + ' ' + (props.unit || '');

    let html = `
        <div class="panel-section">
            <div class="panel-status">
                <span class="status-badge status-${props.status}">${statusLabel}</span>
                <span class="panel-category">${esc(props.category || '')}</span>
            </div>
            <div class="panel-field"><label>Task Type</label><span>${esc(props.task_type || 'N/A')}</span></div>
            <div class="panel-field"><label>Planned</label><span>${planned}</span></div>
            <div class="panel-field"><label>Actual</label><span>${actual}</span></div>
            <div class="panel-field"><label>Remaining</label><span>${remaining}</span></div>
            <div class="panel-progress">
                <div class="progress-bar"><div class="progress-fill" style="width:${props.progress_pct || 0}%;background:${props.status_color}"></div></div>
                <span class="progress-label">${props.progress_pct || 0}% complete</span>
            </div>
        </div>
        ${props.description ? `<div class="panel-section"><label>Description</label><p class="panel-desc">${esc(props.description)}</p></div>` : ''}
        <div class="panel-section">
            <label>Timeline</label>
            <div class="panel-field"><label>Created</label><span>${props.created_at ? new Date(props.created_at).toLocaleDateString() : 'N/A'}</span></div>
            <div class="panel-field"><label>Updated</label><span>${props.updated_at ? new Date(props.updated_at).toLocaleDateString() : 'N/A'}</span></div>
        </div>
        <div class="panel-section" id="panel-inspections">
            <label>Inspections</label>
            <div class="panel-loading">Loading...</div>
        </div>
        <div class="panel-section" id="panel-field-entries">
            <label>Field Entry History</label>
            <div class="panel-loading">Loading...</div>
        </div>
        <div class="panel-section" id="panel-attachments">
            <label>Attachments</label>
            <div class="panel-loading">Loading...</div>
        </div>
        <div class="panel-section" id="panel-ai-analysis" style="display:none">
            <label>&#10024; AI Analysis</label>
            <div id="panel-ai-content" style="font-size:0.8rem;color:#CBD5E1"></div>
        </div>
        <div class="panel-actions">
            <button class="btn btn-primary btn-sm" onclick="showUpdateStatusFromPanel('${props.id}', '${props.status}')">Update Status</button>
            ${props.status === 'submitted' ? `<button class="btn btn-success btn-sm" onclick="showCreateInspection('${props.id}')">Create Inspection</button>` : ''}
            <button class="btn btn-sm btn-ghost" onclick="runTaskAIAnalysis('${props.id}')" title="AI anomaly detection">&#10024; Analyze</button>
        </div>
    `;

    document.getElementById('panel-content').innerHTML = html;
    panel.classList.remove('hidden');

    loadFieldEntries(props.id);
    loadAttachments(props.id);
    loadInspections(props.id);
}

async function loadFieldEntries(taskId) {
    const container = document.getElementById('panel-field-entries');
    try {
        const entries = await api(`/api/tasks/${taskId}/field-entries`);
        if (!entries.length) {
            container.innerHTML = '<label>Field Entry History</label><p class="panel-empty">No field entries yet</p>';
            return;
        }
        container.innerHTML = `
            <label>Field Entry History (${entries.length})</label>
            <div class="field-entries-list">
                ${entries.map(e => {
                    let deviationHtml = '';
                    if (e.deviation_flags) {
                        try {
                            const flags = JSON.parse(e.deviation_flags);
                            const details = e.deviation_details ? JSON.parse(e.deviation_details) : {};
                            deviationHtml = '<div class="fe-deviations">' + flags.map(f => {
                                if (f === 'gps_distance_exceeded') {
                                    return `<span class="deviation-badge deviation-warning" title="GPS distance exceeded">GPS ${details.gps_distance_ft || '?'}ft away</span>`;
                                } else if (f === 'qty_threshold_exceeded') {
                                    return `<span class="deviation-badge deviation-danger" title="Quantity threshold exceeded">Qty ${details.qty_pct_over || '?'}% over</span>`;
                                }
                                return `<span class="deviation-badge deviation-warning">${f}</span>`;
                            }).join('') + '</div>';
                        } catch(ex) {}
                    }
                    return `
                    <div class="field-entry-item">
                        <div class="fe-header">
                            <span class="fe-qty">${e.qty_delta ? (e.qty_delta > 0 ? '+' : '') + formatNumber(e.qty_delta) : '0'}</span>
                            <span class="fe-date">${new Date(e.created_at).toLocaleString()}</span>
                        </div>
                        ${deviationHtml}
                        ${e.labor_hours ? `<div class="fe-detail">Labor: ${e.labor_hours}h</div>` : ''}
                        ${e.notes ? `<div class="fe-notes">${esc(e.notes)}</div>` : ''}
                    </div>
                `}).join('')}
            </div>
        `;
    } catch {
        container.innerHTML = '<label>Field Entry History</label><p class="panel-empty">Failed to load</p>';
    }
}

async function loadAttachments(taskId) {
    const container = document.getElementById('panel-attachments');
    try {
        const headers = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const res = await fetch(`${API}/api/tasks/${taskId}/attachments`, { headers });
        if (!res.ok) throw new Error('Failed');
        const attachments = await res.json();

        let innerHtml = `<label>Attachments (${attachments.length})</label>`;
        innerHtml += `<button class="btn btn-sm attachment-upload-btn" onclick="triggerAttachmentUpload('${taskId}')">Upload Files</button>`;
        innerHtml += `<input type="file" id="attachment-file-input" multiple accept="image/jpeg,image/png,image/webp,application/pdf" style="display:none" onchange="handleAttachmentUpload('${taskId}')">`;

        if (attachments.length) {
            const images = attachments.filter(a => a.file_type && a.file_type.startsWith('image/'));
            const others = attachments.filter(a => !a.file_type || !a.file_type.startsWith('image/'));

            if (images.length) {
                innerHtml += '<div class="attachment-grid">';
                images.forEach(a => {
                    innerHtml += `
                        <div class="attachment-item">
                            <a href="${a.file_path}" target="_blank"><img class="attachment-thumb" src="${a.file_path}" alt="${esc(a.filename)}"></a>
                            <button class="btn btn-sm btn-danger attachment-delete-btn" onclick="deleteAttachment('${a.id}', '${taskId}')">&times;</button>
                        </div>`;
                });
                innerHtml += '</div>';
            }
            if (others.length) {
                others.forEach(a => {
                    const sizeKb = a.file_size ? Math.round(a.file_size / 1024) + ' KB' : '';
                    innerHtml += `
                        <div class="attachment-item attachment-file-item">
                            <a href="${a.file_path}" target="_blank">${esc(a.filename)}</a>
                            <span class="fe-date">${sizeKb}</span>
                            <button class="btn btn-sm btn-danger attachment-delete-btn" onclick="deleteAttachment('${a.id}', '${taskId}')">&times;</button>
                        </div>`;
                });
            }
        } else {
            innerHtml += '<p class="panel-empty">No attachments yet</p>';
        }
        container.innerHTML = innerHtml;
    } catch {
        container.innerHTML = '<label>Attachments</label><p class="panel-empty">Failed to load</p>';
    }
}

function triggerAttachmentUpload(taskId) {
    document.getElementById('attachment-file-input').click();
}

async function handleAttachmentUpload(taskId) {
    const input = document.getElementById('attachment-file-input');
    if (!input.files.length) return;

    const formData = new FormData();
    for (const file of input.files) {
        formData.append('files', file);
    }

    try {
        const headers = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const res = await fetch(`${API}/api/tasks/${taskId}/attachments`, {
            method: 'POST',
            headers,
            body: formData,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            alert(err.detail || 'Upload failed');
            return;
        }
        loadAttachments(taskId);
    } catch (err) {
        alert('Upload failed: ' + err.message);
    }
    input.value = '';
}

async function deleteAttachment(attachmentId, taskId) {
    if (!confirm('Delete this attachment?')) return;
    try {
        const headers = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const res = await fetch(`${API}/api/attachments/${attachmentId}`, {
            method: 'DELETE',
            headers,
        });
        if (!res.ok) throw new Error('Delete failed');
        loadAttachments(taskId);
    } catch (err) {
        alert('Delete failed: ' + err.message);
    }
}

function closeSidePanel() {
    document.getElementById('side-panel').classList.add('hidden');
}

function showUpdateStatusFromPanel(taskId, currentStatus) {
    showUpdateStatus(taskId, currentStatus);
}

async function loadMapData(useBbox = false) {
    const projectId = document.getElementById('map-project-select').value;
    if (!projectId || !map) return;

    const status = document.getElementById('map-status-filter').value;
    let url = `/api/projects/${projectId}/map-layer`;
    const params = [];
    if (status) params.push(`status=${status}`);
    if (useBbox && map.getZoom() > 10) {
        const bounds = map.getBounds();
        params.push(`bbox=${bounds.getWest()},${bounds.getSouth()},${bounds.getEast()},${bounds.getNorth()}`);
    }
    if (params.length) url += '?' + params.join('&');

    try {
        const geojson = await api(url);

        const spans = { type: 'FeatureCollection', features: [] };
        const nodes = { type: 'FeatureCollection', features: [] };
        const drops = { type: 'FeatureCollection', features: [] };
        const zones = { type: 'FeatureCollection', features: [] };

        geojson.features.forEach((f, i) => {
            f.id = i;
            const cat = f.properties.category;
            if (cat === 'span') spans.features.push(f);
            else if (cat === 'node') nodes.features.push(f);
            else if (cat === 'drop') drops.features.push(f);
            else if (cat === 'zone') zones.features.push(f);
            else {
                const gt = f.geometry.type;
                if (gt === 'LineString' || gt === 'MultiLineString') spans.features.push(f);
                else if (gt === 'Polygon' || gt === 'MultiPolygon') zones.features.push(f);
                else nodes.features.push(f);
            }
        });

        if (map.getSource('spans')) map.getSource('spans').setData(spans);
        if (map.getSource('nodes')) map.getSource('nodes').setData(nodes);
        if (map.getSource('drops')) map.getSource('drops').setData(drops);
        if (map.getSource('zones')) map.getSource('zones').setData(zones);

        if (!useBbox && geojson.features.length > 0) {
            const bbox = turf.bbox(geojson);
            map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], { padding: 60, maxZoom: 17 });
        }

        updateLegend(geojson.features);
        loadConflicts();
    } catch (err) {
        console.error('Map data error:', err);
    }
}

function updateLegend(features) {
    const statusCounts = {};
    const typeCounts = {};
    features.forEach(f => {
        const s = f.properties.status;
        statusCounts[s] = (statusCounts[s] || 0) + 1;
        const tt = f.properties.task_type;
        if (tt) typeCounts[tt] = { count: (typeCounts[tt]?.count || 0) + 1, color: f.properties.task_type_color };
    });

    let html = '<div class="legend-section"><strong>By Status</strong>';
    Object.entries(statusCounts).forEach(([s, count]) => {
        html += `<div class="legend-item"><div class="legend-dot" style="background:${STATUS_COLORS[s] || '#94A3B8'}"></div><span>${s.replace(/_/g, ' ')} (${count})</span></div>`;
    });
    html += '</div><div class="legend-section"><strong>By Type</strong>';
    Object.entries(typeCounts).forEach(([name, info]) => {
        html += `<div class="legend-item"><div class="legend-dot" style="background:${info.color}"></div><span>${name} (${info.count})</span></div>`;
    });
    html += '</div>';
    document.getElementById('map-legend').innerHTML = html;
}

function toggleLayer(layerGroup) {
    const checkbox = document.getElementById(`toggle-${layerGroup}`);
    const vis = checkbox.checked ? 'visible' : 'none';
    const layerMap = {
        spans: ['spans-casing', 'spans-line', 'spans-highlight', 'spans-label'],
        nodes: ['nodes-outer', 'nodes-circle', 'nodes-label'],
        drops: ['drops-circle', 'drops-label'],
        zones: ['zones-fill', 'zones-outline']
    };
    (layerMap[layerGroup] || []).forEach(id => {
        if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', vis);
    });
}

function toggleMeasure() {
    measureMode = !measureMode;
    const btn = document.getElementById('btn-measure');
    if (measureMode) {
        btn.classList.add('active');
        measurePoints = [];
        map.getCanvas().style.cursor = 'crosshair';
        map.on('click', onMeasureClick);
    } else {
        btn.classList.remove('active');
        map.getCanvas().style.cursor = '';
        map.off('click', onMeasureClick);
        clearMeasurement();
    }
}

function onMeasureClick(e) {
    measurePoints.push([e.lngLat.lng, e.lngLat.lat]);

    if (map.getSource('measure-points')) {
        map.getSource('measure-points').setData({
            type: 'FeatureCollection',
            features: measurePoints.map(p => ({
                type: 'Feature', geometry: { type: 'Point', coordinates: p }
            }))
        });
    } else {
        map.addSource('measure-points', {
            type: 'geojson',
            data: {
                type: 'FeatureCollection',
                features: measurePoints.map(p => ({
                    type: 'Feature', geometry: { type: 'Point', coordinates: p }
                }))
            }
        });
        map.addLayer({
            id: 'measure-points-layer',
            type: 'circle',
            source: 'measure-points',
            paint: { 'circle-radius': 5, 'circle-color': '#FF6B6B', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 }
        });
    }

    if (measurePoints.length >= 2) {
        const line = turf.lineString(measurePoints);
        if (map.getSource('measure-line')) {
            map.getSource('measure-line').setData(line);
        } else {
            map.addSource('measure-line', { type: 'geojson', data: line });
            map.addLayer({
                id: 'measure-line-layer',
                type: 'line',
                source: 'measure-line',
                paint: { 'line-color': '#FF6B6B', 'line-width': 2, 'line-dasharray': [3, 2] }
            });
        }

        const distKm = turf.length(line, { units: 'kilometers' });
        const distFt = distKm * 3280.84;
        let resultText = `Distance: ${formatNumber(distFt)} ft (${(distKm * 1000).toFixed(1)} m)`;

        if (measurePoints.length >= 3) {
            const poly = turf.polygon([[...measurePoints, measurePoints[0]]]);
            const areaSqM = turf.area(poly);
            const areaSqFt = areaSqM * 10.7639;
            resultText += ` | Area: ${formatNumber(areaSqFt)} sq ft`;
        }

        const el = document.getElementById('measurement-result');
        el.innerHTML = `${resultText} <button class="btn btn-sm btn-ghost" onclick="clearMeasurement()">Clear</button>`;
        el.classList.remove('hidden');
    }
}

function clearMeasurement() {
    measurePoints = [];
    if (map.getLayer('measure-points-layer')) map.removeLayer('measure-points-layer');
    if (map.getSource('measure-points')) map.removeSource('measure-points');
    if (map.getLayer('measure-line-layer')) map.removeLayer('measure-line-layer');
    if (map.getSource('measure-line')) map.removeSource('measure-line');
    document.getElementById('measurement-result').classList.add('hidden');
}

function locateMe() {
    if (!navigator.geolocation) { alert('Geolocation not supported'); return; }
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            const { longitude, latitude, accuracy } = pos.coords;
            map.flyTo({ center: [longitude, latitude], zoom: 16 });

            const el = document.createElement('div');
            el.className = 'locate-marker';
            new mapboxgl.Marker(el).setLngLat([longitude, latitude])
                .setPopup(new mapboxgl.Popup().setHTML(`<strong>Your Location</strong><br>Accuracy: ${Math.round(accuracy)}m`))
                .addTo(map);
        },
        (err) => { alert('Location error: ' + err.message); },
        { enableHighAccuracy: true }
    );
}

function onDrawUpdate(e) {
    const features = draw.getAll();
    if (features.features.length === 0) return;

    const lastFeature = features.features[features.features.length - 1];
    const geomType = lastFeature.geometry.type;

    let resultText = '';
    if (geomType === 'LineString') {
        const line = turf.lineString(lastFeature.geometry.coordinates);
        const distKm = turf.length(line, { units: 'kilometers' });
        resultText = `Drawn line: ${formatNumber(distKm * 3280.84)} ft (${(distKm * 1000).toFixed(1)} m)`;
    } else if (geomType === 'Polygon') {
        const areaSqM = turf.area(lastFeature);
        resultText = `Drawn area: ${formatNumber(areaSqM * 10.7639)} sq ft (${areaSqM.toFixed(1)} sq m)`;
    } else if (geomType === 'Point') {
        const [lng, lat] = lastFeature.geometry.coordinates;
        resultText = `Point: ${lat.toFixed(6)}, ${lng.toFixed(6)}`;
    }

    if (resultText) {
        const el = document.getElementById('measurement-result');
        el.innerHTML = `${resultText} <button class="btn btn-sm btn-ghost" onclick="draw.deleteAll(); document.getElementById('measurement-result').classList.add('hidden');">Clear</button>`;
        el.classList.remove('hidden');
    }
}

async function loadTasks() {
    const projectId = document.getElementById('task-project-select').value;
    if (!projectId) {
        document.getElementById('tasks-tbody').innerHTML = '<tr><td colspan="9" class="empty-state">Select a project</td></tr>';
        return;
    }
    try {
        const tasks = await api(`/api/projects/${projectId}/tasks`);
        document.getElementById('tasks-tbody').innerHTML = tasks.length
            ? tasks.map(t => {
                const pct = t.planned_qty ? Math.round(((t.actual_qty || 0) / t.planned_qty) * 100) : 0;
                return `
                    <tr>
                        <td><strong>${esc(t.name)}</strong></td>
                        <td><span class="type-dot" style="background:${t.task_type_color || '#ccc'}"></span>${esc(t.task_type_name || 'N/A')}</td>
                        <td><span class="status-badge status-${t.status}">${t.status.replace('_', ' ')}</span></td>
                        <td><span class="priority-badge ${t.priority || 'medium'}">${(t.priority || 'medium')}</span></td>
                        <td>${t.planned_qty != null ? formatNumber(t.planned_qty) + ' ' + (t.unit || '') : '-'}</td>
                        <td>${t.actual_qty != null ? formatNumber(t.actual_qty) + ' ' + (t.unit || '') : '-'}</td>
                        <td>
                            <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
                            <div class="progress-text"><span>${pct}%</span></div>
                        </td>
                        <td class="cost-cell ${t.total_cost ? 'has-cost' : ''}">$${(t.total_cost || 0).toLocaleString()}</td>
                        <td>
                            <button class="btn btn-sm btn-ghost" onclick="showUpdateStatus('${t.id}', '${t.status}')">Update</button>
                        </td>
                    </tr>
                `;
            }).join('')
            : '<tr><td colspan="9" class="empty-state">No tasks yet</td></tr>';
    } catch (err) {
        console.error('Tasks error:', err);
    }
}

async function loadTaskTypes() {
    try {
        const types = await api('/api/task-types');
        document.getElementById('task-types-list').innerHTML = types.length
            ? types.map(t => `
                <div class="task-type-card">
                    <div class="task-type-color" style="background:${t.color || '#ccc'}"></div>
                    <div class="task-type-info">
                        <h4>${esc(t.name)}</h4>
                        <p>Unit: ${esc(t.unit)} ${t.description ? '&mdash; ' + esc(t.description) : ''}</p>
                    </div>
                </div>
            `).join('')
            : '<div class="empty-state"><p>No task types defined</p></div>';
    } catch (err) {
        console.error('Task types error:', err);
    }
}

function showCreateProject() {
    openModal('New Project', `
        <form id="create-project-form">
            <div class="form-group">
                <label>Project Name</label>
                <input type="text" id="cp-name" required>
            </div>
            <div class="form-group">
                <label>Description</label>
                <textarea id="cp-desc" rows="3"></textarea>
            </div>
            <button type="submit" class="btn btn-primary btn-full">Create Project</button>
        </form>
    `);
    document.getElementById('create-project-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            const orgs = await api('/api/orgs');
            await api('/api/projects', {
                method: 'POST',
                body: JSON.stringify({
                    name: document.getElementById('cp-name').value,
                    description: document.getElementById('cp-desc').value,
                    executing_org_id: orgs[0]?.id || currentUser.org_id
                })
            });
            closeModal();
            loadProjects();
        } catch (err) { alert(err.message); }
    });
}

function showCreateTask() {
    const projectId = document.getElementById('task-project-select').value;
    if (!projectId) { alert('Select a project first'); return; }

    api('/api/task-types').then(types => {
        openModal('New Task', `
            <form id="create-task-form">
                <div class="form-group">
                    <label>Task Name</label>
                    <input type="text" id="ct-name" required>
                </div>
                <div class="form-group">
                    <label>Task Type</label>
                    <select id="ct-type">
                        <option value="">None</option>
                        ${types.map(t => `<option value="${t.id}" data-unit="${t.unit}">${t.name}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <label>Planned Quantity</label>
                    <input type="number" id="ct-qty" step="0.01">
                </div>
                <div class="form-group">
                    <label>Description</label>
                    <textarea id="ct-desc" rows="2"></textarea>
                </div>
                <button type="submit" class="btn btn-primary btn-full">Create Task</button>
            </form>
        `);
        document.getElementById('create-task-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const typeSelect = document.getElementById('ct-type');
            const unit = typeSelect.selectedOptions[0]?.dataset.unit || 'feet';
            try {
                await api('/api/tasks', {
                    method: 'POST',
                    body: JSON.stringify({
                        name: document.getElementById('ct-name').value,
                        description: document.getElementById('ct-desc').value,
                        project_id: projectId,
                        task_type_id: typeSelect.value || null,
                        planned_qty: parseFloat(document.getElementById('ct-qty').value) || null,
                        unit: unit
                    })
                });
                closeModal();
                loadTasks();
            } catch (err) { alert(err.message); }
        });
    });
}

function showCreateTaskType() {
    openModal('New Task Type', `
        <form id="create-tt-form">
            <div class="form-group">
                <label>Name</label>
                <input type="text" id="ctt-name" required>
            </div>
            <div class="form-group">
                <label>Unit</label>
                <select id="ctt-unit">
                    <option value="feet">Feet</option>
                    <option value="meters">Meters</option>
                    <option value="count">Count</option>
                    <option value="each">Each</option>
                </select>
            </div>
            <div class="form-group">
                <label>Color</label>
                <input type="color" id="ctt-color" value="#3B82F6">
            </div>
            <div class="form-group">
                <label>Description</label>
                <textarea id="ctt-desc" rows="2"></textarea>
            </div>
            <button type="submit" class="btn btn-primary btn-full">Create Task Type</button>
        </form>
    `);
    document.getElementById('create-tt-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            await api('/api/task-types', {
                method: 'POST',
                body: JSON.stringify({
                    name: document.getElementById('ctt-name').value,
                    description: document.getElementById('ctt-desc').value,
                    unit: document.getElementById('ctt-unit').value,
                    color: document.getElementById('ctt-color').value
                })
            });
            closeModal();
            loadTaskTypes();
        } catch (err) { alert(err.message); }
    });
}

function showUpdateStatus(taskId, currentStatus) {
    const statuses = ['not_started', 'in_progress', 'submitted', 'approved', 'billed', 'rework'];
    openModal('Update Task Status', `
        <form id="update-status-form">
            <div class="form-group">
                <label>Status</label>
                <select id="us-status">
                    ${statuses.map(s => `<option value="${s}" ${s === currentStatus ? 'selected' : ''}>${s.replace('_', ' ')}</option>`).join('')}
                </select>
            </div>
            <button type="submit" class="btn btn-primary btn-full">Update</button>
        </form>
    `);
    document.getElementById('update-status-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            await api(`/api/tasks/${taskId}`, {
                method: 'PUT',
                body: JSON.stringify({ status: document.getElementById('us-status').value })
            });
            closeModal();
            loadTasks();
            loadMapData();
        } catch (err) { alert(err.message); }
    });
}

function openModal(title, bodyHtml) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = bodyHtml;
    document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.add('hidden');
}

function formatNumber(n) {
    if (n == null) return '0';
    return Number(n).toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function esc(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

function showImportModal() {
    const projectId = document.getElementById('map-project-select').value;
    if (!projectId) { alert('Select a project first'); return; }

    openModal('Import Tasks', `
        <div class="form-group">
            <label>File (CSV, GeoJSON, KML, KMZ, Shapefile, or DXF)</label>
            <input type="file" id="import-file" accept=".csv,.geojson,.json,.kml,.kmz,.zip,.dxf" style="width:100%;padding:0.5rem;border:1px solid var(--border);border-radius:var(--radius);">
        </div>
        <div class="form-group" style="margin-top:0.5rem;">
            <a href="/api/tasks/import-template" class="btn btn-sm btn-ghost" style="text-decoration:none;">&#x1F4E5; Download CSV Template</a>
        </div>
        <div id="import-status" style="margin-top:1rem;display:none;"></div>
        <button class="btn btn-primary btn-full" style="margin-top:1rem;" onclick="doImport()">Import</button>
    `);
}

async function doImport() {
    const projectId = document.getElementById('map-project-select').value;
    if (!projectId) { alert('Select a project first'); return; }

    const fileInput = document.getElementById('import-file');
    if (!fileInput.files.length) { alert('Please select a file'); return; }

    const file = fileInput.files[0];
    const statusEl = document.getElementById('import-status');
    statusEl.style.display = 'block';
    statusEl.innerHTML = '<p style="color:var(--text-secondary);">Importing...</p>';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const headers = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const res = await fetch(`${API}/api/projects/${projectId}/tasks/import`, {
            method: 'POST',
            headers: headers,
            body: formData
        });
        if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Import failed');
        }
        const result = await res.json();

        let html = `<div style="padding:0.75rem;border-radius:var(--radius);background:#D1FAE5;color:#065F46;margin-bottom:0.5rem;">
            <strong>${result.imported}</strong> task${result.imported !== 1 ? 's' : ''} imported successfully.
        </div>`;

        if (result.errors && result.errors.length > 0) {
            html += `<div style="padding:0.75rem;border-radius:var(--radius);background:#FEE2E2;color:#991B1B;max-height:200px;overflow-y:auto;">
                <strong>${result.errors.length} error${result.errors.length !== 1 ? 's' : ''}:</strong>
                <ul style="margin:0.25rem 0 0 1rem;padding:0;font-size:0.8125rem;">
                    ${result.errors.map(e => `<li>Row ${e.row}: ${esc(e.message)}</li>`).join('')}
                </ul>
            </div>`;
        }

        statusEl.innerHTML = html;

        if (result.imported > 0) {
            loadMapData();
        }
    } catch (err) {
        statusEl.innerHTML = `<div style="padding:0.75rem;border-radius:var(--radius);background:#FEE2E2;color:#991B1B;">${esc(err.message)}</div>`;
    }
}

async function loadInspections(taskId) {
    const container = document.getElementById('panel-inspections');
    if (!container) return;
    try {
        const inspections = await api(`/api/tasks/${taskId}/inspections`);
        if (!inspections.length) {
            container.innerHTML = '<label>Inspections</label><p class="panel-empty">No inspections yet</p>';
            return;
        }
        container.innerHTML = `
            <label>Inspections (${inspections.length})</label>
            <div class="inspections-list">
                ${inspections.map(insp => {
                    let checklistHtml = '';
                    if (insp.checklist_items) {
                        try {
                            const items = JSON.parse(insp.checklist_items);
                            let results = [];
                            if (insp.checklist_results) {
                                try { results = JSON.parse(insp.checklist_results); } catch(ex) {}
                            }
                            checklistHtml = '<div class="insp-checklist">' + items.map((item, idx) => {
                                const result = results[idx] || {};
                                const checked = result.passed ? 'checked' : '';
                                const icon = result.passed === true ? '&#9745;' : result.passed === false ? '&#9746;' : '&#9744;';
                                return `<div class="insp-checklist-item">${icon} ${esc(item)}</div>`;
                            }).join('') + '</div>';
                        } catch(ex) {}
                    }
                    const statusClass = insp.status === 'passed' ? 'status-approved' : insp.status === 'failed' ? 'status-rework' : 'status-' + insp.status;
                    let actionBtns = '';
                    if (insp.status === 'pending' || insp.status === 'in_progress') {
                        actionBtns = `
                            <div class="insp-actions">
                                <button class="btn btn-success btn-sm" onclick="approveInspection('${insp.id}', '${taskId}')">Approve</button>
                                <button class="btn btn-danger btn-sm" onclick="rejectInspection('${insp.id}', '${taskId}')">Reject</button>
                            </div>
                        `;
                    }
                    return `
                        <div class="inspection-item">
                            <div class="insp-header">
                                <span class="status-badge ${statusClass}">${insp.status.replace('_', ' ')}</span>
                                <span class="insp-date">${new Date(insp.created_at).toLocaleString()}</span>
                            </div>
                            <div class="insp-detail">Inspector: ${esc(insp.inspector_name || 'N/A')}</div>
                            ${insp.template_name ? `<div class="insp-detail">Template: ${esc(insp.template_name)}</div>` : ''}
                            ${checklistHtml}
                            ${insp.comments ? `<div class="insp-comments">${esc(insp.comments)}</div>` : ''}
                            ${actionBtns}
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    } catch {
        container.innerHTML = '<label>Inspections</label><p class="panel-empty">Failed to load</p>';
    }
}

async function showCreateInspection(taskId) {
    try {
        const templates = await api('/api/inspection-templates');
        openModal('Create Inspection', `
            <form id="create-inspection-form">
                <div class="form-group">
                    <label>Inspection Template</label>
                    <select id="ci-template">
                        <option value="">None</option>
                        ${templates.map(t => `<option value="${t.id}">${esc(t.name)}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <label>Comments</label>
                    <textarea id="ci-comments" rows="3"></textarea>
                </div>
                <button type="submit" class="btn btn-primary btn-full">Create Inspection</button>
            </form>
        `);
        document.getElementById('create-inspection-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            try {
                await api(`/api/tasks/${taskId}/inspections`, {
                    method: 'POST',
                    body: JSON.stringify({
                        template_id: document.getElementById('ci-template').value || null,
                        comments: document.getElementById('ci-comments').value || null
                    })
                });
                closeModal();
                loadInspections(taskId);
            } catch (err) { alert(err.message); }
        });
    } catch (err) { alert(err.message); }
}

async function approveInspection(inspectionId, taskId) {
    if (!confirm('Approve this inspection? Task will be marked as approved.')) return;
    try {
        await api(`/api/inspections/${inspectionId}/approve`, { method: 'POST', body: '{}' });
        loadInspections(taskId);
        loadMapData();
    } catch (err) { alert(err.message); }
}

async function rejectInspection(inspectionId, taskId) {
    const reason = prompt('Rejection reason (optional):');
    try {
        await api(`/api/inspections/${inspectionId}/reject`, {
            method: 'POST',
            body: JSON.stringify({ comments: reason || null })
        });
        loadInspections(taskId);
        loadMapData();
    } catch (err) { alert(err.message); }
}

async function loadInspectionsPage() {
    const tbody = document.getElementById('inspections-tbody');
    if (!tbody) return;
    try {
        const inspections = await api('/api/inspections/pending');
        if (!inspections.length) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-secondary);padding:2rem;">No pending inspections</td></tr>';
            return;
        }
        tbody.innerHTML = inspections.map(insp => {
            const statusClass = insp.status === 'passed' ? 'status-approved' : insp.status === 'failed' ? 'status-rework' : 'status-' + insp.status;
            return `
                <tr>
                    <td>${esc(insp.task_id.substring(0, 8))}...</td>
                    <td>${esc(insp.template_name || 'N/A')}</td>
                    <td>${esc(insp.inspector_name || 'N/A')}</td>
                    <td><span class="status-badge ${statusClass}">${insp.status.replace('_', ' ')}</span></td>
                    <td>${new Date(insp.created_at).toLocaleDateString()}</td>
                    <td>
                        <button class="btn btn-success btn-sm" onclick="approveInspection('${insp.id}', '${insp.task_id}'); loadInspectionsPage();">Approve</button>
                        <button class="btn btn-danger btn-sm" onclick="rejectInspection('${insp.id}', '${insp.task_id}'); loadInspectionsPage();">Reject</button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--danger);padding:2rem;">Failed to load inspections</td></tr>';
    }
}

function toggleSelectMode() {
    selectMode = !selectMode;
    const btn = document.getElementById('btn-select');
    if (selectMode) {
        btn.classList.add('active');
        if (map) map.getCanvas().style.cursor = 'crosshair';
    } else {
        btn.classList.remove('active');
        if (map) map.getCanvas().style.cursor = '';
        clearSelection();
    }
}

function toggleTaskSelection(taskId) {
    if (selectedTaskIds.has(taskId)) {
        selectedTaskIds.delete(taskId);
    } else {
        selectedTaskIds.add(taskId);
    }
    updateBulkActionsBar();
    updateSelectionHighlight();
}

function updateBulkActionsBar() {
    const bar = document.getElementById('bulk-actions-bar');
    const count = document.getElementById('bulk-count');
    if (selectedTaskIds.size > 0) {
        bar.classList.remove('hidden');
        count.textContent = selectedTaskIds.size + ' task' + (selectedTaskIds.size !== 1 ? 's' : '') + ' selected';
    } else {
        bar.classList.add('hidden');
    }
}

function updateSelectionHighlight() {
    if (!map) return;
    const ids = Array.from(selectedTaskIds);
    const filter = ids.length > 0
        ? ['in', ['get', 'id'], ['literal', ids]]
        : ['==', ['get', 'id'], '__none__'];

    if (map.getLayer('spans-select-highlight')) {
        map.setFilter('spans-select-highlight', filter);
    } else {
        map.addLayer({
            id: 'spans-select-highlight',
            type: 'line',
            source: 'spans',
            filter: filter,
            paint: {
                'line-color': '#FFFFFF',
                'line-width': 8,
                'line-opacity': 0.5
            },
            layout: { 'line-cap': 'round', 'line-join': 'round' }
        }, 'spans-line');
    }

    if (map.getLayer('nodes-select-highlight')) {
        map.setFilter('nodes-select-highlight', filter);
    } else {
        map.addLayer({
            id: 'nodes-select-highlight',
            type: 'circle',
            source: 'nodes',
            filter: filter,
            paint: {
                'circle-radius': 12,
                'circle-color': 'transparent',
                'circle-stroke-color': '#FFFFFF',
                'circle-stroke-width': 3,
                'circle-opacity': 0.8
            }
        }, 'nodes-circle');
    }

    if (map.getLayer('drops-select-highlight')) {
        map.setFilter('drops-select-highlight', filter);
    } else {
        map.addLayer({
            id: 'drops-select-highlight',
            type: 'circle',
            source: 'drops',
            filter: filter,
            paint: {
                'circle-radius': 10,
                'circle-color': 'transparent',
                'circle-stroke-color': '#FFFFFF',
                'circle-stroke-width': 3,
                'circle-opacity': 0.8
            }
        }, 'drops-circle');
    }
}

async function applyBulkUpdate() {
    const projectId = document.getElementById('map-project-select').value;
    if (!projectId) { alert('Select a project first'); return; }
    if (selectedTaskIds.size === 0) { alert('No tasks selected'); return; }

    const status = document.getElementById('bulk-status-select').value;
    if (!status) { alert('Select a status to apply'); return; }

    try {
        const result = await api(`/api/projects/${projectId}/tasks/bulk-update`, {
            method: 'PUT',
            body: JSON.stringify({
                task_ids: Array.from(selectedTaskIds),
                status: status
            })
        });
        alert(`${result.updated} task(s) updated`);
        clearSelection();
        loadMapData();
    } catch (err) {
        alert('Bulk update failed: ' + err.message);
    }
}

function clearSelection() {
    selectedTaskIds.clear();
    updateBulkActionsBar();
    updateSelectionHighlight();
    document.getElementById('bulk-status-select').value = '';
}

async function loadReportsPage() {
    if (!projects.length) projects = await api('/api/projects');
    const sel = document.getElementById('report-project-select');
    if (sel) {
        sel.innerHTML = '<option value="">All Projects</option>' +
            projects.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('');
    }
    loadReports();
}

async function loadReports() {
    const projectId = document.getElementById('report-project-select')?.value || '';
    const pq = projectId ? `project_id=${projectId}` : '';

    try {
        const [statusData, typeData, prodData, crewData] = await Promise.all([
            api(`/api/reports/progress?${pq}${pq ? '&' : ''}group_by=status`),
            api(`/api/reports/progress?${pq}${pq ? '&' : ''}group_by=task_type`),
            api(`/api/reports/productivity?${pq}${pq ? '&' : ''}days=14`),
            api(`/api/reports/crew-performance${pq ? '?' + pq : ''}`)
        ]);

        renderBarChart('chart-progress-status', statusData, 'group', 'task_count', STATUS_COLORS);
        renderBarChart('chart-progress-type', typeData, 'group', 'task_count', null);
        renderProductivityChart('chart-productivity', prodData);
        renderCrewTable('table-crew', crewData);
    } catch (err) {
        console.error('Reports error:', err);
    }
}

function renderBarChart(containerId, data, labelKey, valueKey, colorMap) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!data || !data.length) {
        container.innerHTML = '<div class="report-empty">No data available</div>';
        return;
    }

    const maxVal = Math.max(...data.map(d => d[valueKey] || 0), 1);

    const defaultColors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4'];
    container.innerHTML = '<div class="report-bar-chart">' + data.map((d, i) => {
        const label = (d[labelKey] || 'Unknown').replace(/_/g, ' ');
        const val = d[valueKey] || 0;
        const pct = Math.round((val / maxVal) * 100);
        const color = (colorMap && colorMap[d[labelKey]]) || defaultColors[i % defaultColors.length];
        const completedPct = d.task_count > 0 ? Math.round((d.completed_count / d.task_count) * 100) : 0;
        return `
            <div class="report-bar-row">
                <div class="report-bar-label">${esc(label)}</div>
                <div class="report-bar-track">
                    <div class="report-bar-fill" style="width:${Math.max(pct, 2)}%;background:${color};">${val}</div>
                </div>
                <div class="report-bar-value">${completedPct}% done</div>
            </div>
        `;
    }).join('') + '</div>';
}

function renderProductivityChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!data || !data.length) {
        container.innerHTML = '<div class="report-empty">No productivity data yet</div>';
        return;
    }

    const maxQty = Math.max(...data.map(d => d.qty_completed || 0), 1);

    container.innerHTML = '<div class="report-productivity-chart">' + data.map(d => {
        const pct = Math.round(((d.qty_completed || 0) / maxQty) * 100);
        const dateLabel = d.date ? d.date.substring(5) : '';
        return `
            <div class="report-prod-bar">
                <div class="report-prod-bar-value">${formatNumber(d.qty_completed)}</div>
                <div class="report-prod-bar-fill" style="height:${Math.max(pct, 3)}%;"></div>
                <div class="report-prod-bar-label">${dateLabel}</div>
            </div>
        `;
    }).join('') + '</div>';
}

function renderCrewTable(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!data || !data.length) {
        container.innerHTML = '<div class="report-empty">No crew performance data yet</div>';
        return;
    }

    container.innerHTML = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>Crew Member</th>
                    <th>Total Qty</th>
                    <th>Total Hours</th>
                    <th>Entries</th>
                    <th>Avg Qty/Hour</th>
                </tr>
            </thead>
            <tbody>
                ${data.map(d => `
                    <tr>
                        <td>${esc(d.user_name)}</td>
                        <td>${formatNumber(d.total_qty)}</td>
                        <td>${formatNumber(d.total_hours)}</td>
                        <td>${d.entries_count}</td>
                        <td>${formatNumber(d.avg_qty_per_hour)}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function exportReport(reportType) {
    const projectId = document.getElementById('report-project-select')?.value || '';
    const qs = projectId ? `project_id=${projectId}&` : '';
    const url = `${API}/api/reports/export-csv?${qs}report_type=${reportType}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = `report_${reportType}.csv`;
    if (token) {
        fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
            .then(r => r.blob())
            .then(blob => {
                const blobUrl = URL.createObjectURL(blob);
                a.href = blobUrl;
                a.click();
                URL.revokeObjectURL(blobUrl);
            });
    } else {
        a.click();
    }
}

// ==================== ENTERPRISE FEATURES ====================

const state = {
    get token() { return token; },
    set token(v) { token = v; },
    get projects() { return projects; },
    set projects(v) { projects = v; }
};

async function apiFetch(path, options = {}) {
    const headers = options.headers || {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (!options.body || typeof options.body === 'string') {
        if (!headers['Content-Type'] && typeof options.body === 'string') headers['Content-Type'] = 'application/json';
    }
    const res = await fetch(API + path, { ...options, headers });
    if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
    return res;
}

// --- Budget & Cost Tracking ---
async function loadBudget() {
    const pid = document.getElementById('budget-project-select')?.value;
    if (!pid) return;
    try {
        const [budgetRes, costRes] = await Promise.all([
            apiFetch(`/api/projects/${pid}/budget`),
            apiFetch(`/api/projects/${pid}/cost-summary`)
        ]);
        const budget = await budgetRes.json();
        const cost = await costRes.json();
        renderBudgetOverview(budget, cost);
        renderCostBreakdowns(cost);
    } catch (e) { console.error('Budget error:', e); }
}

function renderBudgetOverview(budget, cost) {
    const el = document.getElementById('budget-overview');
    if (!el) return;
    const utilPct = budget.total_budget > 0 ? (cost.total_actual_cost / budget.total_budget * 100).toFixed(1) : 0;
    const barColor = utilPct > 90 ? '#EF4444' : utilPct > 70 ? '#F59E0B' : '#10B981';
    const varianceClass = cost.variance >= 0 ? 'positive' : 'negative';
    el.innerHTML = `
        <div class="budget-card">
            <div class="budget-label">Total Budget</div>
            <div class="budget-value">$${budget.total_budget.toLocaleString()}</div>
            <div class="budget-sub">${budget.currency}</div>
            <div class="budget-bar"><div class="budget-bar-fill" style="width:${Math.min(utilPct, 100)}%;background:${barColor}"></div></div>
            <div class="budget-sub" style="margin-top:4px">${utilPct}% utilized</div>
        </div>
        <div class="budget-card">
            <div class="budget-label">Spent to Date</div>
            <div class="budget-value">$${cost.total_actual_cost.toLocaleString()}</div>
            <div class="budget-sub">of $${budget.total_budget.toLocaleString()} budget</div>
        </div>
        <div class="budget-card ${varianceClass}">
            <div class="budget-label">Budget Remaining</div>
            <div class="budget-value">$${budget.remaining.toLocaleString()}</div>
            <div class="budget-sub">Contingency: ${budget.contingency_pct}%</div>
        </div>
        <div class="budget-card">
            <div class="budget-label">Planned Cost</div>
            <div class="budget-value">$${cost.total_planned_cost.toLocaleString()}</div>
            <div class="budget-sub">Across all tasks</div>
        </div>
        <div class="budget-card">
            <div class="budget-label">Labor Budget</div>
            <div class="budget-value">$${budget.labor_budget.toLocaleString()}</div>
        </div>
        <div class="budget-card">
            <div class="budget-label">Material Budget</div>
            <div class="budget-value">$${budget.material_budget.toLocaleString()}</div>
        </div>
    `;
}

function renderCostBreakdowns(cost) {
    const statusEl = document.getElementById('cost-by-status');
    const typeEl = document.getElementById('cost-by-type');
    if (statusEl && cost.by_status) {
        statusEl.innerHTML = '<table class="data-table"><thead><tr><th>Status</th><th>Tasks</th><th>Planned Cost</th><th>Actual Cost</th><th>Variance</th></tr></thead><tbody>' +
            cost.by_status.map(s => `<tr><td><span class="status-badge" style="background:${STATUS_COLORS[s.status] || '#94A3B8'}">${s.status.replace(/_/g,' ')}</span></td><td>${s.count}</td><td class="cost-cell has-cost">$${s.planned_cost.toLocaleString()}</td><td class="cost-cell has-cost">$${s.actual_cost.toLocaleString()}</td><td class="cost-cell ${s.planned_cost - s.actual_cost >= 0 ? 'has-cost' : ''}" style="color:${s.planned_cost - s.actual_cost >= 0 ? '#10B981' : '#EF4444'}">$${(s.planned_cost - s.actual_cost).toLocaleString()}</td></tr>`).join('') +
            '</tbody></table>';
    }
    if (typeEl && cost.by_type) {
        typeEl.innerHTML = '<table class="data-table"><thead><tr><th>Type</th><th>Tasks</th><th>Planned Cost</th><th>Actual Cost</th><th>Variance</th></tr></thead><tbody>' +
            cost.by_type.map(s => `<tr><td>${s.type}</td><td>${s.count}</td><td class="cost-cell has-cost">$${s.planned_cost.toLocaleString()}</td><td class="cost-cell has-cost">$${s.actual_cost.toLocaleString()}</td><td class="cost-cell" style="color:${s.planned_cost - s.actual_cost >= 0 ? '#10B981' : '#EF4444'}">$${(s.planned_cost - s.actual_cost).toLocaleString()}</td></tr>`).join('') +
            '</tbody></table>';
    }
}

// --- Materials & Inventory ---
async function loadMaterials() {
    try {
        const [matRes, lowRes] = await Promise.all([
            apiFetch('/api/materials'),
            apiFetch('/api/materials/low-stock')
        ]);
        const materials = await matRes.json();
        const lowStock = await lowRes.json();
        renderLowStockAlerts(lowStock);
        renderMaterialsTable(materials);
    } catch (e) { console.error('Materials error:', e); }
}

function renderLowStockAlerts(items) {
    const el = document.getElementById('low-stock-alerts');
    if (!el) return;
    if (!items.length) { el.innerHTML = ''; return; }
    el.innerHTML = items.map(m => `
        <div class="alert-banner">
            <span class="alert-icon">&#9888;</span>
            <span><strong>${m.name}</strong> (${m.sku || 'No SKU'}) - Stock: ${m.stock_qty} ${m.unit} (min: ${m.min_stock_qty})</span>
        </div>
    `).join('');
}

function renderMaterialsTable(materials) {
    const tbody = document.getElementById('materials-tbody');
    if (!tbody) return;
    tbody.innerHTML = materials.map(m => {
        const stockStatus = m.stock_qty <= m.min_stock_qty && m.min_stock_qty > 0 ? 'low' : m.stock_qty <= m.min_stock_qty * 1.5 && m.min_stock_qty > 0 ? 'warning' : 'ok';
        return `<tr>
            <td><strong>${m.name}</strong></td>
            <td>${m.sku || '-'}</td>
            <td>${m.category || '-'}</td>
            <td class="cost-cell ${m.unit_cost ? 'has-cost' : ''}">$${(m.unit_cost || 0).toFixed(2)}/${m.unit}</td>
            <td>${m.stock_qty.toLocaleString()} ${m.unit}</td>
            <td>${m.min_stock_qty.toLocaleString()}</td>
            <td><span class="stock-badge ${stockStatus}">${stockStatus === 'low' ? 'Low Stock' : stockStatus === 'warning' ? 'Warning' : 'OK'}</span></td>
            <td><button class="btn btn-sm btn-ghost" onclick="editMaterial('${m.id}')">Edit</button></td>
        </tr>`;
    }).join('');
}

function showCreateMaterial() {
    openModal('Add Material', `
        <form onsubmit="createMaterial(event)">
            <div class="form-group"><label>Name</label><input type="text" id="mat-name" required></div>
            <div class="form-group"><label>SKU</label><input type="text" id="mat-sku"></div>
            <div class="form-group"><label>Category</label>
                <select id="mat-category"><option value="fiber">Fiber</option><option value="conduit">Conduit</option><option value="hardware">Hardware</option><option value="tools">Tools</option><option value="other">Other</option></select>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
                <div class="form-group"><label>Unit</label><input type="text" id="mat-unit" value="each"></div>
                <div class="form-group"><label>Unit Cost ($)</label><input type="number" id="mat-cost" step="0.01"></div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
                <div class="form-group"><label>Stock Qty</label><input type="number" id="mat-stock" value="0"></div>
                <div class="form-group"><label>Min Stock</label><input type="number" id="mat-min" value="0"></div>
            </div>
            <div class="form-group"><label>Description</label><textarea id="mat-desc" rows="2"></textarea></div>
            <button type="submit" class="btn btn-primary btn-full">Add Material</button>
        </form>
    `);
}

async function createMaterial(e) {
    e.preventDefault();
    try {
        const res = await apiFetch('/api/materials', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name: document.getElementById('mat-name').value,
                sku: document.getElementById('mat-sku').value || null,
                category: document.getElementById('mat-category').value,
                unit: document.getElementById('mat-unit').value,
                unit_cost: parseFloat(document.getElementById('mat-cost').value) || null,
                stock_qty: parseFloat(document.getElementById('mat-stock').value) || 0,
                min_stock_qty: parseFloat(document.getElementById('mat-min').value) || 0,
                description: document.getElementById('mat-desc').value || null
            })
        });
        if (res.ok) { closeModal(); loadMaterials(); }
    } catch (e) { console.error(e); }
}

async function editMaterial(id) {
    const res = await apiFetch('/api/materials');
    const materials = await res.json();
    const m = materials.find(x => x.id === id);
    if (!m) return;
    openModal('Edit Material', `
        <form onsubmit="updateMaterial(event, '${id}')">
            <div class="form-group"><label>Name</label><input type="text" id="mat-name" value="${m.name}" required></div>
            <div class="form-group"><label>SKU</label><input type="text" id="mat-sku" value="${m.sku || ''}"></div>
            <div class="form-group"><label>Category</label>
                <select id="mat-category">${['fiber','conduit','hardware','tools','other'].map(c => `<option value="${c}" ${m.category === c ? 'selected' : ''}>${c}</option>`).join('')}</select>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
                <div class="form-group"><label>Unit</label><input type="text" id="mat-unit" value="${m.unit}"></div>
                <div class="form-group"><label>Unit Cost ($)</label><input type="number" id="mat-cost" step="0.01" value="${m.unit_cost || ''}"></div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
                <div class="form-group"><label>Stock Qty</label><input type="number" id="mat-stock" value="${m.stock_qty}"></div>
                <div class="form-group"><label>Min Stock</label><input type="number" id="mat-min" value="${m.min_stock_qty}"></div>
            </div>
            <div class="form-group"><label>Description</label><textarea id="mat-desc" rows="2">${m.description || ''}</textarea></div>
            <button type="submit" class="btn btn-primary btn-full">Update Material</button>
        </form>
    `);
}

async function updateMaterial(e, id) {
    e.preventDefault();
    try {
        const res = await apiFetch(`/api/materials/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name: document.getElementById('mat-name').value,
                sku: document.getElementById('mat-sku').value || null,
                category: document.getElementById('mat-category').value,
                unit: document.getElementById('mat-unit').value,
                unit_cost: parseFloat(document.getElementById('mat-cost').value) || null,
                stock_qty: parseFloat(document.getElementById('mat-stock').value) || 0,
                min_stock_qty: parseFloat(document.getElementById('mat-min').value) || 0,
                description: document.getElementById('mat-desc').value || null
            })
        });
        if (res.ok) { closeModal(); loadMaterials(); }
    } catch (e) { console.error(e); }
}

// --- Document Management ---
async function loadDocuments() {
    const pid = document.getElementById('doc-project-select')?.value;
    if (!pid) return;
    const cat = document.getElementById('doc-category-filter')?.value || '';
    const url = `/api/projects/${pid}/documents${cat ? '?category=' + cat : ''}`;
    try {
        const res = await apiFetch(url);
        const docs = await res.json();
        renderDocuments(docs);
    } catch (e) { console.error('Documents error:', e); }
}

function renderDocuments(docs) {
    const el = document.getElementById('documents-grid');
    if (!el) return;
    if (!docs.length) { el.innerHTML = '<div class="card" style="text-align:center;padding:2rem;color:#64748B">No documents uploaded yet</div>'; return; }
    const icons = { 'application/pdf': '&#128196;', 'image/': '&#128247;', 'text/': '&#128221;', 'default': '&#128193;' };
    el.innerHTML = docs.map(d => {
        const icon = d.file_type && d.file_type.startsWith('image/') ? icons['image/'] : d.file_type === 'application/pdf' ? icons['application/pdf'] : icons['default'];
        const size = d.file_size ? (d.file_size > 1048576 ? (d.file_size / 1048576).toFixed(1) + ' MB' : (d.file_size / 1024).toFixed(0) + ' KB') : '';
        return `<div class="doc-card">
            <div class="doc-icon">${icon}</div>
            <div class="doc-name" title="${d.name}">${d.name}</div>
            <div class="doc-meta">
                <span class="doc-badge version">v${d.current_version}</span>
                ${d.category ? `<span class="doc-badge category">${d.category}</span>` : ''}
                ${d.locked_by ? `<span class="doc-badge locked">&#128274; ${d.locker_name || 'Locked'}</span>` : ''}
            </div>
            <div class="doc-meta"><span>${size}</span><span>${d.uploader_name || ''}</span><span>${new Date(d.created_at).toLocaleDateString()}</span></div>
            <div class="doc-actions">
                <button class="btn btn-sm btn-primary" onclick="downloadDoc('${d.id}')">Download</button>
                <button class="btn btn-sm btn-ghost" onclick="showDocVersions('${d.id}','${d.name}')">Versions</button>
                <button class="btn btn-sm btn-ghost" onclick="uploadNewVersion('${d.id}')">New Version</button>
                ${!d.locked_by ? `<button class="btn btn-sm btn-ghost" onclick="lockDoc('${d.id}')">&#128274; Lock</button>` : `<button class="btn btn-sm btn-ghost" onclick="unlockDoc('${d.id}')">&#128275; Unlock</button>`}
            </div>
        </div>`;
    }).join('');
}

function showUploadDocument() {
    const pid = document.getElementById('doc-project-select')?.value;
    if (!pid) { alert('Select a project first'); return; }
    openModal('Upload Document', `
        <form onsubmit="uploadDocument(event)">
            <div class="form-group"><label>File</label><input type="file" id="doc-file" required></div>
            <div class="form-group"><label>Name (optional)</label><input type="text" id="doc-name" placeholder="Uses filename if blank"></div>
            <div class="form-group"><label>Description</label><textarea id="doc-desc" rows="2"></textarea></div>
            <div class="form-group"><label>Category</label>
                <select id="doc-cat"><option value="">None</option><option value="design">Design</option><option value="permit">Permit</option><option value="contract">Contract</option><option value="report">Report</option><option value="as-built">As-Built</option></select>
            </div>
            <button type="submit" class="btn btn-primary btn-full">Upload</button>
        </form>
    `);
}

async function uploadDocument(e) {
    e.preventDefault();
    const pid = document.getElementById('doc-project-select')?.value;
    const fd = new FormData();
    fd.append('file', document.getElementById('doc-file').files[0]);
    const name = document.getElementById('doc-name').value;
    if (name) fd.append('name', name);
    const desc = document.getElementById('doc-desc').value;
    if (desc) fd.append('description', desc);
    const cat = document.getElementById('doc-cat').value;
    if (cat) fd.append('category', cat);
    try {
        const res = await apiFetch(`/api/projects/${pid}/documents`, { method: 'POST', body: fd });
        if (res.ok) { closeModal(); loadDocuments(); }
    } catch (e) { console.error(e); }
}

async function downloadDoc(id) {
    window.open(`/api/documents/${id}/download?token=${state.token}`, '_blank');
}

async function showDocVersions(id, name) {
    const res = await apiFetch(`/api/documents/${id}/versions`);
    const versions = await res.json();
    openModal(`Versions: ${name}`, `
        <div class="saved-views-list">
            ${versions.map(v => `
                <div class="saved-view-item">
                    <div>
                        <div class="view-name">Version ${v.version_number}</div>
                        <div class="view-meta">${v.change_notes || 'No notes'} - ${v.uploader_name || ''} - ${new Date(v.created_at).toLocaleString()}</div>
                    </div>
                    <button class="btn btn-sm btn-ghost" onclick="window.open('/api/documents/${id}/download?version=${v.version_number}&token=${state.token}','_blank')">Download</button>
                </div>
            `).join('')}
        </div>
    `);
}

async function uploadNewVersion(id) {
    openModal('Upload New Version', `
        <form onsubmit="submitNewVersion(event, '${id}')">
            <div class="form-group"><label>File</label><input type="file" id="ver-file" required></div>
            <div class="form-group"><label>Change Notes</label><textarea id="ver-notes" rows="2" placeholder="What changed?"></textarea></div>
            <button type="submit" class="btn btn-primary btn-full">Upload Version</button>
        </form>
    `);
}

async function submitNewVersion(e, id) {
    e.preventDefault();
    const fd = new FormData();
    fd.append('file', document.getElementById('ver-file').files[0]);
    const notes = document.getElementById('ver-notes').value;
    if (notes) fd.append('change_notes', notes);
    const res = await apiFetch(`/api/documents/${id}/versions`, { method: 'POST', body: fd });
    if (res.ok) { closeModal(); loadDocuments(); }
}

async function lockDoc(id) {
    await apiFetch(`/api/documents/${id}/lock`, { method: 'POST' });
    loadDocuments();
}

async function unlockDoc(id) {
    await apiFetch(`/api/documents/${id}/unlock`, { method: 'POST' });
    loadDocuments();
}

// --- Activity Feed ---
async function loadActivities() {
    const pid = document.getElementById('activity-project-select')?.value;
    const type = document.getElementById('activity-type-filter')?.value || '';
    let url;
    if (pid) {
        url = `/api/projects/${pid}/activities?limit=50${type ? '&entity_type=' + type : ''}`;
    } else {
        url = '/api/activities/recent?limit=50';
    }
    try {
        const res = await apiFetch(url);
        const activities = await res.json();
        renderActivities(activities);
    } catch (e) { console.error('Activities error:', e); }
}

function renderActivities(activities) {
    const el = document.getElementById('activity-feed');
    if (!el) return;
    if (!activities.length) { el.innerHTML = '<div class="card" style="text-align:center;padding:2rem;color:#64748B">No activity yet</div>'; return; }
    const iconMap = { task: 'task', inspection: 'inspection', import: 'import', document: 'document', budget: 'budget' };
    const emojiMap = { task: '&#9744;', inspection: '&#9745;', import: '&#128229;', document: '&#128196;', budget: '&#36;' };
    el.innerHTML = activities.map(a => {
        const cls = iconMap[a.entity_type] || 'task';
        const emoji = emojiMap[a.entity_type] || '&#9679;';
        const timeAgo = getTimeAgo(new Date(a.created_at));
        return `<div class="activity-item">
            <div class="activity-icon ${cls}">${emoji}</div>
            <div class="activity-body">
                <div class="activity-text"><strong>${a.user_name || 'System'}</strong> ${formatAction(a.action)} <strong>${a.entity_name || ''}</strong></div>
                <div class="activity-meta">${timeAgo}${a.details ? ' - ' + a.details : ''}</div>
            </div>
        </div>`;
    }).join('');
}

function formatAction(action) {
    const map = {
        'task_created': 'created task', 'status_changed': 'changed status of',
        'import_completed': 'imported data into', 'inspection_created': 'created inspection for',
        'inspection_approved': 'approved inspection for', 'inspection_rejected': 'rejected inspection for',
        'document_uploaded': 'uploaded document', 'document_version_uploaded': 'uploaded new version of',
        'budget_updated': 'updated budget', 'field_entry_created': 'added field entry for'
    };
    return map[action] || action.replace(/_/g, ' ');
}

function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
    if (seconds < 86400) return Math.floor(seconds / 3600) + 'h ago';
    if (seconds < 604800) return Math.floor(seconds / 86400) + 'd ago';
    return date.toLocaleDateString();
}

// --- Saved Map Views ---
async function showSaveViewModal() {
    const pid = document.getElementById('map-project-select')?.value;
    if (!pid) { alert('Select a project first'); return; }
    const res = await apiFetch(`/api/projects/${pid}/map-views`);
    const views = await res.json();
    openModal('Map Views', `
        <div class="saved-views-list">
            ${views.map(v => `
                <div class="saved-view-item" onclick="restoreMapView(${v.center_lng}, ${v.center_lat}, ${v.zoom}, ${v.bearing}, ${v.pitch})">
                    <div>
                        <div class="view-name">${v.name} ${v.is_default ? '&#9733;' : ''}</div>
                        <div class="view-meta">Zoom ${v.zoom.toFixed(1)} - ${new Date(v.created_at).toLocaleDateString()}</div>
                    </div>
                    <button class="btn btn-sm btn-ghost" onclick="event.stopPropagation();deleteMapView('${v.id}')">&#128465;</button>
                </div>
            `).join('') || '<div style="text-align:center;color:#64748B;padding:1rem">No saved views</div>'}
        </div>
        <hr style="border-color:#334155;margin:1rem 0">
        <form onsubmit="saveCurrentView(event)">
            <div class="form-group"><label>Save Current View</label><input type="text" id="view-name" placeholder="View name" required></div>
            <label style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem;color:#94A3B8;font-size:0.85rem"><input type="checkbox" id="view-default"> Set as default</label>
            <button type="submit" class="btn btn-primary btn-full">Save View</button>
        </form>
    `);
}

async function saveCurrentView(e) {
    e.preventDefault();
    const pid = document.getElementById('map-project-select')?.value;
    if (!pid || !window.map) return;
    const center = window.map.getCenter();
    const data = {
        name: document.getElementById('view-name').value,
        center_lng: center.lng,
        center_lat: center.lat,
        zoom: window.map.getZoom(),
        bearing: window.map.getBearing(),
        pitch: window.map.getPitch(),
        is_default: document.getElementById('view-default').checked
    };
    const res = await apiFetch(`/api/projects/${pid}/map-views`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (res.ok) { closeModal(); }
}

function restoreMapView(lng, lat, zoom, bearing, pitch) {
    if (window.map) {
        window.map.flyTo({ center: [lng, lat], zoom, bearing, pitch, duration: 1500 });
        closeModal();
    }
}

async function deleteMapView(id) {
    if (!confirm('Delete this view?')) return;
    await apiFetch(`/api/map-views/${id}`, { method: 'DELETE' });
    showSaveViewModal();
}

// --- Import History (in import modal) ---
async function loadImportHistory() {
    const pid = document.getElementById('map-project-select')?.value;
    if (!pid) return '';
    try {
        const res = await apiFetch(`/api/projects/${pid}/import-history`);
        const batches = await res.json();
        if (!batches.length) return '';
        return `<div class="import-history-list">${batches.slice(0, 10).map(b => `
            <div class="import-item">
                <div><span class="import-file">${b.filename}</span></div>
                <div><span class="import-format">${b.file_format}</span> <span class="import-stats">${b.imported_count} imported, ${b.error_count} errors</span></div>
            </div>
        `).join('')}</div>`;
    } catch { return ''; }
}

// --- Enhanced page loading ---
const origShowPage = typeof showPage === 'function' ? showPage : null;

function populateEnterpriseSelects() {
    const selects = ['budget-project-select', 'doc-project-select', 'activity-project-select', 'integrations-project-select'];
    selects.forEach(selId => {
        const sel = document.getElementById(selId);
        if (!sel || !state.projects) return;
        const val = sel.value;
        const opts = '<option value="">Select Project</option>' + state.projects.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
        sel.innerHTML = opts;
        if (val) sel.value = val;
        else if (state.projects.length === 1) {
            sel.value = state.projects[0].id;
        }
    });
}

const origNavHandler = document.querySelector('[data-page]')?.onclick;
document.addEventListener('click', (e) => {
    const link = e.target.closest('[data-page]');
    if (!link) return;
    const page = link.dataset.page;
    setTimeout(() => {
        populateEnterpriseSelects();
        if (page === 'budget') loadBudget();
        if (page === 'materials') loadMaterials();
        if (page === 'documents') loadDocuments();
        if (page === 'activity') loadActivities();
        if (page === 'integrations') loadIntegrations();
    }, 100);
});

// ==================== ENTERPRISE KPI & ANALYSIS ====================

async function loadDashboardKPIs() {
    if (!projects || !projects.length) return;
    const pid = projects[0].id;
    try {
        const [kpiRes, routeRes] = await Promise.all([
            apiFetch(`/api/projects/${pid}/kpis`),
            apiFetch(`/api/projects/${pid}/route-stats`)
        ]);
        const kpis = await kpiRes.json();
        const route = await routeRes.json();
        renderDashboardKPIs(kpis, route);
    } catch (e) { console.error('KPI error:', e); }
}

function renderDashboardKPIs(kpis, route) {
    const grid = document.getElementById('stats-grid');
    if (!grid) return;
    
    const healthColors = { good: '#10B981', at_risk: '#F59E0B', critical: '#EF4444' };
    const healthLabels = { good: 'Healthy', at_risk: 'At Risk', critical: 'Critical' };
    const healthColor = healthColors[kpis.health_status] || '#94A3B8';
    
    grid.innerHTML = `
        <div class="kpi-widget" style="border-left: 3px solid ${healthColor}">
            <div class="kpi-value" style="color:${healthColor}">${healthLabels[kpis.health_status] || kpis.health_status}</div>
            <div class="kpi-label">Project Health</div>
        </div>
        <div class="kpi-widget">
            <div class="kpi-value">${kpis.completion_pct}%</div>
            <div class="kpi-label">Task Completion</div>
            <div class="kpi-trend neutral">${kpis.completed_tasks}/${kpis.total_tasks} tasks</div>
        </div>
        <div class="kpi-widget">
            <div class="kpi-value">${kpis.qty_progress_pct}%</div>
            <div class="kpi-label">Quantity Progress</div>
            <div class="kpi-trend neutral">${kpis.actual_qty.toLocaleString()} of ${kpis.planned_qty.toLocaleString()}</div>
        </div>
        <div class="kpi-widget">
            <div class="kpi-value">${kpis.spi.toFixed(2)}</div>
            <div class="kpi-label">Schedule Performance (SPI)</div>
            <div class="kpi-trend ${kpis.spi >= 1 ? 'up' : kpis.spi >= 0.8 ? 'neutral' : 'down'}">${kpis.spi >= 1 ? 'On Schedule' : kpis.spi >= 0.8 ? 'Slightly Behind' : 'Behind Schedule'}</div>
        </div>
        <div class="kpi-widget">
            <div class="kpi-value">${kpis.cpi.toFixed(2)}</div>
            <div class="kpi-label">Cost Performance (CPI)</div>
            <div class="kpi-trend ${kpis.cpi >= 1 ? 'up' : kpis.cpi >= 0.9 ? 'neutral' : 'down'}">${kpis.cpi >= 1 ? 'Under Budget' : kpis.cpi >= 0.9 ? 'Near Budget' : 'Over Budget'}</div>
        </div>
        <div class="kpi-widget">
            <div class="kpi-value">$${(kpis.budget_spent / 1000).toFixed(1)}k</div>
            <div class="kpi-label">Budget Spent</div>
            <div class="kpi-trend neutral">of $${(kpis.budget_total / 1000).toFixed(1)}k total</div>
        </div>
        <div class="kpi-widget">
            <div class="kpi-value">${route.total_fiber_length_miles.toFixed(1)} mi</div>
            <div class="kpi-label">Total Fiber Length</div>
            <div class="kpi-trend neutral">${route.total_fiber_length_feet.toLocaleString()} ft</div>
        </div>
        <div class="kpi-widget">
            <div class="kpi-value">${kpis.rework_tasks}</div>
            <div class="kpi-label">Tasks in Rework</div>
            <div class="kpi-trend ${kpis.rework_tasks > 0 ? 'down' : 'up'}">${kpis.rework_tasks > 0 ? 'Needs Attention' : 'All Clear'}</div>
        </div>
    `;
}

// Conflict detection
async function loadConflicts() {
    const pid = document.getElementById('map-project-select')?.value;
    if (!pid) return;
    try {
        const res = await apiFetch(`/api/projects/${pid}/conflicts`);
        const data = await res.json();
        if (data.total_conflicts > 0) {
            showConflictAlerts(data);
        }
    } catch (e) { console.error('Conflicts error:', e); }
}

function showConflictAlerts(data) {
    let alertEl = document.getElementById('conflict-alerts');
    if (!alertEl) {
        alertEl = document.createElement('div');
        alertEl.id = 'conflict-alerts';
        alertEl.style.cssText = 'position:absolute;top:50px;right:10px;z-index:10;max-width:320px;';
        document.querySelector('.map-wrapper')?.appendChild(alertEl);
    }
    
    alertEl.innerHTML = `
        <div style="background:#1E293B;border:1px solid #F59E0B;border-radius:8px;padding:0.75rem;box-shadow:0 4px 12px rgba(0,0,0,0.3);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
                <span style="color:#F59E0B;font-weight:600;font-size:0.85rem;">&#9888; ${data.total_conflicts} Conflicts Detected</span>
                <button onclick="document.getElementById('conflict-alerts').remove()" style="background:none;border:none;color:#94A3B8;cursor:pointer;font-size:1rem;">&times;</button>
            </div>
            <div style="font-size:0.75rem;color:#94A3B8;margin-bottom:0.5rem;">
                ${data.crossings} crossings, ${data.proximities} proximity, ${data.overlaps} overlaps
            </div>
            <div style="max-height:200px;overflow-y:auto;">
                ${data.conflicts.slice(0, 5).map(c => `
                    <div style="padding:0.4rem 0;border-top:1px solid #334155;font-size:0.75rem;color:#CBD5E1;">
                        <span style="color:${c.severity === 'warning' ? '#F59E0B' : '#60A5FA'}">&#9679;</span>
                        ${c.message}
                    </div>
                `).join('')}
                ${data.total_conflicts > 5 ? `<div style="padding:0.4rem 0;font-size:0.75rem;color:#64748B;text-align:center;">+${data.total_conflicts - 5} more conflicts</div>` : ''}
            </div>
        </div>
    `;
}

// ==================== AI FEATURES ====================

let aiInsightsCache = null;
let aiInsightsLoading = false;

async function loadAIInsights() {
    if (aiInsightsLoading) return;
    if (!projects || !projects.length) return;
    const pid = projects[0].id;
    const panel = document.getElementById('ai-insights-panel');
    if (!panel) return;
    
    aiInsightsLoading = true;
    const btn = document.getElementById('ai-refresh-btn');
    if (btn) btn.textContent = 'Analyzing...';
    panel.style.display = 'block';
    document.getElementById('ai-summary').textContent = 'AI is analyzing your project data...';
    
    try {
        const res = await apiFetch(`/api/ai/projects/${pid}/insights`);
        const data = await res.json();
        const insights = data.insights;
        aiInsightsCache = insights;
        
        document.getElementById('ai-summary').textContent = insights.summary || '';
        
        const risksEl = document.getElementById('ai-risks');
        if (risksEl) risksEl.innerHTML = (insights.risks || []).map(r => `<li style="padding:0.25rem 0;border-bottom:1px solid #1E293B">&#8226; ${r}</li>`).join('') || '<li style="color:#64748B">No risks identified</li>';
        
        const recsEl = document.getElementById('ai-recommendations');
        if (recsEl) recsEl.innerHTML = (insights.recommendations || []).map(r => `<li style="padding:0.25rem 0;border-bottom:1px solid #1E293B">&#8226; ${r}</li>`).join('') || '<li style="color:#64748B">No recommendations</li>';
        
        const highEl = document.getElementById('ai-highlights');
        if (highEl) highEl.innerHTML = (insights.highlights || []).map(r => `<li style="padding:0.25rem 0;border-bottom:1px solid #1E293B">&#8226; ${r}</li>`).join('') || '<li style="color:#64748B">No highlights</li>';
    } catch (e) {
        document.getElementById('ai-summary').textContent = 'Could not load AI insights at this time.';
        console.error('AI insights error:', e);
    }
    aiInsightsLoading = false;
    if (btn) btn.textContent = 'Refresh';
}

function refreshAIInsights() {
    aiInsightsCache = null;
    loadAIInsights();
}

async function loadDailyBriefing() {
    if (!projects || !projects.length) return;
    const pid = projects[0].id;
    const panel = document.getElementById('ai-briefing-panel');
    if (!panel) return;
    
    try {
        const res = await apiFetch(`/api/ai/projects/${pid}/briefing`);
        const data = await res.json();
        panel.style.display = 'block';
        document.getElementById('ai-briefing-text').textContent = data.briefing || '';
    } catch (e) {
        console.error('Briefing error:', e);
    }
}

async function loadReportAISummary() {
    const panel = document.getElementById('report-ai-summary');
    const textEl = document.getElementById('report-ai-text');
    if (!panel || !textEl) return;
    
    panel.style.display = 'block';
    textEl.textContent = 'Generating AI analysis...';
    
    const pid = projects && projects.length ? projects[0].id : '';
    try {
        const res = await apiFetch(`/api/ai/reports/summary?report_type=progress&project_id=${pid}`);
        const data = await res.json();
        textEl.textContent = data.summary || 'No summary available';
    } catch (e) {
        textEl.textContent = 'Could not generate summary at this time.';
    }
}

async function loadTaskAnomalies(taskId) {
    try {
        const res = await apiFetch(`/api/ai/tasks/${taskId}/anomalies`);
        const data = await res.json();
        if (data.anomalies && data.anomalies.length > 0) {
            return data.anomalies;
        }
    } catch (e) {
        console.error('Anomaly detection error:', e);
    }
    return [];
}

async function loadTaskRecommendations() {
    if (!projects || !projects.length) return;
    const pid = projects[0].id;
    try {
        const res = await apiFetch(`/api/ai/projects/${pid}/recommendations`);
        const data = await res.json();
        if (data.recommendations && data.recommendations.length > 0) {
            showTaskRecommendations(data.recommendations);
        }
    } catch (e) {
        console.error('Recommendations error:', e);
    }
}

function showTaskRecommendations(recs) {
    let el = document.getElementById('ai-task-recs');
    if (!el) {
        el = document.createElement('div');
        el.id = 'ai-task-recs';
        el.className = 'card mt-4';
        const tasksPage = document.getElementById('page-tasks');
        if (tasksPage) {
            const table = tasksPage.querySelector('.card');
            if (table) tasksPage.insertBefore(el, table);
        }
    }
    
    const urgencyColors = { high: '#EF4444', medium: '#F59E0B', low: '#94A3B8' };
    el.innerHTML = `
        <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem">
            <span style="font-size:1.1rem">&#10024;</span>
            <h3 style="margin:0;font-size:0.95rem">AI Recommendations</h3>
            <button class="btn btn-sm btn-ghost" onclick="document.getElementById('ai-task-recs').style.display='none'" style="margin-left:auto">&times;</button>
        </div>
        ${recs.map(r => `
            <div style="display:flex;align-items:start;gap:0.75rem;padding:0.5rem 0;border-top:1px solid #1E293B">
                <span style="width:8px;height:8px;border-radius:50%;background:${urgencyColors[r.urgency] || '#94A3B8'};margin-top:6px;flex-shrink:0"></span>
                <div>
                    <div style="color:#E2E8F0;font-size:0.85rem"><strong>${r.task_name || ''}</strong>: ${r.action || ''}</div>
                    <div style="color:#64748B;font-size:0.75rem;margin-top:2px">${r.reason || ''}</div>
                </div>
            </div>
        `).join('')}
    `;
}

async function runTaskAIAnalysis(taskId) {
    const section = document.getElementById('panel-ai-analysis');
    const content = document.getElementById('panel-ai-content');
    if (!section || !content) return;
    
    section.style.display = 'block';
    content.innerHTML = '<div style="color:#8B5CF6">Analyzing field data...</div>';
    
    const anomalies = await loadTaskAnomalies(taskId);
    
    if (anomalies.length === 0) {
        content.innerHTML = '<div style="color:#10B981">&#9745; No anomalies detected - data looks consistent</div>';
    } else {
        const severityColors = { critical: '#EF4444', warning: '#F59E0B', info: '#3B82F6' };
        content.innerHTML = anomalies.map(a => `
            <div style="padding:0.4rem 0;border-bottom:1px solid #1E293B;display:flex;align-items:start;gap:0.5rem">
                <span style="color:${severityColors[a.severity] || '#94A3B8'}">&#9679;</span>
                <span>${a.issue || ''}</span>
            </div>
        `).join('');
    }
}

function switchBasemap(styleId) {
    if (!map) return;
    const currentSources = {};
    const currentData = {};
    ['spans', 'nodes', 'drops', 'zones'].forEach(s => {
        const src = map.getSource(s);
        if (src && src._data) currentData[s] = src._data;
    });

    map.setStyle('mapbox://styles/mapbox/' + styleId);
    map.once('style.load', () => {
        addMapSources();
        addMapLayers();
        setupMapInteractions();
        ['spans', 'nodes', 'drops', 'zones'].forEach(s => {
            if (currentData[s] && map.getSource(s)) {
                map.getSource(s).setData(currentData[s]);
            }
        });
    });
}

function toggleLayerPanel() {
    const panel = document.getElementById('layer-panel');
    panel.classList.toggle('hidden');
}

function setLayerOpacity(layerGroup, val) {
    const opacity = parseInt(val) / 100;
    const opacityMap = {
        spans: [{ id: 'spans-line', prop: 'line-opacity' }, { id: 'spans-casing', prop: 'line-opacity' }],
        nodes: [{ id: 'nodes-circle', prop: 'circle-opacity' }],
        drops: [{ id: 'drops-circle', prop: 'circle-opacity' }],
        zones: [{ id: 'zones-fill', prop: 'fill-opacity' }, { id: 'zones-outline', prop: 'line-opacity' }]
    };
    (opacityMap[layerGroup] || []).forEach(l => {
        if (map.getLayer(l.id)) map.setPaintProperty(l.id, l.prop, opacity);
    });
}

function setLineWidth(val) {
    const width = parseInt(val);
    if (map.getLayer('spans-line')) {
        map.setPaintProperty('spans-line', 'line-width', [
            'case',
            ['boolean', ['feature-state', 'hover'], false],
            width * 1.5,
            width
        ]);
    }
    if (map.getLayer('spans-casing')) {
        map.setPaintProperty('spans-casing', 'line-width', [
            'case',
            ['boolean', ['feature-state', 'hover'], false],
            width * 1.5 + 3,
            width + 2
        ]);
    }
}

function toggleLabels(show) {
    const labelLayers = ['spans-label', 'nodes-label', 'drops-label'];
    labelLayers.forEach(id => {
        if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', show ? 'visible' : 'none');
    });
}

async function loadIntegrations() {
    const select = document.getElementById('integrations-project-select');
    if (select && select.options.length <= 1) {
        projects.forEach(p => {
            const o = document.createElement('option');
            o.value = p.id; o.textContent = p.name;
            select.appendChild(o);
        });
        if (projects.length === 1) select.value = projects[0].id;
    }

    try {
        const resp = await api('/api/integrations/platforms');
        const platforms = resp.platforms || resp;
        const grid = document.getElementById('integrations-grid');
        grid.innerHTML = platforms.map(p => `
            <div class="integration-card">
                <div class="integration-header">
                    <span class="integration-icon">${p.logo_icon}</span>
                    <div>
                        <h4 class="integration-name">${p.name}</h4>
                        <span class="badge" style="background:#1E3A5F;color:#60A5FA">${p.status}</span>
                    </div>
                </div>
                <p class="integration-desc">${p.description}</p>
                <div class="integration-features">
                    ${p.features.map(f => `<span class="integration-feature">${f}</span>`).join('')}
                </div>
                <div class="integration-formats">
                    <span style="color:#64748B;font-size:0.75rem">Export formats:</span>
                    ${p.export_formats.map(f => `<span class="integration-format-badge">${f.toUpperCase()}</span>`).join('')}
                </div>
                <div class="integration-actions">
                    <button class="btn btn-primary btn-sm" onclick="exportToIntegration('${p.id}')">Export Data</button>
                    <button class="btn btn-sm" onclick="showIntegrationConfig('${p.id}')">Configure</button>
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Failed to load integrations:', err);
    }
}

async function exportToIntegration(platformId) {
    const projectId = document.getElementById('integrations-project-select').value;
    if (!projectId) { alert('Please select a project first'); return; }

    try {
        const resp = await fetch(`/api/integrations/${platformId}/export?project_id=${projectId}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        const contentType = resp.headers.get('content-type') || '';
        const disposition = resp.headers.get('content-disposition') || '';

        let filename = `${platformId}_export`;
        const match = disposition.match(/filename="?([^"]+)"?/);
        if (match) filename = match[1];
        else if (contentType.includes('xml') || contentType.includes('kml')) filename += '.kml';
        else filename += '.json';

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    } catch (err) {
        console.error('Export failed:', err);
        alert('Export failed: ' + err.message);
    }
}

async function showIntegrationConfig(platformId) {
    try {
        const config = await api(`/api/integrations/${platformId}/config`);
        const modal = document.getElementById('modal-overlay');
        document.getElementById('modal-title').textContent = config.platform + ' Configuration';
        document.getElementById('modal-body').innerHTML = `
            <div style="margin-bottom:1rem">
                <p style="color:var(--text-secondary);font-size:0.875rem;margin-bottom:1rem">${config.instructions}</p>
                ${config.fields.map(f => `
                    <div class="form-group">
                        <label>${f.label}</label>
                        <input class="form-control" type="${f.type === 'password' ? 'password' : 'text'}" placeholder="${f.placeholder || ''}" value="${f.default || ''}">
                        ${f.description ? `<small style="color:var(--text-secondary)">${f.description}</small>` : ''}
                    </div>
                `).join('')}
                ${config.documentation_url ? `<a href="${config.documentation_url}" target="_blank" class="btn btn-sm" style="margin-top:0.5rem">View Documentation</a>` : ''}
            </div>
            <button class="btn btn-primary" onclick="closeModal()">Save Configuration</button>
        `;
        modal.classList.remove('hidden');
    } catch (err) {
        console.error('Config load failed:', err);
    }
}

// ==================== ADMIN PANEL ====================

async function loadAdminPanel() {
    try {
        const [users, stats, roles] = await Promise.all([
            api('/api/admin/users'),
            api('/api/admin/stats'),
            api('/api/admin/roles')
        ]);
        window._adminUsers = users;
        window._adminRoles = roles;

        const statsEl = document.getElementById('admin-stats');
        statsEl.innerHTML = `
            <div class="stat-card"><div class="stat-value">${stats.total_users}</div><div class="stat-label">Total Users</div></div>
            <div class="stat-card"><div class="stat-value">${stats.active_users}</div><div class="stat-label">Active Users</div></div>
            <div class="stat-card"><div class="stat-value">${stats.recent_signups || 0}</div><div class="stat-label">New (30d)</div></div>
            <div class="stat-card"><div class="stat-value">${Object.keys(stats.users_by_role || stats.by_role || {}).length}</div><div class="stat-label">Roles Used</div></div>
        `;

        renderAdminUsers(users);
        switchAdminTab('users');
    } catch (err) {
        console.error('Admin load failed:', err);
    }
}

function renderAdminUsers(users) {
    const tbody = document.getElementById('admin-users-tbody');
    tbody.innerHTML = users.map(u => `
        <tr>
            <td><strong>${u.full_name}</strong></td>
            <td>${u.email}</td>
            <td><span class="badge badge-${getRoleBadgeColor(u.role)}">${formatRole(u.role)}</span></td>
            <td>${u.profile?.department || '-'}</td>
            <td><span class="badge ${u.is_active ? 'badge-success' : 'badge-danger'}">${u.is_active ? 'Active' : 'Inactive'}</span></td>
            <td>
                <button class="btn btn-sm btn-ghost" onclick="showEditUser('${u.id}')">Edit</button>
                <button class="btn btn-sm btn-ghost" onclick="showUserProfile('${u.id}')">Profile</button>
                ${u.is_active ? `<button class="btn btn-sm btn-ghost" style="color:#EF4444" onclick="deactivateUser('${u.id}')">Deactivate</button>` : ''}
            </td>
        </tr>
    `).join('');
}

function getRoleBadgeColor(role) {
    const r = (role || '').toUpperCase();
    const colors = { SUPER_ADMIN: 'purple', ORG_ADMIN: 'blue', PM: 'green', FIELD_LEAD: 'yellow', CREW_MEMBER: 'default', INSPECTOR: 'orange', FINANCE: 'cyan', CLIENT_VIEWER: 'gray' };
    return colors[r] || 'default';
}

function formatRole(role) {
    return (role || '').replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
}

function switchAdminTab(tab) {
    document.querySelectorAll('.admin-tab-content').forEach(c => c.classList.add('hidden'));
    document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
    document.getElementById(`admin-tab-${tab}`).classList.remove('hidden');
    document.querySelector(`[data-admin-tab="${tab}"]`).classList.add('active');

    if (tab === 'roles') loadAdminRoles();
    if (tab === 'org') loadAdminOrg();
    if (tab === 'audit') loadAuditLog();
}

async function loadAdminRoles() {
    const roles = window._adminRoles || await api('/api/admin/roles');
    const grid = document.getElementById('admin-roles-grid');
    grid.innerHTML = roles.map(r => `
        <div class="card" style="border-left:3px solid ${getRoleColor(r.role || r.name)}">
            <h4 style="margin:0 0 0.5rem 0">${formatRole(r.role || r.name)}</h4>
            <p style="color:var(--text-secondary);font-size:0.85rem">${r.description}</p>
        </div>
    `).join('');
}

function getRoleColor(role) {
    const r = (role || '').toUpperCase();
    const c = { SUPER_ADMIN: '#8B5CF6', ORG_ADMIN: '#3B82F6', PM: '#10B981', FIELD_LEAD: '#F59E0B', CREW_MEMBER: '#94A3B8', INSPECTOR: '#F97316', FINANCE: '#06B6D4', CLIENT_VIEWER: '#6B7280' };
    return c[r] || '#94A3B8';
}

async function loadAdminOrg() {
    try {
        const org = await api('/api/admin/org');
        document.getElementById('admin-org-details').innerHTML = `
            <h3>Organization Details</h3>
            <div class="form-group"><label>Name</label><input class="form-control" id="org-name-input" value="${org.name}"></div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;margin:1rem 0">
                <div class="stat-card"><div class="stat-value">${org.member_count}</div><div class="stat-label">Members</div></div>
                <div class="stat-card"><div class="stat-value">${org.project_count}</div><div class="stat-label">Projects</div></div>
                <div class="stat-card"><div class="stat-value">${org.id ? org.id.substring(0,8) : '-'}</div><div class="stat-label">Org ID</div></div>
            </div>
            <button class="btn btn-primary" onclick="updateOrg()">Save Changes</button>
        `;
    } catch (err) { console.error(err); }
}

async function updateOrg() {
    try {
        const name = document.getElementById('org-name-input').value;
        await api('/api/admin/org', { method: 'PUT', body: JSON.stringify({ name }) });
        alert('Organization updated');
    } catch (err) { alert(err.message); }
}

async function loadAuditLog() {
    try {
        const logs = await api('/api/admin/audit-log');
        const tbody = document.getElementById('admin-audit-tbody');
        tbody.innerHTML = (logs || []).map(l => `
            <tr>
                <td style="font-size:0.8rem;color:var(--text-secondary)">${new Date(l.created_at).toLocaleString()}</td>
                <td>${l.user_name || '-'}</td>
                <td><span class="badge">${l.action}</span></td>
                <td>${l.entity_type || ''} ${l.entity_id ? l.entity_id.substring(0,8) : ''}</td>
                <td style="font-size:0.8rem;max-width:200px;overflow:hidden;text-overflow:ellipsis">${l.details || ''}</td>
            </tr>
        `).join('');
    } catch (err) { console.error(err); }
}

function showCreateUser() {
    const roles = window._adminRoles || [];
    const modal = document.getElementById('modal-overlay');
    document.getElementById('modal-title').textContent = 'Add New User';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group"><label>Full Name</label><input class="form-control" id="new-user-name"></div>
        <div class="form-group"><label>Email</label><input class="form-control" type="email" id="new-user-email"></div>
        <div class="form-group"><label>Password</label><input class="form-control" type="password" id="new-user-pass"></div>
        <div class="form-group"><label>Role</label>
            <select class="form-control" id="new-user-role">
                ${roles.map(r => `<option value="${r.role || r.name}">${formatRole(r.role || r.name)}</option>`).join('')}
            </select>
        </div>
        <button class="btn btn-primary" onclick="createUser()">Create User</button>
    `;
    modal.classList.remove('hidden');
}

async function createUser() {
    try {
        await api('/api/admin/users', {
            method: 'POST',
            body: JSON.stringify({
                full_name: document.getElementById('new-user-name').value,
                email: document.getElementById('new-user-email').value,
                password: document.getElementById('new-user-pass').value,
                role: document.getElementById('new-user-role').value
            })
        });
        closeModal();
        loadAdminPanel();
    } catch (err) { alert(err.message); }
}

function showEditUser(userId) {
    const user = (window._adminUsers || []).find(u => u.id === userId);
    if (!user) return;
    const roles = window._adminRoles || [];
    const modal = document.getElementById('modal-overlay');
    document.getElementById('modal-title').textContent = 'Edit User';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group"><label>Full Name</label><input class="form-control" id="edit-user-name" value="${user.full_name}"></div>
        <div class="form-group"><label>Email</label><input class="form-control" type="email" id="edit-user-email" value="${user.email}"></div>
        <div class="form-group"><label>Role</label>
            <select class="form-control" id="edit-user-role">
                ${roles.map(r => `<option value="${r.role || r.name}" ${(r.role || r.name) === user.role ? 'selected' : ''}>${formatRole(r.role || r.name)}</option>`).join('')}
            </select>
        </div>
        <div class="form-group"><label><input type="checkbox" id="edit-user-active" ${user.is_active ? 'checked' : ''}> Active</label></div>
        <button class="btn btn-primary" onclick="updateUser('${userId}')">Save Changes</button>
    `;
    modal.classList.remove('hidden');
}

async function updateUser(userId) {
    try {
        await api(`/api/admin/users/${userId}`, {
            method: 'PUT',
            body: JSON.stringify({
                full_name: document.getElementById('edit-user-name').value,
                email: document.getElementById('edit-user-email').value,
                role: document.getElementById('edit-user-role').value,
                is_active: document.getElementById('edit-user-active').checked
            })
        });
        closeModal();
        loadAdminPanel();
    } catch (err) { alert(err.message); }
}

async function showUserProfile(userId) {
    try {
        const profile = await api(`/api/admin/users/${userId}/profile`);
        const modal = document.getElementById('modal-overlay');
        document.getElementById('modal-title').textContent = 'User Profile';
        document.getElementById('modal-body').innerHTML = `
            <div class="form-group"><label>Phone</label><input class="form-control" id="prof-phone" value="${profile.phone || ''}"></div>
            <div class="form-group"><label>Title</label><input class="form-control" id="prof-title" value="${profile.title || ''}"></div>
            <div class="form-group"><label>Department</label><input class="form-control" id="prof-dept" value="${profile.department || ''}"></div>
            <div class="form-group"><label>Timezone</label><input class="form-control" id="prof-tz" value="${profile.timezone || 'America/Chicago'}"></div>
            <div class="form-group"><label>Hourly Rate ($)</label><input class="form-control" type="number" id="prof-rate" value="${profile.hourly_rate || ''}"></div>
            <div class="form-group"><label>Certifications</label><input class="form-control" id="prof-certs" value="${profile.certifications || ''}"></div>
            <div class="form-group"><label>Emergency Contact</label><input class="form-control" id="prof-emergency" value="${profile.emergency_contact || ''}"></div>
            <button class="btn btn-primary" onclick="updateProfile('${userId}')">Save Profile</button>
        `;
        modal.classList.remove('hidden');
    } catch (err) { alert(err.message); }
}

async function updateProfile(userId) {
    try {
        await api(`/api/admin/users/${userId}/profile`, {
            method: 'PUT',
            body: JSON.stringify({
                phone: document.getElementById('prof-phone').value,
                title: document.getElementById('prof-title').value,
                department: document.getElementById('prof-dept').value,
                timezone: document.getElementById('prof-tz').value,
                hourly_rate: parseFloat(document.getElementById('prof-rate').value) || null,
                certifications: document.getElementById('prof-certs').value,
                emergency_contact: document.getElementById('prof-emergency').value
            })
        });
        closeModal();
    } catch (err) { alert(err.message); }
}

async function deactivateUser(userId) {
    if (!confirm('Deactivate this user?')) return;
    try {
        await api(`/api/admin/users/${userId}`, { method: 'DELETE' });
        loadAdminPanel();
    } catch (err) { alert(err.message); }
}

function showInviteUser() {
    const roles = window._adminRoles || [];
    const modal = document.getElementById('modal-overlay');
    document.getElementById('modal-title').textContent = 'Invite User';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group"><label>Email</label><input class="form-control" type="email" id="invite-email"></div>
        <div class="form-group"><label>Role</label>
            <select class="form-control" id="invite-role">
                ${roles.map(r => `<option value="${r.role || r.name}">${formatRole(r.role || r.name)}</option>`).join('')}
            </select>
        </div>
        <button class="btn btn-primary" onclick="sendInvite()">Send Invite</button>
    `;
    modal.classList.remove('hidden');
}

async function sendInvite() {
    try {
        await api('/api/admin/invites', {
            method: 'POST',
            body: JSON.stringify({
                email: document.getElementById('invite-email').value,
                role: document.getElementById('invite-role').value
            })
        });
        closeModal();
        alert('Invitation sent!');
    } catch (err) { alert(err.message); }
}

// ==================== BILLING ====================

const INVOICE_STATUS_COLORS = { DRAFT: '#94A3B8', SUBMITTED: '#3B82F6', APPROVED: '#10B981', REJECTED: '#EF4444', PAID: '#8B5CF6', PARTIALLY_PAID: '#F59E0B', VOIDED: '#6B7280' };

async function loadBillingPage() {
    populateBillingProjectSelect();
    loadInvoices();
    loadBillingSummary();
}

async function populateBillingProjectSelect() {
    if (!projects.length) { const p = await api('/api/projects'); projects = p; }
    const sel = document.getElementById('billing-project-select');
    sel.innerHTML = '<option value="">All Projects</option>' + projects.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
}

async function loadInvoices() {
    try {
        const projectId = document.getElementById('billing-project-select')?.value || '';
        let url = '/api/billing/invoices?limit=100';
        if (projectId) url += `&project_id=${projectId}`;
        const invoices = await api(url);
        window._billingInvoices = invoices;

        const tbody = document.getElementById('billing-invoices-tbody');
        if (!invoices.length) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--text-secondary)">No invoices yet</td></tr>';
            return;
        }
        tbody.innerHTML = invoices.map(inv => `
            <tr>
                <td><strong>${inv.invoice_number}</strong></td>
                <td>${inv.title}</td>
                <td>${inv.project_name || '-'}</td>
                <td><span class="badge" style="background:${INVOICE_STATUS_COLORS[inv.status] || '#94A3B8'}20;color:${INVOICE_STATUS_COLORS[inv.status] || '#94A3B8'}">${inv.status}</span></td>
                <td>$${(inv.subtotal || 0).toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                <td>$${(inv.total_amount || 0).toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                <td style="font-weight:600;color:${inv.balance_due > 0 ? '#F59E0B' : '#10B981'}">$${(inv.balance_due || 0).toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                <td>${inv.due_date ? new Date(inv.due_date).toLocaleDateString() : '-'}</td>
                <td>
                    <button class="btn btn-sm btn-ghost" onclick="showInvoiceDetail('${inv.id}')">View</button>
                    ${inv.status === 'DRAFT' ? `<button class="btn btn-sm btn-ghost" onclick="submitInvoice('${inv.id}')">Submit</button>` : ''}
                    ${inv.status === 'SUBMITTED' ? `<button class="btn btn-sm btn-ghost" style="color:#10B981" onclick="approveInvoice('${inv.id}')">Approve</button>` : ''}
                    ${inv.status === 'APPROVED' ? `<button class="btn btn-sm btn-ghost" style="color:#8B5CF6" onclick="showRecordPayment('${inv.id}')">Payment</button>` : ''}
                </td>
            </tr>
        `).join('');
    } catch (err) { console.error('Load invoices failed:', err); }
}

async function loadBillingSummary() {
    try {
        const projectId = document.getElementById('billing-project-select')?.value || '';
        let url = '/api/billing/summary';
        if (projectId) url += `?project_id=${projectId}`;
        const summary = await api(url);

        document.getElementById('billing-kpis').innerHTML = `
            <div class="stat-card"><div class="stat-value">$${(summary.total_invoiced || 0).toLocaleString('en-US', {maximumFractionDigits:0})}</div><div class="stat-label">Total Invoiced</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#10B981">$${(summary.total_paid || 0).toLocaleString('en-US', {maximumFractionDigits:0})}</div><div class="stat-label">Total Paid</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#F59E0B">$${(summary.total_outstanding || 0).toLocaleString('en-US', {maximumFractionDigits:0})}</div><div class="stat-label">Outstanding</div></div>
            <div class="stat-card"><div class="stat-value">${summary.invoice_count || 0}</div><div class="stat-label">Invoices</div></div>
        `;
    } catch (err) { console.error(err); }
}

function switchBillingTab(tab) {
    document.querySelectorAll('.billing-tab-content').forEach(c => c.classList.add('hidden'));
    document.querySelectorAll('.billing-tab').forEach(t => t.classList.remove('active'));
    document.getElementById(`billing-tab-${tab}`).classList.remove('hidden');
    document.querySelector(`[data-billing-tab="${tab}"]`).classList.add('active');

    if (tab === 'rate-cards') loadRateCards();
    if (tab === 'change-orders') loadChangeOrders();
}

function showCreateInvoice() {
    const modal = document.getElementById('modal-overlay');
    document.getElementById('modal-title').textContent = 'Create Invoice';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group"><label>Project</label>
            <select class="form-control" id="inv-project">
                ${projects.map(p => `<option value="${p.id}">${p.name}</option>`).join('')}
            </select>
        </div>
        <div class="form-group"><label>Title</label><input class="form-control" id="inv-title" placeholder="Invoice title"></div>
        <div class="form-group"><label>Description</label><textarea class="form-control" id="inv-desc" rows="2"></textarea></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
            <div class="form-group"><label>Billing Period Start</label><input class="form-control" type="date" id="inv-start"></div>
            <div class="form-group"><label>Billing Period End</label><input class="form-control" type="date" id="inv-end"></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem">
            <div class="form-group"><label>Due Date</label><input class="form-control" type="date" id="inv-due"></div>
            <div class="form-group"><label>Tax Rate (%)</label><input class="form-control" type="number" id="inv-tax" value="0" step="0.01"></div>
            <div class="form-group"><label>Retainage (%)</label><input class="form-control" type="number" id="inv-ret" value="10" step="0.01"></div>
        </div>
        <div class="form-group"><label>Terms</label><textarea class="form-control" id="inv-terms" rows="2">Net 30</textarea></div>
        <button class="btn btn-primary" onclick="createInvoice()">Create Invoice</button>
    `;
    modal.classList.remove('hidden');
}

async function createInvoice() {
    try {
        const data = {
            project_id: document.getElementById('inv-project').value,
            title: document.getElementById('inv-title').value,
            description: document.getElementById('inv-desc').value,
            billing_period_start: document.getElementById('inv-start').value || null,
            billing_period_end: document.getElementById('inv-end').value || null,
            due_date: document.getElementById('inv-due').value || null,
            tax_rate: parseFloat(document.getElementById('inv-tax').value) || 0,
            retainage_pct: parseFloat(document.getElementById('inv-ret').value) || 0,
            terms: document.getElementById('inv-terms').value
        };
        const inv = await api('/api/billing/invoices', { method: 'POST', body: JSON.stringify(data) });
        closeModal();
        showInvoiceDetail(inv.id);
    } catch (err) { alert(err.message); }
}

async function showInvoiceDetail(invoiceId) {
    try {
        const inv = await api(`/api/billing/invoices/${invoiceId}`);
        const modal = document.getElementById('modal-overlay');
        document.getElementById('modal-title').textContent = `Invoice ${inv.invoice_number}`;
        const lineItemsHtml = (inv.line_items || []).map((li, i) => `
            <tr>
                <td>${li.line_number || i+1}</td>
                <td><span class="badge">${li.category}</span></td>
                <td style="max-width:200px">${li.description}</td>
                <td>${li.quantity} ${li.unit || ''}</td>
                <td>$${(li.unit_rate || 0).toFixed(2)}</td>
                <td>$${(li.total_amount || 0).toFixed(2)}</td>
                <td>
                    <button class="btn btn-sm btn-ghost" style="color:#EF4444" onclick="deleteLineItem('${invoiceId}','${li.id}')">X</button>
                </td>
            </tr>
        `).join('');

        const paymentsHtml = (inv.payments || []).map(p => `
            <div style="display:flex;justify-content:space-between;padding:0.5rem 0;border-bottom:1px solid var(--border)">
                <span>$${p.amount.toFixed(2)} - ${p.payment_method || 'N/A'}</span>
                <span style="color:var(--text-secondary);font-size:0.8rem">${new Date(p.payment_date).toLocaleDateString()}</span>
            </div>
        `).join('') || '<p style="color:var(--text-secondary)">No payments recorded</p>';

        document.getElementById('modal-body').innerHTML = `
            <div style="display:flex;justify-content:space-between;margin-bottom:1rem">
                <span class="badge" style="background:${INVOICE_STATUS_COLORS[inv.status]}20;color:${INVOICE_STATUS_COLORS[inv.status]}">${inv.status}</span>
                <div>
                    ${inv.status === 'DRAFT' ? `<button class="btn btn-sm" onclick="generateFromTasks('${invoiceId}')">Auto-Generate from Tasks</button>` : ''}
                    ${inv.status === 'DRAFT' ? `<button class="btn btn-sm btn-primary" onclick="submitInvoice('${invoiceId}')">Submit</button>` : ''}
                </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:1rem;margin-bottom:1rem">
                <div><small style="color:var(--text-secondary)">Subtotal</small><div style="font-size:1.1rem">$${(inv.subtotal||0).toFixed(2)}</div></div>
                <div><small style="color:var(--text-secondary)">Tax (${inv.tax_rate}%)</small><div style="font-size:1.1rem">$${(inv.tax_amount||0).toFixed(2)}</div></div>
                <div><small style="color:var(--text-secondary)">Retainage (${inv.retainage_pct}%)</small><div style="font-size:1.1rem">-$${(inv.retainage_amount||0).toFixed(2)}</div></div>
                <div><small style="color:var(--text-secondary)">Total</small><div style="font-size:1.25rem;font-weight:700">$${(inv.total_amount||0).toFixed(2)}</div></div>
            </div>
            <div style="display:flex;justify-content:space-between;padding:0.75rem;background:var(--bg-tertiary);border-radius:8px;margin-bottom:1rem">
                <span>Paid: <strong style="color:#10B981">$${(inv.amount_paid||0).toFixed(2)}</strong></span>
                <span>Balance Due: <strong style="color:#F59E0B">$${(inv.balance_due||0).toFixed(2)}</strong></span>
            </div>
            <h4>Line Items</h4>
            <table class="data-table" style="font-size:0.85rem">
                <thead><tr><th>#</th><th>Category</th><th>Description</th><th>Qty</th><th>Rate</th><th>Total</th><th></th></tr></thead>
                <tbody>${lineItemsHtml || '<tr><td colspan="7" style="text-align:center;color:var(--text-secondary)">No line items</td></tr>'}</tbody>
            </table>
            ${inv.status === 'DRAFT' ? `<button class="btn btn-sm" style="margin-top:0.5rem" onclick="showAddLineItem('${invoiceId}')">+ Add Line Item</button>` : ''}
            <h4 style="margin-top:1.5rem">Payments</h4>
            ${paymentsHtml}
        `;
        modal.classList.remove('hidden');
    } catch (err) { alert(err.message); }
}

function showAddLineItem(invoiceId) {
    const modal = document.getElementById('modal-overlay');
    document.getElementById('modal-title').textContent = 'Add Line Item';
    document.getElementById('modal-body').innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
            <div class="form-group"><label>Category</label>
                <select class="form-control" id="li-category">
                    <option value="labor">Labor</option>
                    <option value="material">Material</option>
                    <option value="equipment">Equipment</option>
                    <option value="aerial">Aerial</option>
                    <option value="underground">Underground</option>
                    <option value="splicing">Splicing</option>
                    <option value="drop">Drop/FTTH</option>
                    <option value="testing">Testing</option>
                    <option value="permits">Permits</option>
                    <option value="restoration">Restoration</option>
                    <option value="other">Other</option>
                </select>
            </div>
            <div class="form-group"><label>Work Type</label><input class="form-control" id="li-worktype" placeholder="e.g., Aerial Fiber 144ct"></div>
        </div>
        <div class="form-group"><label>Description</label><input class="form-control" id="li-desc" placeholder="Line item description"></div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem">
            <div class="form-group"><label>Quantity</label><input class="form-control" type="number" id="li-qty" value="1"></div>
            <div class="form-group"><label>Unit</label><input class="form-control" id="li-unit" value="each"></div>
            <div class="form-group"><label>Unit Rate ($)</label><input class="form-control" type="number" id="li-rate" step="0.01" value="0"></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem">
            <div class="form-group"><label>Labor Cost</label><input class="form-control" type="number" id="li-labor" step="0.01" value="0"></div>
            <div class="form-group"><label>Material Cost</label><input class="form-control" type="number" id="li-material" step="0.01" value="0"></div>
            <div class="form-group"><label>Equipment Cost</label><input class="form-control" type="number" id="li-equip" step="0.01" value="0"></div>
        </div>
        <div class="form-group"><label><input type="checkbox" id="li-co"> Change Order Item</label></div>
        <div class="form-group"><label>Notes</label><input class="form-control" id="li-notes"></div>
        <button class="btn btn-primary" onclick="addLineItem('${invoiceId}')">Add Line Item</button>
    `;
    modal.classList.remove('hidden');
}

async function addLineItem(invoiceId) {
    try {
        await api(`/api/billing/invoices/${invoiceId}/line-items`, {
            method: 'POST',
            body: JSON.stringify({
                category: document.getElementById('li-category').value,
                description: document.getElementById('li-desc').value,
                work_type: document.getElementById('li-worktype').value,
                quantity: parseFloat(document.getElementById('li-qty').value) || 0,
                unit: document.getElementById('li-unit').value,
                unit_rate: parseFloat(document.getElementById('li-rate').value) || 0,
                labor_cost: parseFloat(document.getElementById('li-labor').value) || 0,
                material_cost: parseFloat(document.getElementById('li-material').value) || 0,
                equipment_cost: parseFloat(document.getElementById('li-equip').value) || 0,
                is_change_order: document.getElementById('li-co').checked,
                notes: document.getElementById('li-notes').value
            })
        });
        showInvoiceDetail(invoiceId);
    } catch (err) { alert(err.message); }
}

async function deleteLineItem(invoiceId, itemId) {
    if (!confirm('Remove this line item?')) return;
    try {
        await api(`/api/billing/invoices/${invoiceId}/line-items/${itemId}`, { method: 'DELETE' });
        showInvoiceDetail(invoiceId);
    } catch (err) { alert(err.message); }
}

async function submitInvoice(invoiceId) {
    if (!confirm('Submit this invoice?')) return;
    try {
        await api(`/api/billing/invoices/${invoiceId}/submit`, { method: 'POST' });
        closeModal();
        loadInvoices();
        loadBillingSummary();
    } catch (err) { alert(err.message); }
}

async function approveInvoice(invoiceId) {
    if (!confirm('Approve this invoice?')) return;
    try {
        await api(`/api/billing/invoices/${invoiceId}/approve`, { method: 'POST' });
        closeModal();
        loadInvoices();
        loadBillingSummary();
    } catch (err) { alert(err.message); }
}

async function generateFromTasks(invoiceId) {
    try {
        const result = await api(`/api/billing/invoices/${invoiceId}/generate-from-tasks`, { method: 'POST' });
        showInvoiceDetail(invoiceId);
    } catch (err) { alert(err.message); }
}

function showRecordPayment(invoiceId) {
    const modal = document.getElementById('modal-overlay');
    document.getElementById('modal-title').textContent = 'Record Payment';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group"><label>Amount ($)</label><input class="form-control" type="number" id="pay-amount" step="0.01"></div>
        <div class="form-group"><label>Payment Method</label>
            <select class="form-control" id="pay-method">
                <option value="ACH">ACH Transfer</option>
                <option value="Check">Check</option>
                <option value="Wire">Wire Transfer</option>
                <option value="Credit Card">Credit Card</option>
            </select>
        </div>
        <div class="form-group"><label>Reference #</label><input class="form-control" id="pay-ref"></div>
        <div class="form-group"><label>Payment Date</label><input class="form-control" type="date" id="pay-date" value="${new Date().toISOString().split('T')[0]}"></div>
        <div class="form-group"><label>Notes</label><input class="form-control" id="pay-notes"></div>
        <button class="btn btn-primary" onclick="recordPayment('${invoiceId}')">Record Payment</button>
    `;
    modal.classList.remove('hidden');
}

async function recordPayment(invoiceId) {
    try {
        await api(`/api/billing/invoices/${invoiceId}/payments`, {
            method: 'POST',
            body: JSON.stringify({
                amount: parseFloat(document.getElementById('pay-amount').value),
                payment_method: document.getElementById('pay-method').value,
                reference_number: document.getElementById('pay-ref').value,
                payment_date: document.getElementById('pay-date').value,
                notes: document.getElementById('pay-notes').value
            })
        });
        closeModal();
        loadInvoices();
        loadBillingSummary();
    } catch (err) { alert(err.message); }
}

async function loadRateCards() {
    try {
        const cards = await api('/api/billing/rate-cards');
        const tbody = document.getElementById('billing-ratecards-tbody');
        tbody.innerHTML = cards.map(c => `
            <tr style="${!c.is_active ? 'opacity:0.5' : ''}">
                <td><strong>${c.name}</strong>${c.description ? `<br><small style="color:var(--text-secondary)">${c.description}</small>` : ''}</td>
                <td><span class="badge">${c.category}</span></td>
                <td>${c.unit}</td>
                <td style="font-weight:600">$${(c.unit_rate || 0).toFixed(2)}</td>
                <td>$${(c.labor_rate || 0).toFixed(2)}</td>
                <td>$${(c.material_rate || 0).toFixed(2)}</td>
                <td>$${(c.equipment_rate || 0).toFixed(2)}</td>
                <td>
                    <button class="btn btn-sm btn-ghost" onclick="showEditRateCard('${c.id}')">Edit</button>
                </td>
            </tr>
        `).join('');
    } catch (err) { console.error(err); }
}

function showCreateRateCard() {
    const modal = document.getElementById('modal-overlay');
    document.getElementById('modal-title').textContent = 'Add Rate Card';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group"><label>Name</label><input class="form-control" id="rc-name"></div>
        <div class="form-group"><label>Category</label>
            <select class="form-control" id="rc-cat">
                <option value="aerial">Aerial</option><option value="underground">Underground</option>
                <option value="splicing">Splicing</option><option value="drop">Drop/FTTH</option>
                <option value="equipment">Equipment</option><option value="testing">Testing</option>
                <option value="permits">Permits</option><option value="labor">Labor</option>
                <option value="restoration">Restoration</option>
            </select>
        </div>
        <div class="form-group"><label>Description</label><input class="form-control" id="rc-desc"></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
            <div class="form-group"><label>Unit</label><input class="form-control" id="rc-unit" value="each"></div>
            <div class="form-group"><label>Unit Rate ($)</label><input class="form-control" type="number" id="rc-rate" step="0.01"></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem">
            <div class="form-group"><label>Labor</label><input class="form-control" type="number" id="rc-labor" step="0.01"></div>
            <div class="form-group"><label>Material</label><input class="form-control" type="number" id="rc-material" step="0.01"></div>
            <div class="form-group"><label>Equipment</label><input class="form-control" type="number" id="rc-equip" step="0.01"></div>
        </div>
        <button class="btn btn-primary" onclick="createRateCard()">Create Rate Card</button>
    `;
    modal.classList.remove('hidden');
}

async function createRateCard() {
    try {
        await api('/api/billing/rate-cards', {
            method: 'POST',
            body: JSON.stringify({
                name: document.getElementById('rc-name').value,
                category: document.getElementById('rc-cat').value,
                description: document.getElementById('rc-desc').value,
                unit: document.getElementById('rc-unit').value,
                unit_rate: parseFloat(document.getElementById('rc-rate').value) || 0,
                labor_rate: parseFloat(document.getElementById('rc-labor').value) || 0,
                material_rate: parseFloat(document.getElementById('rc-material').value) || 0,
                equipment_rate: parseFloat(document.getElementById('rc-equip').value) || 0
            })
        });
        closeModal();
        loadRateCards();
    } catch (err) { alert(err.message); }
}

async function showEditRateCard(cardId) {
    try {
        const cards = await api('/api/billing/rate-cards');
        const c = cards.find(x => x.id === cardId);
        if (!c) return;
        const modal = document.getElementById('modal-overlay');
        document.getElementById('modal-title').textContent = 'Edit Rate Card';
        document.getElementById('modal-body').innerHTML = `
            <div class="form-group"><label>Name</label><input class="form-control" id="rc-name" value="${c.name}"></div>
            <div class="form-group"><label>Description</label><input class="form-control" id="rc-desc" value="${c.description || ''}"></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
                <div class="form-group"><label>Unit</label><input class="form-control" id="rc-unit" value="${c.unit}"></div>
                <div class="form-group"><label>Unit Rate ($)</label><input class="form-control" type="number" id="rc-rate" step="0.01" value="${c.unit_rate}"></div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem">
                <div class="form-group"><label>Labor</label><input class="form-control" type="number" id="rc-labor" step="0.01" value="${c.labor_rate || 0}"></div>
                <div class="form-group"><label>Material</label><input class="form-control" type="number" id="rc-material" step="0.01" value="${c.material_rate || 0}"></div>
                <div class="form-group"><label>Equipment</label><input class="form-control" type="number" id="rc-equip" step="0.01" value="${c.equipment_rate || 0}"></div>
            </div>
            <div style="display:flex;gap:1rem">
                <button class="btn btn-primary" onclick="updateRateCard('${cardId}')">Save</button>
                <button class="btn btn-ghost" style="color:#EF4444" onclick="deleteRateCard('${cardId}')">Deactivate</button>
            </div>
        `;
        modal.classList.remove('hidden');
    } catch (err) { alert(err.message); }
}

async function updateRateCard(cardId) {
    try {
        await api(`/api/billing/rate-cards/${cardId}`, {
            method: 'PUT',
            body: JSON.stringify({
                name: document.getElementById('rc-name').value,
                description: document.getElementById('rc-desc').value,
                unit: document.getElementById('rc-unit').value,
                unit_rate: parseFloat(document.getElementById('rc-rate').value) || 0,
                labor_rate: parseFloat(document.getElementById('rc-labor').value) || 0,
                material_rate: parseFloat(document.getElementById('rc-material').value) || 0,
                equipment_rate: parseFloat(document.getElementById('rc-equip').value) || 0
            })
        });
        closeModal();
        loadRateCards();
    } catch (err) { alert(err.message); }
}

async function deleteRateCard(cardId) {
    if (!confirm('Deactivate this rate card?')) return;
    try {
        await api(`/api/billing/rate-cards/${cardId}`, { method: 'DELETE' });
        closeModal();
        loadRateCards();
    } catch (err) { alert(err.message); }
}

async function loadChangeOrders() {
    try {
        const projectId = document.getElementById('billing-project-select')?.value || '';
        let url = '/api/billing/change-orders';
        if (projectId) url += `?project_id=${projectId}`;
        const cos = await api(url);
        const tbody = document.getElementById('billing-cos-tbody');
        if (!cos.length) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-secondary)">No change orders</td></tr>';
            return;
        }
        tbody.innerHTML = cos.map(co => `
            <tr>
                <td><strong>${co.co_number}</strong></td>
                <td>${co.title}</td>
                <td>${co.reason || '-'}</td>
                <td style="font-weight:600">$${(co.amount || 0).toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                <td><span class="badge ${co.status === 'approved' ? 'badge-success' : co.status === 'rejected' ? 'badge-danger' : ''}">${co.status}</span></td>
                <td>
                    ${co.status === 'pending' ? `<button class="btn btn-sm btn-ghost" style="color:#10B981" onclick="approveChangeOrder('${co.id}')">Approve</button>` : ''}
                </td>
            </tr>
        `).join('');
    } catch (err) { console.error(err); }
}

function showCreateChangeOrder() {
    const modal = document.getElementById('modal-overlay');
    document.getElementById('modal-title').textContent = 'New Change Order';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group"><label>Project</label>
            <select class="form-control" id="co-project">
                ${projects.map(p => `<option value="${p.id}">${p.name}</option>`).join('')}
            </select>
        </div>
        <div class="form-group"><label>Title</label><input class="form-control" id="co-title"></div>
        <div class="form-group"><label>Reason</label><input class="form-control" id="co-reason" placeholder="e.g., Scope change, Unforeseen conditions"></div>
        <div class="form-group"><label>Description</label><textarea class="form-control" id="co-desc" rows="3"></textarea></div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:1rem">
            <div class="form-group"><label>Total ($)</label><input class="form-control" type="number" id="co-amount" step="0.01"></div>
            <div class="form-group"><label>Labor ($)</label><input class="form-control" type="number" id="co-labor" step="0.01"></div>
            <div class="form-group"><label>Material ($)</label><input class="form-control" type="number" id="co-material" step="0.01"></div>
            <div class="form-group"><label>Equipment ($)</label><input class="form-control" type="number" id="co-equip" step="0.01"></div>
        </div>
        <button class="btn btn-primary" onclick="createChangeOrder()">Create Change Order</button>
    `;
    modal.classList.remove('hidden');
}

async function createChangeOrder() {
    try {
        await api('/api/billing/change-orders', {
            method: 'POST',
            body: JSON.stringify({
                project_id: document.getElementById('co-project').value,
                title: document.getElementById('co-title').value,
                description: document.getElementById('co-desc').value,
                reason: document.getElementById('co-reason').value,
                amount: parseFloat(document.getElementById('co-amount').value) || 0,
                labor_amount: parseFloat(document.getElementById('co-labor').value) || 0,
                material_amount: parseFloat(document.getElementById('co-material').value) || 0,
                equipment_amount: parseFloat(document.getElementById('co-equip').value) || 0
            })
        });
        closeModal();
        loadChangeOrders();
    } catch (err) { alert(err.message); }
}

async function approveChangeOrder(coId) {
    if (!confirm('Approve this change order?')) return;
    try {
        await api(`/api/billing/change-orders/${coId}/approve`, { method: 'PUT' });
        loadChangeOrders();
    } catch (err) { alert(err.message); }
}

// ==================== DISPATCH BOARD ====================

let dispatchStartDate = getWeekStart(new Date());
let dispatchWs = null;

function getWeekStart(date) {
    const d = new Date(date);
    const day = d.getDay();
    d.setDate(d.getDate() - day + 1);
    d.setHours(0, 0, 0, 0);
    return d;
}

function dispatchDateNav(days) {
    dispatchStartDate = new Date(dispatchStartDate.getTime() + days * 86400000);
    loadDispatchBoard();
}

function dispatchGoToday() {
    dispatchStartDate = getWeekStart(new Date());
    loadDispatchBoard();
}

async function loadDispatchBoard() {
    try {
        populateDispatchProjectSelect();
        const endDate = new Date(dispatchStartDate.getTime() + 6 * 86400000);
        const dateFrom = dispatchStartDate.toISOString();
        const dateTo = endDate.toISOString();

        document.getElementById('dispatch-date-range').textContent =
            `${dispatchStartDate.toLocaleDateString('en-US', {month:'short',day:'numeric'})} - ${endDate.toLocaleDateString('en-US', {month:'short',day:'numeric',year:'numeric'})}`;

        const projectId = document.getElementById('dispatch-project-select')?.value || '';
        let url = `/api/dispatch/timeline?date_from=${dateFrom}&date_to=${dateTo}`;
        if (projectId) url += `&project_id=${projectId}`;

        const [timeline, stats] = await Promise.all([
            api(url),
            api('/api/dispatch/stats')
        ]);

        renderDispatchStats(stats);
        renderTimeline(timeline, dispatchStartDate, endDate);
        renderUnassignedJobs(timeline.unassigned || []);
        loadDispatchCrews();
        connectDispatchWs();
    } catch (err) { console.error('Dispatch load failed:', err); }
}

async function populateDispatchProjectSelect() {
    if (!projects.length) { const p = await api('/api/projects'); projects = p; }
    const sel = document.getElementById('dispatch-project-select');
    if (sel.options.length <= 1) {
        sel.innerHTML = '<option value="">All Projects</option>' + projects.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    }
}

function renderDispatchStats(stats) {
    document.getElementById('dispatch-stats').innerHTML = `
        <div class="stat-card"><div class="stat-value">${stats.total_jobs || 0}</div><div class="stat-label">Total Jobs</div></div>
        <div class="stat-card"><div class="stat-value" style="color:#3B82F6">${stats.jobs_today || 0}</div><div class="stat-label">Today</div></div>
        <div class="stat-card"><div class="stat-value" style="color:#F59E0B">${stats.jobs_this_week || 0}</div><div class="stat-label">This Week</div></div>
        <div class="stat-card"><div class="stat-value" style="color:#10B981">${(stats.by_status || {}).COMPLETED || 0}</div><div class="stat-label">Completed</div></div>
    `;
}

function renderTimeline(timeline, startDate, endDate) {
    const days = [];
    for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
        days.push(new Date(d));
    }

    const headerEl = document.getElementById('dispatch-timeline-header');
    headerEl.innerHTML = `
        <div class="tl-crew-col">Crew</div>
        ${days.map(d => `<div class="tl-day-col ${isToday(d) ? 'tl-today' : ''}">${d.toLocaleDateString('en-US', {weekday:'short'})}<br><small>${d.getDate()}</small></div>`).join('')}
    `;

    const bodyEl = document.getElementById('dispatch-timeline-body');
    const crews = timeline.crews || [];
    const jobs = timeline.jobs || [];

    if (!crews.length) {
        bodyEl.innerHTML = '<div style="padding:2rem;text-align:center;color:var(--text-secondary)">No crews available. Create a crew to get started.</div>';
        return;
    }

    bodyEl.innerHTML = crews.map(crew => {
        const crewJobs = jobs.filter(j => j.crew_id === crew.id);
        return `
            <div class="tl-row">
                <div class="tl-crew-col">
                    <div class="tl-crew-badge" style="background:${crew.color || '#3B82F6'}20;color:${crew.color || '#3B82F6'};border:1px solid ${crew.color || '#3B82F6'}">
                        ${crew.name}
                    </div>
                    <small style="color:var(--text-secondary)">${crew.member_count || (crew.members || []).length} members</small>
                </div>
                ${days.map(d => {
                    const dayJobs = crewJobs.filter(j => {
                        if (!j.scheduled_start) return false;
                        const js = new Date(j.scheduled_start);
                        return js.toDateString() === d.toDateString();
                    });
                    return `<div class="tl-day-col tl-cell ${isToday(d) ? 'tl-today' : ''}" ondragover="event.preventDefault()" ondrop="dropJob(event, '${crew.id}', '${d.toISOString()}')">
                        ${dayJobs.map(j => `
                            <div class="tl-job-card" draggable="true" ondragstart="dragJob(event, '${j.id}')" style="border-left:3px solid ${getJobColor(j)}" onclick="showJobDetail('${j.id}')">
                                <div class="tl-job-title">${j.title}</div>
                                <div class="tl-job-time">${j.scheduled_start ? new Date(j.scheduled_start).toLocaleTimeString('en-US', {hour:'numeric',minute:'2-digit'}) : ''}</div>
                                <span class="badge badge-sm" style="background:${getJobStatusColor(j.status)}20;color:${getJobStatusColor(j.status)}">${j.status}</span>
                            </div>
                        `).join('')}
                    </div>`;
                }).join('')}
            </div>
        `;
    }).join('');
}

function isToday(date) {
    const today = new Date();
    return date.toDateString() === today.toDateString();
}

function getJobColor(job) {
    if (job.color) return job.color;
    const priorityColors = { critical: '#EF4444', high: '#F59E0B', medium: '#3B82F6', low: '#94A3B8' };
    return priorityColors[job.priority] || '#3B82F6';
}

function getJobStatusColor(status) {
    const colors = { UNASSIGNED: '#94A3B8', SCHEDULED: '#3B82F6', EN_ROUTE: '#F59E0B', ON_SITE: '#06B6D4', IN_PROGRESS: '#8B5CF6', COMPLETED: '#10B981', CANCELLED: '#6B7280' };
    return colors[status] || '#94A3B8';
}

function renderUnassignedJobs(jobs) {
    const el = document.getElementById('unassigned-jobs-list');
    if (!jobs.length) {
        el.innerHTML = '<p style="color:var(--text-secondary);font-size:0.85rem;padding:1rem">No unassigned jobs</p>';
        return;
    }
    el.innerHTML = jobs.map(j => `
        <div class="tl-job-card" draggable="true" ondragstart="dragJob(event, '${j.id}')" style="border-left:3px solid ${getJobColor(j)};cursor:grab" onclick="showJobDetail('${j.id}')">
            <div class="tl-job-title">${j.title}</div>
            <div style="font-size:0.75rem;color:var(--text-secondary)">${j.job_type || 'General'} | ${j.priority}</div>
        </div>
    `).join('');
}

let draggedJobId = null;

function dragJob(event, jobId) {
    draggedJobId = jobId;
    event.dataTransfer.setData('text/plain', jobId);
}

async function dropJob(event, crewId, dateIso) {
    event.preventDefault();
    const jobId = draggedJobId || event.dataTransfer.getData('text/plain');
    if (!jobId) return;
    try {
        const scheduledStart = new Date(dateIso);
        scheduledStart.setHours(8, 0, 0, 0);
        const scheduledEnd = new Date(scheduledStart);
        scheduledEnd.setHours(16, 0, 0, 0);
        await api(`/api/dispatch/jobs/${jobId}/reschedule`, {
            method: 'PUT',
            body: JSON.stringify({
                crew_id: crewId,
                scheduled_start: scheduledStart.toISOString(),
                scheduled_end: scheduledEnd.toISOString()
            })
        });
        loadDispatchBoard();
    } catch (err) { alert(err.message); }
    draggedJobId = null;
}

async function showJobDetail(jobId) {
    try {
        const jobs = await api(`/api/dispatch/jobs?limit=200`);
        const job = jobs.find(j => j.id === jobId);
        if (!job) return;
        const modal = document.getElementById('modal-overlay');
        document.getElementById('modal-title').textContent = job.title;
        document.getElementById('modal-body').innerHTML = `
            <div style="display:flex;gap:0.5rem;margin-bottom:1rem">
                <span class="badge" style="background:${getJobStatusColor(job.status)}20;color:${getJobStatusColor(job.status)}">${job.status}</span>
                <span class="badge">${job.priority}</span>
                ${job.job_type ? `<span class="badge">${job.job_type}</span>` : ''}
            </div>
            <p style="color:var(--text-secondary);margin-bottom:1rem">${job.description || 'No description'}</p>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem">
                <div><small style="color:var(--text-secondary)">Crew</small><div>${job.crew?.name || 'Unassigned'}</div></div>
                <div><small style="color:var(--text-secondary)">Est. Duration</small><div>${job.estimated_duration_hrs || '-'} hrs</div></div>
                <div><small style="color:var(--text-secondary)">Scheduled Start</small><div>${job.scheduled_start ? new Date(job.scheduled_start).toLocaleString() : '-'}</div></div>
                <div><small style="color:var(--text-secondary)">Scheduled End</small><div>${job.scheduled_end ? new Date(job.scheduled_end).toLocaleString() : '-'}</div></div>
            </div>
            ${job.location_address ? `<div style="margin-bottom:1rem"><small style="color:var(--text-secondary)">Location</small><div>${job.location_address}</div></div>` : ''}
            ${job.notes ? `<div style="margin-bottom:1rem"><small style="color:var(--text-secondary)">Notes</small><div>${job.notes}</div></div>` : ''}
            <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
                ${job.status !== 'COMPLETED' && job.status !== 'CANCELLED' ? `
                    ${job.status === 'SCHEDULED' ? `<button class="btn btn-sm" onclick="updateJobStatus('${jobId}','EN_ROUTE')">En Route</button>` : ''}
                    ${job.status === 'EN_ROUTE' ? `<button class="btn btn-sm" onclick="updateJobStatus('${jobId}','ON_SITE')">On Site</button>` : ''}
                    ${job.status === 'ON_SITE' ? `<button class="btn btn-sm" onclick="updateJobStatus('${jobId}','IN_PROGRESS')">Start Work</button>` : ''}
                    ${job.status === 'IN_PROGRESS' ? `<button class="btn btn-sm btn-primary" onclick="updateJobStatus('${jobId}','COMPLETED')">Complete</button>` : ''}
                    <button class="btn btn-sm btn-ghost" style="color:#EF4444" onclick="updateJobStatus('${jobId}','CANCELLED')">Cancel</button>
                ` : ''}
            </div>
        `;
        modal.classList.remove('hidden');
    } catch (err) { alert(err.message); }
}

async function updateJobStatus(jobId, status) {
    try {
        await api(`/api/dispatch/jobs/${jobId}/status`, {
            method: 'PUT',
            body: JSON.stringify({ status })
        });
        closeModal();
        loadDispatchBoard();
    } catch (err) { alert(err.message); }
}

function showCreateJob() {
    const modal = document.getElementById('modal-overlay');
    document.getElementById('modal-title').textContent = 'Create Dispatch Job';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group"><label>Project</label>
            <select class="form-control" id="job-project">
                ${projects.map(p => `<option value="${p.id}">${p.name}</option>`).join('')}
            </select>
        </div>
        <div class="form-group"><label>Title</label><input class="form-control" id="job-title" placeholder="Job title"></div>
        <div class="form-group"><label>Description</label><textarea class="form-control" id="job-desc" rows="2"></textarea></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
            <div class="form-group"><label>Job Type</label>
                <select class="form-control" id="job-type">
                    <option value="fiber_install">Fiber Installation</option>
                    <option value="splice">Splice</option>
                    <option value="drop_install">Drop Install</option>
                    <option value="testing">Testing</option>
                    <option value="make_ready">Make Ready</option>
                    <option value="underground">Underground</option>
                    <option value="restoration">Restoration</option>
                    <option value="inspection">Inspection</option>
                    <option value="other">Other</option>
                </select>
            </div>
            <div class="form-group"><label>Priority</label>
                <select class="form-control" id="job-priority">
                    <option value="low">Low</option>
                    <option value="medium" selected>Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                </select>
            </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
            <div class="form-group"><label>Scheduled Start</label><input class="form-control" type="datetime-local" id="job-start"></div>
            <div class="form-group"><label>Scheduled End</label><input class="form-control" type="datetime-local" id="job-end"></div>
        </div>
        <div class="form-group"><label>Estimated Duration (hrs)</label><input class="form-control" type="number" id="job-duration" step="0.5" value="8"></div>
        <div class="form-group"><label>Location Address</label><input class="form-control" id="job-address"></div>
        <div class="form-group"><label>Notes</label><textarea class="form-control" id="job-notes" rows="2"></textarea></div>
        <button class="btn btn-primary" onclick="createJob()">Create Job</button>
    `;
    modal.classList.remove('hidden');
}

async function createJob() {
    try {
        await api('/api/dispatch/jobs', {
            method: 'POST',
            body: JSON.stringify({
                project_id: document.getElementById('job-project').value,
                title: document.getElementById('job-title').value,
                description: document.getElementById('job-desc').value,
                job_type: document.getElementById('job-type').value,
                priority: document.getElementById('job-priority').value,
                scheduled_start: document.getElementById('job-start').value || null,
                scheduled_end: document.getElementById('job-end').value || null,
                estimated_duration_hrs: parseFloat(document.getElementById('job-duration').value) || null,
                location_address: document.getElementById('job-address').value
            })
        });
        closeModal();
        loadDispatchBoard();
    } catch (err) { alert(err.message); }
}

async function loadDispatchCrews() {
    try {
        const crews = await api('/api/dispatch/crews');
        const el = document.getElementById('dispatch-crews-list');
        el.innerHTML = crews.map(c => `
            <div class="card" style="border-left:4px solid ${c.color}">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem">
                    <h4 style="margin:0;color:${c.color}">${c.name}</h4>
                    <span class="badge ${c.is_active ? 'badge-success' : 'badge-danger'}">${c.is_active ? 'Active' : 'Inactive'}</span>
                </div>
                <p style="font-size:0.85rem;color:var(--text-secondary);margin:0.25rem 0">${c.description || ''}</p>
                ${c.vehicle ? `<div style="font-size:0.8rem;color:var(--text-secondary)">Vehicle: ${c.vehicle}</div>` : ''}
                <div style="margin-top:0.5rem;font-size:0.85rem">
                    <strong>${c.member_count || 0}</strong> members
                    ${(c.members || []).map(m => `<span class="badge badge-sm" style="margin-left:0.25rem">${m.full_name}</span>`).join('')}
                </div>
                ${c.skills ? `<div style="margin-top:0.5rem">${c.skills.split(',').map(s => `<span class="badge badge-sm">${s.trim()}</span>`).join(' ')}</div>` : ''}
            </div>
        `).join('');
    } catch (err) { console.error(err); }
}

function showCreateCrew() {
    const modal = document.getElementById('modal-overlay');
    document.getElementById('modal-title').textContent = 'Create Crew';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group"><label>Crew Name</label><input class="form-control" id="crew-name"></div>
        <div class="form-group"><label>Description</label><input class="form-control" id="crew-desc"></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
            <div class="form-group"><label>Color</label><input class="form-control" type="color" id="crew-color" value="#3B82F6"></div>
            <div class="form-group"><label>Vehicle</label><input class="form-control" id="crew-vehicle"></div>
        </div>
        <div class="form-group"><label>Skills (comma-separated)</label><input class="form-control" id="crew-skills" placeholder="aerial,splicing,testing"></div>
        <div class="form-group"><label>Max Jobs/Day</label><input class="form-control" type="number" id="crew-maxjobs" value="5"></div>
        <button class="btn btn-primary" onclick="createCrew()">Create Crew</button>
    `;
    modal.classList.remove('hidden');
}

async function createCrew() {
    try {
        await api('/api/dispatch/crews', {
            method: 'POST',
            body: JSON.stringify({
                name: document.getElementById('crew-name').value,
                description: document.getElementById('crew-desc').value,
                color: document.getElementById('crew-color').value,
                vehicle: document.getElementById('crew-vehicle').value,
                skills: document.getElementById('crew-skills').value,
                max_jobs_per_day: parseInt(document.getElementById('crew-maxjobs').value) || 5
            })
        });
        closeModal();
        loadDispatchBoard();
    } catch (err) { alert(err.message); }
}

function connectDispatchWs() {
    if (dispatchWs && dispatchWs.readyState === WebSocket.OPEN) return;
    try {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        dispatchWs = new WebSocket(`${protocol}//${location.host}/api/dispatch/ws`);
        dispatchWs.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (['job_created','job_updated','job_deleted','job_status_changed','job_assigned','job_rescheduled'].includes(msg.type)) {
                    loadDispatchBoard();
                }
            } catch {}
        };
        dispatchWs.onclose = () => { setTimeout(connectDispatchWs, 5000); };
        dispatchWs.onerror = () => { dispatchWs.close(); };

        setInterval(() => {
            if (dispatchWs && dispatchWs.readyState === WebSocket.OPEN) {
                dispatchWs.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    } catch {}
}

/* ==================== ASSETS PAGE ==================== */
let assetsMap = null;
let assetsMapInitialized = false;

async function loadAssetsPage() {
    await Promise.all([loadAssetStats(), loadAssetCategories(), loadAssets()]);
}

async function loadAssetStats() {
    try {
        const stats = await api('/api/assets/stats');
        document.getElementById('assets-stats-grid').innerHTML = `
            <div class="stat-card"><div class="stat-value">${stats.total_assets}</div><div class="stat-label">Total Assets</div></div>
            <div class="stat-card"><div class="stat-value">$${(stats.total_value||0).toLocaleString()}</div><div class="stat-label">Total Value</div></div>
            <div class="stat-card"><div class="stat-value">${stats.open_incidents}</div><div class="stat-label">Open Incidents</div></div>
            <div class="stat-card"><div class="stat-value">${stats.pending_maintenance}</div><div class="stat-label">Pending Maintenance</div></div>
            <div class="stat-card"><div class="stat-value">$${(stats.depreciation_total||0).toLocaleString()}</div><div class="stat-label">Total Depreciation</div></div>
            <div class="stat-card"><div class="stat-value">${stats.vehicle_count}</div><div class="stat-label">Fleet Vehicles</div></div>
        `;
    } catch(e) { console.error('Asset stats error:', e); }
}

async function loadAssetCategories() {
    try {
        const cats = await api('/api/assets/categories');
        const sel = document.getElementById('assets-category-filter');
        const current = sel.value;
        sel.innerHTML = '<option value="">All Categories</option>' +
            cats.map(c => `<option value="${c.id}">${c.name} (${c.asset_count})</option>`).join('');
        sel.value = current;
    } catch(e) {}
}

async function loadAssets() {
    try {
        const status = document.getElementById('assets-status-filter').value;
        const category = document.getElementById('assets-category-filter').value;
        let url = '/api/assets?';
        if (status) url += `status=${status}&`;
        if (category) url += `category_id=${category}&`;
        const assets = await api(url);
        document.getElementById('assets-tbody').innerHTML = assets.map(a => `
            <tr>
                <td><span style="color:#60A5FA;font-weight:600;font-size:0.8rem">${a.asset_tag || '--'}</span></td>
                <td>
                    <div style="font-weight:500">${a.name}</div>
                    <div style="color:#64748B;font-size:0.75rem">${a.make || ''} ${a.model || ''}</div>
                </td>
                <td><span style="color:${a.category_color};font-size:0.85rem">${a.category_name || 'Uncategorized'}</span></td>
                <td><span class="asset-status-badge asset-status-${a.status}">${a.status.replace('_',' ')}</span></td>
                <td><span class="condition-badge condition-${a.condition}">${a.condition}</span></td>
                <td style="font-weight:600">$${(a.current_value||0).toLocaleString()}</td>
                <td>${a.assigned_user_name || a.assigned_crew_name || '<span style="color:#64748B">Unassigned</span>'}</td>
                <td>
                    <button class="btn btn-sm" onclick="viewAssetDetail('${a.id}')">View</button>
                    <button class="btn btn-sm btn-ghost" onclick="deleteAsset('${a.id}')" style="color:#EF4444">Del</button>
                </td>
            </tr>
        `).join('') || '<tr><td colspan="8" style="text-align:center;color:#64748B;padding:2rem">No assets found</td></tr>';
    } catch(e) { console.error('Load assets error:', e); }
}

function switchAssetsTab(tab) {
    document.querySelectorAll('.assets-tab-content').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('[data-assets-tab]').forEach(el => el.classList.remove('active'));
    const tabEl = document.getElementById(`assets-tab-${tab}`);
    if (tabEl) tabEl.classList.remove('hidden');
    const btn = document.querySelector(`[data-assets-tab="${tab}"]`);
    if (btn) btn.classList.add('active');
    if (tab === 'map') initAssetsMap();
    if (tab === 'ai') loadAssetAIInsights();
}

async function initAssetsMap() {
    if (assetsMapInitialized && assetsMap) {
        assetsMap.resize();
        loadAssetsMapData();
        return;
    }
    try {
        const config = await api('/api/config');
        if (!config.mapbox_token) return;
        mapboxgl.accessToken = config.mapbox_token;
        assetsMap = new mapboxgl.Map({
            container: 'assets-map',
            style: 'mapbox://styles/mapbox/satellite-streets-v12',
            center: [-97.7431, 30.2672],
            zoom: 13
        });
        assetsMap.addControl(new mapboxgl.NavigationControl());
        assetsMap.on('load', () => {
            assetsMapInitialized = true;
            loadAssetsMapData();
        });
    } catch(e) { console.error('Assets map init error:', e); }
}

async function loadAssetsMapData() {
    if (!assetsMap) return;
    try {
        const mapData = await api('/api/fleet/map/all');
        const existingSources = ['assets-techs', 'assets-vehicles'];
        existingSources.forEach(s => {
            if (assetsMap.getLayer(s + '-layer')) assetsMap.removeLayer(s + '-layer');
            if (assetsMap.getSource(s)) assetsMap.removeSource(s);
        });

        if (mapData.technicians && mapData.technicians.length > 0) {
            assetsMap.addSource('assets-techs', {
                type: 'geojson',
                data: {
                    type: 'FeatureCollection',
                    features: mapData.technicians.map(t => ({
                        type: 'Feature',
                        geometry: { type: 'Point', coordinates: [t.lng, t.lat] },
                        properties: { name: t.name || 'Unknown', speed: t.speed, battery: t.battery, source: t.source }
                    }))
                }
            });
            assetsMap.addLayer({
                id: 'assets-techs-layer',
                type: 'circle',
                source: 'assets-techs',
                paint: {
                    'circle-radius': 8,
                    'circle-color': '#10B981',
                    'circle-stroke-width': 3,
                    'circle-stroke-color': '#ffffff'
                }
            });
        }

        if (mapData.vehicles && mapData.vehicles.length > 0) {
            assetsMap.addSource('assets-vehicles', {
                type: 'geojson',
                data: {
                    type: 'FeatureCollection',
                    features: mapData.vehicles.map(v => ({
                        type: 'Feature',
                        geometry: { type: 'Point', coordinates: [v.lng, v.lat] },
                        properties: { name: v.name, type: v.type, status: v.status, speed: v.speed, driver: v.driver }
                    }))
                }
            });
            assetsMap.addLayer({
                id: 'assets-vehicles-layer',
                type: 'circle',
                source: 'assets-vehicles',
                paint: {
                    'circle-radius': 7,
                    'circle-color': ['match', ['get', 'status'], 'active', '#3B82F6', 'in_shop', '#EF4444', '#F59E0B'],
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff'
                }
            });
        }

        const allPoints = [
            ...(mapData.technicians || []).map(t => [t.lng, t.lat]),
            ...(mapData.vehicles || []).map(v => [v.lng, v.lat])
        ];
        if (allPoints.length > 0) {
            const bounds = allPoints.reduce((b, p) => b.extend(p), new mapboxgl.LngLatBounds(allPoints[0], allPoints[0]));
            assetsMap.fitBounds(bounds, { padding: 60, maxZoom: 15 });
        }

        ['assets-techs-layer', 'assets-vehicles-layer'].forEach(layerId => {
            if (!assetsMap.getLayer(layerId)) return;
            assetsMap.on('click', layerId, (e) => {
                const props = e.features[0].properties;
                new mapboxgl.Popup({ offset: 10 })
                    .setLngLat(e.lngLat)
                    .setHTML(`<div style="color:#0F172A;padding:4px"><strong>${props.name}</strong><br>${props.type||props.source||''}<br>${props.driver ? 'Driver: ' + props.driver : ''}<br>${props.battery != null ? 'Battery: ' + props.battery + '%' : ''}</div>`)
                    .addTo(assetsMap);
            });
            assetsMap.on('mouseenter', layerId, () => { assetsMap.getCanvas().style.cursor = 'pointer'; });
            assetsMap.on('mouseleave', layerId, () => { assetsMap.getCanvas().style.cursor = ''; });
        });
    } catch(e) { console.error('Assets map data error:', e); }
}

async function loadAssetAIInsights() {
    const btn = document.getElementById('assets-ai-refresh-btn');
    if (btn) btn.disabled = true;
    document.getElementById('assets-ai-summary').textContent = 'Analyzing asset portfolio...';
    try {
        const data = await api('/api/assets/ai/insights');
        const ins = data.insights;
        document.getElementById('assets-ai-summary').textContent = ins.summary || '';
        document.getElementById('assets-ai-risks').innerHTML = (ins.risks || []).map(r => `<li>${r}</li>`).join('') || '<li>No risks identified</li>';
        document.getElementById('assets-ai-recs').innerHTML = (ins.recommendations || []).map(r => `<li>${r}</li>`).join('') || '<li>No recommendations</li>';
        document.getElementById('assets-ai-utilization').textContent = (ins.utilization_score || 0) + '/100';
        document.getElementById('assets-ai-depreciation').textContent = ins.depreciation_analysis || '--';
    } catch(e) {
        document.getElementById('assets-ai-summary').textContent = 'Unable to load AI insights. Please try again.';
    }
    if (btn) btn.disabled = false;
}

function showCreateAsset() {
    openModal('Add New Asset', `
        <form onsubmit="createAsset(event)">
            <div class="form-group"><label>Name *</label><input id="asset-name" class="form-control" required></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
                <div class="form-group"><label>Asset Tag</label><input id="asset-tag" class="form-control" placeholder="AST-XXX"></div>
                <div class="form-group"><label>Serial Number</label><input id="asset-serial" class="form-control"></div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
                <div class="form-group"><label>Make</label><input id="asset-make" class="form-control"></div>
                <div class="form-group"><label>Model</label><input id="asset-model" class="form-control"></div>
            </div>
            <div class="form-group"><label>Category</label><select id="asset-category" class="form-control"><option value="">Select...</option></select></div>
            <div class="form-group"><label>Description</label><textarea id="asset-desc" class="form-control" rows="2"></textarea></div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.5rem">
                <div class="form-group"><label>Purchase Cost ($)</label><input id="asset-cost" class="form-control" type="number" step="0.01" value="0"></div>
                <div class="form-group"><label>Current Value ($)</label><input id="asset-value" class="form-control" type="number" step="0.01" value="0"></div>
                <div class="form-group"><label>Useful Life (years)</label><input id="asset-life" class="form-control" type="number" value="5"></div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
                <div class="form-group"><label>Purchase Date</label><input id="asset-purchase-date" class="form-control" type="date"></div>
                <div class="form-group"><label>Warranty Expiry</label><input id="asset-warranty" class="form-control" type="date"></div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
                <div class="form-group"><label>Condition</label><select id="asset-condition" class="form-control"><option value="good">Good</option><option value="fair">Fair</option><option value="poor">Poor</option></select></div>
                <div class="form-group"><label>Status</label><select id="asset-status" class="form-control"><option value="available">Available</option><option value="in_use">In Use</option><option value="assigned">Assigned</option><option value="maintenance">Maintenance</option></select></div>
            </div>
            <div class="form-group"><label>Notes</label><textarea id="asset-notes" class="form-control" rows="2"></textarea></div>
            <button type="submit" class="btn btn-primary btn-full">Create Asset</button>
        </form>
    `);
    loadCategoriesForSelect();
}

async function loadCategoriesForSelect() {
    try {
        const cats = await api('/api/assets/categories');
        const sel = document.getElementById('asset-category');
        if (sel) {
            sel.innerHTML = '<option value="">Select...</option>' + cats.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
        }
    } catch(e) {}
}

async function createAsset(e) {
    e.preventDefault();
    try {
        await api('/api/assets', 'POST', {
            name: document.getElementById('asset-name').value,
            asset_tag: document.getElementById('asset-tag').value,
            serial_number: document.getElementById('asset-serial').value,
            make: document.getElementById('asset-make').value,
            model: document.getElementById('asset-model').value,
            category_id: document.getElementById('asset-category').value || null,
            description: document.getElementById('asset-desc').value,
            purchase_cost: parseFloat(document.getElementById('asset-cost').value) || 0,
            current_value: parseFloat(document.getElementById('asset-value').value) || 0,
            useful_life_years: parseFloat(document.getElementById('asset-life').value) || 5,
            purchase_date: document.getElementById('asset-purchase-date').value || null,
            warranty_expiry: document.getElementById('asset-warranty').value || null,
            condition: document.getElementById('asset-condition').value,
            status: document.getElementById('asset-status').value,
            notes: document.getElementById('asset-notes').value,
        });
        closeModal();
        loadAssetsPage();
    } catch(e) { alert('Error creating asset: ' + e.message); }
}

async function deleteAsset(id) {
    if (!confirm('Delete this asset?')) return;
    try {
        await api(`/api/assets/${id}`, 'DELETE');
        loadAssetsPage();
    } catch(e) { alert('Error: ' + e.message); }
}

async function viewAssetDetail(id) {
    try {
        const asset = await api(`/api/assets/${id}`);
        const [allocations, incidents, maintenance] = await Promise.all([
            api(`/api/assets/${id}/allocations`).catch(() => []),
            api(`/api/assets/${id}/incidents`).catch(() => []),
            api(`/api/assets/${id}/maintenance`).catch(() => []),
        ]);

        openModal(`${asset.name}`, `
            <div class="detail-section">
                <h4>Asset Information</h4>
                <div class="detail-grid">
                    <div class="detail-item"><span class="detail-label">Asset Tag</span><span class="detail-value">${asset.asset_tag || '--'}</span></div>
                    <div class="detail-item"><span class="detail-label">Serial</span><span class="detail-value">${asset.serial_number || '--'}</span></div>
                    <div class="detail-item"><span class="detail-label">Make / Model</span><span class="detail-value">${asset.make || ''} ${asset.model || ''}</span></div>
                    <div class="detail-item"><span class="detail-label">Category</span><span class="detail-value" style="color:${asset.category_color}">${asset.category_name || '--'}</span></div>
                    <div class="detail-item"><span class="detail-label">Status</span><span class="detail-value"><span class="asset-status-badge asset-status-${asset.status}">${asset.status.replace('_',' ')}</span></span></div>
                    <div class="detail-item"><span class="detail-label">Condition</span><span class="detail-value"><span class="condition-badge condition-${asset.condition}">${asset.condition}</span></span></div>
                </div>
            </div>
            <div class="detail-section">
                <h4>Financial</h4>
                <div class="detail-grid">
                    <div class="detail-item"><span class="detail-label">Purchase Cost</span><span class="detail-value">$${(asset.purchase_cost||0).toLocaleString()}</span></div>
                    <div class="detail-item"><span class="detail-label">Current Value</span><span class="detail-value" style="color:#10B981;font-weight:600">$${(asset.current_value||0).toLocaleString()}</span></div>
                    <div class="detail-item"><span class="detail-label">Depreciation</span><span class="detail-value" style="color:#EF4444">$${((asset.purchase_cost||0)-(asset.current_value||0)).toLocaleString()}</span></div>
                    <div class="detail-item"><span class="detail-label">Purchase Date</span><span class="detail-value">${asset.purchase_date ? new Date(asset.purchase_date).toLocaleDateString() : '--'}</span></div>
                    <div class="detail-item"><span class="detail-label">Useful Life</span><span class="detail-value">${asset.useful_life_years} years</span></div>
                    <div class="detail-item"><span class="detail-label">Warranty</span><span class="detail-value">${asset.warranty_expiry ? new Date(asset.warranty_expiry).toLocaleDateString() : '--'}</span></div>
                </div>
            </div>
            <div class="detail-section">
                <h4>Assignment</h4>
                <div class="detail-grid">
                    <div class="detail-item"><span class="detail-label">Assigned User</span><span class="detail-value">${asset.assigned_user_name || 'None'}</span></div>
                    <div class="detail-item"><span class="detail-label">Assigned Crew</span><span class="detail-value">${asset.assigned_crew_name || 'None'}</span></div>
                    <div class="detail-item"><span class="detail-label">Project</span><span class="detail-value">${asset.assigned_project_name || 'None'}</span></div>
                </div>
                <div style="margin-top:0.75rem;display:flex;gap:0.5rem">
                    <button class="btn btn-sm btn-primary" onclick="showAllocateAsset('${asset.id}')">Allocate</button>
                    <button class="btn btn-sm" onclick="showReportIncident('${asset.id}')">Report Incident</button>
                    <button class="btn btn-sm" onclick="showScheduleMaintenance('${asset.id}')">Schedule Maintenance</button>
                </div>
            </div>
            <div class="detail-section">
                <h4>Allocation History (${allocations.length})</h4>
                ${allocations.length ? `<table class="data-table" style="font-size:0.8rem">
                    <thead><tr><th>User/Crew</th><th>Project</th><th>Start</th><th>End</th><th>Condition</th></tr></thead>
                    <tbody>${allocations.map(al => `<tr>
                        <td>${al.user_name || al.crew_name || '--'}</td>
                        <td>${al.project_name || '--'}</td>
                        <td>${new Date(al.start_at).toLocaleDateString()}</td>
                        <td>${al.end_at ? new Date(al.end_at).toLocaleDateString() : '<span style="color:#10B981">Active</span>'}</td>
                        <td>${al.returned_condition || '--'}</td>
                    </tr>`).join('')}</tbody>
                </table>` : '<p style="color:#64748B;font-size:0.85rem">No allocation history</p>'}
            </div>
            <div class="detail-section">
                <h4>Incidents (${incidents.length})</h4>
                ${incidents.length ? incidents.map(inc => `
                    <div style="padding:0.5rem 0;border-bottom:1px solid #334155;font-size:0.85rem">
                        <div style="display:flex;justify-content:space-between">
                            <strong>${inc.title}</strong>
                            <span class="asset-status-badge ${inc.status === 'open' ? 'asset-status-damaged' : 'asset-status-available'}">${inc.status}</span>
                        </div>
                        <div style="color:#94A3B8;font-size:0.75rem">${inc.incident_type} | ${inc.severity} | $${(inc.damage_cost||0).toLocaleString()} | ${new Date(inc.occurred_at).toLocaleDateString()}</div>
                        ${inc.resolution ? `<div style="color:#10B981;font-size:0.75rem;margin-top:2px">Resolution: ${inc.resolution}</div>` : ''}
                    </div>
                `).join('') : '<p style="color:#64748B;font-size:0.85rem">No incidents recorded</p>'}
            </div>
            <div class="detail-section">
                <h4>Maintenance (${maintenance.length})</h4>
                ${maintenance.length ? maintenance.map(m => `
                    <div style="padding:0.5rem 0;border-bottom:1px solid #334155;font-size:0.85rem">
                        <div style="display:flex;justify-content:space-between">
                            <strong>${m.title}</strong>
                            <span class="asset-status-badge ${m.status === 'completed' ? 'asset-status-available' : 'asset-status-maintenance'}">${m.status}</span>
                        </div>
                        <div style="color:#94A3B8;font-size:0.75rem">${m.maintenance_type} | $${(m.cost||0).toLocaleString()} | ${m.scheduled_at ? new Date(m.scheduled_at).toLocaleDateString() : 'Not scheduled'}</div>
                    </div>
                `).join('') : '<p style="color:#64748B;font-size:0.85rem">No maintenance records</p>'}
            </div>
        `);
    } catch(e) { console.error('Asset detail error:', e); }
}

function showAllocateAsset(assetId) {
    openModal('Allocate Asset', `
        <form onsubmit="allocateAsset(event, '${assetId}')">
            <div class="form-group"><label>Reason</label><input id="alloc-reason" class="form-control" placeholder="e.g. Field deployment"></div>
            <div class="form-group"><label>Start Date</label><input id="alloc-start" class="form-control" type="date" value="${new Date().toISOString().split('T')[0]}"></div>
            <div class="form-group"><label>End Date (optional)</label><input id="alloc-end" class="form-control" type="date"></div>
            <div class="form-group"><label>Notes</label><textarea id="alloc-notes" class="form-control" rows="2"></textarea></div>
            <button type="submit" class="btn btn-primary btn-full">Create Allocation</button>
        </form>
    `);
}

async function allocateAsset(e, assetId) {
    e.preventDefault();
    try {
        await api(`/api/assets/${assetId}/allocations`, 'POST', {
            reason: document.getElementById('alloc-reason').value,
            start_at: document.getElementById('alloc-start').value || null,
            end_at: document.getElementById('alloc-end').value || null,
            notes: document.getElementById('alloc-notes').value,
        });
        closeModal();
        viewAssetDetail(assetId);
    } catch(e) { alert('Error: ' + e.message); }
}

function showReportIncident(assetId) {
    openModal('Report Incident', `
        <form onsubmit="reportIncident(event, '${assetId}')">
            <div class="form-group"><label>Title *</label><input id="incident-title" class="form-control" required></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
                <div class="form-group"><label>Type</label><select id="incident-type" class="form-control">
                    <option value="damage">Damage</option><option value="theft">Theft</option><option value="malfunction">Malfunction</option>
                    <option value="accident">Accident</option><option value="loss">Loss</option><option value="other">Other</option>
                </select></div>
                <div class="form-group"><label>Severity</label><select id="incident-severity" class="form-control">
                    <option value="low">Low</option><option value="medium" selected>Medium</option><option value="high">High</option><option value="critical">Critical</option>
                </select></div>
            </div>
            <div class="form-group"><label>Description</label><textarea id="incident-desc" class="form-control" rows="3"></textarea></div>
            <div class="form-group"><label>Damage Cost ($)</label><input id="incident-cost" class="form-control" type="number" step="0.01" value="0"></div>
            <button type="submit" class="btn btn-primary btn-full">Submit Incident</button>
        </form>
    `);
}

async function reportIncident(e, assetId) {
    e.preventDefault();
    try {
        await api(`/api/assets/${assetId}/incidents`, 'POST', {
            title: document.getElementById('incident-title').value,
            incident_type: document.getElementById('incident-type').value,
            severity: document.getElementById('incident-severity').value,
            description: document.getElementById('incident-desc').value,
            damage_cost: parseFloat(document.getElementById('incident-cost').value) || 0,
        });
        closeModal();
        viewAssetDetail(assetId);
    } catch(e) { alert('Error: ' + e.message); }
}

function showScheduleMaintenance(assetId) {
    openModal('Schedule Maintenance', `
        <form onsubmit="scheduleMaintenance(event, '${assetId}')">
            <div class="form-group"><label>Title *</label><input id="maint-title" class="form-control" required></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
                <div class="form-group"><label>Type</label><select id="maint-type" class="form-control">
                    <option value="preventive">Preventive</option><option value="corrective">Corrective</option>
                    <option value="inspection">Inspection</option><option value="calibration">Calibration</option>
                </select></div>
                <div class="form-group"><label>Scheduled Date</label><input id="maint-date" class="form-control" type="date"></div>
            </div>
            <div class="form-group"><label>Description</label><textarea id="maint-desc" class="form-control" rows="2"></textarea></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
                <div class="form-group"><label>Vendor</label><input id="maint-vendor" class="form-control"></div>
                <div class="form-group"><label>Estimated Cost ($)</label><input id="maint-cost" class="form-control" type="number" step="0.01" value="0"></div>
            </div>
            <button type="submit" class="btn btn-primary btn-full">Schedule</button>
        </form>
    `);
}

async function scheduleMaintenance(e, assetId) {
    e.preventDefault();
    try {
        await api(`/api/assets/${assetId}/maintenance`, 'POST', {
            title: document.getElementById('maint-title').value,
            maintenance_type: document.getElementById('maint-type').value,
            scheduled_at: document.getElementById('maint-date').value || null,
            description: document.getElementById('maint-desc').value,
            vendor: document.getElementById('maint-vendor').value,
            cost: parseFloat(document.getElementById('maint-cost').value) || 0,
        });
        closeModal();
        viewAssetDetail(assetId);
    } catch(e) { alert('Error: ' + e.message); }
}


/* ==================== FLEET PAGE ==================== */
let fleetMap = null;
let fleetMapInitialized = false;

async function loadFleetPage() {
    await Promise.all([loadFleetStats(), loadFleetVehicles()]);
}

async function loadFleetStats() {
    try {
        const stats = await api('/api/fleet/vehicles/stats');
        document.getElementById('fleet-stats-grid').innerHTML = `
            <div class="stat-card"><div class="stat-value">${stats.total_vehicles}</div><div class="stat-label">Total Vehicles</div></div>
            <div class="stat-card"><div class="stat-value">${stats.active_vehicles}</div><div class="stat-label">Active</div></div>
            <div class="stat-card"><div class="stat-value">${stats.in_shop}</div><div class="stat-label">In Shop</div></div>
            <div class="stat-card"><div class="stat-value">${stats.active_technicians}</div><div class="stat-label">Active Technicians</div></div>
            <div class="stat-card"><div class="stat-value">${(stats.total_odometer||0).toLocaleString()} mi</div><div class="stat-label">Total Fleet Miles</div></div>
            <div class="stat-card"><div class="stat-value">${stats.avg_fuel_level}%</div><div class="stat-label">Avg Fuel Level</div></div>
            <div class="stat-card"><div class="stat-value">${stats.vehicles_with_location}</div><div class="stat-label">GPS Tracked</div></div>
            <div class="stat-card"><div class="stat-value">${stats.active_integrations}</div><div class="stat-label">Telematics Connected</div></div>
        `;
    } catch(e) { console.error('Fleet stats error:', e); }
}

async function loadFleetVehicles() {
    try {
        const vehicles = await api('/api/fleet/vehicles');
        document.getElementById('fleet-vehicles-tbody').innerHTML = vehicles.map(v => {
            const fuelColor = (v.fuel_level||0) > 50 ? '#10B981' : (v.fuel_level||0) > 25 ? '#F59E0B' : '#EF4444';
            return `<tr>
                <td>
                    <div style="font-weight:500">${v.name}</div>
                    <div style="color:#64748B;font-size:0.75rem">${v.make || ''} ${v.model || ''} ${v.year || ''}</div>
                </td>
                <td>${v.vehicle_type || '--'}</td>
                <td><span class="asset-status-badge vehicle-status-${v.status}">${(v.status||'').replace('_',' ')}</span></td>
                <td>${v.driver_name || '<span style="color:#64748B">Unassigned</span>'}</td>
                <td>${(v.odometer||0).toLocaleString()} mi</td>
                <td>${v.fuel_level != null ? `<div class="fuel-bar"><div class="fuel-bar-fill" style="width:${v.fuel_level}%;background:${fuelColor}"></div></div>${v.fuel_level}%` : '--'}</td>
                <td>${v.current_lat ? `<span style="color:#10B981;font-size:0.75rem">${v.current_lat.toFixed(4)}, ${v.current_lng.toFixed(4)}</span>` : '<span style="color:#64748B">No GPS</span>'}</td>
                <td>
                    <button class="btn btn-sm" onclick="viewVehicleDetail('${v.id}')">View</button>
                    <button class="btn btn-sm btn-ghost" onclick="deleteVehicle('${v.id}')" style="color:#EF4444">Del</button>
                </td>
            </tr>`;
        }).join('') || '<tr><td colspan="8" style="text-align:center;color:#64748B;padding:2rem">No vehicles found</td></tr>';
    } catch(e) { console.error('Load vehicles error:', e); }
}

function switchFleetTab(tab) {
    document.querySelectorAll('.fleet-tab-content').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('[data-fleet-tab]').forEach(el => el.classList.remove('active'));
    const tabEl = document.getElementById(`fleet-tab-${tab}`);
    if (tabEl) tabEl.classList.remove('hidden');
    const btn = document.querySelector(`[data-fleet-tab="${tab}"]`);
    if (btn) btn.classList.add('active');
    if (tab === 'map') initFleetMap();
    if (tab === 'techs') loadTechLocations();
    if (tab === 'integrations') loadFleetIntegrations();
    if (tab === 'ai') loadFleetAIInsights();
}

async function initFleetMap() {
    if (fleetMapInitialized && fleetMap) {
        fleetMap.resize();
        loadFleetMapData();
        return;
    }
    try {
        const config = await api('/api/config');
        if (!config.mapbox_token) return;
        mapboxgl.accessToken = config.mapbox_token;
        fleetMap = new mapboxgl.Map({
            container: 'fleet-map',
            style: 'mapbox://styles/mapbox/satellite-streets-v12',
            center: [-97.7431, 30.2672],
            zoom: 13
        });
        fleetMap.addControl(new mapboxgl.NavigationControl());
        fleetMap.on('load', () => {
            fleetMapInitialized = true;
            loadFleetMapData();
        });
    } catch(e) { console.error('Fleet map init error:', e); }
}

async function loadFleetMapData() {
    if (!fleetMap) return;
    try {
        const mapData = await api('/api/fleet/map/all');
        const sources = ['fleet-vehicles', 'fleet-techs'];
        sources.forEach(s => {
            if (fleetMap.getLayer(s + '-layer')) fleetMap.removeLayer(s + '-layer');
            if (fleetMap.getLayer(s + '-labels')) fleetMap.removeLayer(s + '-labels');
            if (fleetMap.getSource(s)) fleetMap.removeSource(s);
        });

        if (mapData.vehicles && mapData.vehicles.length > 0) {
            fleetMap.addSource('fleet-vehicles', {
                type: 'geojson',
                data: {
                    type: 'FeatureCollection',
                    features: mapData.vehicles.map(v => ({
                        type: 'Feature',
                        geometry: { type: 'Point', coordinates: [v.lng, v.lat] },
                        properties: { name: v.name, type: v.type, status: v.status, speed: v.speed, driver: v.driver || '', heading: v.heading }
                    }))
                }
            });
            fleetMap.addLayer({
                id: 'fleet-vehicles-layer',
                type: 'circle',
                source: 'fleet-vehicles',
                paint: {
                    'circle-radius': 9,
                    'circle-color': ['match', ['get', 'status'], 'active', '#3B82F6', 'in_shop', '#EF4444', '#F59E0B'],
                    'circle-stroke-width': 3,
                    'circle-stroke-color': '#ffffff'
                }
            });
            fleetMap.addLayer({
                id: 'fleet-vehicles-labels',
                type: 'symbol',
                source: 'fleet-vehicles',
                layout: {
                    'text-field': ['get', 'name'],
                    'text-size': 11,
                    'text-offset': [0, 1.8],
                    'text-anchor': 'top'
                },
                paint: { 'text-color': '#ffffff', 'text-halo-color': '#000000', 'text-halo-width': 1 }
            });
        }

        if (mapData.technicians && mapData.technicians.length > 0) {
            fleetMap.addSource('fleet-techs', {
                type: 'geojson',
                data: {
                    type: 'FeatureCollection',
                    features: mapData.technicians.map(t => ({
                        type: 'Feature',
                        geometry: { type: 'Point', coordinates: [t.lng, t.lat] },
                        properties: { name: t.name || 'Tech', battery: t.battery, speed: t.speed, source: t.source, time: t.event_time }
                    }))
                }
            });
            fleetMap.addLayer({
                id: 'fleet-techs-layer',
                type: 'circle',
                source: 'fleet-techs',
                paint: {
                    'circle-radius': 7,
                    'circle-color': '#10B981',
                    'circle-stroke-width': 3,
                    'circle-stroke-color': '#ffffff'
                }
            });
            fleetMap.addLayer({
                id: 'fleet-techs-labels',
                type: 'symbol',
                source: 'fleet-techs',
                layout: {
                    'text-field': ['get', 'name'],
                    'text-size': 10,
                    'text-offset': [0, 1.5],
                    'text-anchor': 'top'
                },
                paint: { 'text-color': '#10B981', 'text-halo-color': '#000000', 'text-halo-width': 1 }
            });
        }

        const allPts = [
            ...(mapData.vehicles || []).map(v => [v.lng, v.lat]),
            ...(mapData.technicians || []).map(t => [t.lng, t.lat])
        ];
        if (allPts.length > 0) {
            const bounds = allPts.reduce((b, p) => b.extend(p), new mapboxgl.LngLatBounds(allPts[0], allPts[0]));
            fleetMap.fitBounds(bounds, { padding: 60, maxZoom: 15 });
        }

        ['fleet-vehicles-layer', 'fleet-techs-layer'].forEach(layerId => {
            if (!fleetMap.getLayer(layerId)) return;
            fleetMap.on('click', layerId, (e) => {
                const p = e.features[0].properties;
                new mapboxgl.Popup({ offset: 12 })
                    .setLngLat(e.lngLat)
                    .setHTML(`<div style="color:#0F172A;padding:4px"><strong>${p.name}</strong><br>${p.type||p.source||''}<br>${p.driver ? 'Driver: ' + p.driver : ''}${p.speed ? '<br>Speed: ' + p.speed + ' mph' : ''}${p.battery != null && p.battery !== 'null' ? '<br>Battery: ' + p.battery + '%' : ''}</div>`)
                    .addTo(fleetMap);
            });
            fleetMap.on('mouseenter', layerId, () => { fleetMap.getCanvas().style.cursor = 'pointer'; });
            fleetMap.on('mouseleave', layerId, () => { fleetMap.getCanvas().style.cursor = ''; });
        });
    } catch(e) { console.error('Fleet map data error:', e); }
}

async function loadTechLocations() {
    try {
        const locs = await api('/api/fleet/tech/locations');
        document.getElementById('fleet-techs-tbody').innerHTML = locs.map(l => `
            <tr>
                <td style="font-weight:500">${l.user_name || 'Unknown'}</td>
                <td>${l.lat.toFixed(6)}</td>
                <td>${l.lng.toFixed(6)}</td>
                <td>${l.speed != null ? l.speed.toFixed(1) + ' mph' : '--'}</td>
                <td>${l.battery_level != null ? l.battery_level + '%' : '--'}</td>
                <td>${l.source || '--'}</td>
                <td>${new Date(l.event_time).toLocaleString()}</td>
            </tr>
        `).join('') || '<tr><td colspan="7" style="text-align:center;color:#64748B;padding:2rem">No active technician locations</td></tr>';
    } catch(e) { console.error('Tech locations error:', e); }
}

async function loadFleetIntegrations() {
    try {
        const integs = await api('/api/fleet/integrations');
        const container = document.getElementById('fleet-integrations-list');
        if (integs.length === 0) {
            container.innerHTML = '<p style="color:#64748B;text-align:center;padding:2rem">No telematics providers connected. Click "Connect Provider" to add one.</p>';
            return;
        }
        container.innerHTML = integs.map(i => {
            const providerNames = { samsara: 'Samsara', geotab: 'GeoTab', verizon_connect: 'Verizon Connect' };
            return `<div class="integration-card">
                <div class="integ-info">
                    <div style="font-weight:600;font-size:0.95rem">${providerNames[i.provider] || i.provider}</div>
                    <div style="color:#94A3B8;font-size:0.8rem">${i.display_name || ''} | ${i.vehicle_count} vehicles synced</div>
                    <div style="color:#64748B;font-size:0.75rem">Last sync: ${i.last_sync_at ? new Date(i.last_sync_at).toLocaleString() : 'Never'}</div>
                    ${i.error_message ? `<div style="color:#EF4444;font-size:0.75rem;margin-top:2px">${i.error_message}</div>` : ''}
                </div>
                <div class="integ-status">
                    <span class="sync-dot ${i.status}"></span>
                    <button class="btn btn-sm" onclick="syncIntegration('${i.id}')">Sync Now</button>
                    <button class="btn btn-sm btn-ghost" onclick="deleteFleetIntegration('${i.id}')" style="color:#EF4444">Remove</button>
                </div>
            </div>`;
        }).join('');
    } catch(e) { console.error('Fleet integrations error:', e); }
}

function showAddIntegration(provider) {
    const providers = {
        samsara: { name: 'Samsara', fields: `
            <div class="form-group"><label>API Token *</label><input id="integ-api-key" class="form-control" required placeholder="Your Samsara API token"></div>
            <div class="form-group"><label>API Endpoint</label><input id="integ-endpoint" class="form-control" value="https://api.samsara.com" placeholder="https://api.samsara.com"></div>
        `},
        geotab: { name: 'GeoTab', fields: `
            <div class="form-group"><label>API Key / Password *</label><input id="integ-api-key" class="form-control" required></div>
            <div class="form-group"><label>Database Name *</label><input id="integ-database" class="form-control" required placeholder="Your GeoTab database name"></div>
            <div class="form-group"><label>Username</label><input id="integ-username" class="form-control" placeholder="GeoTab username"></div>
            <div class="form-group"><label>API Endpoint</label><input id="integ-endpoint" class="form-control" value="https://my.geotab.com/apiv1"></div>
        `},
        verizon_connect: { name: 'Verizon Connect', fields: `
            <div class="form-group"><label>API Token *</label><input id="integ-api-key" class="form-control" required></div>
            <div class="form-group"><label>Account ID</label><input id="integ-account" class="form-control" placeholder="Verizon Connect account ID"></div>
            <div class="form-group"><label>API Endpoint</label><input id="integ-endpoint" class="form-control" value="https://fim.api.us.fleetmatics.com/rad/v1"></div>
        `}
    };

    if (!provider) {
        openModal('Select Provider', `
            <div style="display:grid;gap:1rem">
                ${Object.entries(providers).map(([key, p]) => `
                    <div class="provider-card" onclick="showAddIntegration('${key}')">
                        <strong>${p.name}</strong>
                    </div>
                `).join('')}
            </div>
        `);
        return;
    }

    const p = providers[provider];
    openModal(`Connect ${p.name}`, `
        <form onsubmit="createFleetIntegration(event, '${provider}')">
            <div class="form-group"><label>Display Name</label><input id="integ-display-name" class="form-control" value="${p.name}" placeholder="Custom name"></div>
            ${p.fields}
            <div class="form-group"><label>Sync Interval (minutes)</label><input id="integ-interval" class="form-control" type="number" value="5" min="1" max="60"></div>
            <button type="submit" class="btn btn-primary btn-full">Connect ${p.name}</button>
        </form>
    `);
}

async function createFleetIntegration(e, provider) {
    e.preventDefault();
    try {
        const payload = {
            provider: provider,
            display_name: document.getElementById('integ-display-name').value,
            api_key_ref: document.getElementById('integ-api-key').value,
            api_endpoint: document.getElementById('integ-endpoint')?.value || null,
            sync_interval_minutes: parseInt(document.getElementById('integ-interval').value) || 5,
        };
        if (provider === 'geotab') {
            payload.database_name = document.getElementById('integ-database')?.value || '';
            payload.config = { username: document.getElementById('integ-username')?.value || '' };
        }
        if (provider === 'verizon_connect') {
            payload.account_id = document.getElementById('integ-account')?.value || '';
        }
        await api('/api/fleet/integrations', 'POST', payload);
        closeModal();
        loadFleetIntegrations();
    } catch(e) { alert('Error: ' + e.message); }
}

async function syncIntegration(id) {
    try {
        const result = await api(`/api/fleet/integrations/${id}/sync`, 'POST');
        if (result.ok) {
            alert(result.result?.message || 'Sync completed');
        } else {
            alert('Sync error: ' + (result.error || 'Unknown error'));
        }
        loadFleetIntegrations();
        loadFleetStats();
    } catch(e) { alert('Sync error: ' + e.message); }
}

async function deleteFleetIntegration(id) {
    if (!confirm('Remove this telematics integration?')) return;
    try {
        await api(`/api/fleet/integrations/${id}`, 'DELETE');
        loadFleetIntegrations();
    } catch(e) { alert('Error: ' + e.message); }
}

function showCreateVehicle() {
    openModal('Add Vehicle', `
        <form onsubmit="createVehicle(event)">
            <div class="form-group"><label>Name *</label><input id="veh-name" class="form-control" required placeholder="e.g. Bucket Truck #101"></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
                <div class="form-group"><label>Make</label><input id="veh-make" class="form-control"></div>
                <div class="form-group"><label>Model</label><input id="veh-model" class="form-control"></div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.5rem">
                <div class="form-group"><label>Year</label><input id="veh-year" class="form-control" type="number"></div>
                <div class="form-group"><label>License Plate</label><input id="veh-plate" class="form-control"></div>
                <div class="form-group"><label>VIN</label><input id="veh-vin" class="form-control"></div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
                <div class="form-group"><label>Type</label><select id="veh-type" class="form-control">
                    <option value="truck">Truck</option><option value="van">Van</option><option value="pickup">Pickup</option>
                    <option value="bucket_truck">Bucket Truck</option><option value="trailer">Trailer</option><option value="other">Other</option>
                </select></div>
                <div class="form-group"><label>Color</label><input id="veh-color" class="form-control" placeholder="e.g. White"></div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
                <div class="form-group"><label>Odometer (mi)</label><input id="veh-odo" class="form-control" type="number" value="0"></div>
                <div class="form-group"><label>Fuel Level (%)</label><input id="veh-fuel" class="form-control" type="number" value="100" min="0" max="100"></div>
            </div>
            <div class="form-group"><label>Notes</label><textarea id="veh-notes" class="form-control" rows="2"></textarea></div>
            <button type="submit" class="btn btn-primary btn-full">Add Vehicle</button>
        </form>
    `);
}

async function createVehicle(e) {
    e.preventDefault();
    try {
        await api('/api/fleet/vehicles', 'POST', {
            name: document.getElementById('veh-name').value,
            make: document.getElementById('veh-make').value,
            model: document.getElementById('veh-model').value,
            year: document.getElementById('veh-year').value || null,
            license_plate: document.getElementById('veh-plate').value,
            vin: document.getElementById('veh-vin').value,
            vehicle_type: document.getElementById('veh-type').value,
            color: document.getElementById('veh-color').value,
            odometer: parseFloat(document.getElementById('veh-odo').value) || 0,
            fuel_level: parseFloat(document.getElementById('veh-fuel').value),
            notes: document.getElementById('veh-notes').value,
        });
        closeModal();
        loadFleetPage();
    } catch(e) { alert('Error: ' + e.message); }
}

async function viewVehicleDetail(id) {
    try {
        const v = await api(`/api/fleet/vehicles/${id}`);
        const telemetry = await api(`/api/fleet/vehicles/${id}/telemetry?limit=10`).catch(() => []);
        const fuelColor = (v.fuel_level||0) > 50 ? '#10B981' : (v.fuel_level||0) > 25 ? '#F59E0B' : '#EF4444';

        openModal(v.name, `
            <div class="detail-section">
                <h4>Vehicle Information</h4>
                <div class="detail-grid">
                    <div class="detail-item"><span class="detail-label">Make / Model</span><span class="detail-value">${v.make || ''} ${v.model || ''} ${v.year || ''}</span></div>
                    <div class="detail-item"><span class="detail-label">VIN</span><span class="detail-value">${v.vin || '--'}</span></div>
                    <div class="detail-item"><span class="detail-label">License Plate</span><span class="detail-value">${v.license_plate || '--'}</span></div>
                    <div class="detail-item"><span class="detail-label">Type</span><span class="detail-value">${v.vehicle_type || '--'}</span></div>
                    <div class="detail-item"><span class="detail-label">Status</span><span class="detail-value"><span class="asset-status-badge vehicle-status-${v.status}">${(v.status||'').replace('_',' ')}</span></span></div>
                    <div class="detail-item"><span class="detail-label">Driver</span><span class="detail-value">${v.driver_name || 'Unassigned'}</span></div>
                </div>
            </div>
            <div class="detail-section">
                <h4>Metrics</h4>
                <div class="detail-grid">
                    <div class="detail-item"><span class="detail-label">Odometer</span><span class="detail-value">${(v.odometer||0).toLocaleString()} miles</span></div>
                    <div class="detail-item"><span class="detail-label">Fuel Level</span><span class="detail-value">${v.fuel_level != null ? `<div class="fuel-bar" style="width:80px"><div class="fuel-bar-fill" style="width:${v.fuel_level}%;background:${fuelColor}"></div></div> ${v.fuel_level}%` : '--'}</span></div>
                    <div class="detail-item"><span class="detail-label">Engine Hours</span><span class="detail-value">${(v.engine_hours||0).toLocaleString()} hrs</span></div>
                    <div class="detail-item"><span class="detail-label">Speed</span><span class="detail-value">${v.current_speed||0} mph</span></div>
                    <div class="detail-item"><span class="detail-label">Location</span><span class="detail-value">${v.current_lat ? v.current_lat.toFixed(5) + ', ' + v.current_lng.toFixed(5) : 'No GPS'}</span></div>
                    <div class="detail-item"><span class="detail-label">Last Update</span><span class="detail-value">${v.last_location_update ? new Date(v.last_location_update).toLocaleString() : '--'}</span></div>
                </div>
            </div>
            ${v.telematics_provider ? `<div class="detail-section">
                <h4>Telematics</h4>
                <div class="detail-grid">
                    <div class="detail-item"><span class="detail-label">Provider</span><span class="detail-value">${v.telematics_provider}</span></div>
                    <div class="detail-item"><span class="detail-label">Vehicle ID</span><span class="detail-value">${v.telematics_vehicle_id || '--'}</span></div>
                </div>
            </div>` : ''}
            <div class="detail-section">
                <h4>Recent Telemetry (${telemetry.length})</h4>
                ${telemetry.length ? `<table class="data-table" style="font-size:0.8rem">
                    <thead><tr><th>Time</th><th>Position</th><th>Speed</th><th>Event</th><th>Provider</th></tr></thead>
                    <tbody>${telemetry.map(t => `<tr>
                        <td>${new Date(t.event_time).toLocaleString()}</td>
                        <td>${t.lat.toFixed(5)}, ${t.lng.toFixed(5)}</td>
                        <td>${t.speed} mph</td>
                        <td>${t.event_type || '--'}</td>
                        <td>${t.provider || '--'}</td>
                    </tr>`).join('')}</tbody>
                </table>` : '<p style="color:#64748B;font-size:0.85rem">No telemetry data</p>'}
            </div>
        `);
    } catch(e) { console.error('Vehicle detail error:', e); }
}

async function deleteVehicle(id) {
    if (!confirm('Delete this vehicle?')) return;
    try {
        await api(`/api/fleet/vehicles/${id}`, 'DELETE');
        loadFleetPage();
    } catch(e) { alert('Error: ' + e.message); }
}

async function loadFleetAIInsights() {
    document.getElementById('fleet-ai-summary').textContent = 'Analyzing fleet data...';
    try {
        const data = await api('/api/fleet/ai/insights');
        const ins = data.insights;
        document.getElementById('fleet-ai-summary').textContent = ins.summary || '';
        document.getElementById('fleet-ai-risks').innerHTML = (ins.risks || []).map(r => `<li>${r}</li>`).join('') || '<li>No risks identified</li>';
        document.getElementById('fleet-ai-recs').innerHTML = (ins.recommendations || []).map(r => `<li>${r}</li>`).join('') || '<li>No recommendations</li>';
        document.getElementById('fleet-ai-efficiency').textContent = (ins.efficiency_score || 0) + '/100';
    } catch(e) {
        document.getElementById('fleet-ai-summary').textContent = 'Unable to load AI insights. Please try again.';
    }
}


function switchSafetyTab(tab) {
    document.querySelectorAll('[data-safety-tab]').forEach(b => b.classList.remove('active'));
    document.querySelector(`[data-safety-tab="${tab}"]`).classList.add('active');
    ['incidents','inspections','talks','training','ppe','corrective','osha','ai'].forEach(t => {
        const el = document.getElementById(`safety-tab-${t}`);
        if (el) el.classList.toggle('hidden', t !== tab);
    });
}

async function loadSafetyPage() {
    loadSafetyKPIs();
    loadSafetyIncidents();
    loadSafetyInspections();
    loadToolboxTalks();
    loadSafetyTraining();
    loadPPECompliance();
    loadCorrectiveActions();
    loadOSHALogs();
}

async function loadSafetyKPIs() {
    try {
        const kpis = await api('/api/safety/kpis');
        document.getElementById('safety-stats-grid').innerHTML = `
            <div class="stat-card"><div class="stat-value" style="color:${kpis.trir <= 3 ? '#10B981' : '#EF4444'}">${(kpis.trir || 0).toFixed(2)}</div><div class="stat-label">TRIR</div></div>
            <div class="stat-card"><div class="stat-value" style="color:${kpis.dart_rate <= 2 ? '#10B981' : '#EF4444'}">${(kpis.dart_rate || 0).toFixed(2)}</div><div class="stat-label">DART Rate</div></div>
            <div class="stat-card"><div class="stat-value" style="color:${kpis.emr <= 1.0 ? '#10B981' : '#F59E0B'}">${(kpis.emr || 1.0).toFixed(2)}</div><div class="stat-label">EMR</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#3B82F6">${kpis.days_since_last_incident || 0}</div><div class="stat-label">Days Since Last Incident</div></div>
            <div class="stat-card"><div class="stat-value">${kpis.total_incidents || 0}</div><div class="stat-label">Total Incidents</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#F59E0B">${kpis.open_incidents || 0}</div><div class="stat-label">Open Incidents</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#8B5CF6">${kpis.near_misses || 0}</div><div class="stat-label">Near Misses</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#06B6D4">${kpis.training_compliance || 0}%</div><div class="stat-label">Training Compliance</div></div>
        `;
    } catch(e) { console.error('Safety KPIs error:', e); }
}

async function loadSafetyIncidents() {
    try {
        const items = await api('/api/safety/incidents');
        const tbody = document.getElementById('safety-incidents-tbody');
        const sevColors = {critical:'#EF4444',high:'#F59E0B',medium:'#3B82F6',low:'#10B981'};
        const statusColors = {open:'#EF4444',investigating:'#F59E0B',corrective_action:'#8B5CF6',closed:'#10B981'};
        tbody.innerHTML = items.map(i => `<tr>
            <td>${new Date(i.occurred_at).toLocaleDateString()}</td>
            <td><strong>${i.title}</strong><br><small style="color:#94A3B8">${i.description ? i.description.substring(0,80)+'...' : ''}</small></td>
            <td>${(i.incident_type||'').replace(/_/g,' ')}</td>
            <td><span class="badge" style="background:${sevColors[i.severity]||'#64748B'}">${i.severity}</span></td>
            <td><span class="badge" style="background:${statusColors[i.status]||'#64748B'}">${(i.status||'').replace(/_/g,' ')}</span></td>
            <td>${i.is_near_miss ? '<span style="color:#F59E0B">&#9888; Yes</span>' : 'No'}</td>
            <td>${i.is_osha_recordable ? '<span style="color:#EF4444">Yes</span>' : 'No'}</td>
            <td><button class="btn btn-sm" onclick="viewSafetyIncident('${i.id}')">View</button></td>
        </tr>`).join('');
    } catch(e) { console.error('Incidents error:', e); }
}

async function viewSafetyIncident(id) {
    try {
        const i = await api(`/api/safety/incidents/${id}`);
        const sevColors = {critical:'#EF4444',high:'#F59E0B',medium:'#3B82F6',low:'#10B981'};
        showModal('Incident Details', `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
                <div class="form-group"><label>Title</label><div style="color:#CBD5E1">${i.title}</div></div>
                <div class="form-group"><label>Type</label><div style="color:#CBD5E1">${(i.incident_type||'').replace(/_/g,' ')}</div></div>
                <div class="form-group"><label>Severity</label><div><span class="badge" style="background:${sevColors[i.severity]||'#64748B'}">${i.severity}</span></div></div>
                <div class="form-group"><label>Status</label><div style="color:#CBD5E1">${(i.status||'').replace(/_/g,' ')}</div></div>
                <div class="form-group"><label>Date</label><div style="color:#CBD5E1">${new Date(i.occurred_at).toLocaleString()}</div></div>
                <div class="form-group"><label>Location</label><div style="color:#CBD5E1">${i.location_description||'N/A'}</div></div>
                <div class="form-group"><label>Near Miss</label><div style="color:#CBD5E1">${i.is_near_miss?'Yes':'No'}</div></div>
                <div class="form-group"><label>OSHA Recordable</label><div style="color:#CBD5E1">${i.is_osha_recordable?'Yes':'No'}</div></div>
            </div>
            <div class="form-group" style="margin-top:1rem"><label>Description</label><div style="color:#CBD5E1">${i.description||'N/A'}</div></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:1rem">
                <div class="form-group"><label>Injury Type</label><div style="color:#CBD5E1">${i.injury_type||'N/A'}</div></div>
                <div class="form-group"><label>Body Part</label><div style="color:#CBD5E1">${i.body_part||'N/A'}</div></div>
            </div>
            <div class="form-group" style="margin-top:1rem"><label>Root Cause</label><div style="color:#CBD5E1">${i.root_cause||'N/A'}</div></div>
            <div class="form-group"><label>Immediate Actions</label><div style="color:#CBD5E1">${i.immediate_actions||'N/A'}</div></div>
            <div class="form-group"><label>Reporter</label><div style="color:#CBD5E1">${i.reporter_name||'N/A'}</div></div>
        `);
    } catch(e) { console.error('View incident error:', e); }
}

async function showReportIncident() {
    showModal('Report Safety Incident', `
        <form onsubmit="submitIncident(event)">
            <div class="form-group"><label>Title *</label><input class="form-control" id="incident-title" required></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
                <div class="form-group"><label>Type *</label><select class="form-control" id="incident-type" required>
                    <option value="slip_trip_fall">Slip/Trip/Fall</option><option value="struck_by">Struck By</option>
                    <option value="electrical">Electrical</option><option value="ergonomic">Ergonomic</option>
                    <option value="vehicle">Vehicle</option><option value="caught_in">Caught In/Between</option>
                    <option value="fall_from_height">Fall From Height</option><option value="chemical">Chemical Exposure</option>
                    <option value="heat_cold">Heat/Cold Stress</option><option value="other">Other</option>
                </select></div>
                <div class="form-group"><label>Severity *</label><select class="form-control" id="incident-severity" required>
                    <option value="low">Low</option><option value="medium" selected>Medium</option>
                    <option value="high">High</option><option value="critical">Critical</option>
                </select></div>
            </div>
            <div class="form-group"><label>Description</label><textarea class="form-control" id="incident-description" rows="3"></textarea></div>
            <div class="form-group"><label>Location</label><input class="form-control" id="incident-location"></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
                <div class="form-group"><label><input type="checkbox" id="incident-near-miss"> Near Miss</label></div>
                <div class="form-group"><label><input type="checkbox" id="incident-osha"> OSHA Recordable</label></div>
            </div>
            <div class="form-group"><label>Root Cause</label><textarea class="form-control" id="incident-root-cause" rows="2"></textarea></div>
            <div class="form-group"><label>Immediate Actions Taken</label><textarea class="form-control" id="incident-actions" rows="2"></textarea></div>
            <button type="submit" class="btn btn-primary" style="width:100%;margin-top:1rem">Submit Report</button>
        </form>
    `);
}

async function submitIncident(e) {
    e.preventDefault();
    try {
        await api('/api/safety/incidents', {
            method: 'POST',
            body: JSON.stringify({
                title: document.getElementById('incident-title').value,
                incident_type: document.getElementById('incident-type').value,
                severity: document.getElementById('incident-severity').value,
                description: document.getElementById('incident-description').value,
                location_description: document.getElementById('incident-location').value,
                is_near_miss: document.getElementById('incident-near-miss').checked,
                is_osha_recordable: document.getElementById('incident-osha').checked,
                root_cause: document.getElementById('incident-root-cause').value,
                immediate_actions: document.getElementById('incident-actions').value,
            })
        });
        closeModal();
        loadSafetyIncidents();
        loadSafetyKPIs();
    } catch(e) { alert('Error: ' + e.message); }
}

async function loadSafetyInspections() {
    try {
        const items = await api('/api/safety/inspections');
        document.getElementById('safety-inspections-tbody').innerHTML = items.map(i => `<tr>
            <td>${new Date(i.conducted_at).toLocaleDateString()}</td>
            <td>${i.template_name||'Custom'}</td>
            <td>${i.inspector_name||'N/A'}</td>
            <td><span style="color:${(i.score||0)>=90?'#10B981':(i.score||0)>=70?'#F59E0B':'#EF4444'};font-weight:600">${i.score||0}%</span></td>
            <td><span class="badge" style="background:${i.status==='passed'?'#10B981':i.status==='failed'?'#EF4444':'#3B82F6'}">${i.status}</span></td>
            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${i.findings||'None'}</td>
        </tr>`).join('');
    } catch(e) { console.error('Inspections error:', e); }
}

async function loadToolboxTalks() {
    try {
        const items = await api('/api/safety/toolbox-talks');
        document.getElementById('safety-talks-tbody').innerHTML = items.map(t => `<tr>
            <td>${new Date(t.conducted_at).toLocaleDateString()}</td>
            <td><strong>${t.topic}</strong></td>
            <td>${t.category||'General'}</td>
            <td>${t.presenter_name||'N/A'}</td>
            <td>${t.duration_minutes} min</td>
            <td>${t.attendee_count}</td>
        </tr>`).join('');
    } catch(e) { console.error('Toolbox talks error:', e); }
}

async function loadSafetyTraining() {
    try {
        const items = await api('/api/safety/trainings');
        document.getElementById('safety-training-tbody').innerHTML = items.map(t => {
            const isExpiring = t.expiry_date && new Date(t.expiry_date) < new Date(Date.now() + 30*86400000);
            const isExpired = t.expiry_date && new Date(t.expiry_date) < new Date();
            const statusColor = isExpired ? '#EF4444' : isExpiring ? '#F59E0B' : '#10B981';
            const statusText = isExpired ? 'Expired' : isExpiring ? 'Expiring Soon' : t.status || 'Active';
            return `<tr>
                <td>${t.user_name||'N/A'}</td>
                <td><strong>${t.training_name}</strong></td>
                <td>${t.training_type||'N/A'}</td>
                <td>${t.provider||'N/A'}</td>
                <td>${t.completion_date ? new Date(t.completion_date).toLocaleDateString() : 'N/A'}</td>
                <td>${t.expiry_date ? new Date(t.expiry_date).toLocaleDateString() : 'N/A'}</td>
                <td><span class="badge" style="background:${statusColor}">${statusText}</span></td>
            </tr>`;
        }).join('');
    } catch(e) { console.error('Training error:', e); }
}

async function loadPPECompliance() {
    try {
        const items = await api('/api/safety/ppe');
        document.getElementById('safety-ppe-tbody').innerHTML = items.map(p => {
            const statusColors = {compliant:'#10B981', needs_inspection:'#F59E0B', replace:'#EF4444', non_compliant:'#EF4444'};
            return `<tr>
                <td>${p.user_name||'N/A'}</td>
                <td>${p.ppe_type}</td>
                <td><span class="badge" style="background:${statusColors[p.status]||'#64748B'}">${(p.status||'').replace(/_/g,' ')}</span></td>
                <td>${p.condition||'N/A'}</td>
                <td>${p.issued_at ? new Date(p.issued_at).toLocaleDateString() : 'N/A'}</td>
                <td>${p.last_inspected_at ? new Date(p.last_inspected_at).toLocaleDateString() : 'N/A'}</td>
                <td>${p.next_inspection_due ? new Date(p.next_inspection_due).toLocaleDateString() : 'N/A'}</td>
            </tr>`;
        }).join('');
    } catch(e) { console.error('PPE error:', e); }
}

async function loadCorrectiveActions() {
    try {
        const items = await api('/api/safety/corrective-actions');
        const prioColors = {critical:'#EF4444',high:'#F59E0B',medium:'#3B82F6',low:'#10B981'};
        const statusColors = {open:'#EF4444',in_progress:'#F59E0B',completed:'#10B981',verified:'#8B5CF6',overdue:'#EF4444'};
        document.getElementById('safety-corrective-tbody').innerHTML = items.map(c => `<tr>
            <td><strong>${c.title}</strong></td>
            <td>${c.incident_title||'N/A'}</td>
            <td>${c.assignee_name||'Unassigned'}</td>
            <td><span class="badge" style="background:${prioColors[c.priority]||'#64748B'}">${c.priority}</span></td>
            <td><span class="badge" style="background:${statusColors[c.status]||'#64748B'}">${(c.status||'').replace(/_/g,' ')}</span></td>
            <td>${c.due_date ? new Date(c.due_date).toLocaleDateString() : 'N/A'}</td>
        </tr>`).join('');
    } catch(e) { console.error('Corrective actions error:', e); }
}

async function loadOSHALogs() {
    try {
        const items = await api('/api/safety/osha-logs');
        document.getElementById('safety-osha-tbody').innerHTML = items.map(o => `<tr>
            <td><strong>${o.year}</strong></td>
            <td>${(o.total_hours_worked||0).toLocaleString()}</td>
            <td>${o.total_employees||0}</td>
            <td>${o.total_incidents||0}</td>
            <td>${o.recordable_cases||0}</td>
            <td>${o.dart_cases||0}</td>
            <td style="color:${(o.trir||0)<=3?'#10B981':'#EF4444'};font-weight:600">${(o.trir||0).toFixed(2)}</td>
            <td style="color:${(o.dart_rate||0)<=2?'#10B981':'#EF4444'};font-weight:600">${(o.dart_rate||0).toFixed(2)}</td>
            <td style="color:${(o.emr||1)<=1?'#10B981':'#F59E0B'};font-weight:600">${(o.emr||1).toFixed(2)}</td>
        </tr>`).join('');
    } catch(e) { console.error('OSHA logs error:', e); }
}

async function loadSafetyAI() {
    document.getElementById('safety-ai-summary').textContent = 'Analyzing safety data...';
    try {
        const result = await api('/api/safety/ai-risk-analysis', { method: 'POST', body: '{}' });
        document.getElementById('safety-ai-summary').textContent = result.summary || 'Analysis complete.';
        document.getElementById('safety-ai-risks').innerHTML = (result.risks||[]).map(r => `<li>${r}</li>`).join('');
        document.getElementById('safety-ai-recs').innerHTML = (result.recommendations||[]).map(r => `<li>${r}</li>`).join('');
        document.getElementById('safety-ai-score').textContent = result.safety_score || '--';
    } catch(e) {
        document.getElementById('safety-ai-summary').textContent = 'AI analysis unavailable. Try again later.';
    }
}

function switchHRTab(tab) {
    document.querySelectorAll('[data-hr-tab]').forEach(b => b.classList.remove('active'));
    document.querySelector(`[data-hr-tab="${tab}"]`).classList.add('active');
    ['employees','time','pto','onboarding','performance','training','compensation','skills','ai'].forEach(t => {
        const el = document.getElementById(`hr-tab-${t}`);
        if (el) el.classList.toggle('hidden', t !== tab);
    });
}

async function loadHRPage() {
    loadHRKPIs();
    loadHREmployees();
    loadHRTimeEntries();
    loadHRPTORequests();
    loadHROnboarding();
    loadHRReviews();
    loadHRTraining();
    loadHRCompensation();
    loadHRSkills();
}

async function loadHRKPIs() {
    try {
        const kpis = await api('/api/hr/kpis');
        document.getElementById('hr-stats-grid').innerHTML = `
            <div class="stat-card"><div class="stat-value" style="color:#3B82F6">${kpis.total_active||0}</div><div class="stat-label">Active Employees</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#10B981">${kpis.total_headcount||0}</div><div class="stat-label">Total Headcount</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#F59E0B">${kpis.on_leave||0}</div><div class="stat-label">On Leave</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#8B5CF6">${kpis.pending_pto||0}</div><div class="stat-label">Pending PTO Requests</div></div>
            <div class="stat-card"><div class="stat-value">${(kpis.avg_tenure_months||0).toFixed(0)} mo</div><div class="stat-label">Avg Tenure</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#EF4444">${kpis.expiring_licenses||0}</div><div class="stat-label">Expiring Licenses</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#06B6D4">${(kpis.turnover_rate||0).toFixed(1)}%</div><div class="stat-label">Turnover Rate</div></div>
            <div class="stat-card"><div class="stat-value">${Object.keys(kpis.departments||{}).length}</div><div class="stat-label">Departments</div></div>
        `;
    } catch(e) { console.error('HR KPIs error:', e); }
}

async function loadHREmployees() {
    try {
        const items = await api('/api/hr/employees');
        const statusColors = {active:'#10B981',on_leave:'#F59E0B',terminated:'#EF4444',suspended:'#EF4444',onboarding:'#3B82F6'};
        document.getElementById('hr-employees-tbody').innerHTML = items.map(emp => `<tr>
            <td>${emp.employee_id||'N/A'}</td>
            <td><strong>${emp.user_name||emp.full_name||'N/A'}</strong></td>
            <td>${emp.user_email||''}</td>
            <td>${emp.job_title||'N/A'}</td>
            <td>${emp.department||'N/A'}</td>
            <td><span class="badge" style="background:${statusColors[emp.status]||'#64748B'}">${(emp.status||'').replace(/_/g,' ')}</span></td>
            <td>${emp.hire_date ? new Date(emp.hire_date).toLocaleDateString() : 'N/A'}</td>
            <td>${emp.phone||'N/A'}</td>
            <td><button class="btn btn-sm" onclick="viewEmployee('${emp.id}')">View</button></td>
        </tr>`).join('');
    } catch(e) { console.error('HR employees error:', e); }
}

async function viewEmployee(id) {
    try {
        const e = await api(`/api/hr/employees/${id}`);
        showModal('Employee Profile', `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
                <div class="form-group"><label>Name</label><div style="color:#CBD5E1">${e.user_name||'N/A'}</div></div>
                <div class="form-group"><label>Employee ID</label><div style="color:#CBD5E1">${e.employee_id||'N/A'}</div></div>
                <div class="form-group"><label>Job Title</label><div style="color:#CBD5E1">${e.job_title||'N/A'}</div></div>
                <div class="form-group"><label>Department</label><div style="color:#CBD5E1">${e.department||'N/A'}</div></div>
                <div class="form-group"><label>Status</label><div style="color:#CBD5E1">${e.status||'N/A'}</div></div>
                <div class="form-group"><label>Employment Type</label><div style="color:#CBD5E1">${(e.employment_type||'').replace(/_/g,' ')}</div></div>
                <div class="form-group"><label>Hire Date</label><div style="color:#CBD5E1">${e.hire_date ? new Date(e.hire_date).toLocaleDateString() : 'N/A'}</div></div>
                <div class="form-group"><label>Phone</label><div style="color:#CBD5E1">${e.phone||'N/A'}</div></div>
            </div>
            <hr style="border-color:#334155;margin:1rem 0">
            <h4 style="color:#94A3B8;margin-bottom:0.5rem">Address</h4>
            <div style="color:#CBD5E1">${e.address||''} ${e.city||''}, ${e.state||''} ${e.zip_code||''}</div>
            <hr style="border-color:#334155;margin:1rem 0">
            <h4 style="color:#94A3B8;margin-bottom:0.5rem">Emergency Contact</h4>
            <div style="color:#CBD5E1">${e.emergency_contact_name||'N/A'} - ${e.emergency_contact_phone||'N/A'} (${e.emergency_contact_relation||'N/A'})</div>
            <hr style="border-color:#334155;margin:1rem 0">
            <h4 style="color:#94A3B8;margin-bottom:0.5rem">Licenses & Certifications</h4>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
                <div style="color:#CBD5E1">DL: ${e.drivers_license||'N/A'} (exp: ${e.dl_expiry ? new Date(e.dl_expiry).toLocaleDateString() : 'N/A'})</div>
                <div style="color:#CBD5E1">CDL: ${e.cdl_class||'N/A'}</div>
                <div style="color:#CBD5E1">Med Card: ${e.medical_card_expiry ? new Date(e.medical_card_expiry).toLocaleDateString() : 'N/A'}</div>
            </div>
            <hr style="border-color:#334155;margin:1rem 0">
            <h4 style="color:#94A3B8;margin-bottom:0.5rem">PTO Balances</h4>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.5rem">
                <div class="stat-card" style="padding:0.5rem;text-align:center"><div style="font-weight:700;color:#3B82F6">${e.pto_balance_vacation||0}h</div><div style="font-size:0.7rem;color:#94A3B8">Vacation</div></div>
                <div class="stat-card" style="padding:0.5rem;text-align:center"><div style="font-weight:700;color:#F59E0B">${e.pto_balance_sick||0}h</div><div style="font-size:0.7rem;color:#94A3B8">Sick</div></div>
                <div class="stat-card" style="padding:0.5rem;text-align:center"><div style="font-weight:700;color:#10B981">${e.pto_balance_personal||0}h</div><div style="font-size:0.7rem;color:#94A3B8">Personal</div></div>
            </div>
        `);
    } catch(e) { console.error('View employee error:', e); }
}

async function loadHRTimeEntries() {
    try {
        const items = await api('/api/hr/time-entries');
        document.getElementById('hr-time-tbody').innerHTML = items.map(t => `<tr>
            <td>${t.user_name||'N/A'}</td>
            <td>${new Date(t.clock_in).toLocaleDateString()}</td>
            <td>${new Date(t.clock_in).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</td>
            <td>${t.clock_out ? new Date(t.clock_out).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : '<em style="color:#F59E0B">Active</em>'}</td>
            <td>${t.break_minutes||0} min</td>
            <td style="font-weight:600">${t.total_hours ? t.total_hours.toFixed(1) : '--'}</td>
            <td style="color:#F59E0B">${t.overtime_hours ? t.overtime_hours.toFixed(1) : '0'}</td>
            <td>${t.entry_type||'regular'}</td>
            <td>${t.approved ? '<span style="color:#10B981">&#10003;</span>' : '<span style="color:#94A3B8">Pending</span>'}</td>
        </tr>`).join('');
    } catch(e) { console.error('Time entries error:', e); }
}

async function loadHRPTORequests() {
    try {
        const items = await api('/api/hr/pto-requests');
        const typeColors = {vacation:'#3B82F6',sick:'#F59E0B',personal:'#8B5CF6',bereavement:'#64748B',jury_duty:'#06B6D4',fmla:'#10B981',unpaid:'#94A3B8'};
        const statusColors = {pending:'#F59E0B',approved:'#10B981',denied:'#EF4444',cancelled:'#64748B'};
        document.getElementById('hr-pto-tbody').innerHTML = items.map(p => `<tr>
            <td>${p.user_name||'N/A'}</td>
            <td><span class="badge" style="background:${typeColors[p.pto_type]||'#64748B'}">${(p.pto_type||'').replace(/_/g,' ')}</span></td>
            <td>${new Date(p.start_date).toLocaleDateString()}</td>
            <td>${new Date(p.end_date).toLocaleDateString()}</td>
            <td>${p.total_days||1}</td>
            <td><span class="badge" style="background:${statusColors[p.status]||'#64748B'}">${p.status}</span></td>
            <td style="max-width:150px;overflow:hidden;text-overflow:ellipsis">${p.reason||'N/A'}</td>
            <td>${p.status==='pending' ? `<button class="btn btn-sm" style="background:#10B981" onclick="approvePTO('${p.id}')">Approve</button> <button class="btn btn-sm" style="background:#EF4444" onclick="denyPTO('${p.id}')">Deny</button>` : ''}</td>
        </tr>`).join('');
    } catch(e) { console.error('PTO error:', e); }
}

async function approvePTO(id) {
    try { await api(`/api/hr/pto-requests/${id}/approve`, {method:'PUT',body:'{}'}); loadHRPTORequests(); loadHRKPIs(); } catch(e) { alert('Error: '+e.message); }
}

async function denyPTO(id) {
    const reason = prompt('Denial reason:');
    if (reason === null) return;
    try { await api(`/api/hr/pto-requests/${id}/deny`, {method:'PUT',body:JSON.stringify({denial_reason:reason})}); loadHRPTORequests(); } catch(e) { alert('Error: '+e.message); }
}

async function loadHROnboarding() {
    try {
        const checklists = await api('/api/hr/onboarding-checklists');
        const container = document.getElementById('hr-onboarding-content');
        if (!checklists.length) { container.innerHTML = '<div class="card"><p style="color:#94A3B8">No onboarding checklists created yet.</p></div>'; return; }
        let html = '';
        for (const cl of checklists) {
            try {
                const tasks = await api(`/api/hr/onboarding-checklists/${cl.id}/tasks`);
                const completed = tasks.filter(t => t.status === 'completed').length;
                const pct = tasks.length > 0 ? Math.round(completed / tasks.length * 100) : 0;
                html += `<div class="card" style="margin-bottom:1rem">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
                        <div><h3 style="margin:0">${cl.name}</h3><small style="color:#94A3B8">${cl.department||'All'} - ${cl.description||''}</small></div>
                        <div style="text-align:right"><span style="font-size:1.5rem;font-weight:700;color:#3B82F6">${pct}%</span><br><small style="color:#94A3B8">${completed}/${tasks.length} complete</small></div>
                    </div>
                    <div style="background:#1E293B;border-radius:8px;height:8px;margin-bottom:1rem"><div style="background:#3B82F6;height:100%;border-radius:8px;width:${pct}%"></div></div>
                    <div>${tasks.map(t => `<div style="display:flex;align-items:center;padding:0.5rem;border-bottom:1px solid #334155">
                        <span style="margin-right:0.75rem;font-size:1.2rem;color:${t.status==='completed'?'#10B981':'#94A3B8'}">${t.status==='completed'?'&#9745;':'&#9744;'}</span>
                        <div style="flex:1"><strong>${t.title}</strong><br><small style="color:#94A3B8">${t.category||''} | Due: ${t.due_days} days</small></div>
                    </div>`).join('')}</div>
                </div>`;
            } catch(e) { /* skip */ }
        }
        container.innerHTML = html;
    } catch(e) { console.error('Onboarding error:', e); }
}

async function loadHRReviews() {
    try {
        const items = await api('/api/hr/reviews');
        const ratingColors = {exceeds_expectations:'#10B981',meets_expectations:'#3B82F6',needs_improvement:'#F59E0B',unsatisfactory:'#EF4444'};
        document.getElementById('hr-performance-tbody').innerHTML = items.map(r => `<tr>
            <td><strong>${r.user_name||'N/A'}</strong></td>
            <td>${r.period_start ? new Date(r.period_start).toLocaleDateString() : ''} - ${r.period_end ? new Date(r.period_end).toLocaleDateString() : ''}</td>
            <td><span class="badge" style="background:${ratingColors[r.overall_rating]||'#64748B'}">${(r.overall_rating||'N/A').replace(/_/g,' ')}</span></td>
            <td>${r.technical_score||'--'}</td>
            <td>${r.safety_score||'--'}</td>
            <td>${r.teamwork_score||'--'}</td>
            <td>${r.quality_score||'--'}</td>
            <td><span class="badge">${r.status}</span></td>
        </tr>`).join('');
    } catch(e) { console.error('Reviews error:', e); }
}

async function loadHRTraining() {
    try {
        const items = await api('/api/hr/trainings');
        document.getElementById('hr-training-tbody').innerHTML = items.map(t => `<tr>
            <td>${t.user_name||'N/A'}</td>
            <td><strong>${t.training_name}</strong></td>
            <td>${t.training_type||'N/A'}</td>
            <td>${t.provider||'N/A'}</td>
            <td>${t.completion_date ? new Date(t.completion_date).toLocaleDateString() : 'N/A'}</td>
            <td>${t.expiry_date ? new Date(t.expiry_date).toLocaleDateString() : 'N/A'}</td>
            <td>${t.required ? '<span style="color:#F59E0B">Required</span>' : 'Optional'}</td>
            <td><span class="badge" style="background:${t.status==='completed'?'#10B981':'#F59E0B'}">${t.status||'active'}</span></td>
        </tr>`).join('');
    } catch(e) { console.error('HR training error:', e); }
}

async function loadHRCompensation() {
    try {
        const items = await api('/api/hr/compensation');
        document.getElementById('hr-compensation-tbody').innerHTML = items.map(c => `<tr>
            <td>${c.user_name||'N/A'}</td>
            <td>${(c.pay_type||'').replace(/_/g,' ')}</td>
            <td style="font-weight:600">$${(c.hourly_rate||0).toFixed(2)}</td>
            <td>$${(c.overtime_rate||0).toFixed(2)}</td>
            <td>$${(c.per_diem||0).toFixed(2)}</td>
            <td>${new Date(c.effective_date).toLocaleDateString()}</td>
            <td>${c.is_current ? '<span style="color:#10B981">&#10003; Current</span>' : '<span style="color:#94A3B8">Previous</span>'}</td>
            <td>${c.reason||'N/A'}</td>
        </tr>`).join('');
    } catch(e) { console.error('Compensation error:', e); }
}

async function loadHRSkills() {
    try {
        const items = await api('/api/hr/skills');
        const container = document.getElementById('hr-skills-content');
        if (!items.length) { container.innerHTML = '<div class="card"><p style="color:#94A3B8">No skills data available.</p></div>'; return; }
        const byCategory = {};
        items.forEach(s => { const cat = s.category||'Other'; if (!byCategory[cat]) byCategory[cat] = []; byCategory[cat].push(s); });
        const levelColors = ['','#64748B','#3B82F6','#F59E0B','#10B981','#8B5CF6'];
        const levelLabels = ['','Beginner','Intermediate','Advanced','Expert','Master'];
        container.innerHTML = Object.entries(byCategory).map(([cat, skills]) => `
            <div class="card" style="margin-bottom:1rem">
                <h3 style="margin:0 0 1rem 0;color:#94A3B8;font-size:0.9rem;text-transform:uppercase">${cat}</h3>
                <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem">
                    ${skills.map(s => `<div style="background:#1E293B;border-radius:8px;padding:1rem">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem">
                            <strong>${s.skill_name}</strong>
                            ${s.certified ? '<span style="color:#10B981;font-size:0.75rem">&#9733; Certified</span>' : ''}
                        </div>
                        <div style="display:flex;gap:4px;margin-bottom:0.5rem">
                            ${[1,2,3,4,5].map(l => `<div style="width:100%;height:6px;border-radius:3px;background:${l <= s.proficiency_level ? levelColors[s.proficiency_level] : '#334155'}"></div>`).join('')}
                        </div>
                        <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:#94A3B8">
                            <span>${levelLabels[s.proficiency_level]||''}</span>
                            <span>${s.years_experience||0} years</span>
                        </div>
                        <div style="font-size:0.75rem;color:#64748B;margin-top:0.25rem">${s.user_name||''}</div>
                    </div>`).join('')}
                </div>
            </div>
        `).join('');
    } catch(e) { console.error('Skills error:', e); }
}

async function loadHRAI() {
    document.getElementById('hr-ai-summary').textContent = 'Analyzing workforce data...';
    try {
        const result = await api('/api/hr/ai-workforce-analytics', { method: 'POST', body: '{}' });
        document.getElementById('hr-ai-summary').textContent = result.summary || 'Analysis complete.';
        document.getElementById('hr-ai-insights').innerHTML = (result.insights||[]).map(i => `<li>${i}</li>`).join('');
        document.getElementById('hr-ai-recs').innerHTML = (result.recommendations||[]).map(r => `<li>${r}</li>`).join('');
        document.getElementById('hr-ai-score').textContent = result.workforce_score || '--';
    } catch(e) {
        document.getElementById('hr-ai-summary').textContent = 'AI analysis unavailable. Try again later.';
    }
}

if (token) { loadApp(); }

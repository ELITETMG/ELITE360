# Elite Technician Management Group

## Overview
The Elite Technician Management Group platform (formerly FTTH Contractor Platform) is a web-based command center designed to streamline and manage all aspects of fiber construction projects. Its core purpose is to provide a comprehensive solution for contractors, enabling efficient management of field crews, tasks, inspections, and billing. The platform aims to be an enterprise-grade solution for the fiber-to-the-home industry.

Key capabilities include:
- End-to-end project management with spatial task tracking.
- Advanced mapping features with Mapbox GL JS and GIS integrations.
- Comprehensive inspection workflows and reporting.
- Multi-format data import and export capabilities.
- Robust budget, material, and document management.
- Real-time activity feeds and KPI dashboards.
- AI-powered insights for project health, task prioritization, and anomaly detection.
- Full administrative control with role-based access.
- Integrated billing, invoicing, and payment tracking.
- A real-time dispatch board for crew and job scheduling.
- Complete Assets & Fleet Management with telematics integration.
- Safety Management module with OSHA compliance, incident tracking, PPE management.
- Human Resources module with employee profiles, time tracking, PTO, performance reviews, skills matrix.

## User Preferences
- Backend: FastAPI + SQLAlchemy (Python)
- Spatial: PostGIS with GeoAlchemy2
- Frontend: Vanilla JS + Mapbox GL JS maps (served from FastAPI)
- Auth: JWT tokens with PBKDF2 password hashing
- Map: Mapbox GL JS v3.3.0 with satellite-streets-v12 style, GL Draw, Geocoder, Turf.js

## System Architecture

### Core Design Principles
The platform is built as a single-page application (SPA) with a FastAPI backend and a PostgreSQL database leveraging PostGIS for spatial data. Frontend interactions are handled with vanilla JavaScript, utilizing Mapbox GL JS for advanced mapping functionalities. Authentication is managed via JWT tokens with robust password hashing.

### User Interface / User Experience
The platform features an enterprise UI with 19 dedicated navigation pages covering all functionalities: Dashboard, Projects, Map View, Tasks, Task Types, Inspections, Reports, Budget, Materials, Documents, Activity, Integrations, Billing, Dispatch, Assets, Fleet, Safety, HR, and Admin. The UI incorporates status pipelines with color-coded indicators for various workflows (e.g., tasks, invoices, dispatch jobs) to provide clear visual cues on progress and states.

### Technical Implementations
- **AI Integration**: Utilizes `gpt-4o-mini` via Replit AI Integrations for project insights, daily briefings, task recommendations, report summaries, and field data anomaly detection, integrated directly into dashboards, task panels, and reports.
- **GIS Mapping**: Employs Mapbox GL JS for interactive maps, including satellite imagery as the default basemap, a basemap switcher, layer controls (visibility, opacity, line width), and enhanced line/node rendering for fiber spans. It also supports KML/KMZ style preservation during import and along-line labels.
- **Data Import/Export**: A unified parser service handles multi-format imports (CSV, GeoJSON, KML, KMZ, Shapefile, DXF) with import history tracking. GIS integrations allow export to platforms like Vetro, ESRI ArcGIS, 3-GIS, Power BI, Deep Up, QGIS, and Google Earth in formats like GeoJSON, KML, Shapefile, and Power BI JSON.
- **Project Management**: Includes detailed task management with PostGIS geometry, status pipelines, priority levels, unit costs, and due dates. Work packages define project zones.
- **Financial Management**: Features comprehensive budget tracking with labor/material/equipment breakdowns, material inventory management with BOM tracking and low-stock alerts, and document versioning with check-in/check-out lock workflows.
- **Billing & Invoicing**: Implements a full invoicing system with auto-generated numbers, customizable line items, 27 pre-seeded rate cards for fiber construction, an approval workflow (Draft → Submitted → Approved → Paid), payment tracking, and change order management. Invoices can be auto-generated from approved tasks.
- **Dispatch**: Provides a real-time dispatch board with crew management, job scheduling, a timeline view with drag-and-drop functionality, and WebSocket-based real-time updates for job status changes. Jobs progress through statuses from UNASSIGNED to COMPLETED.
- **Reporting & Analytics**: Offers various reports (progress, productivity, crew performance), an activity feed, saved map views, spatial conflict detection (using PostGIS), route statistics, and a KPI dashboard (project health, SPI, CPI, completion %, budget utilization).
- **Access Control**: Implements Role-Based Access Control (RBAC) with eight distinct roles (super_admin, org_admin, pm, field_lead, crew_member, inspector, finance, client_viewer), restricting access to sensitive areas like the admin panel and inspection approvals.
- **Admin Panel**: Centralized control for user CRUD, role management, organization details, user profiles (phone, title, department, timezone, hourly rate, certifications, emergency contact), organization invitations, audit log viewing, and key admin statistics.
- **Assets & Fleet Management**: Full asset lifecycle tracking with categories, depreciation, GIS mapping of equipment/vehicles/technicians, fleet telematics with live map, vehicle maintenance scheduling, fuel tracking, and AI-powered asset insights.
- **Safety Management**: Comprehensive safety module with incident reporting (near-miss tracking, OSHA recordability), safety inspections with templates, toolbox talks with attendance tracking, training/certification management with expiry alerts, PPE compliance monitoring, corrective actions with root cause analysis, OSHA log metrics (TRIR, DART, EMR calculations), and AI-powered safety risk analysis.
- **Human Resources**: Full workforce management with employee profiles (emergency contacts, licenses, CDL), time tracking with overtime calculation, PTO request/approval workflow, onboarding checklists with progress tracking, performance reviews with multi-criteria scoring, training compliance, compensation history, visual skills matrix, and AI workforce analytics.

### Database Models
The database schema is comprehensive, including tables for organizations, users, user profiles, org invites, projects, work packages, task types, tasks (with spatial data), field entries, attachments, inspection templates, inspections, audit logs, import batches, project budgets, materials, task materials, documents, document versions, activities, saved map views, rate cards, invoices, invoice line items, change orders, payments, crews, crew members, dispatch jobs, asset categories, assets, fleet vehicles, technician locations, safety incidents, safety inspection templates, safety inspection records, toolbox talks, toolbox talk attendance, safety trainings, PPE compliance, corrective actions, OSHA logs, safety documents, employee profiles, time entries, PTO requests, onboarding checklists, onboarding tasks, performance reviews, HR training records, employee documents, compensation records, and skill entries. PostgreSQL with PostGIS extension is used for spatial queries.

## External Dependencies
- **Mapbox GL JS**: For interactive mapping, basemaps, and spatial data visualization.
- **OpenAI (via Replit AI Integrations)**: For AI-powered insights, recommendations, and anomaly detection.
- **PostgreSQL with PostGIS**: The primary database system, essential for spatial data storage and queries.
- **Vetro**: GIS integration for data export.
- **ESRI ArcGIS**: GIS integration for data export.
- **3-GIS**: GIS integration for data export.
- **Power BI**: Business intelligence integration for data export.
- **Deep Up**: GIS integration for data export.
- **QGIS**: GIS integration for data export.
- **Google Earth**: GIS integration for data export.
- **Turf.js**: For advanced geospatial analysis on the frontend.
- **Mapbox GL Draw**: For drawing and editing features on the map.
- **Mapbox Geocoder**: For geocoding functionalities.
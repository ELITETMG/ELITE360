# FTTH Contractor Platform

## Overview

Enterprise-grade web application for managing Fiber-To-The-Home (FTTH) construction projects. Built for contractors managing field crews, task pipelines, inspections, billing, and dispatch operations across fiber construction sites.

**Default Login:** `admin@ftth.com` / `admin123`

---

## Technology Stack

### Backend
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Web Framework | FastAPI | 0.129.0 | REST API + WebSocket server |
| ASGI Server | Uvicorn | 0.41.0 | Serves the application on port 5000 |
| ORM | SQLAlchemy | 2.0.46 | Database models and queries |
| Spatial ORM | GeoAlchemy2 | 0.18.1 | PostGIS geometry support |
| Database | PostgreSQL | (Neon-backed) | Primary data store |
| Spatial Extension | PostGIS | - | Geometry storage, spatial queries |
| Auth | python-jose | 3.5.0 | JWT token generation/validation |
| Password Hashing | passlib (bcrypt) | 1.7.4 / 5.0.0 | PBKDF2/bcrypt password hashing |
| AI Integration | openai | 2.21.0 | GPT-4o-mini for insights/analysis |
| GIS File Parsing | Fiona, Shapely, ezdxf, lxml | Various | Import CSV/GeoJSON/KML/KMZ/Shapefile/DXF |
| Templates | Jinja2 | 3.1.6 | HTML template rendering |
| Validation | Pydantic | 2.12.5 | Request/response data validation |

### Frontend
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| UI Framework | Vanilla JavaScript | ES6+ | Single-page application (SPA) |
| Maps | Mapbox GL JS | 3.3.0 | Interactive mapping with satellite imagery |
| Map Drawing | Mapbox GL Draw | 1.4.3 | Drawing/editing map features |
| Geocoding | Mapbox Geocoder | 5.0.2 | Address search and geocoding |
| Spatial Analysis | Turf.js | 7.x | Client-side geospatial calculations |
| Styling | Custom CSS | - | Dark theme enterprise UI |

### External Services
| Service | Purpose | Environment Variable |
|---------|---------|---------------------|
| PostgreSQL (Neon) | Database | `DATABASE_URL` |
| Mapbox | Maps, geocoding, satellite imagery | `MAPBOX_PUBLIC_TOKEN` |
| OpenAI | AI insights, briefings, anomaly detection | Managed via Replit AI Integration (`OPENAI_API_KEY`) |

---

## Project Structure

```
/
├── main.py                          # Application entry point, startup config, route registration
├── requirements.txt                 # Python dependencies (auto-managed)
├── pyproject.toml                   # Python project configuration
├── replit.md                        # Replit-specific project summary
├── README.md                        # This file
│
├── app/
│   ├── core/
│   │   ├── auth.py                  # JWT authentication, password hashing, get_current_user dependency
│   │   └── config.py                # Environment variable configuration (DATABASE_URL, SECRET_KEY, MAPBOX_PUBLIC_TOKEN)
│   │
│   ├── db/
│   │   └── session.py               # SQLAlchemy engine and session factory
│   │
│   ├── models/
│   │   ├── base.py                  # SQLAlchemy declarative base
│   │   └── models.py               # All database models (37 models, enums)
│   │
│   ├── api/                         # All API route handlers
│   │   ├── auth.py                  # /api/auth/* - Login, register, profile
│   │   ├── projects.py              # /api/projects/* - CRUD, import (CSV/GeoJSON/KML/KMZ/SHP/DXF)
│   │   ├── tasks.py                 # /api/tasks/* - Task CRUD with PostGIS geometry
│   │   ├── task_types.py            # /api/task-types/* - Task type definitions
│   │   ├── work_packages.py         # /api/work-packages/* - Work package management
│   │   ├── orgs.py                  # /api/orgs/* - Organization management
│   │   ├── dashboard.py             # /api/dashboard/* - Dashboard stats
│   │   ├── inspections.py           # /api/inspections/* - Inspection workflows
│   │   ├── reports.py               # /api/reports/* - Progress/productivity/crew reports
│   │   ├── budget.py                # /api/budget/* - Budget tracking
│   │   ├── materials.py             # /api/materials/* - Material inventory, BOM
│   │   ├── documents.py             # /api/documents/* - Document management with versioning
│   │   ├── activities.py            # /api/activities/* - Activity feed
│   │   ├── attachments.py           # /api/attachments/* - File uploads
│   │   ├── map_views.py             # /api/map-views/* - Saved map views
│   │   ├── analysis.py              # /api/analysis/* - KPI, spatial conflict detection, route stats
│   │   ├── ai.py                    # /api/ai/* - AI-powered insights, briefings, anomaly detection
│   │   ├── integrations.py          # /api/integrations/* - GIS export (Vetro, ESRI, 3-GIS, Power BI, etc.)
│   │   ├── admin.py                 # /api/admin/* - User CRUD, roles, org, audit log, invitations
│   │   ├── billing.py               # /api/billing/* - Invoices, line items, rate cards, payments
│   │   └── dispatch.py              # /api/dispatch/* - Crews, jobs, timeline, WebSocket real-time
│   │
│   ├── templates/
│   │   └── index.html               # Main SPA HTML template (all 15 pages)
│   │
│   └── static/
│       ├── css/
│       │   └── style.css            # Full application styles (~1860 lines)
│       ├── js/
│       │   └── app.js               # Full application JavaScript (~3840 lines)
│       └── uploads/                 # User file uploads directory
```

---

## Database Models (37 total)

### Core Models
- **Org** - Organizations (contractor, isp_owner)
- **User** - Users with role-based access (8 roles)
- **OrgMember** - Organization membership
- **UserProfile** - Extended user profiles (phone, title, department, certs, hourly rate)
- **OrgInvite** - Organization invitations

### Project Management
- **Project** - Construction projects with owner/executing org
- **WorkPackage** - Project zones/packages
- **TaskType** - Configurable task types with unit costs
- **Task** - Tasks with PostGIS geometry, status pipeline, priorities
- **FieldEntry** - Field data collection entries
- **Attachment** - File attachments

### Inspections
- **InspectionTemplate** - Configurable inspection checklists
- **Inspection** - Inspection records with pending/in_progress/passed/failed status

### Financial
- **ProjectBudget** - Budget tracking (labor/material/equipment breakdowns)
- **RateCard** - 27 pre-seeded fiber construction rate cards
- **Invoice** - Invoices with approval workflow (Draft -> Submitted -> Approved -> Paid)
- **InvoiceLineItem** - Individual invoice line items
- **Payment** - Payment records
- **ChangeOrder** - Change order tracking

### Materials & Documents
- **Material** - Material inventory with BOM tracking
- **TaskMaterial** - Material usage per task
- **Document** - Documents with check-in/check-out locking
- **DocumentVersion** - Document version history

### Operations
- **Crew** - Field crews with skills, vehicle, color coding
- **CrewMember** - Crew membership
- **DispatchJob** - Dispatch jobs (7-status pipeline: UNASSIGNED -> COMPLETED)

### System
- **AuditLog** - Audit trail for all actions
- **ImportBatch** - Import history tracking
- **Activity** - Activity feed entries
- **SavedMapView** - Saved map view configurations

### Enums
- **RoleName** - 8 roles: super_admin, org_admin, pm, field_lead, crew_member, inspector, finance, client_viewer
- **ProjectStatus** - planning, active, on_hold, completed, archived
- **TaskStatus** - not_started, in_progress, submitted, approved, billed, rework, failed_inspection
- **InvoiceStatus** - draft, submitted, approved, rejected, paid, partially_paid, voided
- **DispatchJobStatus** - unassigned, scheduled, en_route, on_site, in_progress, completed, cancelled
- **InspectionStatus** - pending, in_progress, passed, failed
- **OrgType** - contractor, isp_owner

---

## API Routes Summary

| Prefix | Module | Endpoints | Key Features |
|--------|--------|-----------|-------------|
| `/api/auth` | auth.py | 4 | Login, register, me, update profile |
| `/api/projects` | projects.py | 8+ | CRUD, multi-format import, spatial data |
| `/api/tasks` | tasks.py | 6+ | CRUD with PostGIS geometry |
| `/api/task-types` | task_types.py | 4 | Task type CRUD |
| `/api/work-packages` | work_packages.py | 4 | Work package CRUD |
| `/api/orgs` | orgs.py | 3 | Org management |
| `/api/dashboard` | dashboard.py | 2 | Dashboard stats |
| `/api/inspections` | inspections.py | 6+ | Templates, inspections, status workflow |
| `/api/reports` | reports.py | 4 | Progress, productivity, crew reports |
| `/api/budget` | budget.py | 4 | Budget CRUD |
| `/api/materials` | materials.py | 5 | Inventory, BOM, low-stock alerts |
| `/api/documents` | documents.py | 6+ | Versioning, check-in/check-out |
| `/api/activities` | activities.py | 2 | Activity feed |
| `/api/attachments` | attachments.py | 3 | File upload/download |
| `/api/map-views` | map_views.py | 4 | Saved map view CRUD |
| `/api/analysis` | analysis.py | 4 | KPIs, route stats, spatial conflicts |
| `/api/ai` | ai.py | 5 | Insights, briefings, recommendations, anomaly detection |
| `/api/integrations` | integrations.py | 2 | GIS export (Vetro, ESRI, 3-GIS, etc.) |
| `/api/admin` | admin.py | 15 | Users, profiles, roles, org, invites, audit log |
| `/api/billing` | billing.py | 22 | Invoices, line items, rate cards, payments, change orders |
| `/api/dispatch` | dispatch.py | 16 | Crews, jobs, timeline, reschedule, WebSocket |

---

## Environment Variables

These must be set for the application to function:

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `DATABASE_URL` | Yes | PostgreSQL connection string with PostGIS | `postgresql://localhost/ftth` |
| `SECRET_KEY` | Yes | JWT signing key (change for production!) | Hard-coded dev default |
| `MAPBOX_PUBLIC_TOKEN` | Yes | Mapbox GL JS public access token for maps | Empty string |
| `OPENAI_API_KEY` | No | OpenAI API key for AI features | Managed by Replit integration |

### Setting up on Replit
- `DATABASE_URL` is automatically provided by Replit's built-in PostgreSQL database
- `MAPBOX_PUBLIC_TOKEN` is stored as a Replit secret
- `OPENAI_API_KEY` is managed by the Replit AI integration (python_openai_ai_integrations)

---

## Running the Application

### On Replit
The application runs automatically via the configured workflow:
```bash
python main.py
```
This starts Uvicorn on `0.0.0.0:5000`.

### On Another Host / Local Development

1. **Install Python 3.11+**

2. **Install PostgreSQL with PostGIS extension**
   ```bash
   # Ubuntu/Debian
   sudo apt install postgresql postgresql-contrib postgis

   # macOS
   brew install postgresql postgis
   ```

3. **Create database and enable PostGIS**
   ```sql
   CREATE DATABASE ftth;
   \c ftth
   CREATE EXTENSION postgis;
   ```

4. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   If `requirements.txt` doesn't exist, install these core packages:
   ```bash
   pip install fastapi uvicorn sqlalchemy geoalchemy2 psycopg2-binary python-jose passlib bcrypt python-multipart jinja2 aiofiles openai fiona shapely ezdxf lxml openpyxl httpx numpy pydantic
   ```

5. **Set environment variables**
   ```bash
   export DATABASE_URL="postgresql://user:password@localhost:5432/ftth"
   export SECRET_KEY="your-secure-secret-key-here"
   export MAPBOX_PUBLIC_TOKEN="pk.your_mapbox_token_here"
   export OPENAI_API_KEY="sk-your-openai-key-here"  # Optional, for AI features
   ```

6. **Run the application**
   ```bash
   python main.py
   ```
   The app starts on `http://localhost:5000`

---

## Migration Guide (Moving Off Replit)

### Critical Steps

1. **Database Export**
   ```bash
   pg_dump --format=custom --no-owner --no-acl $DATABASE_URL > ftth_backup.dump
   ```
   On your new host:
   ```bash
   createdb ftth
   psql ftth -c "CREATE EXTENSION postgis;"
   pg_restore --no-owner --no-acl -d ftth ftth_backup.dump
   ```

2. **Environment Variables**
   - Copy all secrets from Replit's Secrets tab
   - `DATABASE_URL` must point to your new PostgreSQL instance (must have PostGIS)
   - `SECRET_KEY` should be regenerated for production
   - `MAPBOX_PUBLIC_TOKEN` get from your Mapbox account (mapbox.com)
   - `OPENAI_API_KEY` get from your OpenAI account (platform.openai.com)

3. **File Uploads**
   - Copy the `app/static/uploads/` directory to your new server
   - Ensure the directory is writable by the application process

4. **PostGIS Requirement**
   - The database MUST have PostGIS extension enabled
   - Tasks store geometries as PostGIS geometry columns
   - Spatial queries (conflict detection, route stats) require PostGIS functions
   - If PostGIS is unavailable, the Task model's `geometry` column and spatial query endpoints will fail

5. **Production Server**
   Replace `uvicorn` with a production ASGI server:
   ```bash
   # Option 1: Uvicorn with workers
   uvicorn main:app --host 0.0.0.0 --port 5000 --workers 4

   # Option 2: Gunicorn with Uvicorn workers
   pip install gunicorn
   gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:5000
   ```

6. **CORS Configuration**
   Update the CORS settings in `main.py` if deploying frontend and backend on different domains:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://your-domain.com"],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

7. **Cache Headers**
   The app sets `Cache-Control: no-cache` headers via middleware in `main.py`. This is important because the frontend is an SPA served from the same server. If you add a CDN or reverse proxy, configure it accordingly.

8. **WebSocket Support**
   The dispatch board uses WebSocket for real-time updates at `/api/dispatch/ws`. Ensure your reverse proxy (nginx, Caddy, etc.) supports WebSocket connections:
   ```nginx
   # Nginx WebSocket config
   location /api/dispatch/ws {
       proxy_pass http://127.0.0.1:5000;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "upgrade";
   }
   ```

### Things That Will Need Updating

| Item | Location | What to Change |
|------|----------|---------------|
| Database URL | `app/core/config.py` | Update `DATABASE_URL` env var |
| JWT Secret | `app/core/config.py` | Set strong `SECRET_KEY` env var |
| Mapbox Token | `app/core/config.py` | Set `MAPBOX_PUBLIC_TOKEN` env var |
| OpenAI Key | Environment | Set `OPENAI_API_KEY` env var (currently via Replit integration) |
| CORS Origins | `main.py` | Update allowed origins for your domain |
| Static Files | `main.py` | Consider serving via nginx/CDN in production |
| Upload Path | `main.py` | `app/static/uploads/` - ensure writable + persistence |
| Startup Seed | `main.py` | `@app.on_event("startup")` creates demo data on first run |

### Docker Deployment (Optional)

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libpq-dev gcc libgdal-dev libgeos-dev libproj-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "4"]
```

```bash
docker build -t ftth-platform .
docker run -p 5000:5000 \
  -e DATABASE_URL="postgresql://..." \
  -e SECRET_KEY="..." \
  -e MAPBOX_PUBLIC_TOKEN="pk...." \
  ftth-platform
```

---

## Authentication & Authorization

### JWT Tokens
- Tokens are generated on login via `/api/auth/login`
- Token includes `sub` (user ID) claim
- Frontend stores token in `localStorage` as `ftth_token`
- All API requests include `Authorization: Bearer <token>` header

### Role-Based Access Control (RBAC)
| Role | Access Level |
|------|-------------|
| super_admin | Full platform access |
| org_admin | Full org access + admin panel |
| pm | Project management, task assignment |
| field_lead | Field operations, crew management |
| crew_member | Task execution, field data entry |
| inspector | Inspections, quality control |
| finance | Billing, invoices, budget |
| client_viewer | Read-only project views |

### Admin-Only Endpoints
Admin endpoints (`/api/admin/*`) are restricted to `super_admin` and `org_admin` roles via the `_require_admin` helper in `app/api/admin.py`.

---

## Key Features by Page

| Page | Description |
|------|-------------|
| Dashboard | Project stats, KPIs (SPI, CPI, completion %), AI briefings |
| Projects | Project CRUD, multi-format import |
| Map View | Mapbox GL JS with satellite imagery, drawing tools, layer controls |
| Tasks | Task management with PostGIS geometry, status pipeline |
| Task Types | Configurable task type definitions with unit costs |
| Inspections | Inspection templates, scheduling, pass/fail workflow |
| Reports | Progress, productivity, and crew performance reports |
| Budget | Labor/material/equipment budget tracking |
| Materials | Inventory management, BOM tracking, low-stock alerts |
| Documents | Document management with versioning and check-in/check-out |
| Activity | Real-time activity feed |
| Integrations | GIS export to Vetro, ESRI, 3-GIS, Power BI, QGIS, Google Earth |
| Billing | Invoices, 27 rate cards, payments, approval workflow |
| Dispatch | Timeline board, crew management, drag-and-drop scheduling, WebSocket |
| Admin | User CRUD, role management, org settings, audit log |

---

## Troubleshooting

### Common Issues

**PostGIS not available:**
The app will fail on startup if PostGIS isn't enabled. Run `CREATE EXTENSION postgis;` in your database.

**Maps not loading:**
Ensure `MAPBOX_PUBLIC_TOKEN` is set. Get a free token from mapbox.com.

**AI features not working:**
Set `OPENAI_API_KEY`. On Replit, this is managed automatically via the AI integration.

**Sidebar nav items not visible:**
All 15 nav items are in a scrollable sidebar. Scroll down to see Billing, Dispatch, and Admin.

**CSS not updating:**
The app sends `Cache-Control: no-cache` headers. If using a CDN, purge cache or hard-refresh the browser.

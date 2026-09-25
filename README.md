# FastaFasta 🚗

**FastaFasta** is a full-stack ride-hailing web application built to work like Uber — riders request trips, nearby drivers get matched in real time, both parties track the trip live on a map, fares are calculated automatically, and trips complete with ratings and payment.

- **Backend:** Django + Django REST Framework + Django Channels (WebSockets for live tracking/matching) + Celery (background jobs / scheduler)
- **Frontend:** React (Vite) + Google Maps JavaScript API
- **Database:** PostgreSQL (+ PostGIS recommended for geo queries) — SQLite works for local dev
- **Realtime:** WebSockets (Django Channels + Redis channel layer)
- **Auth:** JWT (SimpleJWT)

---

## 1. Core Features

### Rider
- Register/login (rider role)
- Set pickup & drop-off on Google Map (autocomplete + drag pins)
- See live fare estimate before requesting (distance × rate + base fare + time)
- Request a ride, get matched with nearest available driver
- Track driver's live location moving toward pickup, then toward destination
- Cancel ride (with cancellation window/fee logic)
- Pay (mock wallet / cash / card placeholder)
- Rate driver + trip history

### Driver
- Register/login (driver role) with vehicle details
- Toggle Online/Offline (go online to receive ride requests)
- Send live GPS location (WebSocket) while online
- Receive ride requests (accept/decline) within a timeout window
- Navigate to pickup → start trip → complete trip
- View earnings, trip history
- Rate rider

### System
- Real-time driver-rider matching (nearest driver first, using Haversine/PostGIS distance)
- Live location broadcast via WebSocket groups (per-trip channel)
- Dynamic fare calculation service (base fare + per-km + per-minute + surge multiplier)
- Scheduled/background jobs (Celery beat) — e.g., auto-cancel unmatched requests, timeout stale ride offers, driver payout batching
- Trip state machine: `REQUESTED → ACCEPTED → ARRIVED → IN_PROGRESS → COMPLETED / CANCELLED`

---

## 2. Full Project Structure

```
fastafasta/
│
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env
│   │
│   ├── core/                        # Main Django project (settings/urls)
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py                  # main url.py -> includes api.urls
│   │   ├── asgi.py                  # ASGI entrypoint for Channels/WebSockets
│   │   └── wsgi.py
│   │
│   └── api/                         # single "api" app (as requested)
│       ├── __init__.py
│       ├── apps.py
│       ├── admin.py
│       ├── models.py                # User, Driver, Rider, Vehicle, Trip, Location, Payment, Rating...
│       ├── serializers.py           # DRF serializers for every model
│       ├── services.py              # business logic: fare calc, matching engine, geo utils
│       ├── views.py                 # DRF APIViews/ViewSets
│       ├── permissions.py           # IsDriver, IsRider custom permissions
│       ├── consumers.py             # Channels WebSocket consumers (live location, trip updates)
│       ├── routing.py               # websocket url routing
│       ├── tasks.py                 # Celery tasks (auto-cancel, payouts, notifications)
│       ├── scheduler.py             # Celery beat schedule / periodic task registration
│       ├── urls.py                  # api app url.py -> included by core/urls.py
│       └── migrations/
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── .env
    ├── public/
    │   └── favicon.svg
    │
    └── src/
        ├── main.jsx
        ├── App.jsx                  # src/app.jsx — routes
        │
        ├── services/
        │   ├── api.js                # axios instance + REST calls
        │   ├── socket.js              # WebSocket client wrapper
        │   └── maps.js                # Google Maps loader + geolocation helpers
        │
        ├── context/
        │   └── AuthContext.jsx
        │
        ├── hooks/
        │   ├── useGeolocation.js
        │   └── useRideSocket.js
        │
        ├── components/
        │   ├── layout/ (Navbar.jsx, Footer.jsx, ProtectedRoute.jsx)
        │   ├── map/ (MapView.jsx, LocationSearchInput.jsx, DriverMarker.jsx, RoutePolyline.jsx)
        │   ├── ride/ (FareEstimateCard.jsx, RideRequestModal.jsx, DriverOfferCard.jsx, TripStatusBar.jsx)
        │   └── common/ (Button.jsx, Spinner.jsx, Rating.jsx)
        │
        ├── pages/
        │   ├── HomePage.jsx           # landing page (from homepage as requested)
        │   ├── LoginPage.jsx
        │   ├── RegisterPage.jsx
        │   ├── rider/
        │   │   ├── RiderDashboard.jsx  # book a ride, map
        │   │   ├── RideTracking.jsx    # live trip tracking
        │   │   ├── RideHistory.jsx
        │   │   └── RiderProfile.jsx
        │   ├── driver/
        │   │   ├── DriverDashboard.jsx # online/offline toggle, incoming requests
        │   │   ├── ActiveTrip.jsx
        │   │   ├── Earnings.jsx
        │   │   └── DriverProfile.jsx
        │   └── NotFound.jsx
        │
        └── styles/
            ├── web.css                # desktop styles
            └── mobile.css             # responsive/mobile styles
```

---

## 3. Build Order

Because this is a large system, it will be delivered in stages, in this order:

1. ✅ README.md (this file) — project overview + structure
2. `backend/api/models.py` — all data models
3. `backend/api/serializers.py`
4. `backend/api/services.py` — fare engine + matching engine
5. `backend/api/views.py`
6. `backend/api/urls.py` + `core/urls.py`
7. `backend/core/settings.py`
8. `backend/api/consumers.py` + `routing.py` (WebSockets)
9. `backend/api/tasks.py` + `backend/api/scheduler.py` (Celery)
10. `frontend/index.html`, `src/main.jsx`, `src/App.jsx`
11. `frontend/src/services/api.js`, `socket.js`, `maps.js`
12. `frontend/src/pages/HomePage.jsx`
13. `frontend/src/pages/LoginPage.jsx`, `RegisterPage.jsx`
14. Remaining rider/driver pages + components + CSS

---

## 4. Environment Variables

**backend/.env**
```
SECRET_KEY=change-me
DEBUG=True
DATABASE_URL=postgres://postgres:postgres@localhost:5432/fastafasta
REDIS_URL=redis://localhost:6379/0
GOOGLE_MAPS_SERVER_KEY=your_server_side_key   # used for distance matrix/geocoding
BASE_FARE=100
RATE_PER_KM=45
RATE_PER_MIN=5
CANCELLATION_FEE=50
DRIVER_SEARCH_RADIUS_KM=5
```

**frontend/.env**
```
VITE_API_BASE_URL=http://localhost:8000/api
VITE_WS_BASE_URL=ws://localhost:8000/ws
VITE_GOOGLE_MAPS_API_KEY=your_browser_side_key
```

---

## 5. Quick Start

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
daphne -b 0.0.0.0 -p 8000 core.asgi:application   # ASGI server for WebSockets
celery -A core worker -l info                     # separate terminal
celery -A core beat -l info                       # separate terminal
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

---

Next file: **`backend/api/models.py`**

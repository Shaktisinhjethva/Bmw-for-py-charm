# BioWaste Pro — Biomedical Waste Management Platform

A full-stack Python Flask web application for hospital biomedical waste management with CPCB-compliant features.

## Features

- **Home Page** — 3D animated waste category cube, platform stats, feature overview
- **Certified Collectors** — Profiles of CPCB-certified BMW handlers with ratings & vehicle info
- **Hospital Login** — Secure authentication portal for hospitals
- **Hospital Dashboard** — Real-time waste monitoring sidebar, charts, alerts, collection dispatch
- **Live Vehicle Tracking** — GPS map tracking of collection vehicles (simulated)
- **Waste Guidelines** — BMW Rules 2016 compliance information

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5001** in your browser.

## Demo Login

| Email | Password |
|-------|----------|
| apollo@hospital.com | hospital123 |
| max@hospital.com | hospital123 |

## Pages

| Route | Description |
|-------|-------------|
| `/` | Landing page with 3D effects |
| `/collectors` | Certified waste collectors |
| `/hospital/login` | Hospital login |
| `/hospital/dashboard` | Waste control & tracking dashboard |
| `/about` | BMW guidelines & regulations |

## Tech Stack

- **Backend:** Python, Flask, SQLite
- **Frontend:** HTML5, CSS3 (3D transforms, glassmorphism), JavaScript
- **Charts:** Chart.js
- **Maps:** Leaflet.js (OpenStreetMap)

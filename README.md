# RunQuest

Turn your daily runs into a massive multiplayer turf war. Claim your grid. Defend your territory. Become a legend.

RunQuest is a gamified fitness web application built with Python (Flask) and JavaScript. It uses real-time GPS tracking to map your runs onto a global grid system. The more you run, the more territory you capture and color with your unique player neon hue!

## Features
- **GPS Territory Tracking**: Converts real-time GPS coordinates into 150x150m grid cells using Geohashes.
- **Global Multiplayer Map**: Interactive CartoDB Dark Matter map where players compete to capture and take over territories.
- **Inactivity Decay**: Don't stop running! Your captured cells will start decaying and turn neutral after 3 days of inactivity.
- **Backend Anti-Cheat**: Secure Haversine distance calculations verify your speed in real-time. If you travel over 25 km/h, your run is flagged and captures are disabled.
- **Live Leaderboard**: 24-hour rotating leaderboard to track who is currently dominating the city.
- **Premium Glassmorphism UI**: Beautiful, responsive dark-mode interface with neon accents, custom animations, and a unified design system.

## Tech Stack
- **Backend**: Python, Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF
- **Frontend**: HTML5, CSS3, JavaScript, Leaflet.js (Map), latlon-geohash (Grid Logic)
- **Database**: SQLite (Development)

## Local Setup
1. Clone the repository.
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment.
4. Install dependencies: `pip install -r requirements.txt`
5. Run the app: `python app.py`
6. Access at `http://127.0.0.1:5000`

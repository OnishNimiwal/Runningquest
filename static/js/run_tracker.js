let watchId = null;
let isRunning = false;
let isPaused = false;
let startTime = null;
let durationSeconds = 0;
let timerInterval = null;
let totalDistanceKm = 0;
let routeCoordinates = []; // Array of [lng, lat] for GeoJSON
let capturedCells = new Set();
let capturesCount = 0;

// UI Elements
const distanceDisplay = document.getElementById('distanceDisplay');
const timeDisplay = document.getElementById('timeDisplay');
const capturesDisplay = document.getElementById('capturesDisplay');
const startBtn = document.getElementById('startBtn');
const pauseBtn = document.getElementById('pauseBtn');
const stopBtn = document.getElementById('stopBtn');

// Map Setup
const map = L.map('map').setView([0, 0], 2);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap'
}).addTo(map);

const routeLine = L.polyline([], {color: '#38bdf8', weight: 5}).addTo(map);
const marker = L.circleMarker([0, 0], {radius: 8, color: 'white', fillColor: '#3b82f6', fillOpacity: 1, weight: 2}).addTo(map);
let mapInitialized = false;

// Haversine formula to calculate distance in km
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

function updateTimer() {
    durationSeconds++;
    const mins = Math.floor(durationSeconds / 60).toString().padStart(2, '0');
    const secs = (durationSeconds % 60).toString().padStart(2, '0');
    timeDisplay.textContent = `${mins}:${secs}`;
}

function startRun() {
    if (!navigator.geolocation) {
        alert("Geolocation is not supported by your browser");
        return;
    }
    
    isRunning = true;
    isPaused = false;
    startBtn.style.display = 'none';
    pauseBtn.style.display = 'block';
    stopBtn.style.display = 'block';

    timerInterval = setInterval(updateTimer, 1000);

    watchId = navigator.geolocation.watchPosition((position) => {
        if (isPaused) return;

        const lat = position.coords.latitude;
        const lng = position.coords.longitude;
        
        // Update Map
        marker.setLatLng([lat, lng]);
        routeLine.addLatLng([lat, lng]);
        
        if (!mapInitialized) {
            map.setView([lat, lng], 16);
            mapInitialized = true;
        } else {
            map.panTo([lat, lng]);
        }

        // Calculate Distance
        if (routeCoordinates.length > 0) {
            const lastPos = routeCoordinates[routeCoordinates.length - 1];
            // GeoJSON stores [lng, lat] so lastPos[1] is lat
            const dist = calculateDistance(lastPos[1], lastPos[0], lat, lng);
            totalDistanceKm += dist;
            distanceDisplay.textContent = totalDistanceKm.toFixed(2);
        }

        // GeoJSON uses [lng, lat]
        routeCoordinates.push([lng, lat]);

        if (typeof Geohash !== 'undefined') {
            const currentHash = Geohash.encode(lat, lng, 7);
            if (!capturedCells.has(currentHash)) {
                capturedCells.add(currentHash);
                captureTerritory(currentHash, lat, lng);
            }
        }

    }, (error) => {
        console.warn('ERROR(' + error.code + '): ' + error.message);
    }, {
        enableHighAccuracy: true,
        maximumAge: 5000,
        timeout: 5000
    });
}

function pauseRun() {
    isPaused = !isPaused;
    if (isPaused) {
        clearInterval(timerInterval);
        pauseBtn.textContent = 'Resume';
        pauseBtn.style.background = '#22c55e';
    } else {
        timerInterval = setInterval(updateTimer, 1000);
        pauseBtn.textContent = 'Pause';
        pauseBtn.style.background = '#eab308';
    }
}

async function stopRun() {
    if(confirm("Are you sure you want to finish this run?")) {
        clearInterval(timerInterval);
        if (watchId) navigator.geolocation.clearWatch(watchId);
        
        startBtn.style.display = 'none';
        pauseBtn.style.display = 'none';
        stopBtn.textContent = 'Saving...';
        stopBtn.disabled = true;

        const geojson = {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "LineString",
                "coordinates": routeCoordinates
            }
        };

        const payload = {
            distance: parseFloat(totalDistanceKm.toFixed(2)),
            duration: durationSeconds,
            route_data: JSON.stringify(geojson)
        };

        try {
            const response = await fetch('/api/save_run', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                alert("Run saved successfully!");
                window.location.href = '/dashboard';
            } else {
                alert("Failed to save run.");
                stopBtn.textContent = 'Finish & Save';
                stopBtn.disabled = false;
            }
        } catch (error) {
            console.error('Error saving run:', error);
            alert("Network error. Could not save run.");
            stopBtn.textContent = 'Finish & Save';
            stopBtn.disabled = false;
        }
    }
}

// Event Listeners
startBtn.addEventListener('click', startRun);
pauseBtn.addEventListener('click', pauseRun);
stopBtn.addEventListener('click', stopRun);

// Try to get initial location just to center the map before starting
if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition((position) => {
        if (!isRunning) {
            map.setView([position.coords.latitude, position.coords.longitude], 15);
            marker.setLatLng([position.coords.latitude, position.coords.longitude]);
        }
    });
}

async function captureTerritory(cell_id, lat, lng) {
    try {
        const response = await fetch('/api/capture_cell', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({cell_id: cell_id})
        });
        const data = await response.json();
        
        if (data.status === 'captured') {
            capturesCount++;
            capturesDisplay.textContent = capturesCount;
            L.circle([lat, lng], {radius: 75, color: data.color, fillOpacity: 0.3}).addTo(map);
        }
    } catch (e) {
        console.error('Capture failed:', e);
    }
}

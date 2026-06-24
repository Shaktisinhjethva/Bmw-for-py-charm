document.addEventListener('DOMContentLoaded', () => {
    // Countdown timers for job offers
    function updateCountdowns() {
        document.querySelectorAll('.countdown-timer').forEach(el => {
            const deadline = new Date(el.dataset.deadline.replace(' ', 'T'));
            const now = new Date();
            const diff = Math.max(0, Math.floor((deadline - now) / 1000));
            const mins = Math.floor(diff / 60);
            const secs = diff % 60;
            el.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
            if (diff <= 0) {
                el.textContent = 'Expired';
                el.classList.add('expired');
            } else if (diff <= 60) {
                el.classList.add('urgent');
            }
        });
    }
    updateCountdowns();
    setInterval(updateCountdowns, 1000);

    // Accept job
    document.querySelectorAll('.accept-job').forEach(btn => {
        btn.addEventListener('click', async () => {
            btn.disabled = true;
            btn.textContent = 'Accepting...';
            const res = await fetch(`/api/collector/accept/${btn.dataset.id}`, { method: 'POST' });
            if (res.ok) location.reload();
            else {
                alert('Failed to accept job');
                btn.disabled = false;
            }
        });
    });

    // Reject job
    document.querySelectorAll('.reject-job').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('Decline this pickup? It will be reassigned to another collector.')) return;
            const res = await fetch(`/api/collector/reject/${btn.dataset.id}`, { method: 'POST' });
            if (res.ok) location.reload();
        });
    });

    // Complete trip
    document.querySelector('.complete-trip')?.addEventListener('click', async () => {
        const id = document.querySelector('.complete-trip').dataset.id;
        if (!confirm('Mark pickup as complete at hospital?')) return;
        const res = await fetch(`/api/collector/complete/${id}`, { method: 'POST' });
        if (res.ok) location.reload();
    });

    // Map for active trip
    let map, vehicleMarker, hospitalMarker, routeLine;
    const mapEl = document.getElementById('collector-map');

    if (mapEl && typeof ACTIVE_JOB !== 'undefined' && ACTIVE_JOB && typeof L !== 'undefined') {
        const cLat = ACTIVE_JOB.vehicle_lat || COLLECTOR.lat;
        const cLng = ACTIVE_JOB.vehicle_lng || COLLECTOR.lng;
        const hLat = ACTIVE_JOB.hospital_lat;
        const hLng = ACTIVE_JOB.hospital_lng;

        map = L.map('collector-map').setView([(cLat + hLat) / 2, (cLng + hLng) / 2], 12);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap'
        }).addTo(map);

        const vehicleIcon = L.divIcon({
            html: '<div class="map-vehicle-marker">&#128666;</div>',
            className: '', iconSize: [40, 40], iconAnchor: [20, 20]
        });
        const hospitalIcon = L.divIcon({
            html: '<div class="map-hospital-marker">&#127973;</div>',
            className: '', iconSize: [36, 36], iconAnchor: [18, 18]
        });

        vehicleMarker = L.marker([cLat, cLng], { icon: vehicleIcon }).addTo(map).bindPopup('Your Vehicle');
        hospitalMarker = L.marker([hLat, hLng], { icon: hospitalIcon }).addTo(map).bindPopup(`<b>${ACTIVE_JOB.hospital_name}</b><br>Pickup Point`);
        routeLine = L.polyline([[cLat, cLng], [hLat, hLng]], {
            color: '#f59e0b', weight: 4, dashArray: '10, 10', opacity: 0.8
        }).addTo(map);
        map.fitBounds(L.latLngBounds([[cLat, cLng], [hLat, hLng]]), { padding: [40, 40] });

        // Simulate vehicle movement toward hospital
        let progress = 0;
        setInterval(() => {
            if (progress >= 1) return;
            progress += 0.02;
            const lat = cLat + (hLat - cLat) * progress;
            const lng = cLng + (hLng - cLng) * progress;
            vehicleMarker.setLatLng([lat, lng]);
            routeLine.setLatLngs([[lat, lng], [hLat, hLng]]);

            fetch('/api/collector/location', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lat, lng })
            });

            const etaEl = document.getElementById('eta-countdown');
            if (etaEl && ACTIVE_JOB.eta_minutes) {
                const remaining = Math.max(1, Math.round(ACTIVE_JOB.eta_minutes * (1 - progress)));
                etaEl.textContent = remaining;
            }
        }, 8000);
    }

    // Poll for new messages
    setInterval(async () => {
        const res = await fetch('/api/collector/messages');
        if (res.ok) {
            const messages = await res.json();
            const oldCount = document.querySelectorAll('.job-card').length;
            if (messages.length > oldCount) location.reload();
        }
    }, 5000);

    // ── Disposal Video Upload ──────────────────────────────────────────
    
    // Get current location for geotag
    const getLocationBtn = document.getElementById('get-location-btn');
    const latInput = document.getElementById('disposal-latitude');
    const lngInput = document.getElementById('disposal-longitude');
    const locationStatus = document.getElementById('location-status');

    if (getLocationBtn) {
        getLocationBtn.addEventListener('click', () => {
            if (!navigator.geolocation) {
                locationStatus.textContent = '❌ Geolocation not supported in your browser';
                locationStatus.style.color = 'var(--danger)';
                return;
            }

            getLocationBtn.disabled = true;
            getLocationBtn.textContent = 'Getting location...';
            locationStatus.textContent = '📍 Fetching location...';
            locationStatus.style.color = 'var(--text-secondary)';

            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const lat = position.coords.latitude.toFixed(6);
                    const lng = position.coords.longitude.toFixed(6);
                    latInput.value = lat;
                    lngInput.value = lng;
                    locationStatus.textContent = `✓ Location captured: ${lat}, ${lng}`;
                    locationStatus.style.color = 'var(--accent)';
                    getLocationBtn.disabled = false;
                    getLocationBtn.textContent = '📍 Get Current Location';
                },
                (error) => {
                    locationStatus.textContent = `❌ ${error.message}`;
                    locationStatus.style.color = 'var(--danger)';
                    getLocationBtn.disabled = false;
                    getLocationBtn.textContent = '📍 Get Current Location';
                },
                { enableHighAccuracy: true, timeout: 10000 }
            );
        });
    }

    // Handle photo file selection
    const photoInput = document.getElementById('disposal-photos');
    const photoPreview = document.getElementById('photo-preview');

    if (photoInput) {
        photoInput.addEventListener('change', (e) => {
            photoPreview.innerHTML = '';
            const files = Array.from(e.target.files);
            
            if (files.length > 0) {
                photoPreview.style.display = 'grid';
                files.forEach((file, idx) => {
                    const reader = new FileReader();
                    reader.onload = (event) => {
                        const div = document.createElement('div');
                        div.className = 'photo-preview-item';
                        div.innerHTML = `
                            <img src="${event.target.result}" alt="Photo ${idx + 1}">
                            <button type="button" class="photo-remove-btn" data-idx="${idx}">×</button>
                        `;
                        photoPreview.appendChild(div);

                        // Remove photo
                        div.querySelector('.photo-remove-btn').addEventListener('click', () => {
                            const dt = new DataTransfer();
                            Array.from(photoInput.files).forEach((f, i) => {
                                if (i !== idx) dt.items.add(f);
                            });
                            photoInput.files = dt.files;
                            div.remove();
                            if (photoPreview.children.length === 0) {
                                photoPreview.style.display = 'none';
                            }
                        });
                    };
                    reader.readAsDataURL(file);
                });
            } else {
                photoPreview.style.display = 'none';
            }
        });
    }

    // Upload disposal video
    const uploadBtn = document.getElementById('upload-disposal-btn');
    const clearBtn = document.getElementById('clear-disposal-form');
    const videoInput = document.getElementById('disposal-video');
    const addressInput = document.getElementById('disposal-address');
    const progressDiv = document.getElementById('upload-progress');
    const progressBar = document.getElementById('progress-bar');
    const uploadStatus = document.getElementById('upload-status');

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            videoInput.value = '';
            photoInput.value = '';
            latInput.value = '';
            lngInput.value = '';
            addressInput.value = '';
            document.getElementById('disposal-notes').value = '';
            photoPreview.innerHTML = '';
            photoPreview.style.display = 'none';
            progressDiv.style.display = 'none';
        });
    }

    if (uploadBtn) {
        uploadBtn.addEventListener('click', async () => {
            if (!videoInput.files.length) {
                alert('Please select a video file');
                return;
            }

            if (!latInput.value || !lngInput.value) {
                alert('Please capture location first');
                return;
            }

            const activeJob = document.querySelector('[data-id]');
            if (!activeJob) {
                alert('No active job found');
                return;
            }

            const formData = new FormData();
            formData.append('video', videoInput.files[0]);
            
            // Add all selected photos
            Array.from(photoInput.files).forEach(file => {
                formData.append('photos[]', file);
            });

            formData.append('latitude', parseFloat(latInput.value));
            formData.append('longitude', parseFloat(lngInput.value));
            formData.append('address', addressInput.value);
            formData.append('hospital_id', ACTIVE_JOB.hospital_id);
            formData.append('request_id', ACTIVE_JOB.id);

            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';
            progressDiv.style.display = 'block';
            progressBar.style.width = '0%';

            try {
                const xhr = new XMLHttpRequest();
                
                xhr.upload.addEventListener('progress', (e) => {
                    if (e.lengthComputable) {
                        const percentComplete = (e.loaded / e.total) * 100;
                        progressBar.style.width = percentComplete + '%';
                        uploadStatus.textContent = `Uploading... ${Math.round(percentComplete)}%`;
                    }
                });

                xhr.addEventListener('load', () => {
                    if (xhr.status === 200) {
                        const response = JSON.parse(xhr.responseText);
                        uploadStatus.textContent = '✓ ' + response.message;
                        uploadStatus.style.color = 'var(--accent)';
                        progressBar.style.width = '100%';
                        
                        // Reset form after 2 seconds
                        setTimeout(() => {
                            clearBtn.click();
                            alert('Disposal video uploaded successfully and sent to hospital!');
                        }, 2000);
                    } else {
                        const error = JSON.parse(xhr.responseText);
                        uploadStatus.textContent = '❌ ' + (error.error || 'Upload failed');
                        uploadStatus.style.color = 'var(--danger)';
                        uploadBtn.disabled = false;
                        uploadBtn.textContent = '⭐ Upload Video & Photos';
                    }
                });

                xhr.addEventListener('error', () => {
                    uploadStatus.textContent = '❌ Network error';
                    uploadStatus.style.color = 'var(--danger)';
                    uploadBtn.disabled = false;
                    uploadBtn.textContent = '⭐ Upload Video & Photos';
                });

                xhr.open('POST', '/api/disposal/upload');
                xhr.send(formData);
            } catch (error) {
                console.error('Upload error:', error);
                alert('Error uploading file: ' + error.message);
                uploadBtn.disabled = false;
                uploadBtn.textContent = '⭐ Upload Video & Photos';
            }
        });
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const catColors = {
        yellow: '#eab308', red: '#dc2626', white: '#e2e8f0',
        blue: '#3b82f6', black: '#64748b'
    };

    // Trend chart
    const trendCtx = document.getElementById('trendChart');
    if (trendCtx && typeof TREND_DATA !== 'undefined') {
        new Chart(trendCtx, {
            type: 'line',
            data: {
                labels: TREND_DATA.map(d => d.day.slice(5)),
                datasets: [{
                    label: 'Waste (kg)',
                    data: TREND_DATA.map(d => d.total),
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16,185,129,0.1)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#10b981',
                    pointRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' }, beginAtZero: true }
                }
            }
        });
    }

    // Pie chart
    const pieCtx = document.getElementById('pieChart');
    if (pieCtx && typeof CATEGORY_DATA !== 'undefined' && typeof CATEGORIES !== 'undefined') {
        new Chart(pieCtx, {
            type: 'doughnut',
            data: {
                labels: CATEGORIES.map(c => c.name),
                datasets: [{
                    data: CATEGORIES.map(c => CATEGORY_DATA[c.id] || 0),
                    backgroundColor: CATEGORIES.map(c => catColors[c.id] || '#64748b'),
                    borderColor: '#0a0e17',
                    borderWidth: 3,
                    hoverOffset: 8,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#94a3b8', padding: 12, usePointStyle: true } }
                }
            }
        });
    }

    // Log waste
    const wasteForm = document.getElementById('waste-log-form');
    if (wasteForm) {
        wasteForm.addEventListener('submit', async e => {
            e.preventDefault();
            const res = await fetch('/api/waste/log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    category: document.getElementById('waste-category').value,
                    quantity: parseFloat(document.getElementById('waste-quantity').value),
                    notes: document.getElementById('waste-notes')?.value || ''
                })
            });
            if (res.ok) location.reload();
        });
    }

    // Delete waste log
    document.querySelectorAll('.delete-log').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('Remove this waste entry? Use this if you entered the wrong amount.')) return;
            const res = await fetch(`/api/waste/delete/${btn.dataset.id}`, { method: 'POST' });
            if (res.ok) location.reload();
        });
    });

    // Correct waste log modal
    const modal = document.getElementById('correct-modal');
    document.querySelectorAll('.edit-log').forEach(btn => {
        btn.addEventListener('click', () => {
            document.getElementById('correct-log-id').value = btn.dataset.id;
            document.getElementById('correct-quantity').value = btn.dataset.qty;
            document.getElementById('correct-category').value = btn.dataset.cat;
            modal.style.display = 'flex';
        });
    });
    document.getElementById('cancel-correct')?.addEventListener('click', () => modal.style.display = 'none');
    modal?.addEventListener('click', e => { if (e.target === modal) modal.style.display = 'none'; });

    document.getElementById('correct-form')?.addEventListener('submit', async e => {
        e.preventDefault();
        const id = document.getElementById('correct-log-id').value;
        const res = await fetch(`/api/waste/correct/${id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                quantity: parseFloat(document.getElementById('correct-quantity').value),
                category: document.getElementById('correct-category').value
            })
        });
        if (res.ok) location.reload();
    });

    // Schedule pickup
    const scheduleForm = document.getElementById('pickup-schedule-form');
    if (scheduleForm) {
        const dtInput = document.getElementById('pickup-time');
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        dtInput.min = now.toISOString().slice(0, 16);

        scheduleForm.addEventListener('submit', async e => {
            e.preventDefault();
            const res = await fetch('/api/pickup/schedule', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    scheduled_time: document.getElementById('pickup-time').value,
                    notes: document.getElementById('pickup-notes')?.value || ''
                })
            });
            if (res.ok) location.reload();
            else {
                const err = await res.json();
                alert(err.error || 'Failed to schedule');
            }
        });
    }

    document.querySelectorAll('.btn-cancel-schedule').forEach(btn => {
        btn.addEventListener('click', async () => {
            const res = await fetch(`/api/pickup/cancel/${btn.dataset.id}`, { method: 'POST' });
            if (res.ok) location.reload();
        });
    });

    // Request collection
    const requestBtn = document.getElementById('request-collection-btn');
    if (requestBtn) {
        requestBtn.addEventListener('click', async () => {
            requestBtn.disabled = true;
            requestBtn.textContent = 'Dispatching...';
            const res = await fetch('/api/collection/request', { method: 'POST' });
            if (res.ok) location.reload();
            else {
                const err = await res.json();
                alert(err.error || 'Request failed');
                requestBtn.disabled = false;
                requestBtn.innerHTML = '&#128666; Request Collection Vehicle';
            }
        });
    }

    // Map tracking
    let map, vehicleMarker;
    const hospLat = typeof HOSPITAL_LAT !== 'undefined' ? HOSPITAL_LAT : 28.6289;
    const hospLng = typeof HOSPITAL_LNG !== 'undefined' ? HOSPITAL_LNG : 77.2065;

    function initMap(lat, lng) {
        const mapEl = document.getElementById('map');
        if (!mapEl || typeof L === 'undefined') return;

        map = L.map('map').setView([hospLat, hospLng], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap'
        }).addTo(map);

        const hospitalIcon = L.divIcon({
            html: '<div style="background:#ef4444;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;border:3px solid white;box-shadow:0 2px 10px rgba(0,0,0,0.5);">&#127973;</div>',
            className: '', iconSize: [32, 32], iconAnchor: [16, 16]
        });
        const vehicleIcon = L.divIcon({
            html: '<div style="background:#10b981;width:36px;height:36px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px;border:3px solid white;box-shadow:0 4px 15px rgba(16,185,129,0.5);">&#128666;</div>',
            className: '', iconSize: [36, 36], iconAnchor: [18, 18]
        });

        L.marker([hospLat, hospLng], { icon: hospitalIcon }).addTo(map).bindPopup('<b>Hospital</b><br>Collection Point');
        if (lat && lng) {
            vehicleMarker = L.marker([lat, lng], { icon: vehicleIcon }).addTo(map).bindPopup('<b>Collection Vehicle</b>');
            map.fitBounds(L.latLngBounds([[hospLat, hospLng], [lat, lng]]), { padding: [50, 50] });
        }
    }

    async function updateTracking() {
        if (!ACTIVE_REQUEST) return;
        const res = await fetch(`/api/collection/track/${ACTIVE_REQUEST.id}`);
        if (!res.ok) return;
        const data = await res.json();
        const etaEl = document.getElementById('eta-display');
        if (etaEl) etaEl.textContent = `${data.eta_minutes} min`;
        const statusEl = document.getElementById('tracking-status');
        if (statusEl) statusEl.textContent = data.status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        if (vehicleMarker && data.vehicle_lat && data.vehicle_lng) {
            vehicleMarker.setLatLng([data.vehicle_lat, data.vehicle_lng]);
        }
    }

    if (typeof ACTIVE_REQUEST !== 'undefined' && ACTIVE_REQUEST) {
        document.getElementById('tracking-section').style.display = 'block';
        initMap(ACTIVE_REQUEST.vehicle_lat, ACTIVE_REQUEST.vehicle_lng);
        setInterval(updateTracking, 5000);
    }

    document.getElementById('complete-btn')?.addEventListener('click', async () => {
        const id = document.getElementById('complete-btn').dataset.id;
        if (!confirm('Mark collection complete? Waste logs will be cleared.')) return;
        const res = await fetch(`/api/collection/complete/${id}`, { method: 'POST' });
        if (res.ok) location.reload();
    });

    // ── Disposal Videos ──────────────────────────────────────────
    
    async function loadDisposalVideos() {
        try {
            const res = await fetch('/api/disposal/videos');
            if (!res.ok) return;
            
            const videos = await res.json();
            const listDiv = document.getElementById('disposal-videos-list');
            const noVideosDiv = document.getElementById('no-disposal-videos');
            
            if (!listDiv) return;
            
            if (videos.length === 0) {
                listDiv.style.display = 'none';
                if (noVideosDiv) noVideosDiv.style.display = 'block';
                document.getElementById('disposal-video-count').textContent = '0';
                return;
            }
            
            listDiv.style.display = 'grid';
            if (noVideosDiv) noVideosDiv.style.display = 'none';
            
            listDiv.innerHTML = videos.map(v => `
                <div class="disposal-video-card" data-video-id="${v.id}">
                    <div class="video-thumbnail">
                        <span style="font-size: 2.5rem;">&#127907;</span>
                        <div class="video-play-icon">▶</div>
                    </div>
                    <div class="video-card-body">
                        <div class="video-collector-info">
                            <div class="video-collector-avatar">${v.collector_name[0]}</div>
                            <div class="video-collector-details">
                                <span class="video-collector-name">${v.collector_name}</span>
                                <span class="video-collector-cert">${v.certification_id}</span>
                            </div>
                        </div>
                        <div class="video-status ${v.status}">${v.status.charAt(0).toUpperCase() + v.status.slice(1)}</div>
                        <div class="video-meta">
                            <div class="video-meta-item">
                                <span class="video-meta-label">Uploaded</span>
                                <span class="video-meta-value">${new Date(v.uploaded_at).toLocaleDateString()}</span>
                            </div>
                            <div class="video-meta-item">
                                <span class="video-meta-label">Size</span>
                                <span class="video-meta-value">${v.file_size_mb?.toFixed(1) || '—'} MB</span>
                            </div>
                        </div>
                        ${v.address ? `<div class="video-location">📍 ${v.address}</div>` : ''}
                        <div class="video-actions">
                            <button class="btn btn-primary btn-sm view-video-btn" data-id="${v.id}">View</button>
                            ${v.status === 'pending' ? `<button class="btn btn-secondary btn-sm review-video-btn" data-id="${v.id}">Review</button>` : ''}
                        </div>
                    </div>
                </div>
            `).join('');
            
            document.getElementById('disposal-video-count').textContent = videos.length;
            
            // Add event listeners
            document.querySelectorAll('.view-video-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    showDisposalVideoModal(parseInt(btn.dataset.id));
                });
            });
            
            document.querySelectorAll('.review-video-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    showReviewModal(parseInt(btn.dataset.id));
                });
            });
            
            document.querySelectorAll('.disposal-video-card').forEach(card => {
                card.addEventListener('click', () => {
                    showDisposalVideoModal(parseInt(card.dataset.videoId));
                });
            });
        } catch (error) {
            console.error('Error loading disposal videos:', error);
        }
    }

    async function showDisposalVideoModal(videoId) {
        try {
            const res = await fetch(`/api/disposal/video/${videoId}`);
            if (!res.ok) return;
            
            const video = await res.json();
            const contentDiv = document.getElementById('video-modal-content');
            
            if (!contentDiv) return;
            
            contentDiv.innerHTML = `
                <div class="video-modal-player">
                    <video controls style="width: 100%; height: 100%;">
                        <source src="/upload/disposal/${videoId}/video" type="video/mp4">
                        Your browser does not support the video tag.
                    </video>
                </div>
                
                <div class="video-modal-info">
                    <div class="info-group">
                        <h4>Collector</h4>
                        <p>${video.collector_name}</p>
                        <p style="font-size: 0.85rem; margin-top: 0.3rem;">${video.certification_id}</p>
                    </div>
                    <div class="info-group">
                        <h4>Status</h4>
                        <p class="video-status ${video.status}">${video.status.toUpperCase()}</p>
                        ${video.reviewed_at ? `<p style="font-size: 0.85rem; margin-top: 0.3rem;">Reviewed: ${new Date(video.reviewed_at).toLocaleString()}</p>` : ''}
                    </div>
                    <div class="info-group">
                        <h4>Uploaded</h4>
                        <p>${new Date(video.uploaded_at).toLocaleString()}</p>
                    </div>
                    <div class="info-group">
                        <h4>Location</h4>
                        <p>${video.address || (video.latitude && video.longitude ? `${video.latitude.toFixed(4)}, ${video.longitude.toFixed(4)}` : 'N/A')}</p>
                    </div>
                    <div class="info-group">
                        <h4>File Size</h4>
                        <p>${video.file_size_mb?.toFixed(2) || '—'} MB</p>
                    </div>
                    <div class="info-group">
                        <h4>Vehicle</h4>
                        <p>${video.vehicle_no || '—'}</p>
                    </div>
                </div>
                
                ${video.photos && video.photos.length > 0 ? `
                <div class="video-photos-section">
                    <h4>Geotag Photos</h4>
                    <div class="video-photos-gallery">
                        ${video.photos.map((photo, idx) => `
                            <div class="photo-item" onclick="openPhotoFullscreen('${photo}')">
                                <img src="/upload/disposal/${videoId}/photo/${photo}" alt="Photo ${idx + 1}">
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : '<p class="text-muted">No photos attached.</p>'}
                
                ${video.hospital_notes ? `
                <div style="margin-top: 1.5rem; padding: 1rem; background: rgba(255,255,255,0.04); border-radius: 8px; border-left: 3px solid var(--collector);">
                    <h4 style="margin-bottom: 0.5rem;">Hospital Notes</h4>
                    <p>${video.hospital_notes}</p>
                </div>
                ` : ''}
                
                <div class="video-modal-actions">
                    ${video.status === 'pending' ? `
                    <button class="btn btn-primary" onclick="showReviewModal(${videoId})">Review Video</button>
                    ` : ''}
                    <button class="btn btn-secondary" onclick="closeDisposalVideoModal()">Close</button>
                </div>
            `;
            
            document.getElementById('disposal-video-modal').style.display = 'flex';
        } catch (error) {
            console.error('Error loading video details:', error);
            alert('Failed to load video details');
        }
    }

    function closeDisposalVideoModal() {
        document.getElementById('disposal-video-modal').style.display = 'none';
    }

    document.getElementById('close-video-modal')?.addEventListener('click', closeDisposalVideoModal);
    document.getElementById('disposal-video-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'disposal-video-modal') closeDisposalVideoModal();
    });

    async function showReviewModal(videoId) {
        document.getElementById('review-disposal-modal').style.display = 'flex';
        document.getElementById('review-disposal-modal').dataset.videoId = videoId;
    }

    document.getElementById('review-disposal-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const videoId = document.getElementById('review-disposal-modal').dataset.videoId;
        const status = document.getElementById('review-status').value;
        const notes = document.getElementById('review-notes').value;
        
        const res = await fetch(`/api/disposal/video/${videoId}/review`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status, notes })
        });
        
        if (res.ok) {
            alert(`Video marked as ${status}`);
            document.getElementById('review-disposal-modal').style.display = 'none';
            closeDisposalVideoModal();
            loadDisposalVideos();
        } else {
            alert('Failed to review video');
        }
    });

    document.getElementById('cancel-review')?.addEventListener('click', () => {
        document.getElementById('review-disposal-modal').style.display = 'none';
    });

    document.getElementById('review-disposal-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'review-disposal-modal') {
            document.getElementById('review-disposal-modal').style.display = 'none';
        }
    });

    // Load disposal videos on page load
    loadDisposalVideos();
    setInterval(loadDisposalVideos, 10000);  // Refresh every 10 seconds
});


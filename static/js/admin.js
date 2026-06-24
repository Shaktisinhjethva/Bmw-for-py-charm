document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('collector-modal');
    const form = document.getElementById('collector-form');

    document.getElementById('add-collector-btn')?.addEventListener('click', () => {
        document.getElementById('modal-title').textContent = 'Add Collector';
        document.getElementById('collector-id').value = '';
        form.reset();
        document.getElementById('col-certified').checked = true;
        document.getElementById('col-expiry').value = '2026-12-31';
        modal.style.display = 'flex';
    });

    document.querySelectorAll('.edit-collector').forEach(btn => {
        btn.addEventListener('click', () => {
            const c = JSON.parse(btn.dataset.collector);
            document.getElementById('modal-title').textContent = 'Edit Collector';
            document.getElementById('collector-id').value = c.id;
            document.getElementById('col-name').value = c.name;
            document.getElementById('col-email').value = c.email;
            document.getElementById('col-cert').value = c.certification_id;
            document.getElementById('col-vehicle').value = c.vehicle_no || '';
            document.getElementById('col-phone').value = c.phone || '';
            document.getElementById('col-expiry').value = c.cert_expiry || '2026-12-31';
            document.getElementById('col-certified').checked = !!c.is_certified;
            modal.style.display = 'flex';
        });
    });

    document.getElementById('cancel-modal')?.addEventListener('click', () => modal.style.display = 'none');
    modal?.addEventListener('click', e => { if (e.target === modal) modal.style.display = 'none'; });

    form?.addEventListener('submit', async e => {
        e.preventDefault();
        const id = document.getElementById('collector-id').value;
        const payload = {
            name: document.getElementById('col-name').value,
            email: document.getElementById('col-email').value,
            certification_id: document.getElementById('col-cert').value,
            vehicle_no: document.getElementById('col-vehicle').value,
            phone: document.getElementById('col-phone').value,
            cert_expiry: document.getElementById('col-expiry').value,
            is_certified: document.getElementById('col-certified').checked,
            password: document.getElementById('col-password').value || 'collector123'
        };

        const url = id ? `/api/admin/collector/${id}` : '/api/admin/collector';
        const method = id ? 'PUT' : 'POST';
        const res = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) location.reload();
        else {
            const err = await res.json();
            alert(err.error || 'Save failed');
        }
    });

    document.querySelectorAll('.delete-collector').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('Delete this collector permanently?')) return;
            const res = await fetch(`/api/admin/collector/${btn.dataset.id}`, { method: 'DELETE' });
            if (res.ok) location.reload();
        });
    });
});

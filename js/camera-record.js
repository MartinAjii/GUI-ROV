/* Recording runs on the laptop; refreshing the GUI does not stop it. */
(() => {
  const panels = [...document.querySelectorAll('[data-record-camera]')];
  let state = {};
  let busy = false;
  let filesSignature = '';
  const actionErrors = {};
  const api = '/api/recordings';

  async function request(path = '', method = 'GET') {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(api + path, { method, signal: controller.signal, cache: 'no-store' });
      if (response.status === 404) throw new Error('Buka GUI laptop di http://127.0.0.1:8080 setelah menjalankan perekam.');
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Permintaan rekaman gagal.');
      return data;
    } finally {
      clearTimeout(timeout);
    }
  }

  function render(data) {
    if (data.storage !== 'laptop') throw new Error('Jalankan GUI dari program perekam laptop, bukan alamat Raspberry Pi.');
    state = data.cameras;
    const signature = JSON.stringify(data.files);
    panels.forEach(panel => {
      const id = panel.dataset.recordCamera;
      const camera = state[id];
      const button = panel.querySelector('button');
      const label = panel.querySelector('.record-status');
      const seconds = Math.floor(camera.duration_seconds);
      const duration = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
      button.disabled = false;
      button.textContent = camera.recording ? 'Stop rekam' : 'Mulai rekam';
      button.setAttribute('aria-pressed', String(camera.recording));
      panel.classList.toggle('is-recording', camera.recording);
      label.textContent = actionErrors[id] || camera.error || (camera.recording ? `● REC ${duration}` : camera.filename ? `Tersimpan di laptop · ${duration}` : 'Siap merekam ke laptop');
      panel.querySelector('.record-destination').textContent = `Folder laptop: ${data.output_directory}`;
      if (signature !== filesSignature) {
        const list = panel.querySelector('ul');
        list.replaceChildren();
        data.files.filter(file => file.filename.startsWith(id + '_')).forEach(file => {
          const item = document.createElement('li');
          const link = document.createElement('a');
          link.href = `${api}/download/${encodeURIComponent(file.filename)}`;
          link.download = file.filename;
          link.textContent = `${file.filename} (${(file.size_bytes / 1048576).toFixed(1)} MB)`;
          item.append(link);
          list.append(item);
        });
        if (!list.children.length) {
          const item = document.createElement('li');
          item.textContent = 'Belum ada rekaman selesai.';
          list.append(item);
        }
      }
    });
    filesSignature = signature;
  }

  function showError(error) {
    panels.forEach(panel => {
      panel.querySelector('.record-status').textContent = `${error.message || 'Perekam tidak terhubung.'} Pastikan program perekam laptop masih berjalan.`;
      panel.querySelector('button').disabled = true;
    });
  }

  async function poll() {
    if (!busy) {
      busy = true;
      try { render(await request()); }
      catch (error) { showError(error); }
      finally { busy = false; }
    }
    setTimeout(poll, 1000);
  }

  if (CONFIG.camera.mode !== 'network') {
    panels.forEach(panel => {
      panel.querySelector('.record-status').textContent = 'Rekam tersedia untuk kamera Raspberry Pi (mode network).';
    });
    return;
  }

  panels.forEach(panel => {
    panel.querySelector('button').addEventListener('click', async () => {
      if (busy) return;
      const id = panel.dataset.recordCamera;
      if (!state[id]) return;
      busy = true;
      delete actionErrors[id];
      panels.forEach(p => { p.querySelector('button').disabled = true; });
      try {
        await request(`/${id}/${state[id].recording ? 'stop' : 'start'}`, 'POST');
        render(await request());
      } catch (error) {
        actionErrors[id] = error.message;
        // Reconcile state first: a timed-out start may already be recording.
        try { render(await request()); } catch (_) { showError(error); }
        panel.querySelector('.record-status').textContent = error.message;
      } finally { busy = false; }
    });
  });
  poll();
})();

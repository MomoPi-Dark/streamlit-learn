# GOAL.md — Background Job/Worker Architecture (NTE Sentiment Analyzer)

## Konteks

App Streamlit multi-page (`BasePage`, `PageLoader`, custom routing) buat skripsi
"Analisis Sentimen pada Game Neverness to Everness dengan Algoritma Naive Bayes".
Pipeline: scraping → Sastrawi preprocessing → TF-IDF → SMOTE (training only) → MultinomialNB.

Saat ini preprocessing jalan pakai background threading dengan live progress UI,
tapi ada isu multi-browser safety yang udah sebagian di-fix pakai global job lock.
Tujuan dokumen ini: pindahin arsitektur job/worker ke pola yang lebih robust
pakai Redis Queue (RQ), biar job survive restart dan aman diakses dari
banyak browser/tab sekaligus.

## Tujuan

1. Semua long-running task (scraping, preprocessing, training) jalan sebagai
   background job lewat RQ, bukan threading manual.
2. Job punya lifecycle yang jelas: `queued → started → progress → finished/failed`.
3. Global lock per job-type (misal: cuma boleh 1 preprocessing job jalan
   bersamaan) biar nggak ada race condition antar user/tab.
4. UI Streamlit bisa polling status job tanpa blocking, dan tetap nunjukin
   progress meski user refresh/pindah halaman.
5. Job history tersimpan (buat debugging & re-run kalau gagal).
6. Job runner-nya **generik & reusable** — nambah task baru cukup pasang
   decorator di function yang udah ada, tanpa bikin file baru khusus buat
   ngurus tiap tahapan (`jobs/scrape_job.py`, `jobs/train_job.py`, dst).

## Arsitektur

```
┌─────────────┐      enqueue       ┌───────────┐      pop job      ┌────────────┐
│  Streamlit   │ ─────────────────▶ │   Redis    │ ─────────────────▶ │  RQ Worker  │
│  (producer)  │                     │  (queue)  │                     │ (consumer) │
└─────────────┘ ◀───────────────── └───────────┘ ◀───────────────── └────────────┘
      │              poll status/progress                                  │
      │                                                                     │
      └──────────────── session_state (job_id) ───────────────────────────┘
```

- **Redis**: broker (queue) + progress store (key: `job:{id}:progress`).
- **RQ Worker**: proses terpisah (`rq worker`), dijalankan via Docker/Coolify
  sebagai service sendiri, bukan bagian dari proses Streamlit.
- **Streamlit**: cuma enqueue job dan poll status, nggak pernah eksekusi
  task berat langsung di main thread.

## Desain: Generic Job Runner (tanpa file per-job)

Ide utamanya: satu module reusable (`job_runner.py`) yang nyediain
decorator. Function yang mau dijadiin background job tinggal di-decorate
di tempat dia udah ada — nggak perlu dipindah ke folder/file `jobs/`
khusus tiap nambah task baru. Lock, queue routing, dan progress reporting
semua ke-handle otomatis lewat decorator ini.

```python
# job_runner.py — 1 file, reusable, taruh di mana pun (utils/, core/, dst)
import functools
from rq import Queue
from redis import Redis

redis_conn = Redis()

class JobRunner:
    def __init__(self, redis_conn):
        self.redis = redis_conn
        self._queues = {}

    def _queue(self, name: str) -> Queue:
        if name not in self._queues:
            self._queues[name] = Queue(name, connection=self.redis)
        return self._queues[name]

    def job(self, queue_name: str = "default", lock_ttl: int = 600):
        """Decorator: jadiin function apapun sebagai background job."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(job_id: str, *args, **kwargs):
                lock_key = f"lock:{func.__name__}"
                if not self.redis.set(lock_key, job_id, nx=True, ex=lock_ttl):
                    raise RuntimeError(f"{func.__name__} sedang berjalan")
                try:
                    return func(job_id, *args, **kwargs)
                finally:
                    self.redis.delete(lock_key)
            wrapper._queue_name = queue_name
            return wrapper
        return decorator

    def enqueue(self, func, *args, **kwargs):
        return self._queue(func._queue_name).enqueue(func, *args, **kwargs)

    def report_progress(self, job_id: str, current: int, total: int, stage: str = ""):
        self.redis.hset(f"job:{job_id}:meta", mapping={
            "current": current, "total": total, "stage": stage,
        })

runner = JobRunner(redis_conn)
```

Cara pakai — cukup tempel decorator di function yang udah ada, di mana pun
posisinya sekarang (nggak perlu dipindah):

```python
# di dalam page preprocessing yang udah ada, misal pages/preprocessing.py
from job_runner import runner

@runner.job(queue_name="preprocess", lock_ttl=1200)
def preprocess_task(job_id, data):
    for i, item in enumerate(data):
        # ... sastrawi stemming dst
        if i % 10 == 0:  # throttle biar nggak spam Redis
            runner.report_progress(job_id, i, len(data), stage="stemming")
    return result

# enqueue dari Streamlit
if st.button("Start"):
    job = runner.enqueue(preprocess_task, job_id_baru, data)
    st.session_state["job_id"] = job.id
```

Kenapa ini worth dipakai:

- Nambah job baru (misal nanti ada task `export_report`) cukup tempel
  1 decorator, nggak perlu bikin file/module baru buat "ngurus tahapan"-nya.
- Logic lock, progress format, dan queue routing konsisten otomatis di
  semua job — nggak ada copy-paste boilerplate tiap task baru.
- Karena cuma 1 file tanpa dependency ke struktur project spesifik, bisa
  di-reuse langsung di project lain yang juga butuh background job
  pattern serupa.

## Task Breakdown

### Fase 1 — Generic Job Runner (1 module, reusable di mana pun)

- [ ] Bikin satu module `job_runner.py` berisi class `JobRunner`
      (registry + decorator), bukan `jobs/` folder dengan file per task
- [ ] Decorator `@runner.job(queue_name=..., lock_ttl=...)` bisa langsung
      ditempel ke function manapun di codebase (scraper, preprocessing,
      training) — nggak perlu mindahin function ke file khusus
- [ ] Decorator otomatis handle: acquire/release lock, register ke queue
      yang sesuai, terima `job_id` buat progress reporting
- [ ] Setup `RQ` + `Redis` connection config (reuse existing self-hosted Redis)
- [ ] Module ini didesain portable — bisa di-copy/paste atau di-package
      jadi internal lib, dipakai lagi di project lain (misal discord-turbo-repo
      kalau butuh background job di Node.js versi serupa)

### Fase 2 — Global Lock

- [ ] Implement lock pakai Redis key dengan `NX` + `EX` (misal
      `lock:preprocess` dengan TTL sesuai estimasi durasi max)
- [ ] Sebelum enqueue, cek lock — kalau ada job sejenis yang masih jalan,
      tolak enqueue baru dan tampilkan pesan "job masih berjalan"
- [ ] Auto-release lock di `finally` block job function (termasuk saat job fail)

### Fase 3 — Progress Reporting

- [ ] Standardisasi format progress: `{"current": int, "total": int, "stage": str}`
      disimpan di Redis hash `job:{id}:meta`
- [ ] Job function update progress secara berkala (bukan tiap iterasi kecil,
      biar nggak spam Redis writes — throttle tiap N item atau tiap X detik)
- [ ] Simpan job status resmi lewat RQ (`job.get_status()`) sebagai source of truth,
      progress detail dari custom meta key

### Fase 4 — Streamlit Integration

- [ ] Ganti pemanggilan threading di halaman preprocessing dengan `q.enqueue(...)`
- [ ] Simpan `job_id` di `st.session_state`, bukan objek job/thread-nya
      (biar reattach-able setelah refresh)
- [ ] Polling loop pakai `st.rerun()` + `time.sleep()` kecil, fetch job by id
      tiap rerun
- [ ] Tangani 3 state UI: idle (belum ada job) / running (progress bar) /
      selesai (tampilkan hasil atau error)

### Fase 5 — Worker Deployment

- [ ] Dockerfile/service terpisah buat `rq worker`, deploy via Coolify
- [ ] Worker restart policy (auto-restart kalau crash)
- [ ] Health check / monitoring dasar (jumlah job pending, worker alive atau nggak)

### Fase 6 — Job History & Recovery

- [ ] Simpan record job (id, type, status, created_at, finished_at, error)
      di SQLite/Postgres buat histori (RQ job result punya TTL default, jangan
      andelin itu doang buat histori jangka panjang)
- [ ] Halaman "Job History" di Streamlit buat liat job-job sebelumnya
- [ ] Retry mechanism manual buat job yang gagal

## Non-Goals (buat sekarang)

- Distributed worker di banyak mesin (cukup 1 worker process dulu)
- Real-time push (WebSocket) — polling based dulu, cukup buat use case ini
- Scheduling/cron job otomatis (di luar scope background job on-demand ini)

## Keputusan Arsitektur

### TTL Lock per job-type

| Job type     | Estimasi durasi                                            | TTL lock            |
| ------------ | ---------------------------------------------------------- | ------------------- |
| `scrape`     | tergantung jumlah data & rate limit target                 | cap **30 menit**    |
| `preprocess` | Sastrawi stemming CPU-bound, bisa lama untuk dataset besar | cap **15-20 menit** |
| `train`      | TF-IDF + SMOTE + MultinomialNB biasanya cepat              | **5-10 menit**      |

Prinsip: TTL = perkiraan waktu terlama realistis × 1.5, bukan pas-pasan.
Kalau belum ada angka pasti, jalanin manual sekali per tipe job dulu buat
catat durasi aktual, baru fix TTL-nya.

TTL cuma safety net kalau worker crash/mati mendadak — lock tetap harus
di-release manual di `finally` block job function (lihat Fase 2), jangan
cuma andelin expiry.

### Strategi Queue

**Queue terpisah per tipe** (`scrape`, `preprocess`, `train`), tapi
**1 worker process** yang listen ke semua queue sekaligus dengan urutan
prioritas:

```bash
rq worker scrape preprocess train --url redis://localhost:6379
```

Alasan: kasih kontrol prioritas (misal `train` bisa didahuluin walau
`scrape` lagi ngantri) tanpa nambah kompleksitas infra. Kalau nanti butuh
paralel beneran (2 job jalan bersamaan), tinggal tambah worker process
kedua — struktur queue nggak perlu diubah.

### Lokasi Worker

Jalan di mesin `kirara` yang sama, tapi sebagai **service/container
terpisah** dari proses Streamlit (via Docker/Coolify), bukan `subprocess`
dari dalam app.

Alasan: yang penting itu separation of _process_, bukan separation of
mesin. Worker sebagai service independen berarti kalau Streamlit app
restart/crash, job yang lagi jalan di worker nggak ke-interrupt. Kalau
nanti beban makin berat (misal demo publik pas sidang), gampang pindahin
worker ke VM terpisah karena udah didesain independen dari awal.

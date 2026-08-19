# Category Config Plan

## Goal

- Menambahkan konfigurasi per category yang disimpan di folder `docs`.
- Setiap category bisa punya `name`, `description`, `enabled`, dan `validator()`.
- `validator()` menerima `state` dan `page` untuk memvalidasi isi page sesuai aturan category yang diinginkan.
- Setiap page bisa dipaksa nonaktif dari `src/structures/base.py`.
- Category yang tidak punya page aktif harus otomatis disembunyikan.
- `src/lib/loader.py` tidak diubah.

## Scope

Perubahan hanya di:

- `src/structures/base.py`
- `src/app.py`
- file config baru di `docs/`

## Rencana Implementasi

1. Tambah properti `enabled` pada `PageMetadata` dan `Options` di `src/structures/base.py`.
2. Buat file config category di `docs/` berisi mapping folder category ke:
   - `name`
   - `description`
   - `enabled`
3. Ubah `src/app.py` agar:
   - membaca config category dari file di `docs/`
   - memfilter page yang `enabled=False`
   - memfilter category yang `enabled=False`
   - hanya merender category yang masih punya page aktif
   - menampilkan nama dan deskripsi category dari config
4. Validasi error Python setelah perubahan.

## Dampak

- Sidebar jadi bisa dikontrol tanpa ubah `loader.py`.
- Category kosong tidak tampil.
- Page bisa dimatikan per file dengan flag metadata.

## Catatan

Pendekatan ini sengaja minimal. Loader tetap hanya bertugas memuat page dan category dari folder, sedangkan logika tampil/sembunyi dipindah ke level metadata dan app.

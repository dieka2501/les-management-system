# Sistem Manajemen Les Belajar

Sistem operasional untuk perusahaan les belajar anak yang mencakup chatbot customer service/sales, pendaftaran, data orang tua dan murid, guru, jadwal, billing, serta pengingat otomatis.

Proyek ini mulai masuk tahap implementasi. Analisis pola yang akan diadaptasi dari `isp-manajemen-system` tersedia di [docs/analisis-adaptasi-isp-ke-sistem-les.md](docs/analisis-adaptasi-isp-ke-sistem-les.md). Kebutuhan dashboard operasional yang mudah digunakan dicatat secara terpisah di [docs/fitur-dashboard-client.md](docs/fitur-dashboard-client.md). Mockup UI awal tersedia di [mockups/dashboard-client/index.html](mockups/dashboard-client/index.html).

## Prinsip produk

- Dashboard dibuat untuk admin operasional non-teknis: satu pekerjaan utama per layar, bahasa Indonesia yang jelas, dan aksi penting tidak tersembunyi.
- Chatbot menggunakan data bisnis yang disetujui sebagai sumber fakta; LLM tidak boleh mengarang paket, biaya, jadwal, atau ketersediaan guru.
- Pendaftaran dari chatbot menjadi data operasional yang dapat ditinjau dan diproses, bukan sekadar riwayat percakapan.
- Jadwal yang dibuat otomatis wajib lolos pemeriksaan bentrok guru dan murid sebelum disimpan.

## Ruang lingkup tahap awal

1. Chatbot informasi dan pendaftaran.
2. Dashboard pendaftaran, orang tua, murid, guru, mata pelajaran, paket, dan jadwal.
3. Generator jadwal tanpa tumpang tindih.
4. Billing dan pengingat jadwal untuk orang tua serta guru.

## Implementasi MVP saat ini

Slice awal aplikasi sudah mencakup:

- Backend Python standard library + SQLite.
- CRUD cabang sebagai scope data operasional, termasuk edit dan arsip.
- CRUD orang tua, termasuk edit dan arsip.
- CRUD murid dengan relasi orang tua dan mata pelajaran, termasuk edit dan arsip.
- CRUD guru dengan mata pelajaran dan availability, termasuk edit dan arsip.
- Pembuatan dan edit jadwal manual dengan validasi anti-bentrok.
- Generator kandidat jadwal otomatis yang tidak langsung menyimpan; admin harus konfirmasi.
- Dashboard web sederhana di `frontend/static`.

### Prinsip cabang/kota

Data operasional memakai `branch_id`, bukan teks kota bebas. Cabang menyimpan nama, alamat, dan kota/kabupaten, misalnya:

- Cabang Jalan Kenangan, Kota Tasikmalaya.
- Cabang Jalan Delima, Kabupaten Tasik.
- Cabang Jalan Seram, Kota Bandung.

Pada MVP ini jadwal hanya boleh dibuat jika murid dan guru berada di cabang yang sama. Mode lintas-cabang/online bisa ditambahkan nanti sebagai aturan eksplisit, bukan perilaku default.

### Menjalankan aplikasi lokal

Jika memakai virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Membuat schema database lokal/prod tanpa seed data:

```bash
python3 -m backend.app.migrate
```

Opsional untuk development: isi master data awal cabang dan mata pelajaran.

```bash
python3 -m backend.app.seed
```

Opsional untuk development demo: isi master data plus contoh orang tua, murid, guru, dan jadwal.

```bash
python3 -m backend.app.seed --demo
```

```bash
python3 -m backend.app.main
```

Lalu buka:

```text
http://127.0.0.1:8000
```

Secara default aplikasi hanya memastikan schema database tersedia dan tidak mengisi data demo. Jika butuh demo cepat saat menjalankan server:

```bash
LES_SEED_DEMO=1 python3 -m backend.app.main
```

### Menjalankan test

```bash
python3 -m unittest discover -s tests
```

## Dokumen

- [Analisis adaptasi logika ISP](docs/analisis-adaptasi-isp-ke-sistem-les.md)
- [Fitur dashboard client/operasional](docs/fitur-dashboard-client.md)
- [Mockup dashboard client/operasional](mockups/dashboard-client/index.html)
- [Logic baru yang bisa dibawa ke ISP](docs/logic-baru-untuk-isp.md)

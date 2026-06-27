# Sistem Manajemen Les Belajar

Sistem operasional untuk perusahaan les belajar anak yang mencakup chatbot customer service/sales, pendaftaran, data orang tua dan murid, guru, jadwal, billing, serta pengingat otomatis.

Proyek ini masih pada tahap perancangan. Analisis pola yang akan diadaptasi dari `isp-manajemen-system` tersedia di [docs/analisis-adaptasi-isp-ke-sistem-les.md](docs/analisis-adaptasi-isp-ke-sistem-les.md). Kebutuhan dashboard operasional yang mudah digunakan dicatat secara terpisah di [docs/fitur-dashboard-client.md](docs/fitur-dashboard-client.md). Mockup UI awal tersedia di [mockups/dashboard-client/index.html](mockups/dashboard-client/index.html).

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

## Dokumen

- [Analisis adaptasi logika ISP](docs/analisis-adaptasi-isp-ke-sistem-les.md)
- [Fitur dashboard client/operasional](docs/fitur-dashboard-client.md)
- [Mockup dashboard client/operasional](mockups/dashboard-client/index.html)

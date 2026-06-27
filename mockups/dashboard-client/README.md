# Mockup Dashboard Client / Operasional Les

Mockup ini dibuat sebagai rencana UI/UX awal untuk dashboard yang akan dipakai staf non-teknis.

Buka file berikut di browser:

```text
mockups/dashboard-client/index.html
```

## Rencana UX utama

- Beranda menampilkan pekerjaan yang perlu ditangani hari ini: pendaftaran baru, jadwal, tagihan, dan pengingat.
- Menu memakai istilah bisnis: Pendaftaran, Orang Tua & Murid, Guru, Jadwal, Tagihan, Pengetahuan Chatbot.
- Pendaftaran dari chatbot masuk sebagai data siap-review, bukan chat mentah.
- Form dibuat pendek dan kontekstual; detail penting muncul di panel kanan.
- CRUD Guru menonjolkan mata pelajaran dan availability karena dua data ini dipakai generator jadwal.
- CRUD Orang Tua & Murid dibuat dalam konsep “keluarga”, agar relasi satu orang tua dengan banyak anak mudah dipahami.
- Jadwal otomatis tidak langsung menyimpan; sistem menampilkan kandidat dan alasan, lalu admin mengonfirmasi.
- Status dibuat sederhana: Baru, Perlu Review, Aktif, Menunggu Bayar, Aman, Menunggu Guru.

## Layar yang sudah dimockup

1. Beranda operasional.
2. Pendaftaran dari chatbot.
3. CRUD Orang Tua & Murid.
4. CRUD Guru.
5. Kalender jadwal dan generator otomatis tanpa bentrok.
6. Tagihan.
7. Pengetahuan Chatbot.

## Catatan implementasi

Mockup ini masih statis HTML/CSS. Saat implementasi aplikasi, alur yang paling penting untuk diprioritaskan adalah:

1. Pendaftaran chatbot → review → buat orang tua/murid/enrollment.
2. Guru + mata pelajaran + availability.
3. Jadwal manual dengan validasi bentrok.
4. Generator jadwal otomatis dengan preview kandidat.
5. Pengingat jadwal ke guru dan orang tua.

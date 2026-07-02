# Logic Baru yang Bisa Diimplementasikan ke ISP Manajemen Sistem

Dokumen ini mencatat logic baru dari proyek les yang berpotensi berguna untuk `isp-manajemen-system`.

## 1. Generator slot dengan preview kandidat

Di proyek les, generator jadwal tidak langsung menyimpan perubahan. Sistem menampilkan kandidat slot yang sudah dicek, lengkap dengan alasan, lalu admin mengonfirmasi.

Potensi adaptasi ke ISP:

- Penjadwalan teknisi instalasi pelanggan baru.
- Penjadwalan kunjungan maintenance.
- Penjadwalan survey coverage.

Nilai tambah untuk ISP:

- Mengurangi bentrok teknisi.
- Admin melihat beberapa opsi, bukan menerima satu keputusan otomatis.
- Backend tetap melakukan pengecekan ulang saat admin konfirmasi.

## 2. Validasi resource conflict generik

Logic anti-bentrok di sistem les saat ini mengecek:

- resource guru;
- resource murid;
- hari;
- jam mulai dan selesai;
- status jadwal aktif.

Potensi adaptasi ke ISP:

- resource teknisi;
- kendaraan;
- perangkat pinjaman;
- slot kunjungan pelanggan;
- jadwal maintenance jaringan.

Formula overlap yang bisa dipakai ulang:

```text
slot_baru_mulai < slot_lama_selesai
dan
slot_baru_selesai > slot_lama_mulai
```

## 3. Entity conversion dari intake ke data operasional

Pada sistem les, pendaftaran dari chatbot nantinya tidak berhenti sebagai chat. Data akan dikonversi menjadi:

- orang tua;
- murid;
- enrollment/mapel;
- jadwal awal;
- tagihan.

Potensi adaptasi ke ISP:

- lead chatbot/form dikonversi menjadi pelanggan;
- alamat service;
- paket internet;
- jadwal instalasi;
- invoice awal.

Catatan penting: sebelum konversi, sistem sebaiknya menampilkan potensi duplikasi nomor WhatsApp/email/alamat.

## 4. Dashboard berbasis pekerjaan harian

Mockup dan MVP dashboard les memprioritaskan pekerjaan hari ini, bukan menu teknis.

Potensi adaptasi ke ISP:

- pendaftaran baru yang perlu diproses;
- instalasi hari ini;
- tiket gangguan terbuka;
- tagihan jatuh tempo;
- pesan WhatsApp gagal terkirim.

Ini bisa membuat dashboard ISP lebih ramah untuk operator non-teknis.

## 5. Knowledge preview sebelum publish

Untuk chatbot les, knowledge bisnis harus bisa dipreview sebelum aktif.

Potensi adaptasi ke ISP:

- admin mengubah FAQ paket internet;
- admin preview jawaban chatbot;
- baru publish setelah jawaban sesuai.

Logic ini membantu menjaga chatbot tidak menjawab dengan informasi harga/paket yang belum disetujui.

## 6. Scope cabang/lokasi sebagai master data

Pada proyek les, cabang tidak disimpan sebagai teks kota di setiap tabel. Sistem memakai master `branches`, lalu data operasional menyimpan `branch_id`.

Alasan:

- Satu kota bisa memiliki banyak cabang.
- Cabang memiliki metadata sendiri: nama, alamat, kota/kabupaten, dan status.
- Filter dashboard, jadwal, billing, dan reminder bisa memakai scope yang konsisten.

Potensi adaptasi ke ISP:

- `branch_id`, `area_id`, `pop_id`, atau `service_zone_id` sebagai scope operasional.
- Pelanggan, teknisi, tiket, jadwal instalasi, perangkat, dan tagihan dapat difilter per area/POP.
- Validasi jadwal teknisi bisa mencegah teknisi area Bandung dijadwalkan ke pelanggan Tasik tanpa izin lintas-area eksplisit.

Catatan desain:

- Jangan hanya menyimpan teks kota di pelanggan/tiket karena rawan typo dan sulit dipakai untuk permission.
- Jika ada operasi lintas-area, buat aturan eksplisit seperti `allow_cross_area_assignment`, bukan perilaku default.

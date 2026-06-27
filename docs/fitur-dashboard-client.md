# Fitur Dashboard Client / Operasional Les

Dokumen ini mencatat kebutuhan dashboard yang akan dipakai staf perusahaan les non-teknis. Nama yang disarankan pada aplikasi adalah **Dashboard Operasional Les**, agar tidak membingungkan dengan orang tua sebagai pelanggan.

## Prinsip pengalaman pengguna

- Gunakan istilah bisnis yang sudah dikenal staf: “Orang Tua”, “Murid”, “Guru”, “Jadwal”, dan “Tagihan”.
- Sediakan tombol aksi utama yang jelas di setiap halaman, misalnya “Tambah Murid” atau “Buat Jadwal”.
- Form dipisah menjadi langkah pendek bila datanya banyak; tampilkan contoh format dan validasi dekat kolomnya.
- Aksi berisiko—hapus, batalkan, kirim ulang pengingat, terbitkan tagihan—memerlukan konfirmasi yang menjelaskan akibatnya.
- Tampilkan status dalam bahasa sederhana dan konsisten, bukan kode teknis.
- Halaman beranda memprioritaskan pekerjaan hari ini, bukan statistik berlebihan.

## Navigasi versi awal

| Menu | Tujuan utama | Aksi utama |
| --- | --- | --- |
| Beranda | Melihat pendaftaran baru, jadwal hari ini, tagihan jatuh tempo, dan pengingat gagal | Buka pekerjaan yang perlu ditangani |
| Pendaftaran | Meninjau pendaftaran hasil chatbot/form | Setujui, minta kelengkapan, batalkan, ubah menjadi murid aktif |
| Orang Tua & Murid | Mengelola data keluarga dan enrollment | Tambah/edit orang tua, tambah/edit murid, pilih mapel/paket |
| Guru | Mengelola data guru dan ketersediaannya | Tambah/edit/nonaktifkan guru, atur mapel ajar dan availability |
| Jadwal | Menyusun dan melihat kalender belajar | Buat manual, buat otomatis, pindah/batalkan sesi |
| Paket & Mata Pelajaran | Mengelola produk pembelajaran yang dijual | CRUD paket dan mata pelajaran |
| Tagihan | Mengelola tagihan atas nama orang tua | Buat tagihan, tandai bayar, kirim pengingat |
| Pesan & Pengingat | Mengawasi pesan otomatis kepada guru/orang tua | Jadwalkan, kirim ulang, lihat status gagal |
| Pengetahuan Chatbot | Memperbarui FAQ, paket, kebijakan, dan pertanyaan belum terjawab | Tinjau dan publikasikan knowledge |

Menu “Pengetahuan Chatbot” dapat dibatasi untuk Admin. Menu teknis seperti database explorer, log mentah API, token, dan konfigurasi integrasi tidak menjadi bagian dari dashboard operasional.

## Penambahan fitur yang diminta

### 1. CRUD Guru

**Data guru**

- Kode guru (dibuat otomatis oleh sistem)
- Nama lengkap
- Tanggal lahir
- Jenis kelamin
- Pendidikan
- Mata pelajaran yang dapat diajar (lebih dari satu)
- Status aktif/nonaktif
- Ketersediaan mengajar: hari, jam mulai, jam selesai
- Catatan internal (opsional)

**Aturan bisnis**

- Guru nonaktif tidak muncul pada generator jadwal baru, tetapi jadwal historisnya tetap terlihat.
- Setiap guru wajib memiliki sedikitnya satu mata pelajaran sebelum dapat dipilih pada jadwal.
- Ketersediaan guru tidak sama dengan jadwal. Availability adalah rentang yang boleh dipilih; jadwal adalah sesi yang sudah dikonfirmasi.
- Saat mapel atau availability guru diubah, sistem memperingatkan bila berpengaruh pada jadwal aktif; perubahan tidak boleh menghapus jadwal tanpa konfirmasi.

**Layar sederhana**

- Daftar guru dengan pencarian nama/mapel dan filter status.
- Form “Tambah/Edit Guru” berisi bagian identitas, mapel ajar, dan ketersediaan.
- Halaman detail berisi ringkasan jadwal mingguan guru dan daftar murid yang diajar.

### 2. CRUD Orang Tua dan Murid

**Data orang tua**

- Kode orang tua (otomatis)
- Nama lengkap
- Email
- Nomor telepon/WhatsApp
- Alamat rumah

**Data murid**

- Kode anak (otomatis)
- Nama lengkap
- Tempat dan tanggal lahir
- Jenis kelamin
- Orang tua utama
- Mata pelajaran yang diambil (lebih dari satu)
- Paket belajar, status enrollment, serta catatan kebutuhan belajar (opsional)

**Aturan bisnis**

- Satu orang tua dapat memiliki banyak murid.
- Satu murid dapat mengambil lebih dari satu mata pelajaran, tanpa membuat profil murid ganda.
- Data orang tua menjadi alamat penagihan default; perubahan alamat/nomor harus ditampilkan sebelum pengingat atau invoice berikutnya dikirim.
- Pendaftaran yang disetujui dapat membuat data orang tua, murid, dan enrollment melalui satu aksi dengan pemeriksaan duplikasi nomor WhatsApp/email.
- Penghapusan data yang telah memiliki jadwal atau tagihan sebaiknya menjadi “nonaktif/arsip”, bukan hapus permanen.

**Layar sederhana**

- Satu halaman keluarga: kartu orang tua di bagian atas dan daftar anak di bawahnya.
- Tombol “Tambah Anak” dari detail orang tua agar relasi langsung jelas.
- Form murid menggunakan langkah: identitas → pilihan belajar → konfirmasi.

### 3. CRUD Jadwal Belajar

**Data jadwal**

- Kode jadwal (otomatis)
- Murid
- Guru
- Mata pelajaran
- Hari belajar
- Jam mulai dan selesai
- Tanggal berlaku mulai/selesai
- Mode/lokasi belajar (daring, rumah, kelas; bila diperlukan)
- Status: rancangan, aktif, dipindah, selesai, dibatalkan
- Catatan

**Aksi**

- Tambah jadwal manual.
- Edit atau pindahkan jadwal; sistem memeriksa bentrok sebelum menyimpan.
- Batalkan satu sesi atau seluruh jadwal berulang dengan alasan yang dicatat.
- Lihat jadwal sebagai daftar harian dan kalender mingguan.
- Filter berdasarkan murid, guru, mata pelajaran, status, dan rentang tanggal.

**Pemeriksaan wajib sebelum simpan**

- Guru mengajar mata pelajaran yang dipilih.
- Guru tersedia pada hari dan jam tersebut.
- Murid memiliki enrollment/mapel aktif.
- Jadwal tidak bertabrakan dengan jadwal aktif guru.
- Jadwal tidak bertabrakan dengan jadwal aktif murid.
- Bila menggunakan kelas fisik, kapasitas ruangan tidak terlampaui.

### 4. Generate Jadwal Otomatis Tanpa Tumpang Tindih

Generator adalah fitur pendamping, bukan tombol yang langsung mengubah kalender. Admin mengisi kebutuhan, melihat beberapa pilihan, lalu mengonfirmasi satu rancangan.

**Input generator**

- Murid dan mata pelajaran/enrollment.
- Jumlah sesi per minggu serta durasi sesi dari paket (dapat disesuaikan jika berizin).
- Hari/jam yang disukai orang tua/murid.
- Rentang tanggal berlaku.
- Guru pilihan atau opsi “carikan guru yang sesuai”.
- Mode/lokasi belajar dan batas kapasitas bila relevan.

**Output generator**

- Satu atau beberapa kandidat jadwal yang tidak bentrok.
- Guru terpilih dan alasan ringkas, misalnya “sesuai mapel dan tersedia Selasa/Kamis sore”.
- Peringatan bila preferensi tidak dapat dipenuhi, disertai alternatif yang paling dekat.
- Ringkasan perubahan sebelum disimpan.

**Aturan anti-bentrok**

- Tidak ada jadwal guru yang tumpang tindih.
- Tidak ada jadwal murid yang tumpang tindih.
- Slot wajib berada di dalam availability guru dan preferensi yang disetujui.
- Sesi yang sudah berlangsung atau telah diberi presensi tidak boleh diganti otomatis.
- Pemeriksaan bentrok dijalankan lagi di backend dalam satu transaksi saat admin menekan “Konfirmasi Jadwal”.

## Definisi selesai tahap dashboard

Fitur dashboard dianggap siap dipakai ketika staf non-teknis dapat:

1. Menerima pendaftaran chatbot dan mengubahnya menjadi orang tua, murid, serta enrollment tanpa memasukkan data ulang.
2. Menambah guru beserta mata pelajaran dan waktu mengajarnya.
3. Membuat jadwal manual yang menolak guru/murid bentrok dengan penjelasan yang mudah dimengerti.
4. Meminta generator untuk menghasilkan kandidat jadwal tanpa bentrok dan menyimpan kandidat yang disetujui.
5. Menemukan data keluarga, guru, dan jadwal melalui pencarian/filter sederhana.
6. Melihat pekerjaan harian serta status pengingat tanpa membuka halaman teknis.

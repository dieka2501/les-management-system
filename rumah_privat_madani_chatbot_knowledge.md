# Knowledge Base Chatbot — Rumah Privat Madani

## 1. Identitas Lembaga

- **Nama:** Rumah Privat Madani
- **Jenis layanan:** Les privat
- **Format yang tercantum:** 1 anak 1 tutor
- **Wilayah layanan:** Tasikmalaya, Ciamis, dan Singaparna
- **WhatsApp/telepon:** 0812 8367 9665
- **Instagram:** `@rumahprivatmadani`

> Catatan: Data sumber belum menjelaskan durasi sesi, jam operasional, biaya pendaftaran, biaya transportasi tutor, metode online/offline, serta kebijakan pembatalan.

---

## 2. Daftar Paket

### A. Les Privat Calistung

**Kebutuhan yang ditangani**
- Anak sulit fokus saat belajar di rumah.
- Anak cepat bosan atau menyerah ketika melihat angka atau huruf.
- Orang tua tidak memiliki cukup waktu untuk mendampingi secara intensif.
- Orang tua khawatir anak belum siap menghadapi syarat masuk SD.

**Materi**
- **Baca:** mengenal huruf, suku kata, dan membaca kalimat dengan lancar tanpa mengeja.
- **Tulis:** melatih motorik halus, memegang pensil dengan benar, dan menulis rapi.
- **Hitung:** mengenal angka, memahami konsep jumlah, serta penjumlahan dan pengurangan dasar secara logis.

**Metode**
- Multisensori: sentuhan, penglihatan, dan gerakan.
- Kurikulum bertahap dari materi sederhana menuju tingkat mahir sesuai kesiapan anak.
- Positive reinforcement: apresiasi terhadap progres kecil.
- Laporan perkembangan anak secara berkala.

**Harga**
- Rp55.000 per sesi.

**Tagline**
- Bekali si kecil kepercayaan diri sebelum sekolah.

---

### B. Les Privat BTQ

**Fitur**
- Guru berpengalaman.
- Pembiasaan adab.
- Jadwal fleksibel.
- Metode belajar menyenangkan.
- Fokus dan intensif.

**Jenjang**
1. **Kelas Iqra (Dasar)**
   - Pengenalan huruf Hijaiyah.
   - Makhraj yang benar.
   - Kelancaran membaca dasar.

2. **Kelas Al-Qur'an (Lanjut)**
   - Perbaikan tajwid, termasuk mad dan idgham.
   - Gharib.
   - Kelancaran tadarus.

**Materi penunjang**
- Hafalan surat pendek.
- Praktik wudhu.
- Praktik shalat.
- Hafalan doa harian.
- Kisah teladan Nabi.

**Harga**
- Rp55.000 per sesi.

**Catatan sumber**
- Tagline bahasa Inggris pada poster BTQ tampaknya merupakan sisa template. Jangan gunakan sebagai informasi program BTQ.

---

### C. English Private for Children

**Fitur**
- Fun and interactive lessons.
- Latihan speaking, reading, dan writing.
- Vocabulary building melalui permainan dan lagu.
- Tutor sabar dan berpengalaman.
- Personalized 1-on-1.

**Pendekatan**
- Kurikulum standar global, disesuaikan dengan usia dan perkembangan anak.
- Pendekatan personal sesuai kemampuan, gaya belajar, dan tujuan belajar.
- Laporan perkembangan anak secara berkala.

**Harga**
- **Belum boleh dianggap final.**
- Dua poster memuat harga berbeda: **Rp55.000** dan **Rp60.000** per sesi.
- Chatbot wajib meminta pengguna mengonfirmasi harga terbaru kepada admin.

**Tagline**
- Learning English becomes a fun adventure.

---

### D. Les Privat Matematika

**Fitur**
- Guru berpengalaman.
- Konsultasi PR dan ujian.
- Jadwal fleksibel.
- Modul dan latihan soal disediakan.
- Latihan soal dari tingkat mudah, HOTS, hingga soal lomba.

**Pendekatan**
- Materi dapat disesuaikan dengan kurikulum Singapura atau Cambridge.
- Step by Step Mastery: anak melanjutkan ke bab baru setelah memahami bab sebelumnya.
- Laporan perkembangan anak secara berkala.

**Harga**
- Rp55.000 per sesi.

**Tagline**
- Taklukkan angka, asah logika.

---

## 3. Intent Chatbot yang Disarankan

### `list_packages`
Menjawab daftar paket: Calistung, BTQ, English for Children, dan Matematika.

### `package_recommendation`
Routing berdasarkan kebutuhan:
- Belum lancar membaca, menulis, atau berhitung → **Calistung**
- Iqra, Al-Qur'an, tajwid, ngaji, wudhu, shalat → **BTQ**
- Speaking, vocabulary, reading, atau writing bahasa Inggris → **English**
- PR matematika, ujian, HOTS, Cambridge, atau kurikulum Singapura → **Matematika**

### `package_price`
Mengambil harga berdasarkan paket. Khusus English, chatbot harus menyatakan bahwa harga perlu dikonfirmasi karena terdapat dua nilai berbeda pada materi promosi.

### `coverage_area`
Menjawab bahwa cakupan yang tercantum adalah Tasikmalaya, Ciamis, dan Singaparna.

### `learning_materials`
Menjawab materi, level, metode, dan target pembelajaran masing-masing paket.

### `teaching_method`
Menjelaskan format 1 anak 1 tutor serta metode spesifik setiap paket.

### `progress_report`
Menjawab ketersediaan laporan perkembangan untuk paket yang mencantumkannya.

### `registration_contact`
Mengarahkan pengguna ke WhatsApp 0812 8367 9665 atau Instagram `@rumahprivatmadani`.

---

## 4. Entity yang Perlu Diekstrak

- `package`: calistung | btq | english | matematika
- `location`: Tasikmalaya | Ciamis | Singaparna
- `child_age`
- `school_grade`
- `learning_goal`
- `learning_problem`
- `btq_level`: iqra | al_quran
- `curriculum`: nasional | Singapura | Cambridge | belum diketahui
- `schedule_preference`

---

## 5. Aturan Jawaban

1. Jangan membuat informasi yang tidak terdapat dalam knowledge base.
2. Jangan menentukan durasi sesi, jadwal, biaya tambahan, trial class, atau metode online/offline tanpa data admin.
3. Jangan menetapkan harga English sebagai harga pasti.
4. Gunakan pertanyaan klarifikasi saat kebutuhan pengguna belum spesifik.
5. Setelah menjelaskan paket, arahkan ke admin hanya ketika pengguna ingin mendaftar, mengecek jadwal, mengecek area rinci, atau mengonfirmasi informasi yang belum tersedia.

---

## 6. Pertanyaan Klarifikasi Utama

- Paket belajar apa yang sedang dicari?
- Anak tinggal di Tasikmalaya, Ciamis, atau Singaparna?
- Berapa usia atau kelas anak?
- Kesulitan atau target belajar utamanya apa?
- Untuk BTQ, anak masih belajar Iqra atau sudah membaca Al-Qur'an?
- Untuk Matematika, kurikulum sekolah yang digunakan apa?

---

## 7. Informasi yang Masih Harus Dikonfirmasi Admin

- Harga resmi paket English.
- Durasi satu sesi.
- Jadwal dan jam layanan.
- Apakah tutor datang ke rumah, kelas online, atau keduanya.
- Kecamatan/desa yang tercakup di setiap wilayah.
- Biaya pendaftaran dan biaya transportasi.
- Trial class.
- Sistem pembayaran.
- Kebijakan reschedule/cancel.
- Rentang usia dan jenjang kelas untuk setiap paket.
- Kualifikasi dan sertifikasi tutor.
- Mekanisme serta frekuensi laporan perkembangan.

---

## 8. Contoh Jawaban Chatbot

**Pengguna:** Anak saya belum lancar membaca dan cepat bosan.

**Chatbot:** Paket yang paling sesuai adalah Les Privat Calistung. Materinya mencakup pengenalan huruf, suku kata, membaca tanpa mengeja, latihan menulis, serta berhitung dasar. Pembelajaran menggunakan metode multisensori dan disusun bertahap sesuai kesiapan anak. Boleh diinformasikan usia atau kelas anak dan domisilinya?

**Pengguna:** Berapa harga English?

**Chatbot:** Pada materi promosi terdapat dua harga yang berbeda, yaitu Rp55.000 dan Rp60.000 per sesi. Agar tidak memberikan informasi yang keliru, harga English terbaru perlu dikonfirmasi ke admin melalui WhatsApp 0812 8367 9665.

**Pengguna:** Anak sudah bisa Iqra tetapi tajwidnya masih kurang.

**Chatbot:** Paket BTQ kelas Al-Qur'an lanjutan lebih sesuai. Fokusnya meliputi perbaikan tajwid seperti mad dan idgham, pembelajaran gharib, serta kelancaran tadarus.

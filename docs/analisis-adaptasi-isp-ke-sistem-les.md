# Analisis Adaptasi `isp-manajemen-system` ke Sistem Les

Tanggal analisis: 26 Juni 2026
Sumber: `/Users/dikdikkusdinar/works/htdocs/de-certificate/isp-manajemen-system`

## Kesimpulan

Pola bisnis dan teknis dari proyek ISP dapat dipakai sebagai fondasi, terutama chatbot hibrida, workflow pendaftaran berstatus, pemisahan akses, dan audit percakapan. Namun, struktur dua dashboard ISP tidak perlu disalin mentah-mentah.

Pada ISP, **Provider Dashboard** dipakai perusahaan pembuat platform untuk mengelola banyak tenant ISP, sedangkan **Client Dashboard** dipakai operator dari masing-masing ISP. Pada proyek les saat ini, targetnya adalah satu perusahaan penyedia les. Karena itu, tahap awal cukup memakai satu **Dashboard Operasional Les** untuk admin/staf perusahaan les. Istilah “dashboard client” pada kebutuhan proyek ini dicatat sebagai dashboard tersebut.

Apabila produk kelak menjadi SaaS untuk banyak perusahaan les, tambahkan lapisan tenant seperti proyek ISP: `organization_id` dari sesi login harus menjadi scope semua query data bisnis. Jangan menerima tenant dari URL atau body request sebagai sumber otoritas.

## Logic ISP yang layak digunakan

| Logic di ISP | Adaptasi untuk les | Keputusan |
| --- | --- | --- |
| Webhook WhatsApp menyimpan pesan, memuat state, menentukan intent, mengambil knowledge, membuat balasan, lalu mencatat audit | Pesan orang tua menjadi percakapan prospek/aktif; knowledge berisi paket, mata pelajaran, metode belajar, area, guru, dan kebijakan pembayaran | Gunakan |
| Native intent + entity extraction + LLM sebagai penyusun bahasa | Intent seperti tanya paket, biaya, mapel, jadwal, lokasi, guru, pendaftaran, dan pembayaran; LLM hanya merangkai jawaban dari fakta yang lolos retrieval | Gunakan dengan guardrail lebih ketat |
| Conversation state dengan TTL dan slot yang dikumpulkan | Simpan tahap pendaftaran serta data sementara: nama orang tua, nomor WhatsApp, nama anak, usia/kelas, mapel, paket, preferensi hari/jam | Gunakan, dengan transisi status eksplisit |
| Knowledge retrieval tenant/device-specific | Ambil data aktif dari paket, mapel, guru, ketersediaan, FAQ, metode pembayaran, dan kebijakan lembaga | Gunakan |
| Queue pesan unknown/low-confidence untuk ditinjau | Admin meninjau pertanyaan yang belum terjawab dan menambahkan contoh pertanyaan/knowledge yang benar | Gunakan; sebut sebagai “Tinjau Pertanyaan”, bukan “melatih AI” |
| Pendaftaran publik/token dan status workflow | Data dari chatbot menjadi pendaftaran dengan status `baru → ditinjau → menunggu konfirmasi → aktif/batal` | Gunakan, sesuaikan status |
| Cookie sesi, route guard, permission API server-side | Role minimal `admin` dan `staf`; seluruh mutasi data diperiksa di backend | Gunakan |
| Provider/Client dashboard terpisah | Hanya dibutuhkan jika platform melayani banyak lembaga les | Tunda untuk tahap SaaS |
| SQLite Explorer dan menu teknis | Tidak relevan untuk operator non-teknis | Jangan tampilkan di dashboard operasional |

Referensi implementasi ISP: pipeline chat berada di `backend/app/services/chatbot.py`, retriever di `backend/app/services/knowledge_retrieval.py`, pembuat jawaban LLM di `backend/app/services/llm_response.py`, guard akses di `backend/app/auth/guards.py`, dan workflow pendaftaran di `backend/app/api/client_dashboard.py` serta `backend/app/api/registrations.py`.

## Arsitektur yang direkomendasikan

```text
WhatsApp / Web chat
        ↓
Webhook chat
        ↓
Simpan pesan dan muat state percakapan
        ↓
Intent + validasi data yang diberikan orang tua
        ↓
Ambil fakta bisnis dari database
        ↓
Tentukan aksi workflow secara deterministik
        ↓
LLM menyusun bahasa (atau gunakan balasan template untuk aksi kritis)
        ↓
Simpan state, audit log, dan data pendaftaran
        ↓
Kirim balasan / pengingat WhatsApp
```

### Batas tugas komponen

| Komponen | Tanggung jawab | Tidak boleh dilakukan |
| --- | --- | --- |
| Intent & entity engine | Memahami maksud dan mengambil data awal dari pesan | Menentukan biaya atau guru tanpa data bisnis |
| Knowledge retrieval | Mengambil fakta aktif dan relevan dari database | Menulis jawaban akhir |
| Workflow engine | Mengubah status pendaftaran, membuat kandidat jadwal, atau mengarahkan ke pembayaran | Mengandalkan teks bebas LLM untuk keputusan bisnis |
| LLM | Menulis balasan ramah dan singkat berdasarkan fakta yang diberikan | Mengarang fakta, menyimpan data, atau menyetujui pendaftaran |
| Dashboard operasional | Memberi kontrol manusia untuk data dan keputusan | Menjadi satu-satunya sumber validasi aturan bisnis |

Untuk pemberitahuan yang mengubah status—misalnya pendaftaran diterima, jadwal berhasil dibuat, tagihan jatuh tempo, atau pembayaran diterima—gunakan template terstruktur. LLM boleh menulis FAQ dan follow-up, tetapi bukan fakta transaksi.

## Perbaikan atas risiko yang ditemukan di ISP

Hasil analisis ISP menunjukkan beberapa risiko yang perlu dicegah dari awal.

1. **Intent baru tidak boleh kalah oleh slot lama.** Jika percakapan sedang menunggu alamat, pesan jelas seperti “saya ingin membatalkan” harus membatalkan/mengubah workflow, bukan dianggap alamat.
2. **Validasi slot harus spesifik.** Nama, nomor WhatsApp, kelas, usia, alamat, dan pilihan jadwal memerlukan validator; teks pendek bebas tidak boleh otomatis diterima sebagai semua jenis data.
3. **Formulir dan chat harus menyinkronkan state.** Saat pendaftaran dikirim, state percakapan harus berubah menjadi `submitted` dan slot pendaftaran ditutup agar bot tidak kembali meminta data yang telah masuk.
4. **Undangan/tautan harus idempoten.** Jika pendaftaran sudah ada, bot menampilkan status atau tautan yang sama, bukan diam maupun membuat pendaftaran ganda.
5. **Preview admin harus meniru jalur produksi.** Uji coba chatbot perlu memasukkan state, knowledge, workflow, dan aturan respons yang sama, tetapi tanpa mengirim WhatsApp atau menulis data produksi.
6. **Pembelajaran chatbot bukan fine-tuning otomatis.** Menyetujui pertanyaan baru hanya menambah knowledge, contoh intent, atau aturan respons yang dapat ditinjau. Setiap perubahan perlu skenario uji regresi.

## Model data operasional

| Entitas | Data utama | Relasi dan aturan penting |
| --- | --- | --- |
| `branches` | kode, nama cabang, alamat, kota/kabupaten, status | Scope operasional untuk data multi-kota/multi-cabang |
| `parents` | kode, branch_id, nama, email, telepon, alamat | Satu orang tua dapat memiliki banyak murid |
| `students` | kode, branch_id, nama, tempat/tanggal lahir, jenis kelamin, parent_id, status | Wajib memiliki tepat satu orang tua utama pada tahap awal |
| `subjects` | kode, nama, deskripsi, status aktif | Dipakai paket, guru, dan jadwal |
| `tutors` | kode, branch_id, nama, tanggal lahir, jenis kelamin, pendidikan, status | Guru dapat mengajar banyak mata pelajaran |
| `tutor_subjects` | tutor_id, subject_id, kompetensi/level | Kombinasi unik per guru dan mata pelajaran |
| `tutor_availabilities` | tutor_id, hari, jam mulai/selesai | Menjadi sumber kandidat generator jadwal |
| `learning_packages` | kode, nama, biaya, durasi sesi, frekuensi, status | Paket menentukan kuota/frekuensi dan mapel yang ditawarkan |
| `enrollments` | student_id, package_id, status mulai/akhir | Satu murid dapat memiliki beberapa mapel melalui detail enrollment |
| `enrollment_subjects` | enrollment_id, subject_id | Mencatat mapel yang benar-benar dipilih murid |
| `schedules` | kode, branch_id, student_id, tutor_id, subject_id, hari, jam mulai/selesai, mode, status | Tidak boleh berbenturan untuk guru atau murid; tahap MVP wajib satu cabang |
| `registrations` | branch_id, sumber, parent data sementara, student data sementara, paket/mapel, status, PIC | Hasil chatbot harus dapat dikonversi menjadi master data tanpa input ulang |
| `invoices` dan `payments` | orang tua penagih, periode, nominal, status, metode bayar | Billing ditujukan kepada orang tua, bukan anak |
| `reminders` | penerima, jenis, waktu kirim, status, isi pesan | Catat seluruh upaya kirim untuk audit dan retry |
| `conversations` dan `conversation_states` | nomor, pesan, intent, state, jawaban, expiry | Dipisahkan dari data master, tetapi terhubung ke parent/registration bila cocok |

Semua kode bisnis (`kode orang tua`, `kode anak`, `kode guru`, dan seterusnya) dibuat di server, unik, dan tidak dipakai sebagai primary key internal. Gunakan ID internal untuk relasi serta kode yang mudah dibaca manusia untuk operasi sehari-hari.

Catatan cabang: gunakan `branch_id` sebagai sumber otoritas, bukan teks kota bebas. Kota/kabupaten disimpan di master `branches`, karena satu kota dapat memiliki beberapa cabang. Pada tahap MVP, jadwal hanya valid bila murid dan guru berada pada cabang yang sama. Mode online lintas cabang dapat ditambahkan nanti sebagai aturan eksplisit.

## Workflow pendaftaran dari chatbot

```text
Prospek bertanya
  → bot memberi informasi dari knowledge aktif
  → bot mengumpulkan data minimum secara bertahap
  → buat/temukan pendaftaran berstatus BARU
  → admin meninjau dan menghubungi bila perlu
  → admin menyetujui paket/mapel dan membuat atau mengonfirmasi jadwal
  → data orang tua dan murid diaktifkan
  → invoice pertama diterbitkan
  → pengingat jadwal berjalan
```

Data minimum sebelum pendaftaran dibuat: nama orang tua, nomor WhatsApp, nama anak, usia atau kelas, mata pelajaran yang diminati, serta preferensi hari/jam. Alamat lengkap boleh dikumpulkan belakangan bila kelas daring atau lokasi belum pasti.

Status awal yang direkomendasikan:

```text
draft → baru → ditinjau → menunggu_konfirmasi → aktif
                              ↘ dibatalkan
```

Status dan aktor yang mengubahnya harus tercatat dalam histori. Bot tidak boleh mengaktifkan murid atau mengonfirmasi jadwal sendiri tanpa aturan dan otorisasi yang jelas.

## Generator jadwal tanpa tumpang tindih

Generator tidak boleh sekadar memilih slot kosong pertama. Ia harus menerima permintaan yang jelas: murid, mapel, jumlah sesi per minggu, durasi sesi, rentang hari/jam pilihan, mode belajar, dan—bila relevan—guru pilihan.

Urutan kerja:

1. Validasi murid aktif, mapel diambil, paket masih memiliki kuota, dan guru menguasai mapel tersebut.
2. Bangun kandidat slot dari irisan preferensi murid/orang tua dan ketersediaan guru.
3. Buang kandidat yang bertabrakan dengan jadwal aktif guru, jadwal murid, serta kapasitas ruang/kelas bila dipakai.
4. Urutkan kandidat dengan skor: preferensi orang tua, beban guru paling ringan, jarak antar sesi yang sehat, dan konsistensi hari/jam mingguan.
5. Pilih kombinasi slot sesuai frekuensi paket; jangan simpan hasil parsial bila jumlah sesi belum terpenuhi.
6. Tampilkan rancangan jadwal kepada admin untuk konfirmasi. Hanya setelah dikonfirmasi, simpan di dalam transaksi dan lakukan pemeriksaan bentrok sekali lagi.
7. Bila gagal, jelaskan kendala dan alternatif terdekat—misalnya guru yang tersedia, hari lain, atau perlu menambah availability—bukan pesan teknis.

Aturan bentrok untuk interval setengah terbuka adalah:

```text
slot_baru_mulai < slot_lama_selesai
dan slot_baru_selesai > slot_lama_mulai
```

Dengan aturan ini, sesi 15.00–16.00 boleh diikuti sesi 16.00–17.00, tetapi tidak boleh berdurasi tumpang tindih satu menit pun. Gunakan zona waktu `Asia/Jakarta`; jadwal berulang mingguan harus memiliki tanggal mulai/akhir agar perubahan paket dan hari libur dapat dikelola.

## Dashboard dan akses

Struktur yang dianjurkan untuk tahap awal:

```text
backend/
  app/
    auth/
    api/
    services/
    domain/
      registrations/
      branches/
      parents/
      students/
      tutors/
      schedules/
      billing/
      reminders/
      chatbot/
frontend/
  dashboard/
    navigation/
    pages/
    components/
```

Role awal cukup sederhana:

| Role | Hak utama |
| --- | --- |
| Admin | Semua data, konfigurasi, billing, jadwal, knowledge chatbot, dan pengguna |
| Staf operasional | Pendaftaran, orang tua/murid, guru, jadwal, pengingat; tanpa konfigurasi sensitif |
| Staf keuangan (opsional) | Billing dan pembayaran |

Route dan API harus sama-sama memeriksa sesi serta permission. Menyembunyikan menu di browser bukan mekanisme keamanan.

## Urutan implementasi

1. Buat fondasi FastAPI, autentikasi, migrasi database, dan shell dashboard sederhana.
2. Implementasikan CRUD master: mata pelajaran, paket, orang tua, murid, guru, dan ketersediaan guru.
3. Implementasikan pendaftaran beserta konversi aman ke orang tua/murid/enrollment.
4. Implementasikan CRUD jadwal, validasi bentrok, lalu generator jadwal dengan halaman preview/konfirmasi.
5. Implementasikan billing, pengingat, dan log pengiriman.
6. Implementasikan chatbot dengan knowledge retrieval dan workflow pendaftaran yang terintegrasi.
7. Tambahkan queue review pertanyaan, preview production-equivalent, audit, dan uji regresi chatbot.

Setiap tahap perlu pengujian aturan bisnis, terutama kepemilikan data orang tua-anak, kualifikasi guru-mapel, bentrok jadwal, konversi pendaftaran, serta idempotensi pengingat.

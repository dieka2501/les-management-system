# Sistem Manajemen Les Belajar

Sistem operasional untuk perusahaan les belajar anak yang mencakup chatbot customer service, pendaftaran,
data orang tua dan murid, guru, jadwal, serta generator jadwal tanpa tumpang tindih.

Implementasi saat ini memakai Python standard library dan SQLite. Analisis pola yang akan diadaptasi dari
`isp-manajemen-system` tersedia di [docs/analisis-adaptasi-isp-ke-sistem-les.md](docs/analisis-adaptasi-isp-ke-sistem-les.md).
Kebutuhan dashboard operasional yang mudah digunakan dicatat di
[docs/fitur-dashboard-client.md](docs/fitur-dashboard-client.md), dan mockup awal tersedia di
[mockups/dashboard-client/index.html](mockups/dashboard-client/index.html).

## Prinsip produk

- Dashboard dibuat untuk admin operasional non-teknis: satu pekerjaan utama per layar, bahasa Indonesia yang jelas, dan aksi penting tidak tersembunyi.
- Chatbot menggunakan data bisnis yang disetujui sebagai sumber fakta; LLM tidak boleh mengarang paket, biaya, jadwal, atau ketersediaan guru.
- Pendaftaran dari chatbot menjadi data operasional yang dapat ditinjau dan diproses, bukan sekadar riwayat percakapan.
- Jadwal yang dibuat otomatis wajib lolos pemeriksaan bentrok guru dan murid sebelum disimpan.

## Fitur backend

- CRUD cabang, orang tua, murid, guru, dan jadwal.
- Validasi jadwal agar guru dan murid tidak bentrok.
- Generator kandidat jadwal yang perlu dikonfirmasi admin sebelum disimpan.
- Knowledge base chatbot Rumah Privat Madani dalam format JSON terstruktur.
- Simulasi percakapan provider untuk melatih/evaluasi respons LLM berdasarkan knowledge base.
- Integrasi Gemini AI lewat backend proxy dengan guardrail agar hanya menjawab berdasarkan knowledge base.
- Lifecycle close chat: chatbot hanya menjawab pertanyaan, lalu meminta persetujuan sebelum chat diteruskan ke admin manusia.

## Dashboard client

Dashboard operasional client tersedia di root aplikasi:

```text
/
```

Halaman ini wajib login karena menampilkan dan mengubah data operasional. Jika belum ada session, user akan diarahkan ke:

```text
/provider/login?next=/
```

Slice MVP dashboard mencakup CRUD cabang, orang tua, murid, guru, jadwal manual, dan generator jadwal otomatis. Data operasional memakai `branch_id`, bukan teks kota bebas. Cabang menyimpan nama, alamat, dan kota/kabupaten, misalnya:

- Cabang Jalan Kenangan, Kota Tasikmalaya.
- Cabang Jalan Delima, Kabupaten Tasik.
- Cabang Jalan Seram, Kota Bandung.

Pada MVP ini jadwal hanya boleh dibuat jika murid dan guru berada di cabang yang sama. Mode lintas-cabang/online bisa ditambahkan nanti sebagai aturan eksplisit.

## Konfigurasi environment

Semua environment variable disatukan di file root project:

```text
.env
```

Template aman untuk repository tersedia di:

```text
.env.example
```

File ini otomatis dibaca oleh:

- `./reload_local.sh`
- Backend Python saat menjalankan `python3 -m backend.app.main`, `migrate`, atau `seed`

Environment variable dari shell tetap menang atas `.env`. Jadi kalau suatu saat menjalankan `PORT=8002 ./reload_local.sh`, nilai `PORT=8002` akan dipakai untuk run itu saja.

Isi utama `.env`:

```bash
HOST=127.0.0.1
PORT=8001
LES_SEED_DEMO=0
LES_DB_PATH=backend/data/les.sqlite3

APP_AUTH_PASSWORD=madani-internal-dev
APP_AUTH_SECRET=

GEMINI_API_KEY=
GOOGLE_API_KEY=
GEMINI_MODEL=gemini-3.1-flash-lite

IG_WEBHOOK_VERIFY_TOKEN=change-me-madani-verify-token
IG_APP_SECRET=
IG_ACCESS_TOKEN=
IG_USER_ID=
IG_REPLY_MODE=
IG_SEND_ENABLED=0
IG_GRAPH_API_VERSION=v24.0
```

Catatan penting: `.env` masuk `.gitignore` karena bisa berisi API key/token. Untuk production, isi secret langsung di server atau secret manager deployment.

## Railway production dengan SQLite

Railway production tetap memakai SQLite, tetapi file database tidak boleh mengandalkan path repository seperti `backend/data/les.sqlite3`. Untuk production, pasang Railway Volume agar data tidak hilang saat redeploy.

Start command Railway/Railpack sudah dikonfigurasi di root project melalui:

```text
railpack.json
```

Isi start command:

```bash
python3 -m backend.app.main
```

Rekomendasi setup Railway:

1. Attach Railway Volume ke service aplikasi.
2. Set mount path volume ke:

```text
/data
```

3. Set service variables di Railway:

```bash
LES_SEED_DEMO=0
LES_DB_PATH=/data/les.sqlite3
APP_AUTH_PASSWORD=password-production-kamu
APP_AUTH_SECRET=random-session-secret-production
```

Railway akan inject variable `PORT` sendiri, jadi tidak perlu hardcode `PORT` di Railway. Jangan isi `HOST` dengan domain publik Railway/custom domain; saat mendeteksi Railway, aplikasi otomatis bind ke `0.0.0.0`.

Untuk production, jangan biarkan `APP_AUTH_PASSWORD` kosong. Jika app mendeteksi Railway/production tetapi password login belum dikonfigurasi, area internal akan gagal login secara aman.

Jika `LES_DB_PATH` tidak diset tetapi Railway Volume sudah terpasang, aplikasi otomatis memakai:

```text
$RAILWAY_VOLUME_MOUNT_PATH/les.sqlite3
```

Dengan mount path `/data`, hasilnya sama dengan:

```text
/data/les.sqlite3
```

Untuk membuat schema production tanpa seed demo:

```bash
python3 -m backend.app.migrate
```

Atau biarkan aplikasi menjalankan migrasi saat start; `LesStore` akan memastikan schema tersedia. Jangan set `LES_SEED_DEMO=1` di production.

## Halaman pendukung Meta/Instagram App

Halaman static berikut disiapkan agar field di Meta App Dashboard bisa dilengkapi:

- `/meta-app-details/` sebagai Website URL publik. Catatan: `/` adalah dashboard operasional dan wajib login.
- `/privacy-policy/` sebagai URL Kebijakan Privasi.
- `/terms-of-service/` sebagai Ketentuan Layanan URL.
- `/data-deletion/` sebagai URL Petunjuk Penghapusan Data.
- `/instagram-test-instructions/` sebagai petunjuk pengujian untuk reviewer/tester.
- `/meta-app-details/` sebagai checklist internal untuk copy-paste field Meta App.

Saat production atau memakai HTTPS tunnel, ganti host lokal dengan domain kamu. Contoh:

```text
https://domain-kamu/meta-app-details/
https://domain-kamu/privacy-policy/
https://domain-kamu/terms-of-service/
https://domain-kamu/data-deletion/
https://domain-kamu/webhooks/instagram
```

## Login area internal

Area internal dilindungi form login password-only:

```text
/ 
/provider/chat-simulations
```

Password disimpan di `.env`:

```bash
APP_AUTH_PASSWORD=madani-internal-dev
```

Tidak ada username. Setelah password benar, browser akan menerima session cookie `HttpOnly` selama 12 jam. Dashboard operasional, API CRUD/generate/list data, dan API provider seperti `/api/provider/chat-simulations` ikut diproteksi, jadi tidak hanya tampilan UI yang terkunci.

Untuk mengganti password:

1. Edit `APP_AUTH_PASSWORD` di `.env`.
2. Jalankan ulang server:

```bash
./reload_local.sh
```

Jika password mengandung spasi atau karakter khusus, bungkus dengan tanda kutip:

```bash
APP_AUTH_PASSWORD="password rahasia kamu"
```

Alias lama `CHATBOT_TEST_PASSWORD` dan `CHATBOT_AUTH_SECRET` masih didukung untuk kompatibilitas, tetapi konfigurasi baru sebaiknya memakai `APP_AUTH_PASSWORD` dan `APP_AUTH_SECRET`.

## Simulasi percakapan provider

UI simulasi tersedia di:

```text
/provider/chat-simulations
```

Fitur simulasi hanya tersedia di area provider dan tidak menambah layar atau kode client.

Untuk mengganti jawaban ideal, klik `Edit respons` pada bubble asisten di chat simulation. Perubahan itu akan memperbarui pesan asisten dan `Training Examples`.

- `GET /api/provider/chatbot-knowledge`
- `GET /api/provider/chat-simulations/faq-script`
- `POST /api/provider/chat-simulations`
- `GET /api/provider/chat-simulations`
- `GET /api/provider/chat-simulations/{id}`
- `POST /api/provider/chat-simulations/{id}/messages`
- `GET /api/provider/chat-simulations/training-examples`

Sumber utama chatbot ada di `backend/app/knowledge/rumah_privat_madani.json`, hasil normalisasi dari `rumah_privat_madani_chatbot_knowledge.md`.

Gunakan `seed_from_faq: true` saat membuat sesi untuk mengisi contoh Q/A dari knowledge base sebagai dataset respons ideal. Nama field ini tetap dipertahankan agar kompatibel dengan UI/API simulasi yang sudah ada.

### Mode Gemini AI

API key Gemini tidak disimpan di source code. Isi salah satu value ini di `.env`:

```bash
GEMINI_API_KEY=isi_api_key_kamu
```

Alternatifnya, kamu juga bisa memakai `GOOGLE_API_KEY`.

Opsional, pilih model Gemini di `.env`:

```bash
GEMINI_MODEL=gemini-3.1-flash-lite
```

Lalu jalankan server:

```bash
./reload_local.sh
```

Di `/provider/chat-simulations`, pilih mode `Gemini AI` pada dropdown `Mode`, lalu kirim pesan seperti biasa.

Backend hanya mengirim pertanyaan yang relevan ke Gemini. Pertanyaan yang jelas di luar knowledge base akan ditolak lokal dengan jawaban aman, tanpa memanggil API.

### Close chat ke admin

MVP chatbot tidak melakukan aksi sales langsung. Chatbot hanya menjawab pertanyaan dari knowledge base, lalu menanyakan persetujuan sebelum diteruskan ke admin.

Trigger close confirmation:

- Pengguna meminta pendaftaran, misalnya `Saya mau daftar les`.
- Jumlah pertanyaan dalam satu sesi mencapai 10.
- Sistem mendeteksi konteks inti knowledge base sudah terpakai semua dalam sesi.

Kalimat konfirmasi:

```text
Apakah mau diteruskan ke pendaftaran?
```

Jika pengguna setuju, chatbot menjawab:

```text
Baik, saya akan hubungkan ke admin.
```

Setelah itu status sesi menjadi `transferred_to_admin`, dan composer di UI simulator dimatikan agar percakapan berikutnya ditangani admin manusia.

## Integrasi Instagram DM

Webhook Instagram disiapkan langsung di backend:

```text
GET  /webhooks/instagram
POST /webhooks/instagram
```

File handler webhook ada di `backend/app/instagram_webhook.py`, lalu dipasang ke HTTP server lewat `backend/app/main.py`.

Alurnya:

1. Meta melakukan verifikasi ke `GET /webhooks/instagram`.
2. Meta mengirim event DM ke `POST /webhooks/instagram`.
3. Backend mengambil pesan teks dari payload webhook.
4. Pesan dimasukkan ke sistem simulasi chatbot dengan channel `instagram`.
5. Chatbot menjawab memakai mode `gemini` jika `GEMINI_API_KEY` tersedia, atau `rule_based` jika tidak.
6. Jika sesi sudah `transferred_to_admin`, bot tidak membalas lagi supaya admin manusia bisa mengambil alih.

### Environment variable Instagram

```bash
IG_WEBHOOK_VERIFY_TOKEN=buat-string-random-yang-sama-dengan-dashboard-meta
IG_APP_SECRET=app-secret-dari-meta
IG_ACCESS_TOKEN=access-token-instagram-atau-page
IG_USER_ID=id-instagram-professional-account
IG_REPLY_MODE=gemini
IG_SEND_ENABLED=1
IG_GRAPH_API_VERSION=v24.0
```

Catatan:

- `IG_WEBHOOK_VERIFY_TOKEN` dibuat sendiri oleh kamu, lalu dimasukkan juga ke Meta App Dashboard.
- `IG_APP_SECRET` dipakai untuk validasi signature `X-Hub-Signature-256`.
- `IG_ACCESS_TOKEN` jangan pernah dicommit ke git.
- `IG_REPLY_MODE` bisa `gemini` atau `rule_based`.
- `IG_SEND_ENABLED=0` berguna untuk dry run: webhook diterima dan diproses, tapi backend tidak mengirim balasan ke Instagram.
- `IG_GRAPH_API_VERSION` default-nya `v24.0`, jadi boleh tidak diset kalau ingin pakai default.

Contoh menjalankan lokal:

```bash
# Edit .env lebih dulu:
# GEMINI_API_KEY=isi_api_key_gemini_kamu
# IG_WEBHOOK_VERIFY_TOKEN=madani-dev-verify-token
# IG_REPLY_MODE=gemini
# IG_SEND_ENABLED=0
./reload_local.sh
```

Default `reload_local.sh` memakai port `8001`.

### Test webhook lokal

Test verifikasi webhook:

```bash
curl "http://127.0.0.1:8001/webhooks/instagram?hub.mode=subscribe&hub.verify_token=$IG_WEBHOOK_VERIFY_TOKEN&hub.challenge=CHALLENGE_OK"
```

Jika benar, output-nya:

```text
CHALLENGE_OK
```

Test event DM lokal:

```bash
curl -X POST "http://127.0.0.1:8001/webhooks/instagram" \
  -H "Content-Type: application/json" \
  -d '{"object":"instagram","entry":[{"messaging":[{"sender":{"id":"test-user"},"recipient":{"id":"test-ig-business"},"message":{"mid":"m_1","text":"Halo"}}]}]}'
```

Jika benar, output-nya:

```text
EVENT_RECEIVED
```

Untuk konfigurasi di Meta App Dashboard, callback URL harus HTTPS publik. Saat development lokal, gunakan tunnel seperti ngrok atau Cloudflare Tunnel:

```text
https://domain-tunnel-kamu/webhooks/instagram
```

### Cara mendapatkan API key/token Instagram

Instagram API tidak memakai satu “API key” seperti Gemini. Yang dipakai adalah kombinasi Meta App, App Secret, access token, dan Instagram Professional Account ID.

Langkah ringkas:

1. Ubah akun Instagram lembaga menjadi Professional Account, boleh Business atau Creator.
2. Hubungkan akun Instagram itu ke Facebook Page atau Meta Business yang sesuai.
3. Buka [Meta for Developers](https://developers.facebook.com/), lalu buat app baru.
4. Pilih tipe/use case yang mendukung Instagram API atau Instagram Messaging.
5. Di App Dashboard, buka `Settings > Basic`, lalu copy `App Secret` ke `IG_APP_SECRET`.
6. Buat verify token sendiri, misalnya `madani-prod-verify-token`, lalu set sebagai `IG_WEBHOOK_VERIFY_TOKEN`.
7. Generate access token dengan permission messaging Instagram. Untuk Instagram Login, permission yang dibutuhkan umumnya mencakup:
   - `instagram_business_basic`
   - `instagram_business_manage_messages`
8. Jika memakai Facebook Login/Page flow, ambil Page access token dari Page yang terhubung ke Instagram, lalu pastikan permission Page dan Instagram messaging sudah diberikan.
9. Ambil `IG_USER_ID`, yaitu ID Instagram Professional Account. Pada Page flow, biasanya bisa dicek dengan Graph API:

```bash
curl "https://graph.facebook.com/v24.0/me/accounts?fields=name,access_token,tasks,instagram_business_account&access_token=USER_ACCESS_TOKEN"
```

Copy:

- `instagram_business_account.id` sebagai `IG_USER_ID`.
- `access_token` milik Page/Instagram yang valid sebagai `IG_ACCESS_TOKEN`.

Setelah `IG_USER_ID` dan `IG_ACCESS_TOKEN` ada, subscribe akun Instagram ke webhook:

```bash
curl -X POST "https://graph.instagram.com/v24.0/$IG_USER_ID/subscribed_apps?subscribed_fields=messages,messaging_postbacks&access_token=$IG_ACCESS_TOKEN"
```

Response sukses biasanya:

```json
{"success": true}
```

Terakhir, di Meta App Dashboard:

1. Buka produk Instagram atau Webhooks.
2. Isi Callback URL dengan `https://domain-kamu/webhooks/instagram`.
3. Isi Verify Token dengan nilai yang sama seperti `IG_WEBHOOK_VERIFY_TOKEN`.
4. Subscribe field `messages` dan `messaging_postbacks`.
5. Kirim test event dari dashboard atau DM akun Instagram tersebut dari akun lain.

Untuk production, app biasanya perlu App Review/Advanced Access agar permission messaging bisa dipakai oleh user di luar role developer/tester.

### Troubleshooting token Instagram

Jika klik `Buat token` / `Generate token` hanya membuka halaman profil Instagram dan token tidak muncul, biasanya flow permission popup Meta gagal di browser. Kasus yang pernah terjadi: Safari berhasil login Instagram, tetapi tidak menampilkan popup `Allow` untuk permission, sehingga token tidak tergenerate. Solusinya:

1. Gunakan Google Chrome.
2. Lebih aman pakai Incognito/Private Window agar session Meta dan Instagram tidak tercampur.
3. Matikan ad blocker/privacy blocker sementara.
4. Izinkan pop-up dan redirect untuk:
   - `developers.facebook.com`
   - `facebook.com`
   - `instagram.com`
5. Login Meta Developer dengan akun developer.
6. Klik `Buat token` dari Meta Dashboard.
7. Login/continue Instagram dengan akun tester yang sudah ditambahkan dan menerima invite.
8. Pastikan popup permission muncul, lalu klik `Allow` / `Izinkan semua permission`.

Kalau hanya masuk ke profil Instagram, ulangi dari Chrome/incognito. Untuk setup token test, Chrome lebih stabil daripada Safari.

Referensi:

- [Meta/Postman Instagram API - Subscribe to webhooks](https://www.postman.com/meta/instagram/request/23987686-0223707a-7035-46a2-8015-1fdf7249278f)
- [Meta/Postman Messenger Platform Webhooks](https://www.postman.com/meta/messenger-platform-api/folder/22794852-b5d97624-14d8-4e67-a2e4-529add49ca58)

## Menjalankan

```bash
python3 -m backend.app.migrate
python3 -m backend.app.seed
python3 -m backend.app.main
```

Atau reload server lokal dengan script:

```bash
./reload_local.sh
```

Default script memakai port `8001`. Untuk port lain:

```bash
PORT=8002 ./reload_local.sh
```

Jika ingin proses tetap terlihat di terminal:

```bash
./reload_local.sh foreground
```

## Test

```bash
python3 -m unittest discover -s tests
```

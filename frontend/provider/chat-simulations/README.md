# Admin Chatbot Training UI

UI ini disajikan untuk admin les lewat route:

```text
/client/chatbot
```

Route lama `/provider/chat-simulations` masih tersedia sebagai alias teknis agar link lama tidak putus, tetapi jangan dipakai di UX client.

Sebelum membuka halaman latihan, user akan diminta password. Password disimpan di root `.env`:

```bash
APP_AUTH_PASSWORD=...
```

Tidak ada username. API internal chatbot juga ikut diproteksi oleh session cookie setelah login. Alias lama `CHATBOT_TEST_PASSWORD` tetap didukung jika konfigurasi lama masih dipakai.

Asset JavaScript dan CSS berada di `frontend/provider/assets`. Nama folder lama hanya detail teknis internal.

Dropdown `Mode` mendukung:

- `Rule-based`: balasan lokal dari logic simulator.
- `Gemini AI`: balasan dari Gemini API lewat backend, memakai knowledge base dan guardrail.

Jika chatbot sudah mendapat persetujuan untuk diteruskan ke admin, sesi masuk stage `transferred_to_admin` dan input chat di simulator dimatikan.

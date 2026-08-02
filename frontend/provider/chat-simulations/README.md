# Provider Chat Simulations UI

UI ini hanya disajikan lewat route provider:

```text
/provider/chat-simulations
```

Sebelum membuka simulator, user akan diminta password. Password disimpan di root `.env`:

```bash
APP_AUTH_PASSWORD=...
```

Tidak ada username. API provider juga ikut diproteksi oleh session cookie setelah login. Alias lama `CHATBOT_TEST_PASSWORD` tetap didukung jika konfigurasi lama masih dipakai.

Asset JavaScript dan CSS berada di `frontend/provider/assets`. Tidak ada file yang ditambahkan ke dashboard client.

Dropdown `Mode` mendukung:

- `Rule-based`: balasan lokal dari logic simulator.
- `Gemini AI`: balasan dari Gemini API lewat backend, memakai knowledge base dan guardrail.

Jika chatbot sudah mendapat persetujuan untuk diteruskan ke admin, sesi masuk stage `transferred_to_admin` dan input chat di simulator dimatikan.

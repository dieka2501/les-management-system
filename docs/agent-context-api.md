# Agent Context API

Endpoint ini dipakai untuk membaca konteks UAT lewat API tanpa akses DB langsung.

## Environment

Set token khusus di UAT:

```bash
AGENT_CONTEXT_TOKEN=isi-token-panjang-random
```

Jangan gunakan password admin sebagai token ini.

## Request

```bash
curl -H "Authorization: Bearer $AGENT_CONTEXT_TOKEN" \
  https://<host-uat>/api/agent/context
```

Alternatif header:

```bash
curl -H "X-Agent-Context-Token: $AGENT_CONTEXT_TOKEN" \
  https://<host-uat>/api/agent/context
```

## Isi Snapshot

Response berisi snapshot terbatas untuk debugging:

- ringkasan jumlah data
- knowledge chatbot statis
- paket, aturan jawaban, dan koreksi chatbot
- sesi chatbot terbaru dari latihan, WA, dan Instagram
- cabang, mata pelajaran, guru, jadwal, orang tua, murid, dan pendaftaran

Field kontak privat seperti telepon, email, dan alamat orang tua dimasking.

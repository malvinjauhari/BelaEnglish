# BelaEnglish

Voice agent untuk latihan speaking bahasa Inggris — ngobrol suara dengan
karakter 2.5D semi-realistis bernama **Rey**. Python + PyQt6 + Gemini Live API.

> **Status: M1 — UI shell + karakter blockout.** Suara, Gemini, dan database
> menyusul di M2–M4. Baca **[PLAN.md](PLAN.md)** untuk arsitektur lengkap.

## Yang sudah jalan (M1)

- Jendela frameless rounded, tema gelap, drag + resize + maximize.
- Karakter Rey digambar penuh dengan `QPainter` (blockout semi-realistis):
  napas, kedip acak, arah pandang mengikuti kursor, 6 ekspresi, 7 bentuk mulut.
- Animasi 60 fps dengan auto-degrade ke 30 fps kalau mesin keberatan.
- State machine percakapan (idle → listening → thinking → speaking → interrupted)
  yang nanti disambungkan ke Gemini Live.
- Panel transkrip dengan bubble Rey/kamu + kartu koreksi.
- Pemilih mode (Free Talk, Roleplay, Drill, Review), tombol mic + mute,
  statistik sesi, dialog pengaturan, penyimpanan `config.json`.
- 23 unit test untuk state machine, config, dan viseme.

Belum aktif di M1: input teks, mikrofon, suara, API, database, aset art final.

## Jalankan

Butuh Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

M1 tidak butuh API key. Saat M2 masuk, salin config dan isi key:

```bash
cp config.example.json config.json   # isi GEMINI_API_KEY
```

Key juga bisa dari environment: `export GEMINI_API_KEY=...`.

## Kontrol

| Aksi | Cara |
|---|---|
| Mute / unmute | `Ctrl+Space` atau klik tombol mic |
| Ganti mode | Klik chip Free Talk / Roleplay / Drill / Review |
| Pengaturan | Ikon ⚙ di title bar |
| Tutup | `Esc` atau tombol ✕ |

## Test

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
```

## Dokumen

| File | Isi |
|---|---|
| [PLAN.md](PLAN.md) | Rencana lengkap: arsitektur, data, UI, roadmap, risiko |
| [docs/PERSONA.md](docs/PERSONA.md) | Kepribadian Rey + system instruction final |
| [docs/MARK-LI-STUDY.md](docs/MARK-LI-STUDY.md) | Hasil studi codebase Mark-LI dan keputusan turunannya |

## Konsep

```
User bicara → AI memproses → AI melihat data (skenario, vocab, profil,
riwayat kesalahan) → AI merespons dengan suara + animasi karakter
```

Rey spontan, padat, friendly. Boleh pakai ekspresi kasual ("anjir", "gila",
"damn") sebagai bahan edukasi register — tidak pernah sebagai hinaan.

## Target MVP

- Ngobrol suara real-time, latency terasa < 1,1 detik.
- Karakter hidup: napas, kedip, lip sync, 6 ekspresi.
- 4 mode: Free Talk, Roleplay, Drill, Review.
- Laporan sesi + spaced repetition.
- 100% lokal untuk data; hanya audio yang dikirim ke Gemini.

## Struktur

```
BelaEnglish/
├── run.py
├── app/
│   ├── main.py
│   ├── config.py
│   ├── core/     # bus, state machine (+ live session, audio, tools di M2+)
│   └── ui/       # window, avatar rig, transcript, theme
├── assets/rig.json
├── tests/
└── docs/
```

## Lisensi

Belum ditentukan. Jangan distribusikan sebelum diputuskan.

# BelaEnglish

Voice agent untuk latihan speaking bahasa Inggris — ngobrol suara dengan
karakter 2.5D semi-realistis bernama **Rey**. Python + PyQt6 + Gemini Live API.

> **Status: PLAN.** Belum ada implementasi. Baca **[PLAN.md](PLAN.md)** dulu.

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

## Struktur Rencana

```
BelaEnglish/
├── PLAN.md
├── requirements.txt
├── config.example.json
├── app/
│   ├── core/     # live session, audio, tools, memory, persona
│   ├── ui/       # window, avatar rig, transcript, theme
│   └── data/     # schema.sql + seed
├── tests/
└── docs/
```

## Menjalankan (nanti, setelah M1)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json   # isi GEMINI_API_KEY
python run.py
```

## Lisensi

Belum ditentukan. Jangan distribusikan sebelum diputuskan.

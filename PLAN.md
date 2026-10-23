# BelaEnglish — Rencana Pembangunan (Plan First)

> Voice agent untuk latihan speaking bahasa Inggris, dengan karakter 2.5D
> semi-realistis yang bisa diajak ngobrol. Dibangun ulang dengan Python + PyQt6,
> mengambil pola arsitektur dari codebase **Mark-LI** (repo ini) sebagai
> referensi.

Status: **PLAN — belum ada implementasi.** Dokumen ini yang jadi kontrak kerja
sebelum kode pertama ditulis.

Tanggal: 2026-10-23

---

## 1. Ringkasan Produk

BelaEnglish adalah aplikasi desktop yang membuat user bisa **ngobrol suara**
dengan karakter bernama **Rey** untuk latihan bahasa Inggris. Rey bukan chatbot
kaku: dia spontan, padat, friendly, dan boleh pakai ekspresi kasual
("anjir", "gila", "damn") sebagai bahan edukasi register bahasa.

Alur inti yang diminta:

```
User bicara  →  AI memproses  →  AI melihat data yang tersedia  →  AI merespons
                 (Gemini Live)     (scenario, vocab, profil,      (suara + teks +
                                    riwayat kesalahan)              animasi karakter)
```

### Tujuan MVP

1. Ngobrol suara real-time, latency terasa natural (< 1 detik sebelum Rey mulai
   bicara).
2. Karakter 2.5D semi-realistis yang bereaksi: idle, mendengar, berpikir,
   bicara (lip sync), ekspresi senang/bingung/termotivasi.
3. Rey punya "data yang tersedia": skenario latihan, bank frasa/kosakata,
   profil user, dan riwayat kesalahan — diakses lewat tool call.
4. Koreksi bahasa yang halus: maksimal satu koreksi per turn, dibungkus recast
   natural, bukan ceramah grammar.
5. Laporan akhir sesi: kesalahan, kosakata baru, saran latihan berikutnya.

### Non-tujuan MVP (sengaja ditunda)

- Multi-user / akun cloud.
- Mobile / web remote dashboard.
- Menilai aksen dengan skor fonem (butuh model khusus).
- Login, pembayaran, marketplace skenario.
- 3D penuh (VRM/glTF). Keputusan: 2.5D dulu, 3D adalah upgrade terpisah.

---

## 2. Keputusan Arsitektur (ADR ringkas)

| # | Keputusan | Alasan | Konsekuensi |
|---|---|---|---|
| A1 | **PyQt6** untuk UI | Diminta user; Mark-LI juga PyQt6 sehingga pola rendering & threading bisa diadaptasi | — |
| A2 | **Gemini Live API native audio** (`gemini-2.5-flash-native-audio-preview-12-2025`) | Latency paling rendah, barge-in natural, tidak perlu rangkai STT→LLM→TTS | Kontrol materi via tool call + system instruction, bukan via pipeline teks |
| A3 | **Karakter 2.5D semi-realistis** dengan layered PNG rig di QPainter, bukan WebEngine/3D | Ringan, tanpa dependensi browser, 60fps, dan tetap bisa tampil "hidup" dengan shading yang sudah di-bake | Butuh art semi-realistis yang konsisten (bukan vector); lip sync harus pakai crossfade tekstur, bukan shape swap |
| A4 | **SQLite (stdlib)** untuk data latihan & progres | Lokal, nol biaya, cukup untuk skala personal | Migrasi manual sederhana (versioned SQL) |
| A5 | **qasync** — satu event loop untuk Qt + asyncio | Menghindari jembatan thread manual yang rawan race | Wajib disiplin: tidak boleh blocking call di event loop |
| A6 | **Tool calling** sebagai jembatan "AI melihat data" | Model tetap bisa jawab bebas, tapi fakta latihan tetap deterministik dari DB | Perlu schema tool yang ketat + timeout/fallback |
| A7 | **Repo terpisah** (`BelaEnglish.git`) walau folder ada di dalam Mark-LI | Riwayat & rilis independen; Mark-LI tetap referensi yang tidak diubah | Folder di-ignore oleh git Mark-LI via `.git/info/exclude` |

### Alternatif yang ditolak (untuk sekarang)

- **Cascaded STT→LLM→TTS**: kontrol lebih besar, tapi 3 hop latency + 3 vendor.
  Disimpan sebagai backend cadangan kalau Gemini Live bermasalah (interface
  `RealtimeBackend` disiapkan agar bisa ditukar).
- **QtQuick3D / three.js + VRM**: hasil visual lebih hidup, tapi menambah
  QWebEngine + ratusan MB dan isu transparansi di Linux. Ditunda ke v2.
- **Gemini `avatar_config`** (avatar video bawaan Gemini): menarik untuk
  eksperimen, tapi tidak cocok dengan art style 2.5D yang kita mau.

---

## 3. Hasil Studi Codebase Mark-LI

Analisis dilakukan langsung pada source (repo ini lengkap), bukan pada binary,
jadi REA (lihat §12) hanya dipakai untuk verifikasi tooling — bukan untuk
membedah artefak.

### 3.1 Yang diambil (pola terbukti)

| Pola Mark-LI | Lokasi | Yang diadopsi |
|---|---|---|
| Audio in 16 kHz, chunk 1024, callback sounddevice → `asyncio.Queue` | `main.py:86-89`, `main.py:962-989` | Struktur yang sama untuk mic BelaEnglish |
| Audio out 24 kHz, chunk dipotong 2400 byte (~50 ms) supaya interrupt responsif | `main.py:1005-1010` | Pemotongan chunk yang sama |
| TaskGroup: sender / listener / receiver / player berjalan paralel | `main.py:1526-1534` | Orkestrasi task yang sama, ditambah state machine eksplisit |
| Reconnect loop + fallback config saat API menolak fitur preview | `main.py:1488-1568` | Wajib untuk stabilitas preview API |
| Transkrip in/out + `turn_complete` sebagai penanda akhir giliran | `main.py:1012-1060` | Sumber teks untuk UI, log, dan statistik sesi |
| Tool call → eksekusi Python → `send_tool_response` | `main.py:1093-1101` | Inti mekanisme "AI melihat data" |
| Prompt disusun berlapis: waktu + identitas + memori + prompt inti | `main.py:696-741` | Prompt builder berlapis yang sama |
| UI update lintas thread lewat `pyqtSignal` | `ui.py:2013-2020`, `ui.py:3697-3700` | Event bus signal-based |
| Avatar audio-reactive via `set_volume()` | `ui.py:380-409`, `ui.py:525-532` | Diganti rig QPainter, ide envelope-nya dipakai |
| Plugin sebagai satu file + registry tool | `core/plugin_loader.py` | Ditunda; tapi `ToolRegistry` disiapkan agar plugin mudah masuk |

### 3.2 Yang sengaja tidak diambil

| Hal di Mark-LI | Kenapa tidak dipakai |
|---|---|
| Mic diblokir total saat AI bicara (`main.py:966-975`) | Mematikan barge-in. Untuk tutor, user harus bisa menyela. Lihat §6.4 |
| Memory berbasis JSON bebas (`memory/long_term.json`) | Tidak cocok untuk query statistik & spaced repetition → SQLite |
| Prompt "JARVIS profesional, no fluff, panggil 'sir'" (`core/prompt.txt`) | Bertentangan total dengan persona Rey yang kasual |
| 20+ tool sistem operasi (browser, volume, game updater, dll.) | Di luar scope; hanya tool latihan bahasa yang didaftarkan |
| UI HUD sci-fi berat (scanline, glow, boot sequence) | Diganti UI companion yang lebih tenang dan fokus percakapan |
| `main.py` monolit 80 KB | Dipecah per modul (lihat §10) |

### 3.3 Catatan teknis dari Mark-LI yang harus diwaspadai

1. **Model ID preview gampang berubah.** Mark-LI memakai
   `models/gemini-2.5-flash-native-audio-preview-12-2025` (`main.py:85`).
   BelaEnglish menyimpan daftar model di config + fallback berurutan.
2. **SDK di venv adalah `google-genai 2.20.0`**, lebih baru dari
   `requirements.txt` Mark-LI (`>=2.8.0`). Fitur yang tersedia dan sudah
   diverifikasi: `realtime_input_config` (`activity_handling`,
   `automatic_activity_detection`), `LiveServerContent.interrupted`,
   `context_window_compression`, `proactivity`, `safety_settings`.
3. **`interrupted` belum dipakai Mark-LI.** BelaEnglish memakainya untuk
   flush queue audio + reset animasi mulut.
4. **UI dan asyncio dipisah thread** di Mark-LI (`main.py:1618-1622`). Pola itu
   jalan, tapi qasync membuat kode lebih sederhana dan aman.
5. **Tidak ada test sama sekali.** BelaEnglish menetapkan test untuk persona,
   tool, dan DB sejak milestone pertama.

---

## 4. Arsitektur Sistem

```
┌──────────────────────────── Qt Main Thread ────────────────────────────┐
│  MainWindow ── AvatarStage (QPainter 60fps) ── TranscriptView          │
│        ▲                ▲                        ▲                      │
│        │ pyqtSignal     │ envelope/emotion       │ token/transcript     │
└────────┼────────────────┼────────────────────────┼──────────────────────┘
         │                │                        │
┌────────┴────────────────┴────────────────────────┴──────────────────────┐
│                    asyncio event loop (qasync)                          │
│  LiveSession ── TurnStateMachine ── ToolRegistry ── MemoryService       │
│      │                │                  │              │               │
│      │                │                  │              └── SQLite      │
│      │                │                  └── scenario / vocab / progress │
│      ▼                ▼                                                  │
│  AudioIn (sounddevice)   AudioOut (sounddevice) ──► EnvelopeAnalyzer     │
└─────────────────────────────────────────────────────────────────────────┘
         │ mic 16 kHz int16                         speaker 24 kHz int16
```

### 4.1 Pembagian tanggung jawab

- `LiveSession` — koneksi, reconnect, kirim audio, terima audio/transkrip/tool
  call. Tidak tahu UI.
- `TurnStateMachine` — state `CONNECTING → IDLE → LISTENING → THINKING →
  SPEAKING → INTERRUPTED`, memutuskan kapan UI berubah.
- `ToolRegistry` — deklarasi tool untuk Gemini + dispatcher ke service Python,
  dengan timeout dan error yang tidak mematikan sesi.
- `MemoryService` — semua akses SQLite (profil, skenario, kesalahan, progres).
- `AudioIn/Out` — device I/O murni, tanpa logika bisnis.
- `EnvelopeAnalyzer` — PCM → RMS + fitur spektral ringan → `speech_level`,
  `viseme_hint` untuk avatar.

### 4.2 Threading rules

1. Hanya main thread yang menyentuh widget Qt.
2. Semua I/O jaringan/DB async, tidak ada `time.sleep`.
3. Callback sounddevice hanya menaruh bytes ke queue (tidak boleh alokasi berat).
4. Komunikasi async → UI selalu lewat `pyqtSignal`.
5. Setiap tool punya timeout 4 detik; kalau lewat, kirim `{"error": "timeout"}`
   ke model supaya dia tetap menjawab.

---

## 5. Pipeline Audio (Gemini Live)

### 5.1 Input

| Parameter | Nilai |
|---|---|
| Sample rate | 16 000 Hz |
| Channels | 1 (mono) |
| Format | int16 PCM |
| Block size | 1024 frame (~64 ms) |
| Kirim ke API | `send_realtime_input(media={"data": bytes, "mime_type": "audio/pcm"})` |

- Pre-roll buffer 300 ms supaya kata pertama tidak terpotong setelah VAD buka.
- Noise gate ringan (RMS threshold adaptif) untuk mengurangi kiriman saat hening.
- Pilihan device & level meter di Settings.

### 5.2 Output

| Parameter | Nilai |
|---|---|
| Sample rate | 24 000 Hz |
| Channels | 1 |
| Chunk | dipotong 2400 byte (~50 ms) |
| Device | `sd.RawOutputStream` |

### 5.3 Konfigurasi Live yang direncanakan

```python
LiveConnectConfig(
    response_modalities=["AUDIO"],
    system_instruction=persona_prompt,
    tools=[{"function_declarations": [...], "google_search": {}}],  # eval nanti
    input_audio_transcription={},
    output_audio_transcription={},
    speech_config=SpeechConfig(
        voice_config=VoiceConfig(
            prebuilt_voice_config=PrebuiltVoiceConfig(voice_name="Kore")
        )
    ),
    realtime_input_config=RealtimeInputConfig(
        activity_handling=ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
        automatic_activity_detection=AutomaticActivityDetection(
            start_of_speech_sensitivity=StartSensitivity.START_SENSITIVITY_HIGH,
            silence_duration_ms=650,
            prefix_padding_ms=300,
        ),
        turn_coverage=TurnCoverage.TURN_INCLUDES_ONLY_ACTIVITY,
    ),
    context_window_compression=ContextWindowCompressionConfig(
        sliding_window=SlidingWindow()
    ),
    session_resumption=SessionResumptionConfig(),
)
```

Nilai di atas adalah titik awal; tuning dilakukan di M2 dengan metrik latency
nyata.

### 5.4 Barge-in (penting, beda dari Mark-LI)

1. Mic **tidak** dimatikan saat Rey bicara (Mark-LI mematikannya — lihat §3.2).
2. `activity_handling=START_OF_ACTIVITY_INTERRUPTS` membuat server memutus
   respons sendiri saat user mulai bicara.
3. Saat menerima `server_content.interrupted`:
   - kosongkan `audio_out_queue`,
   - hentikan animasi mulut & set state `LISTENING`,
   - tandai turn yang dipotong sebagai `interrupted` di DB.
4. Mode "headphone" (default) vs "speaker":
   - headphone: barge-in penuh.
   - speaker: setengah dupleks adaptif — input di-attenuasi saat output keras,
     supaya suara Rey tidak memicu interrupt sendiri.
5. Tombol mute + push-to-talk (`Ctrl+Space`) sebagai fallback.

### 5.5 Latency budget (target)

| Tahap | Target |
|---|---|
| Akhir ucapan user → VAD tutup | 650 ms (config) |
| Kirim → first audio byte | ≤ 400 ms |
| First audio byte → suara keluar speaker | ≤ 80 ms (buffer 50 ms) |
| **Total terasa** | **≤ 1.1 s** |

Diukur dan dicatat per turn (`latency_ms`) supaya bisa dibandingkan antar versi.

---

## 6. Alur Percakapan

### 6.1 Turn loop

```
1. User bicara                      → state LISTENING
2. Server VAD menutup giliran       → state THINKING
3. Model memutuskan tool call       → ToolRegistry (timeout 4 s)
     • get_scenario_context()
     • get_user_profile()
     • lookup_phrase(query)
     • save_mistake(...)
     • set_emotion(...)
4. Hasil tool dikirim balik         → model lanjut
5. Model streaming audio + transkrip→ state SPEAKING
6. turn_complete                    → simpan turn, hitung statistik, state IDLE
```

### 6.2 Mode latihan

| Mode | Perilaku Rey | Data yang dipakai |
|---|---|---|
| **Free Talk** | Ngobrol bebas, topik mengikuti user | profil, riwayat kesalahan, kosakata due |
| **Roleplay** | Main peran sesuai skenario (kafe, interview, bandara) | `scenarios`, `phrases` |
| **Drill** | Fokus satu pola/kosakata, minta user ulangi | `vocab`, `phrases` |
| **Review** | Bahas kesalahan sesi sebelumnya, kuis singkat | `mistakes`, `vocab_reviews` |

### 6.3 Aturan pedagogis (ditanam di prompt + ditegakkan tool)

1. **Satu koreksi per turn.** Kalau ada 3 kesalahan, pilih yang paling
   mengganggu makna.
2. **Recast dulu, jelaskan kemudian.** Contoh: user bilang "I go there
   yesterday" → Rey: "Oh you went there yesterday? Nice. (quick note: 'go' →
   'went' for past)". Kalau intensitas koreksi = 1, bagian note dihilangkan.
3. **Jangan pernah bilang "wrong".** Gunakan "more natural", "native speakers
   usually say…".
4. **Kosakata baru dicatat lewat tool**, bukan diucapkan sebagai daftar.
5. **Satu pertanyaan penutup** agar percakapan tidak mati.
6. **Sesuaikan level** (A2/B1/B2/C1): panjang kalimat, kecepatan, kerumitan
   kosakata.

### 6.4 Penanganan kasus khusus

- **User diam > 12 s**: Rey memberi satu prompt ringan ("Still there? Take your
  time — want me to repeat the question?"). Maksimal 2 kali, lalu idle.
- **User bicara Indonesia**: tetap jawab Inggris, boleh satu kalimat klarifikasi
  Indonesia, lalu kembali.
- **User minta bantuan arti**: `lookup_phrase` → jawab singkat + contoh kalimat.
- **Audio tidak jelas**: minta ulang sekali, lalu tawarkan 2 kemungkinan.
- **User marah/kesal**: spice level turun otomatis, nada lebih suportif.

---

## 7. Persona & System Instruction

Dokumen lengkap + prompt final: **[docs/PERSONA.md](docs/PERSONA.md)**.

Ringkasan kepribadian:

- **Rey**, 24 tahun, teman ngobrol bilingual (English/Indonesian) yang jago
  bahasa Inggris tapi santai, bukan guru formal.
- **Spontan**: reaksi dulu ("Wait, seriously?"), baru menjawab.
- **Padat**: default 1–3 kalimat, ≤ 40 kata.
- **Friendly**: kontraksi, filler natural, humor ringan.
- **Boleh kasual/kasar sebagai ekspresi**, bukan serangan: "anjir", "gila",
  "damn", "what the hell", "goblok" (self/ekslamasi). Tidak pernah
  diarahkan sebagai hinaan ke user.
- **Edukatif**: kalau pakai slang/kata kasar, sesekali beri gloss 3–6 kata
  supaya user belajar register.

### Spice level (setting user, default 1)

| Level | Contoh | Kapan |
|---|---|---|
| 0 | Bersih total | Anak-anak / mode formal |
| 1 | "damn", "hell", "shoot" | Default |
| 2 | "crap", "anjir", "gila", "what the hell" | User sudah nyaman |
| 3 | "goblok", "shit", "freaking" (eksklamasi) | User pilih sendiri |

### Guardrail

- Tanpa slur, tanpa konten seksual, tanpa ancaman.
- Kata kasar tidak pernah jadi predikat tentang user ("you are stupid" → dilarang).
- Kalau user terlihat terganggu, spice level turun dan Rey minta maaf singkat.
- Tetap patuh pada safety policy penyedia model; jika model menolak, ada
  fallback kalimat netral (bukan error ke user).

---

## 8. Data Layer

### 8.1 Prinsip

- Satu file `rayenglish.db` di direktori data user (`platformdirs`), bukan di repo.
- Skema versioned (`PRAGMA user_version`), migrasi idempoten saat start.
- WAL mode, semua akses lewat `MemoryService`.
- Seed data ada di `app/data/seed/*.json` dan di-import sekali.

### 8.2 Skema awal

```sql
CREATE TABLE profile (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  name TEXT, native_lang TEXT DEFAULT 'id',
  cefr_level TEXT DEFAULT 'B1',
  spice_level INTEGER DEFAULT 1,
  correction_level INTEGER DEFAULT 2,
  created_at TEXT, updated_at TEXT
);

CREATE TABLE scenarios (
  id INTEGER PRIMARY KEY, slug TEXT UNIQUE, title TEXT,
  cefr TEXT, setting TEXT, ai_role TEXT, user_role TEXT,
  goals_json TEXT, system_hint TEXT, active INTEGER DEFAULT 1
);

CREATE TABLE phrases (
  id INTEGER PRIMARY KEY, scenario_id INTEGER REFERENCES scenarios(id),
  en TEXT, id_translation TEXT, register TEXT, tags TEXT
);

CREATE TABLE vocab (
  id INTEGER PRIMARY KEY, lemma TEXT UNIQUE, pos TEXT, cefr TEXT,
  meaning_id TEXT, example_en TEXT, created_at TEXT
);

CREATE TABLE sessions (
  id INTEGER PRIMARY KEY, scenario_id INTEGER, mode TEXT,
  started_at TEXT, ended_at TEXT, turns INTEGER DEFAULT 0,
  words_spoken INTEGER DEFAULT 0, interrupted_count INTEGER DEFAULT 0
);

CREATE TABLE turns (
  id INTEGER PRIMARY KEY, session_id INTEGER, role TEXT,
  text TEXT, ts TEXT, latency_ms INTEGER, audio_ms INTEGER,
  interrupted INTEGER DEFAULT 0
);

CREATE TABLE mistakes (
  id INTEGER PRIMARY KEY, session_id INTEGER, turn_id INTEGER,
  kind TEXT, user_text TEXT, correction TEXT,
  note TEXT, created_at TEXT, resolved_at TEXT
);

CREATE TABLE vocab_reviews (
  id INTEGER PRIMARY KEY, vocab_id INTEGER,
  due_at TEXT, box INTEGER DEFAULT 1, ease REAL DEFAULT 2.5,
  last_reviewed_at TEXT
);

CREATE TABLE facts (
  id INTEGER PRIMARY KEY, key TEXT UNIQUE, value TEXT, updated_at TEXT
);

CREATE VIRTUAL TABLE search_fts USING fts5(
  kind, ref_id UNINDEXED, text, tokenize='unicode61'
);
```

### 8.3 Tool yang didaftarkan ke Gemini

| Tool | Input | Output | Dipakai saat |
|---|---|---|---|
| `get_scenario_context` | `{}` | setting, peran, tujuan, 5 frasa kunci | awal roleplay / user ganti topik |
| `get_user_profile` | `{}` | nama, level, preferensi, topik favorit | awal sesi / personalisasi |
| `lookup_phrase` | `query` | arti, contoh, register | user tanya arti/frasa |
| `save_mistake` | `kind, user_text, correction, note` | `ok` | setelah koreksi diberikan |
| `get_progress` | `{}` | level, akurasi 7 hari, kata lemah | user tanya progres / awal sesi |
| `set_emotion` | `emotion` | `ok` | setiap respons (animasi) |
| `next_drill` | `{}` | target kata/pola | mode drill / review |

Aturan: tool call tidak boleh lebih dari 2 per turn, dan `save_mistake` hanya
setelah koreksi benar-benar diucapkan.

### 8.4 Seed MVP

- 6 skenario: `cafe-order`, `job-interview`, `airport-checkin`, `small-talk`,
  `opinion-debate`, `storytelling`.
- ~120 frasa (20 per skenario), ~300 kata CEFR A2–C1.
- 4 paket drill bawaan: past tense, articles, connected speech, filler words.

---

## 9. UI / UX

### 9.1 Layout (1180 × 720, resizable, frameless rounded 18 px)

```
┌──────────────────────────────────────────────────────────────────────┐
│  BelaEnglish                                   ─   □   ✕             │
├───────────────────────────┬──────────────────────────────────────────┤
│                           │  Cafe Order · B1           00:42         │
│      ┌─────────────┐      │  ┌────────────────────────────────────┐  │
│      │             │      │  │ Rey  "So, what can I get you?"    │  │
│      │   KARAKTER  │      │  └────────────────────────────────────┘  │
│      │    2.5D     │      │       ┌──────────────────────────────┐   │
│      │             │      │       │ You  "I want one coffee"     │   │
│      └─────────────┘      │       └──────────────────────────────┘   │
│         ◉ mic orb         │  ┌─ correction ──────────────────────┐   │
│                           │  │ I'd like a coffee  ·  more natural│   │
│  [ Free Talk ] [ Roleplay]│  └───────────────────────────────────┘   │
│  [ Drill ]     [ Review ] │  ┌────────────────────────────────────┐  │
│                           │  │ Type instead…                  ➤   │  │
│  level ▓▓▓░░  WPM 92      │  └────────────────────────────────────┘  │
│  words +3   mistakes 1    │                                          │
└───────────────────────────┴──────────────────────────────────────────┘
```

### 9.2 Palet & tipografi

| Token | Nilai |
|---|---|
| Background | `#0B1020` (deep navy) |
| Surface | `#141A2E` (glass, 60% alpha) |
| Accent primary | `#7C5CFF` (violet) |
| Accent secondary | `#22D3EE` (cyan) |
| Correction | `#FF8A65` (coral) |
| Success | `#4ADE80` |
| Text | `#E8ECF8`, sekunder `#98A2C0` |
| Font | Inter / Segoe UI Variable, fallback system sans |

Semua warna di satu modul `ui/theme.py` (token, bukan hardcode di widget).

### 9.3 State karakter

| State | Visual |
|---|---|
| `IDLE` | napas halus, kedip tiap 2–6 s, senyum tipis |
| `LISTENING` | kepala miring 3°, alis naik, ring mic menyala |
| `THINKING` | mata ke atas, titik-titik kecil, mulut tertutup |
| `SPEAKING` | lip sync dari envelope, gerak kepala kecil, tangan opsional |
| `INTERRUPTED` | ekspresi kaget singkat, lalu `LISTENING` |
| `ERROR` | ekspresi bingung + tombol reconnect |

### 9.4 Interaksi

- Hotkey global `Ctrl+Space`: mute/unmute.
- Klik karakter: Rey bereaksi kecil (contoh: "Hm? Yeah?").
- Klik kartu koreksi: Rey membacakan versi yang benar.
- `Esc`: tutup overlay; window bisa selalu di atas (opsi).
- Tray icon: show/hide, mode, quit.
- Onboarding pertama: pilih nama, level, spice level, mic device, API key.

### 9.5 Accessibility & fallback

- Semua aksi bisa dilakukan dengan keyboard.
- Input teks selalu tersedia (bukan cuma suara).
- Transcript bisa di-copy; sesi bisa di-export ke Markdown.

---

## 10. Struktur Folder

```
BelaEnglish/
├── PLAN.md                  ← dokumen ini
├── README.md
├── requirements.txt
├── run.py                   ← entry point tipis
├── app/
│   ├── __init__.py
│   ├── main.py              ← bootstrap qasync + window
│   ├── config.py            ← load/save config, api key resolution
│   ├── core/
│   │   ├── live_session.py  ← koneksi Gemini Live, reconnect
│   │   ├── audio_io.py      ← sounddevice in/out
│   │   ├── envelope.py      ← RMS + viseme hint
│   │   ├── state.py         ← TurnStateMachine
│   │   ├── bus.py           ← pyqtSignal event bus
│   │   ├── tools.py         ← ToolRegistry + dispatcher
│   │   ├── persona.py       ← prompt builder
│   │   └── memory.py        ← MemoryService (SQLite)
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── avatar/
│   │   │   ├── stage.py     ← widget QPainter 60fps
│   │   │   ├── rig.py       ← layer, transform, ekspresi
│   │   │   ├── visemes.py   ← pemetaan envelope → bentuk mulut
│   │   │   └── assets/      ← SVG/PNG per layer
│   │   ├── transcript.py
│   │   ├── sidebar.py
│   │   ├── settings.py
│   │   ├── theme.py
│   │   └── tray.py
│   └── data/
│       ├── schema.sql
│       └── seed/*.json
├── tests/
│   ├── test_persona.py
│   ├── test_tools.py
│   ├── test_memory.py
│   └── test_state.py
└── docs/
    ├── PERSONA.md
    └── MARK-LI-STUDY.md
```

Prinsip: `ui/` tidak pernah import `google.genai`; `core/` tidak pernah import
`PyQt6` kecuali `bus.py`.

---

## 11. Avatar 2.5D Semi-Realistis — Spesifikasi Teknis

Art style: **semi-realistis** (kulit dengan shading halus, mata detail, rambut
berlapis, pencahayaan lembut). Konsekuensinya: tidak bisa mengandalkan bentuk
vector sederhana, dan pergantian bentuk mulut harus mulus agar tidak terlihat
"uncanny". Karena itu rig memakai **layer PNG yang sudah di-bake** + crossfade.

### 11.1 Layer (urutan render)

```
bg_glow → hair_back → torso → neck → head_base (kulit + telinga)
→ face_shadow → eye_white L/R → iris L/R → eyelid L/R → lashes L/R
→ brows L/R → nose → mouth_base → mouth_inner (gigi + lidah)
→ lips_upper → lips_lower → hair_front → accessory → blush/gloss → fx
```

- Format aset: **PNG RGBA**, canvas 1600×1600 (head) dan 1600×2000 (torso),
  diekspor @2x lalu di-downscale saat load.
- Setiap layer punya anchor tetap yang dicatat di `assets/rig.json`
  (`head`, `mouth`, `eye_l`, `eye_r`, `brow_l`, `brow_r`, `neck`).
- SVG **tidak** dipakai untuk art final (tidak cocok untuk painting); SVG hanya
  untuk ikon UI.

### 11.2 Placeholder vs art final

- **M1** memakai *blockout* prosedural (bentuk dasar + shading gradien) dengan
  kontrak anchor yang sama, supaya aplikasi bisa jalan dan diuji sebelum art ada.
- **M3** art semi-realistis menggantikan blockout tanpa mengubah kode rig —
  cukup ganti file + `rig.json`.
- Blockout **tidak** dipakai untuk demo publik; itu alat kerja.

### 11.3 Rig

- Breathing: `y = 2 * sin(2π * 0.25 * t)`, scale 1.000–1.005.
- Head sway: `rot = 1.5° * sin(2π * 0.18 * t + φ)`; tambahan tilt 3° saat
  `LISTENING`.
- Micro-saccade mata: geser iris 1–2 px setiap 1–3 s (semi-realistis butuh mata
  yang tidak "beku").
- Blink: 3 frame (open / half / closed), crossfade 70 ms, jadwal acak 2–6 s.
- Look-at kursor: iris bergeser maks 10 px, dengan dead-zone supaya tidak gelisah.
- Semua transisi pakai lerp eksponensial (`α = 1 - exp(-dt/τ)`).

### 11.4 Lip sync semi-realistis

Karena Gemini hanya mengirim PCM:

1. RMS per 20 ms → `level` (0–1, dinormalisasi adaptif).
2. FFT 512 titik → energi 3 band (low/mid/high) → `shape_hint`.
3. Petakan ke **7 tekstur mulut**: `M` (tertutup), `A`, `E`, `O`, `U`, `F`,
   `smile`.
4. **Crossfade dua tekstur terdekat** (alpha 60 ms), bukan hard swap. Ini kunci
   agar wajah semi-realistis tidak "patah".
5. Lapisan `jaw` ikut bergeser turun maks 3 px saat `A/O` untuk ilusi rahang.
6. Smoothing attack 40 ms / release 90 ms; saat `interrupted` paksa `M` dalam
   60 ms.
7. Saat hening, mulut kembali ke `M` dengan ekspresi netral (bukan senyum
   terus-menerus).

### 11.5 Emosi

`neutral, happy, thinking, confused, encouraging, surprised` — mengatur:
bentuk alis (4 varian per sisi), tinggi kelopak, curve sudut mulut, dan warna
rim light. Karena wajah semi-realistis, emosi **tidak** mengubah geometri wajah
secara ekstrem; cukup alis + mata + mulut + pencahayaan.

Dipicu tool `set_emotion` + heuristik lokal (mis. `THINKING` saat menunggu tool,
`SURPRISED` saat interupsi).

### 11.6 Performa & memori

- Pre-scale semua layer ke ukuran tampil saat load (bukan tiap frame).
- **Cache komposit statis** (`torso + hair_back + head_base + face_shadow +
  hair_front`) ke satu `QPixmap`; per frame hanya gambar 6–8 layer dinamis.
- Budget memori tekstur < 120 MB (1600² RGBA ≈ 10 MB per layer → jangan simpan
  semua di resolusi penuh).
- Target 60 fps @ 1180×720; CPU karakter < 8% satu core.
- Jika fps < 45 selama 3 s → turunkan ke 30 fps otomatis.

### 11.7 Pipeline & lisensi aset

Semi-realistis berarti kualitas art menentukan 60% hasil akhir. Opsi:

1. **Komisi artis** (paling konsisten): minta layer terpisah + anchor, bukan
   satu gambar jadi.
2. **AI-generated + retouch manual**: boleh untuk eksplorasi, tapi wajah harus
   konsisten antar layer; butuh kerja manual besar.
3. **Base 3D → render 2D**: buat/model karakter sederhana, render layer dari
   angle yang sama (paling mahal, paling konsisten).

Semua aset wajib punya izin pakai komersial dan dicatat di `assets/LICENSE.md`.


---

## 12. REA (Reverse Engineering Tooling)

- **Status: terpasang dan sehat.** `rea 6.7.0`, MCP terdaftar untuk OpenCode
  (`~/.config/opencode/opencode.jsonc`), skill versi 42, 207 tool.
- `doctor` melaporkan `healthy: true`; `environment_healthy: false` hanya karena
  engine native (Ghidra/IDA/Hopper) tidak dipasang.
- **Tidak diperlukan untuk proyek ini**, karena Mark-LI tersedia sebagai source
  Python lengkap. Analisis dilakukan dengan pembacaan source langsung
  (`grep`/`read`) dan hasilnya dicatat di `docs/MARK-LI-STUDY.md`.
- REA baru berguna kalau nanti kita mau membedah aplikasi pihak ketiga
  (mis. kompetitor desktop, paket Electron, APK) — bukan untuk repo ini.

---

## 13. Roadmap & Acceptance Criteria

### M0 — Plan (selesai saat dokumen ini di-commit)

- [x] Analisis Mark-LI
- [x] Keputusan arsitektur
- [x] Skema data & tool
- [x] Persona prompt draft
- [x] Review user (gerbang sebelum M1) — voice `Kore`, karakter perempuan

### M1 — Skeleton yang bisa dijalankan (selesai)

Deliverable: `python run.py` membuka window, karakter *blockout* idle bernapas &
berkedip, mode chip bisa diklik, transcript kosong, settings tersimpan.

Acceptance:
- [x] Window frameless + rounded, resize mulus, tidak flicker.
- [ ] 60 fps di mesin target — auto-degrade 30 fps sudah ada; perlu ukur di
      mesin user (belum bisa diverifikasi dari sesi ini).
- [x] Kontrak anchor `rig.json` sudah ada, walau art masih blockout.
- [x] `pytest` hijau (23 test: state, config, viseme).
- [x] Tidak ada API key hardcoded.

### M2 — Gemini Live tersambung

Deliverable: ngobrol suara 2 arah, transkrip muncul, barge-in bekerja, reconnect
otomatis.

Acceptance:
- [ ] First audio ≤ 1.1 s (diukur 20 turn, median).
- [ ] Interupsi menghentikan suara < 150 ms.
- [ ] Putus internet 5 s → reconnect tanpa restart aplikasi.
- [ ] Log transkrip tersimpan di DB.

### M3 — Karakter hidup (semi-realistis)

Deliverable: art semi-realistis terpasang, lip sync crossfade, emosi, state
visual sinkron dengan audio.

Acceptance:
- [ ] Layer PNG + `rig.json` menggantikan blockout tanpa ubah kode rig.
- [ ] Crossfade mulut tidak terlihat "patah" saat 10 kalimat uji.
- [ ] Mulut tertutup ≤ 120 ms setelah audio berhenti.
- [ ] 6 emosi bisa dipicu manual dan lewat tool.
- [ ] CPU karakter < 8%, memori tekstur < 120 MB.

### M4 — Data & tool

Deliverable: 6 skenario, frasa, profil, `save_mistake`, `lookup_phrase`,
`get_progress` berfungsi; Rey benar-benar memakai datanya.

Acceptance:
- [ ] Roleplay memakai frasa skenario (diverifikasi lewat log tool call).
- [ ] Koreksi tercatat di DB dan muncul di laporan.
- [ ] Tool timeout tidak mematikan sesi.

### M5 — Report & review

Deliverable: laporan akhir sesi, daftar kesalahan, kosakata baru, mode review
dengan spaced repetition.

Acceptance:
- [ ] Export Markdown rapi.
- [ ] `vocab_reviews` menjadwalkan ulang dengan benar (unit test).
- [ ] Mode review bisa kuis 5 item tanpa bug.

### M6 — Polish & distribusi

Deliverable: onboarding, tray, hotkey, PyInstaller build Linux, README.

Acceptance:
- [ ] Install di mesin bersih (venv) tanpa langkah manual tambahan.
- [ ] Build sekali klik; ukuran wajar (< 250 MB).
- [ ] Crash log tersimpan lokal.

Estimasi kasar: M1 2–3 hari, M2 3–4 hari, M3 4–6 hari, M4 4–5 hari,
M5 3–4 hari, M6 3–4 hari (bisa berubah sesuai iterasi desain).

---

## 14. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Model preview dihapus/di-rename | App tidak connect | Daftar model + fallback + pesan jelas; config bisa diedit |
| Gemini menolak persona kasar | Rey jadi datar | Spice default 1, prompt bertahap, fallback kalimat netral; opsi backend Ollama (v2) |
| Echo speaker memicu interrupt | Rey memotong diri sendiri | Mode headphone default; guard setengah dupleks; AEC (v2) |
| Latency internet Indonesia | Percakapan patah | Ukur p50/p95; chunk kecil; opsi region; cache prompt |
| Qt + asyncio race | Crash acak | qasync + aturan threading; test state machine; signal-only UI update |
| Aset karakter belum ada | Tidak bisa demo | Rig prosedural default di M1 |
| API key bocor | Biaya/penyalahgunaan | Key di file lokal `0600`/env, tidak pernah di-commit; `.gitignore` |
| Scope creep (plugin, OS control) | MVP tidak selesai | Non-goals ditulis eksplisit; plugin ditunda ke v2 |
| Data user sensitif | Privasi | Semua lokal; tidak ada upload selain audio ke Gemini; tombol hapus data |

---

## 15. Setup Development (rencana)

```bash
cd BelaEnglish
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp config.example.json config.json      # isi API key
python run.py
```

- API key: `GEMINI_API_KEY` env var, atau `config.json` (permission 0600).
- `config.json` masuk `.gitignore`.
- Test: `pytest -q`.
- Lint: `ruff check` (tanpa `ruff format`; formatting manual agar diff kecil).

---

## 16. Pertanyaan Terbuka

Sudah diputuskan: app **BelaEnglish**, karakter **Rey** (perempuan, pertengahan
20-an), art style **semi-realistis**, voice **Kore**.

1. **Sumber aset**: komisi artis, AI + retouch, atau render dari base 3D?
   (menentukan jadwal M3)
2. Level default user: B1? Dan apakah onboarding menanyakan level?
3. Perlu mode "Indonesian explanation" (penjelasan grammar dalam bahasa
   Indonesia) sebagai toggle, atau cukup sesekali?
4. Target platform rilis pertama: Linux saja, atau Windows juga?

---

## 17. Definisi Selesai (MVP)

BelaEnglish dinyatakan MVP kalau:

1. User bisa buka aplikasi, pilih skenario, dan ngobrol suara tanpa menyentuh
   keyboard.
2. Karakter terlihat hidup: bernapas, berkedip, mulut bergerak sesuai suara,
   ekspresi berubah sesuai konteks.
3. Rey memakai minimal 3 sumber data (skenario, profil, riwayat kesalahan) dan
   itu terlihat di log tool call.
4. Setiap sesi menghasilkan laporan yang bisa dibaca ulang.
5. Tidak ada crash selama 30 menit sesi terus-menerus.

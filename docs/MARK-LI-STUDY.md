# Studi Codebase Mark-LI → Bahan RayEnglish

Catatan analisis source Mark-LI (repo induk, versi ini: commit `d3238af`).
Tujuannya bukan menyalin, tapi mengambil pola yang sudah terbukti di lapangan
dan memperbaiki kelemahannya.

Semua rujukan baris merujuk ke file di root repo Mark-LI.

---

## 1. Peta Arsitektur Mark-LI

```
main.py (1.6k baris)          ui.py (3.7k baris)
├── JarvisLive                ├── MainWindow
│   ├── _build_config         │   ├── HudCanvas (QPainter, 60fps)
│   ├── _listen_audio         │   ├── _AvatarWebWidget (QWebEngineView + Three.js)
│   ├── _send_realtime        │   ├── LogWidget
│   ├── _receive_audio        │   ├── overlays (setup, customize, plugin, QR)
│   ├── _play_audio           │   └── tray + hotkeys
│   ├── _execute_tool         └── tema & palet (retheming runtime)
│   └── run (reconnect loop)
├── TOOL_DECLARATIONS (20+ tool OS)
└── main(): asyncio loop di thread terpisah

core/             memory/            actions/           plugins/
├── prompt.txt    ├── memory_manager ├── 20+ modul aksi  └── loader + template
├── plugin_loader └── long_term.json  └── (browser, file, dsb.)
├── stt.py
├── tts.py
└── llm_client.py
```

**Karakter dominan:** monolit fungsional. `main.py` memegang koneksi, audio,
tool dispatch, dan prompt sekaligus. `ui.py` memegang semua widget dalam satu
file. Tidak ada layer domain/service.

---

## 2. Konstanta Audio & Model

`main.py:85-89`

```python
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024
```

Implikasi untuk RayEnglish:

- Nilai ini sudah teruji, langsung dipakai.
- Model ID menyimpan tanggal preview (`12-2025`) → **harus** bisa dikonfigurasi.
- `CHUNK_SIZE=1024` @16 kHz ≈ 64 ms; cukup responsif, tidak terlalu banyak
  overhead callback.

---

## 3. Alur Audio

### 3.1 Mic → API

`main.py:962-989`

```python
def callback(indata, frames, time_info, status):
    with self._speaking_lock:
        jarvis_speaking = self._is_speaking
    if not jarvis_speaking and not self.ui.muted and not self._phone_active:
        data = indata.tobytes()
        loop.call_soon_threadsafe(
            self.out_queue.put_nowait,
            {"data": data, "mime_type": "audio/pcm"}
        )
```

Poin penting:

- Callback **tidak** melakukan I/O jaringan; hanya queue. Ini benar dan
  dipertahankan.
- `mime_type` cukup `"audio/pcm"`; SDK menyimpulkan rate dari konfigurasi live.
- **Kelemahan:** selama `_is_speaking` true, mic dibuang total. Barge-in mati.
  RayEnglish menghapus guard ini dan mengandalkan `activity_handling` +
  `interrupted`.

### 3.2 API → speaker

`main.py:999-1010`

```python
if response.data:
    _SLICE = 2400                      # 24000 Hz * 2 byte * 50 ms
    for _i in range(0, len(_audio_data), _SLICE):
        self.audio_in_queue.put_nowait(_audio_data[_i:_i+_SLICE])
```

Alasan pemotongan 50 ms: `interrupt()` bisa menghentikan suara dalam ≤ 50 ms
(komentar aslinya di `main.py:1005-1006`). Pola ini dipertahankan.

### 3.3 Playback

`main.py:1107-1116` membuka `sd.RawOutputStream` 24 kHz, mono, int16,
`blocksize=CHUNK_SIZE`, lalu menarik dari queue dengan timeout 0,1 s. Saat
`turn_done` dan queue kosong, stream di-flush. RayEnglish menambahkan envelope
analyzer di titik ini sebelum bytes dikirim ke device.

---

## 4. Siklus Sesi & Ketahanan

`main.py:1488-1568` — loop `while True` membungkus seluruh sesi:

1. Bangun config baru setiap reconnect (`_build_config`, `main.py:696`).
2. Client baru setiap reconnect (hindari state HTTP basi, `main.py:1494-1500`).
3. `TaskGroup` menjalankan 4 task inti + task fitur (`main.py:1526-1534`).
4. `except BaseException` menangkap `BaseExceptionGroup` dari TaskGroup
   (`main.py:1545-1550`) — detail penting, karena `except Exception` tidak
   menangkap cancellation group.
5. Fallback fitur preview: kalau error mengandung `INVALID_ARGUMENT` /
   `affective` / `proactiv`, matikan fitur lalu `continue`
   (`main.py:1555-1568`).

RayEnglish mengadopsi semuanya, plus exponential backoff + status UI yang jelas
(tidak hanya `print`).

---

## 5. Tool Calling

Deklarasi tool ada di `TOOL_DECLARATIONS` (lihat `_build_config`, `main.py:742`),
eksekusi di `_execute_tool` (`main.py:765-955`), pengiriman balik di
`main.py:1093-1101`.

Pola yang dipakai:

```python
if response.tool_call:
    fn_responses = []
    for fc in response.tool_call.function_calls:
        fr = await self._execute_tool(fc)
        fn_responses.append(fr)
    await self.session.send_tool_response(function_responses=fn_responses)
```

Catatan:

- `_execute_tool` menangkap exception dan mengembalikan
  `{"result": "Tool 'x' failed: ..."}` (`main.py:943-946`) sehingga sesi tidak
  mati. RayEnglish mempertahankan prinsip ini + timeout.
- Tool `save_memory` mengembalikan `{"silent": True}` (`main.py:781-784`) supaya
  model tidak mengumumkan bahwa ia menyimpan sesuatu. Prinsip yang sama dipakai
  untuk `save_mistake`.
- Semua tool dijalankan **sekuensial** dalam satu turn. Untuk RayEnglish, 2 tool
  per turn sudah cukup; tidak perlu paralel.

---

## 6. Penyusunan Prompt

`main.py:696-741` menyusun prompt berlapis:

```
[CURRENT DATE & TIME]  →  [IDENTITY]  →  memory string  →  core/prompt.txt
```

Lalu `system_instruction="\n".join(parts)` (`main.py:741`).

`core/prompt.txt` (2,6 KB) berisi aturan eksekusi, routing tool, deteksi bahasa,
dan penanganan pesan sistem. Gaya penulisannya: instruksi pendek, tegas,
berulang untuk hal kritis ("One-Call Policy", "Never guess").

Yang diadopsi:

- Prompt berlapis dengan blok yang bisa dikosongkan.
- Identitas dinamis (nama asisten & user) disuntikkan, bukan hardcoded.
- Aturan kritis diulang di beberapa tempat (model besar cenderung mengabaikan
  instruksi yang hanya muncul sekali).

Yang diubah:

- Tidak ada lagi "one-call policy" untuk vision (tidak ada vision di MVP).
- Gaya bahasa dibalik total: santai, bukan formal.
- Blok data (skenario, progres, kesalahan) menjadi bagian dari prompt, bukan
  hanya memory JSON.

---

## 7. Memori

`memory/memory_manager.py` + `memory/long_term.json`.

Contoh isi nyata (dari repo):

```json
{
  "identity": { "language": { "value": "Indonesian" } },
  "notes":    { "has_stash": { "value": "yes" } },
  "schedule": { "work_commute": { "value": "Goes to work with brother at 9 AM" } }
}
```

Kelebihan: sederhana, mudah dibaca manusia, tanpa migrasi.
Kekurangan: tidak bisa query agregat ("berapa kali salah past tense minggu
ini?"), tidak ada indeks, rawan korup kalau dua penulis bersamaan.

RayEnglish memakai SQLite dengan tabel eksplisit (lihat `PLAN.md` §8). JSON
tetap dipakai untuk **config** (bukan data), karena cocok untuk itu.

---

## 8. UI & Threading

### 8.1 Jembatan thread

`ui.py:2013-2020` mendefinisikan signal di `MainWindow`:

```python
_log_sig        = pyqtSignal(str)
_state_sig      = pyqtSignal(str)
_content_sig    = pyqtSignal(str, str)
_reconfig_sig   = pyqtSignal()
_camera_sig     = pyqtSignal(bytes)
...
```

`ui.py:3697-3700`:

```python
def set_state(self, state: str):
    self._state_sig.emit(state)

def write_log(self, text: str):
    self._log_sig.emit(text)
```

Asyncio berjalan di thread terpisah (`main.py:1618-1622`):

```python
def runner():
    asyncio.run(jarvis.run())

threading.Thread(target=runner, daemon=True).start()
```

Pola ini benar (signal aman lintas thread) dan diadopsi. Perbedaannya:
RayEnglish memakai **qasync** supaya hanya ada satu loop, sehingga sinyal masih
dipakai untuk UI tetapi tidak perlu thread asyncio terpisah.

### 8.2 Rendering 60 fps

`ui.py:473-536` — `HudCanvas._step()` dipanggil `QTimer` ~16 ms, menggambar
ulang seluruh HUD dengan `QPainter` (anti-alias, gradient, path). Ini membuktikan
QPainter cukup untuk animasi 60 fps di Python.

RayEnglish memakai pendekatan yang sama, tetapi:

- render hanya layer yang berubah (cache),
- transform dihitung dengan `dt` (bukan frame count) agar stabil di berbagai
  refresh rate,
- ada auto-degradasi ke 30 fps bila frame time tinggi.

### 8.3 Avatar yang sudah dicoba user

`ui.py:380-409` — `_AvatarWebWidget` membungkus `QWebEngineView`, memuat
`ui/avatar/index.html` (Three.js + `Scfi_Fi_Helmet.glb`), dan menembak volume
lewat:

```python
self.view.page().runJavaScript(f"window.animateAvatar({volume:.3f});")
```

Panggilan terjadi ~2 frame sekali dari `HudCanvas` (`ui.py:525-532`).

Ini membuktikan minat pada avatar audio-reactive, tapi untuk RayEnglish
pendekatan WebEngine ditolak (lihat `PLAN.md` A3): terlalu berat, transparansi
WebEngine di Linux rapuh, dan tidak ada wajah/mulut untuk lip sync. Konsep
"envelope → parameter animasi" tetap dipakai, hanya kanalnya diganti signal Qt.

---

## 9. Plugin System

`core/plugin_loader.py` — satu file `.py` per plugin, deklarasi `PLUGIN` dict +
fungsi `run()`, validasi saat load, isolasi crash (plugin rusak ditandai
`BROKEN` tanpa mematikan aplikasi), deteksi benturan nama tool.

Untuk MVP RayEnglish, plugin **tidak** diaktifkan. Namun `ToolRegistry`
didesain dengan antarmuka yang sama (nama, schema, handler, metadata) supaya
plugin bisa ditambahkan tanpa refactor.

---

## 10. Masalah di Mark-LI yang Tidak Diwarisi

| Masalah | Bukti | Dampak | Solusi RayEnglish |
|---|---|---|---|
| Mic dimatikan saat AI bicara | `main.py:966-975` | Tidak bisa menyela; terasa seperti walkie-talkie | `START_OF_ACTIVITY_INTERRUPTS` + flush queue |
| `interrupted` tidak ditangani | `main.py:997-1101` | Sisa audio bisa tetap berbunyi setelah interupsi | Tangani `server_content.interrupted` |
| Monolit `main.py` 80 KB | struktur file | Sulit diuji, sulit diubah | Modul per tanggung jawab |
| Tidak ada test | — | Refactor berbahaya | pytest sejak M1 |
| Semua state di JSON | `memory/` | Tidak bisa query/analitik | SQLite |
| Error hanya `print` + traceback | `main.py:1102-1105` | User tidak tahu apa yang salah | Status UI + log file |
| Prompt sangat panjang & bercabang | `_build_config` | Sulit di-debug | Prompt builder + unit test |
| `except BaseException` luas | `main.py:1545` | Bisa menelan bug nyata | Tangkap tipe spesifik + logging |
| Tanpa backoff reconnect | `main.py:1488` | Spam koneksi saat jaringan buruk | Exponential backoff + jitter |

---

## 11. Ringkasan: yang Dipinjam vs Dibuang

**Dipinjam (dengan perbaikan):** konstanta audio, struktur queue, pemotongan
chunk 50 ms, TaskGroup, reconnect + fallback config, transkrip per turn, tool
loop, prompt berlapis, signal lintas thread, QPainter 60 fps, envelope audio
untuk animasi.

**Dibuang:** mic lock saat bicara, memory JSON untuk data, persona JARVIS,
tool OS, HUD sci-fi, monolit, WebEngine avatar, plugin (ditunda).

**Ditambah (tidak ada di Mark-LI):** state machine eksplisit, SQLite +
skenario/frasa/progres, koreksi terstruktur, laporan sesi, spaced repetition,
rig karakter 2.5D, qasync single loop, test suite.

# Budget Tracker

Web app pribadi pengganti Excel budget: catat transaksi, split gajian ke banyak akun, saldo per akun otomatis,
rekap harian/kategori/akun, aset kripto Bitget Wallet dengan kurs otomatis, export Excel/CSV. Dark/light mode, Indonesia/English,
responsif (HP = bottom bar, laptop = sidebar), bisa di-install sebagai PWA.

Stack: Python 3.12 · FastAPI · SQLAlchemy · SQLite · Jinja2 (tanpa framework frontend, tanpa CDN).

## Jalankan

### A. Docker (disarankan)
```bash
mkdir -p data logos            # sudah ada kalau dari zip; pastikan dimiliki user kamu (bukan root)
docker compose up -d --build
# buka http://localhost:8000
```
User container default `1000:1000` (user pertama di Arch). Kalau UID kamu beda: `PUID=$(id -u) PGID=$(id -g) docker compose up -d --build`.
Opsional kunci dengan password: `APP_PASSWORD=rahasia docker compose up -d` (HTTP Basic, user bebas).

### B. Native (tanpa Docker)
```bash
./run.sh                       # bikin .venv, install, jalan di 127.0.0.1:8000
```
Jalan otomatis saat login (systemd user), simpan sebagai `~/.config/systemd/user/budget-tracker.service`:
```ini
[Service]
WorkingDirectory=%h/budget-tracker
ExecStart=%h/budget-tracker/run.sh
Restart=on-failure
[Install]
WantedBy=default.target
```
lalu `systemctl --user enable --now budget-tracker`.

## Akses dari HP (Tailscale)
```bash
tailscale serve --bg 8000      # HTTPS di https://<laptop>.<tailnet>.ts.net
tailscale serve status
```
HTTPS inilah yang membuat tombol "Install / Add to Home Screen" muncul. Port 8000 sengaja hanya di-bind ke localhost.
Laptop mati/sleep = app tidak bisa diakses dari HP.

## Pindah dari Excel lama
Taruh file di `data/`, lalu:
```bash
docker compose exec app python -m app.import_excel /data/Journal_Keuangan_Bulanan.xlsx --sheet Oktober
# native: python -m app.import_excel data/Journal_Keuangan_Bulanan.xlsx --sheet Oktober
```
- 1 sheet = 1 periode (tanggal dari sel D2). Transaksi tanpa tanggal → **Rencana** (berulang).
- Kolom "Akun" dan tabel Saldo Akun ("Diterima dari Split") ikut diimpor sebagai transfer split.
- Saran: impor **sheet terbaru saja**. Sheet lama tidak punya data saldo/split lengkap, jadi saldo akun akan terlihat membengkak.
  Setelah impor, di **Asset Management → Sinkronkan** isi saldo asli tiap akun, selisihnya otomatis masuk ke saldo awal.
- `--opening` memakai "Saldo Awal" dari sheet terlama yang diimpor. Sheet yang namanya sudah ada dilewati.

## Cara kerja saldo
- Gajian (income periode) masuk ke **akun landing** (default Seabank).
- **Split** = transfer dari akun landing ke akun lain. "Sisa belum dipindah" = gajian − total split.
- Saldo akun = saldo awal + gajian masuk + transfer masuk − transfer keluar − pengeluaran **berstatus Sudah dibayar** dari akun itu. Saldo terbawa lintas periode.
- **Rencana** (kos, listrik, kirim ortu) tidak mengurangi saldo sampai kamu tekan *Tandai dibayar*. Centang *Berulang* → otomatis tersalin ke periode baru.
- Akun jenis `crypto` (Bitget Wallet) menampilkan nilai aset kripto dalam Rupiah, bukan saldo ledger.

## Kripto & kurs otomatis
Asset Management → Aset kripto → isi simbol + jumlah (USDT, BTC, ETH, …). Nilai = jumlah × harga USDT × kurs USD→IDR.
- Kurs USD→IDR: Frankfurter (kurs referensi ECB, harian, tanpa API key), cadangan open.er-api.com.
- Harga token: API publik Bitget (`/api/v2/spot/market/tickers`, tanpa API key). USDT/USDC dianggap 1 USD.
- Diperbarui tiap `RATE_REFRESH_MINUTES` (default 15), atau tombol *Perbarui sekarang*. Kalau gagal, nilai terakhir dipakai dan waktu update tetap tampil.
- Token yang tidak ada di pasar spot Bitget: isi **Harga manual (USD)**.
- Jumlah token kamu isi sendiri (app tidak membaca isi wallet). TradingView tidak dipakai karena tidak punya API data publik.

## Export
Rekap/Pengaturan → Excel atau CSV (periode ini / semua). Excel berisi sheet Transactions, Summary, Daily, Accounts, Crypto.

## Logo akun
Taruh file di folder `logos/` dengan nama akun huruf kecil tanpa spasi: `seabank.png`, `shopeepay.svg`, `bitgetwallet.png`
(png/svg/webp/jpg). Tidak ada file → tampil kotak inisial berwarna.

## Backup
Semua data ada di `data/budget.db`. Backup aman saat app jalan:
```bash
sqlite3 data/budget.db ".backup 'backup-$(date +%F).db'"
```
(atau `docker compose stop` lalu copy folder `data/`).

## Konfigurasi (env)
| Variabel | Default | Fungsi |
|---|---|---|
| `DATA_DIR` | `data` (`/data` di Docker) | lokasi database |
| `TZ` | `Asia/Jakarta` | zona waktu untuk "hari ini" |
| `APP_PASSWORD` | kosong | kalau diisi, semua halaman minta password |
| `RATE_REFRESH_MINUTES` | `15` | interval update kurs/harga |
| `RATES_DISABLED` | kosong | isi `1` untuk mematikan fetch kurs |

## Tes
```bash
pip install pytest && python -m pytest -q tests
```

## Struktur
```
app/main.py        route & halaman       app/services.py   hitung saldo, rekap, kripto
app/models.py      tabel SQLAlchemy      app/rates.py      kurs & harga (background loop)
app/exports.py     CSV/XLSX              app/import_excel.py  impor Excel lama
app/i18n.py        teks ID/EN            app/templates, app/static   UI
```
Menambah bahasa: tambah kolom di `app/i18n.py`. Skema DB dibuat otomatis (`create_all`); kalau nanti kolom/tabel berubah di versi baru, pakai Alembic atau hapus `data/budget.db` untuk mulai bersih.

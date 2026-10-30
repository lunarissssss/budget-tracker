import os

D = {
    "home": ("Beranda", "Home"), "tx": ("Transaksi", "Transactions"), "add": ("Catat", "Add"), "rekap": ("Rekap", "Recap"),
    "assets": ("Asset Management", "Asset Management"), "settings": ("Pengaturan", "Settings"), "period": ("Periode", "Period"),
    "unmoved": ("Sisa belum dipindah", "Not yet moved"), "income": ("Gajian", "Income"), "moved": ("Sudah dipindah", "Moved"),
    "spent": ("Terpakai", "Spent"), "planned": ("Rencana", "Planned"), "net": ("Sisa setelah rencana", "Left after plans"),
    "daily": ("Pengeluaran harian", "Daily spending"), "accounts": ("Saldo akun", "Account balances"), "see_all": ("Lihat semua", "See all"),
    "recent": ("Transaksi terbaru", "Recent transactions"), "planned_unpaid": ("Rencana · belum dibayar", "Planned · unpaid"), "none": ("Belum ada data", "Nothing yet"),
    "all": ("Semua", "All"), "paid": ("Sudah dibayar", "Paid"), "no_account": ("akun belum dipilih", "no account yet"),
    "pay": ("Tandai dibayar", "Mark paid"), "account": ("Akun", "Account"), "date": ("Tanggal", "Date"),
    "add_title": ("Catat transaksi", "Add transaction"), "edit_title": ("Ubah transaksi", "Edit transaction"), "saved": ("Tersimpan", "Saved"),
    "quick": ("Template cepat", "Quick templates"), "amount": ("Nominal", "Amount"), "repeat": ("Berulang tiap periode", "Repeat every period"),
    "category": ("Kategori", "Category"), "desc": ("Deskripsi", "Description"), "save": ("Simpan", "Save"),
    "save_more": ("Simpan & tambah lagi", "Save & add another"), "delete": ("Hapus", "Delete"),
    "total_assets": ("Total aset", "Total assets"), "reconcile": ("Sinkronkan dengan saldo asli", "Match with real balance"),
    "actual": ("Saldo asli di aplikasi", "Real balance in app"), "sync": ("Sinkronkan", "Sync"),
    "split_title": ("Split gajian", "Split income"), "income_to": ("Gajian masuk ke", "Income lands in"), "left_in": ("Sisa di", "Left in"),
    "save_split": ("Simpan split", "Save split"), "no_landing": ("Pilih akun penerima gajian di Pengaturan > Periode.", "Choose the landing account in Settings > Periods."),
    "transfer": ("Transfer antar akun", "Transfer between accounts"), "from": ("Dari", "From"), "to": ("Ke", "To"), "note": ("Catatan", "Note"),
    "transfer_btn": ("Catat transfer", "Add transfer"), "crypto": ("Aset kripto", "Crypto assets"), "updated": ("Diperbarui", "Updated"),
    "never": ("belum pernah", "never"), "symbol": ("Simbol", "Symbol"), "qty": ("Jumlah", "Quantity"), "no_price": ("belum ada harga", "no price yet"),
    "total": ("Total", "Total"), "manual_price": ("Harga manual (USD, opsional)", "Manual price (USD, optional)"),
    "add_holding": ("Simpan aset", "Save holding"), "refresh": ("Perbarui kurs & harga sekarang", "Refresh rates & prices now"),
    "daily_tab": ("Harian", "Daily"), "category_tab": ("Kategori", "By category"), "account_tab": ("Akun", "By account"),
    "export": ("Export", "Export"), "export_period": ("periode ini", "this period"), "export_all": ("semua periode", "all periods"),
    "periods": ("Periode", "Periods"), "new_period": ("Periode baru", "New period"), "name": ("Nama", "Name"), "start": ("Mulai", "Start"),
    "end": ("Selesai", "End"), "landing": ("Gajian masuk ke akun", "Income lands in account"),
    "copy_recurring": ("Salin rencana berulang", "Copy recurring plans"), "new_account": ("Akun baru", "New account"),
    "initials": ("Inisial", "Initials"), "kind": ("Jenis", "Type"), "color": ("Warna", "Color"), "opening": ("Saldo awal", "Opening balance"),
    "categories": ("Kategori", "Categories"), "new_category": ("Kategori baru", "New category"), "templates": ("Template cepat", "Quick templates"),
    "label": ("Label", "Label"), "edit": ("Ubah", "Edit"),
}
STRICT = bool(os.getenv("STRICT_I18N"))


def T(key, lang="id"):
    if key not in D:
        if STRICT:
            raise KeyError(key)
        return key
    return D[key][1 if lang == "en" else 0]

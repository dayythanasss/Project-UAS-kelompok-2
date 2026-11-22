"""
SPACE-BOOK - Smart Reservation and Booking Management System
Booking Lapangan Olahraga / Coworking Space
Python + Tkinter + SQLite

Cara menjalankan:
    python main.py

Saat pertama dijalankan, file database `space_book.db` dibuat otomatis
lengkap dengan tabel dan data awal. Akun bawaan:
    admin / admin123   (role admin)
Penyewa (user) mendaftar sendiri lewat tombol "Registrasi Akun".
"""

import csv
import hashlib
import sqlite3
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox, filedialog


# =========================================================
# KONFIGURASI
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "space_book.db"

JAM_BUKA = 8 * 60       # 08:00 (dalam menit)
JAM_TUTUP = 22 * 60     # 22:00 (dalam menit)
DURASI_MIN = 60         # minimal booking 1 jam

# Status booking
MENUNGGU_BAYAR = "MENUNGGU PEMBAYARAN"
MENUNGGU_VERIF = "MENUNGGU VERIFIKASI"
LUNAS = "LUNAS"
SELESAI = "SELESAI"
DIBATALKAN = "DIBATALKAN"
SEMUA_STATUS = [MENUNGGU_BAYAR, MENUNGGU_VERIF, LUNAS, SELESAI, DIBATALKAN]

# Status pembayaran
BELUM_BAYAR = "BELUM BAYAR"
BELUM_LUNAS = "BELUM LUNAS"
DITOLAK = "DITOLAK"

PINK = "#ff69b4"
DARK_PINK = "#d63384"
LIGHT_PINK = "#ffe6f2"
WHITE = "#ffffff"
TEXT = "#333333"
GRAY = "#777777"
RED = "#dc3545"
GREEN = "#198754"


# =========================================================
# STRUKTUR DATABASE (SQLite)
# =========================================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    no_hp TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'user'))
);

CREATE TABLE IF NOT EXISTS fasilitas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_fasilitas TEXT NOT NULL,
    jenis TEXT NOT NULL,
    harga_per_jam INTEGER NOT NULL CHECK (harga_per_jam >= 0)
);

CREATE TABLE IF NOT EXISTS booking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_fasilitas INTEGER NOT NULL,
    id_user INTEGER NOT NULL,
    tanggal TEXT NOT NULL,
    jam_mulai TEXT NOT NULL,
    jam_selesai TEXT NOT NULL,
    nama_penyewa TEXT NOT NULL,
    no_hp_penyewa TEXT NOT NULL,
    catatan TEXT,
    status_booking TEXT NOT NULL,
    status_bayar TEXT NOT NULL,
    FOREIGN KEY (id_fasilitas) REFERENCES fasilitas(id),
    FOREIGN KEY (id_user) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS pembayaran (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_booking INTEGER NOT NULL,
    metode TEXT NOT NULL,
    referensi TEXT,
    tanggal_bayar TEXT NOT NULL,
    FOREIGN KEY (id_booking) REFERENCES booking(id)
);
"""

# (nama, no_hp, username, password, role)
USER_AWAL = [
    ("Administrator", "081200000000", "admin", "admin123", "admin"),
]

# (nama_fasilitas, jenis, harga_per_jam)
FASILITAS_AWAL = [
    ("Lapangan Futsal A", "Olahraga", 150000),
    ("Lapangan Badminton B", "Olahraga", 60000),
    ("Ruang Meeting Alpha", "Coworking", 100000),
    ("Ruang Meeting Beta", "Coworking", 100000),
]


# =========================================================
# FUNGSI BANTU
# =========================================================
def rupiah(angka):
    """Format angka menjadi Rp150.000"""
    return "Rp{:,.0f}".format(angka).replace(",", ".")


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def kode_booking(id_booking):
    """1 -> BK0001"""
    return f"BK{id_booking:04d}"


def ke_menit(jam):
    """'18:30' -> 1110 (menit sejak 00:00)"""
    h, m = jam.split(":")
    return int(h) * 60 + int(m)


def dari_menit(menit):
    """1110 -> '18:30'"""
    return f"{menit // 60:02d}:{menit % 60:02d}"


def hitung_total(harga_per_jam, jam_mulai, jam_selesai):
    """Total biaya = harga per jam x lama booking (jam)."""
    durasi_menit = ke_menit(jam_selesai) - ke_menit(jam_mulai)
    return harga_per_jam * durasi_menit // 60


def total_booking(b):
    """Total biaya dari satu baris booking (hasil ambil_booking)."""
    return hitung_total(b["harga_per_jam"], b["jam_mulai"], b["jam_selesai"])


def id_dari_combo(teks):
    """'1 - Lapangan Futsal A' -> 1. Mengembalikan None jika kosong."""
    if teks.strip() == "":
        return None
    return int(teks.split(" - ")[0])


# Pilihan jam untuk combobox (setiap 30 menit)
JAM_PILIHAN = [dari_menit(m) for m in range(JAM_BUKA, JAM_TUTUP + 1, 30)]


# =========================================================
# DATABASE
# =========================================================
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Buat tabel dan isi data awal jika database masih kosong."""
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)

        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            for nama, hp, username, password, role in USER_AWAL:
                conn.execute(
                    "INSERT INTO users (nama, no_hp, username, password, role) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (nama, hp, username, hash_password(password), role),
                )

        if conn.execute("SELECT COUNT(*) FROM fasilitas").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO fasilitas (nama_fasilitas, jenis, harga_per_jam) "
                "VALUES (?, ?, ?)",
                FASILITAS_AWAL,
            )

        conn.commit()
    finally:
        conn.close()


def query_all(sql, params=()):
    conn = get_conn()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def query_one(sql, params=()):
    conn = get_conn()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def execute(sql, params=()):
    """Jalankan INSERT/UPDATE/DELETE. Mengembalikan id baris terakhir."""
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# =========================================================
# LOGIKA: REGISTRASI & LOGIN
# =========================================================
def registrasi_user(nama, no_hp, username, password):
    """Daftar akun penyewa baru. Mengembalikan (berhasil, pesan)."""
    nama = nama.strip()
    no_hp = no_hp.strip()
    username = username.strip()
    password = password.strip()

    if nama == "" or username == "":
        return False, "Nama dan username wajib diisi!"
    if not no_hp.isdigit() or len(no_hp) < 10:
        return False, "Nomor HP minimal 10 digit dan hanya berisi angka!"
    if len(password) < 6:
        return False, "Password minimal 6 karakter!"
    if query_one("SELECT id FROM users WHERE username = ?", (username,)):
        return False, "Username sudah dipakai, pilih username lain!"

    execute(
        "INSERT INTO users (nama, no_hp, username, password, role) "
        "VALUES (?, ?, ?, ?, 'user')",
        (nama, no_hp, username, hash_password(password)),
    )
    return True, "Registrasi berhasil. Silakan login."


def cek_login(username, password):
    """Mengembalikan data user (Row) jika benar, None jika salah."""
    return query_one(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, hash_password(password)),
    )


# =========================================================
# LOGIKA: FASILITAS
# =========================================================
def ambil_semua_fasilitas():
    return query_all("SELECT * FROM fasilitas ORDER BY id")


def ambil_fasilitas(id_fasilitas):
    return query_one("SELECT * FROM fasilitas WHERE id = ?", (id_fasilitas,))


def simpan_fasilitas(id_fasilitas, nama, jenis, harga):
    """Tambah (id_fasilitas None) atau ubah fasilitas. Mengembalikan (ok, pesan)."""
    nama = nama.strip()
    jenis = jenis.strip()
    if nama == "" or jenis == "":
        return False, "Nama fasilitas dan jenis wajib diisi!"
    try:
        harga = int(harga)
    except ValueError:
        return False, "Harga per jam harus berupa angka!"
    if harga < 0:
        return False, "Harga tidak boleh negatif!"

    if id_fasilitas is None:
        execute("INSERT INTO fasilitas (nama_fasilitas, jenis, harga_per_jam) "
                "VALUES (?, ?, ?)", (nama, jenis, harga))
        return True, "Fasilitas berhasil ditambahkan."

    execute("UPDATE fasilitas SET nama_fasilitas = ?, jenis = ?, "
            "harga_per_jam = ? WHERE id = ?", (nama, jenis, harga, id_fasilitas))
    return True, "Fasilitas berhasil diubah."


def hapus_fasilitas(id_fasilitas):
    """Fasilitas yang sudah punya riwayat booking tidak boleh dihapus."""
    if query_one("SELECT id FROM booking WHERE id_fasilitas = ?", (id_fasilitas,)):
        return False, ("Fasilitas sudah punya riwayat booking, "
                       "tidak bisa dihapus.")
    execute("DELETE FROM fasilitas WHERE id = ?", (id_fasilitas,))
    return True, "Fasilitas berhasil dihapus."


# =========================================================
# LOGIKA: JADWAL & VALIDASI BENTROK
# =========================================================
def cek_format_tanggal(teks):
    """Validasi tanggal DD-MM-YYYY. Mengembalikan (valid, tanggal_atau_pesan)."""
    try:
        tgl = datetime.strptime(teks.strip(), "%d-%m-%Y")
    except ValueError:
        return False, "Format tanggal salah! Gunakan DD-MM-YYYY, contoh 10-06-2026"
    if tgl.date() < datetime.now().date():
        return False, "Tanggal tidak boleh sebelum hari ini!"
    return True, tgl.strftime("%d-%m-%Y")


def validasi_jam(tanggal, mulai, selesai):
    """Cek aturan jam booking. Mengembalikan (valid, pesan)."""
    m = ke_menit(mulai)
    s = ke_menit(selesai)

    if s <= m:
        return False, "Jam selesai harus lebih besar dari jam mulai."
    if s - m < DURASI_MIN:
        return False, "Durasi booking minimal 1 jam."
    if m < JAM_BUKA or s > JAM_TUTUP:
        return False, "Jam operasional hanya 08:00 - 22:00."

    sekarang = datetime.now()
    menit_sekarang = sekarang.hour * 60 + sekarang.minute
    if tanggal == sekarang.strftime("%d-%m-%Y") and m <= menit_sekarang:
        return False, "Jam mulai sudah lewat."

    return True, ""


def cek_bentrok(id_fasilitas, tanggal, mulai, selesai):
    """
    Logika validasi bentrok:
    Jam baru bertabrakan dengan booking lama jika
        mulai_baru < selesai_lama  DAN  selesai_baru > mulai_lama
    Booking yang sudah DIBATALKAN tidak dihitung.
    Mengembalikan True jika bentrok.
    """
    booking_lama = query_all(
        "SELECT jam_mulai, jam_selesai FROM booking "
        "WHERE id_fasilitas = ? AND tanggal = ? AND status_booking != ?",
        (id_fasilitas, tanggal, DIBATALKAN),
    )

    mulai_baru = ke_menit(mulai)
    selesai_baru = ke_menit(selesai)

    for b in booking_lama:
        mulai_lama = ke_menit(b["jam_mulai"])
        selesai_lama = ke_menit(b["jam_selesai"])
        if mulai_baru < selesai_lama and selesai_baru > mulai_lama:
            return True
    return False


def cari_slot_kosong(id_fasilitas, tanggal):
    """Rekomendasi: daftar slot 1 jam yang masih kosong pada tanggal tsb."""
    hasil = []
    sekarang = datetime.now()
    hari_ini = tanggal == sekarang.strftime("%d-%m-%Y")
    menit_sekarang = sekarang.hour * 60 + sekarang.minute

    for awal in range(JAM_BUKA, JAM_TUTUP, 60):
        if hari_ini and awal <= menit_sekarang:
            continue
        a = dari_menit(awal)
        b = dari_menit(awal + 60)
        if not cek_bentrok(id_fasilitas, tanggal, a, b):
            hasil.append((a, b))
    return hasil


def teks_rekomendasi(id_fasilitas, tanggal):
    """Teks rekomendasi slot kosong (3 slot per baris)."""
    slot = cari_slot_kosong(id_fasilitas, tanggal)
    if not slot:
        return "Tidak ada slot kosong pada tanggal tersebut."

    teks = [f"{a} - {b}" for a, b in slot]
    baris = []
    for i in range(0, len(teks), 3):
        baris.append("   ".join(teks[i:i + 3]))
    return "Rekomendasi:\n" + "\n".join(baris)


def jadwal_harian(id_fasilitas, tanggal):
    """Jadwal per jam: list of (label, 'KOSONG' / 'BOOKED')."""
    hasil = []
    for awal in range(JAM_BUKA, JAM_TUTUP, 60):
        a = dari_menit(awal)
        b = dari_menit(awal + 60)
        status = "BOOKED" if cek_bentrok(id_fasilitas, tanggal, a, b) else "KOSONG"
        hasil.append((f"{a.replace(':', '.')}-{b.replace(':', '.')}", status))
    return hasil


# =========================================================
# LOGIKA: BOOKING & STATUS
# =========================================================
def ambil_booking(where="", params=()):
    """Ambil booking beserta nama fasilitas, harga, dan username pemesan."""
    sql = (
        "SELECT b.*, f.nama_fasilitas, f.harga_per_jam, u.username "
        "FROM booking b "
        "JOIN fasilitas f ON f.id = b.id_fasilitas "
        "JOIN users u ON u.id = b.id_user "
        + where + " ORDER BY b.id"
    )
    return query_all(sql, params)


def buat_booking(user, id_f, tanggal, mulai, selesai, nama, no_hp, catatan):
    """
    Buat booking baru (dengan validasi jam dan bentrok).
    Mengembalikan (berhasil, pesan).
    """
    fas = ambil_fasilitas(id_f)
    if fas is None:
        return False, "Fasilitas tidak ditemukan!"

    valid, tanggal = cek_format_tanggal(tanggal)
    if not valid:
        return False, tanggal   # berisi pesan error

    valid, pesan = validasi_jam(tanggal, mulai, selesai)
    if not valid:
        return False, pesan

    if cek_bentrok(id_f, tanggal, mulai, selesai):
        return False, ("Jadwal sudah digunakan.\nSilakan pilih jam lain.\n\n"
                       + teks_rekomendasi(id_f, tanggal))

    nama = nama.strip() or user["nama"]
    no_hp = no_hp.strip() or user["no_hp"]
    if not no_hp.isdigit() or len(no_hp) < 10:
        return False, "Nomor HP minimal 10 digit dan hanya berisi angka!"

    id_booking = execute(
        "INSERT INTO booking (id_fasilitas, id_user, tanggal, jam_mulai, "
        "jam_selesai, nama_penyewa, no_hp_penyewa, catatan, status_booking, "
        "status_bayar) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (id_f, user["id"], tanggal, mulai, selesai, nama, no_hp,
         catatan.strip(), MENUNGGU_BAYAR, BELUM_BAYAR),
    )

    total = hitung_total(fas["harga_per_jam"], mulai, selesai)
    return True, (
        "Booking Berhasil\n\n"
        f"Kode Booking : {kode_booking(id_booking)}\n"
        f"Fasilitas    : {fas['nama_fasilitas']}\n"
        f"Jadwal       : {tanggal}  {mulai} - {selesai}\n"
        f"Total Biaya  : {rupiah(total)}\n"
        f"Status       : {MENUNGGU_BAYAR}\n\n"
        "Lanjutkan ke tab 5. Pembayaran."
    )


def ubah_status(id_booking, status_baru, status_bayar=None):
    """
    Ubah status booking sesuai alur:
      MENUNGGU PEMBAYARAN -> MENUNGGU VERIFIKASI -> LUNAS -> SELESAI
      MENUNGGU PEMBAYARAN -> DIBATALKAN
    (MENUNGGU VERIFIKASI -> MENUNGGU PEMBAYARAN dipakai jika pembayaran DITOLAK)
    Mengembalikan (berhasil, pesan).
    """
    b = query_one("SELECT * FROM booking WHERE id = ?", (id_booking,))
    if b is None:
        return False, "Booking tidak ditemukan."

    saat_ini = b["status_booking"]
    if saat_ini == MENUNGGU_BAYAR:
        boleh = [MENUNGGU_VERIF, DIBATALKAN]
    elif saat_ini == MENUNGGU_VERIF:
        boleh = [LUNAS, MENUNGGU_BAYAR]
    elif saat_ini == LUNAS:
        boleh = [SELESAI]
    else:
        boleh = []   # SELESAI dan DIBATALKAN sudah final

    if status_baru not in boleh:
        return False, f"Status {saat_ini} tidak bisa diubah menjadi {status_baru}."

    if status_bayar is None:
        status_bayar = b["status_bayar"]

    execute(
        "UPDATE booking SET status_booking = ?, status_bayar = ? WHERE id = ?",
        (status_baru, status_bayar, id_booking),
    )
    return True, f"Status booking {kode_booking(id_booking)} menjadi {status_baru}."


def perbarui_status_selesai():
    """Booking LUNAS yang jamnya sudah lewat otomatis menjadi SELESAI."""
    sekarang = datetime.now()
    for b in query_all(
        "SELECT id, tanggal, jam_selesai FROM booking WHERE status_booking = ?",
        (LUNAS,),
    ):
        akhir = datetime.strptime(
            f"{b['tanggal']} {b['jam_selesai']}", "%d-%m-%Y %H:%M")
        if akhir < sekarang:
            ubah_status(b["id"], SELESAI)


# =========================================================
# LOGIKA: PEMBAYARAN
# =========================================================
def simpan_pembayaran(id_booking, metode, referensi):
    execute(
        "INSERT INTO pembayaran (id_booking, metode, referensi, tanggal_bayar) "
        "VALUES (?, ?, ?, ?)",
        (id_booking, metode, referensi,
         datetime.now().strftime("%d-%m-%Y %H:%M")),
    )


def bayar_booking(id_booking, metode, bank="", referensi=""):
    """
    Simulasi pembayaran. metode 1 = Transfer Bank, 2 = Bayar di Tempat.
      Transfer Bank   -> status MENUNGGU VERIFIKASI
      Bayar di Tempat -> status BELUM LUNAS
    Mengembalikan (berhasil, pesan).
    """
    kode = kode_booking(id_booking)

    if metode == 1:
        bank = bank.strip()
        referensi = referensi.strip()
        if bank == "" or referensi == "":
            return False, "Nama bank dan nomor referensi wajib diisi!"
        berhasil, pesan = ubah_status(id_booking, MENUNGGU_VERIF, MENUNGGU_VERIF)
        if not berhasil:
            return False, pesan
        simpan_pembayaran(id_booking, "Transfer Bank", f"{bank} - {referensi}")
        return True, f"Pembayaran {kode} tercatat.\n\nStatus: {MENUNGGU_VERIF}"

    if metode == 2:
        berhasil, pesan = ubah_status(id_booking, MENUNGGU_VERIF, BELUM_LUNAS)
        if not berhasil:
            return False, pesan
        simpan_pembayaran(id_booking, "Bayar di Tempat", "-")
        return True, f"Pembayaran {kode} tercatat.\n\nStatus: {BELUM_LUNAS}"

    return False, "Pilih metode pembayaran!"


def validasi_pembayaran(id_booking, setuju):
    """Admin: ubah status pembayaran menjadi LUNAS (setuju) atau DITOLAK."""
    if setuju:
        return ubah_status(id_booking, LUNAS, LUNAS)

    # Ditolak: kembali ke MENUNGGU PEMBAYARAN agar penyewa bisa bayar ulang
    berhasil, pesan = ubah_status(id_booking, MENUNGGU_BAYAR, DITOLAK)
    if berhasil:
        execute("DELETE FROM pembayaran WHERE id_booking = ?", (id_booking,))
        pesan = (f"Pembayaran {kode_booking(id_booking)} DITOLAK. "
                 "Penyewa dapat melakukan pembayaran ulang.")
    return berhasil, pesan


def batalkan_booking(id_booking):
    """Admin: batalkan booking (hanya yang MENUNGGU PEMBAYARAN)."""
    return ubah_status(id_booking, DIBATALKAN)


# =========================================================
# LOGIKA: LAPORAN
# =========================================================
def ambil_laporan():
    """Hitung data laporan penggunaan fasilitas."""
    semua = ambil_booking()
    aktif = 0
    selesai = 0
    pendapatan = 0
    per_fasilitas = {}   # nama -> [jumlah booking, pendapatan]

    for b in semua:
        status = b["status_booking"]
        if status in (MENUNGGU_BAYAR, MENUNGGU_VERIF, LUNAS):
            aktif += 1
        elif status == SELESAI:
            selesai += 1

        if status == DIBATALKAN:
            continue

        data = per_fasilitas.setdefault(b["nama_fasilitas"], [0, 0])
        data[0] += 1
        if status in (LUNAS, SELESAI):
            data[1] += total_booking(b)
            pendapatan += total_booking(b)

    populer = None
    for nama, (jumlah, _) in per_fasilitas.items():
        if populer is None or jumlah > populer[1]:
            populer = (nama, jumlah)

    return {
        "total": len(semua),
        "aktif": aktif,
        "selesai": selesai,
        "pendapatan": pendapatan,
        "populer": populer,
        "per_fasilitas": per_fasilitas,
    }


# Pemisah kolom CSV. Excel versi Indonesia membaca titik koma (;) sebagai
# pemisah kolom, sedangkan Excel versi Inggris memakai koma (,).
CSV_DELIMITER = ";"


def export_laporan_csv(path):
    """Bonus: export seluruh booking ke CSV. Mengembalikan jumlah baris."""
    data = ambil_booking()
    # utf-8-sig = UTF-8 dengan BOM, supaya Excel membaca huruf dengan benar
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=CSV_DELIMITER)
        writer.writerow(["Kode", "Penyewa", "No HP", "Fasilitas", "Tanggal",
                         "Jam Mulai", "Jam Selesai", "Total", "Status Booking",
                         "Status Bayar"])
        for b in data:
            writer.writerow([
                kode_booking(b["id"]), b["nama_penyewa"], b["no_hp_penyewa"],
                b["nama_fasilitas"], b["tanggal"], b["jam_mulai"],
                b["jam_selesai"], total_booking(b),
                b["status_booking"], b["status_bayar"]])
    return len(data)


# =========================================================
# KOMPONEN GUI
# =========================================================
def buat_tree(parent, kolom, tinggi=14):
    """kolom = [(key, judul, lebar, anchor), ...] -> (frame, tree)"""
    frame = tk.Frame(parent, bg=WHITE)
    tree = ttk.Treeview(
        frame,
        columns=[k[0] for k in kolom],
        show="headings",
        height=tinggi,
        selectmode="browse",
    )
    for key, judul, lebar, anchor in kolom:
        tree.heading(key, text=judul)
        tree.column(key, width=lebar, anchor=anchor)

    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    return frame, tree


def kosongkan_tree(tree):
    for item in tree.get_children():
        tree.delete(item)


def tombol(parent, teks, command, warna=DARK_PINK):
    return tk.Button(
        parent, text=teks, command=command,
        bg=warna, fg=WHITE, activebackground=warna, activeforeground=WHITE,
        font=("Arial", 10, "bold"), relief="flat", padx=12, pady=6,
        cursor="hand2",
    )


def label_form(parent, teks, baris, bg=WHITE):
    """Label di kolom kiri sebuah form (grid)."""
    tk.Label(parent, text=teks, bg=bg, fg=TEXT, font=("Arial", 11)
             ).grid(row=baris, column=0, sticky="w", pady=6, padx=(0, 15))


# =========================================================
# APLIKASI UTAMA
# =========================================================
class SpaceBookApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SPACE-BOOK - Sistem Booking Lapangan & Coworking Space")
        self.geometry("1150x720")
        self.minsize(1000, 650)

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=26, font=("Arial", 10))
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"))
        style.configure("TNotebook.Tab", font=("Arial", 11, "bold"), padding=(14, 6))

        self.user = None
        self.refreshers = []   # daftar fungsi refresh tiap tab
        self.combos = []       # daftar combobox fasilitas

        self.show_login()

    # -----------------------------------------------------
    # UTIL
    # -----------------------------------------------------
    def bersihkan(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.refreshers = []
        self.combos = []

    def buat_combo_fasilitas(self, parent, width=34):
        cmb = ttk.Combobox(parent, state="readonly", width=width,
                           font=("Arial", 11))
        self.combos.append(cmb)
        self.refresh_combo()
        return cmb

    def refresh_combo(self):
        nilai = [f"{f['id']} - {f['nama_fasilitas']}"
                 for f in ambil_semua_fasilitas()]
        for cmb in self.combos:
            sekarang = cmb.get()
            cmb["values"] = nilai
            if sekarang in nilai:
                cmb.set(sekarang)
            elif nilai:
                cmb.current(0)
            else:
                cmb.set("")

    def refresh_semua(self, event=None):
        perbarui_status_selesai()
        self.refresh_combo()
        for fungsi in self.refreshers:
            fungsi()

    def buat_combo_jam(self, parent, mulai=True):
        nilai = JAM_PILIHAN[:-1] if mulai else JAM_PILIHAN[1:]
        cmb = ttk.Combobox(parent, values=nilai, state="readonly", width=12,
                           font=("Arial", 11))
        cmb.set(nilai[0])
        return cmb

    # -----------------------------------------------------
    # LOGIN & REGISTRASI
    # -----------------------------------------------------
    def show_login(self):
        self.bersihkan()
        self.configure(bg=LIGHT_PINK)
        self.user = None

        box = tk.Frame(self, bg=WHITE, padx=45, pady=40)
        box.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(box, text="SPACE-BOOK", font=("Arial", 26, "bold"),
                 bg=WHITE, fg=DARK_PINK).pack()
        tk.Label(box, text="Booking Lapangan Olahraga & Coworking Space",
                 font=("Arial", 11), bg=WHITE, fg=GRAY).pack(pady=(0, 20))

        tk.Label(box, text="Username", bg=WHITE, fg=TEXT,
                 font=("Arial", 11)).pack(anchor="w")
        self.ent_user = tk.Entry(box, font=("Arial", 12), width=28)
        self.ent_user.pack(pady=(0, 10))

        tk.Label(box, text="Password", bg=WHITE, fg=TEXT,
                 font=("Arial", 11)).pack(anchor="w")
        self.ent_pass = tk.Entry(box, font=("Arial", 12), width=28, show="*")
        self.ent_pass.pack(pady=(0, 18))

        tombol(box, "LOGIN", self.proses_login).pack(fill="x")
        tombol(box, "REGISTRASI AKUN", self.dialog_registrasi, GREEN
               ).pack(fill="x", pady=(8, 0))

        tk.Label(box, text="Admin: admin / admin123",
                 bg=WHITE, fg=GRAY, font=("Arial", 9)).pack(pady=(15, 0))

        self.ent_user.focus()
        self.bind("<Return>", lambda e: self.proses_login())

    def proses_login(self):
        username = self.ent_user.get().strip()
        password = self.ent_pass.get().strip()

        if username == "" or password == "":
            messagebox.showwarning("Login", "Username dan password wajib diisi!")
            return

        user = cek_login(username, password)
        if user is None:
            messagebox.showerror("Login Gagal",
                                 "Username atau Password Salah")
            return

        self.user = user
        self.unbind("<Return>")
        self.show_main()

    def dialog_registrasi(self):
        win = tk.Toplevel(self)
        win.title("Registrasi Akun")
        win.configure(bg=WHITE, padx=25, pady=20)
        win.transient(self)
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win, text="Registrasi Akun", font=("Arial", 15, "bold"),
                 bg=WHITE, fg=DARK_PINK).grid(row=0, column=0, columnspan=2,
                                              pady=(0, 15))

        daftar = [("Nama Lengkap", "nama"), ("No HP (min. 10 digit)", "hp"),
                  ("Username", "username"), ("Password (min. 6 karakter)", "pw")]
        entri = {}
        for i, (label, key) in enumerate(daftar, start=1):
            label_form(win, label, i)
            e = tk.Entry(win, font=("Arial", 11), width=28,
                         show="*" if key == "pw" else "")
            e.grid(row=i, column=1, pady=6)
            entri[key] = e

        def daftar_akun():
            berhasil, pesan = registrasi_user(
                entri["nama"].get(), entri["hp"].get(),
                entri["username"].get(), entri["pw"].get())
            if berhasil:
                win.destroy()
                messagebox.showinfo("Registrasi", pesan)
            else:
                messagebox.showerror("Registrasi Gagal", pesan, parent=win)

        tombol(win, "DAFTAR", daftar_akun, GREEN).grid(
            row=6, column=0, columnspan=2, pady=(15, 0), sticky="ew")
        entri["nama"].focus()

    def logout(self):
        if messagebox.askyesno("Logout", "Yakin ingin logout?"):
            self.show_login()

    # -----------------------------------------------------
    # HALAMAN UTAMA (MENU)
    # -----------------------------------------------------
    def show_main(self):
        self.bersihkan()
        self.configure(bg=LIGHT_PINK)
        perbarui_status_selesai()
        admin = self.user["role"] == "admin"

        head = tk.Frame(self, bg=PINK, height=65)
        head.pack(fill="x")
        head.pack_propagate(False)

        judul = "===== DASHBOARD ADMIN =====" if admin else "===== SPACE BOOK ====="
        tk.Label(head, text=judul, font=("Arial", 20, "bold"),
                 bg=PINK, fg=WHITE).pack(side="left", padx=20)

        tk.Button(head, text="6. Logout", command=self.logout,
                  bg=WHITE, fg=DARK_PINK, font=("Arial", 10, "bold"),
                  relief="flat", padx=15).pack(side="right", padx=20)
        tk.Label(head, text=f"Login: {self.user['nama']} ({self.user['role']})",
                 font=("Arial", 11), bg=PINK, fg=WHITE
                 ).pack(side="right", padx=10)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=12)

        if admin:
            daftar_tab = [
                ("1. Kelola Fasilitas", self.bangun_tab_fasilitas),
                ("2. Lihat Booking", self.bangun_tab_lihat_booking),
                ("3. Validasi Pembayaran", self.bangun_tab_validasi),
                ("4. Batalkan Booking", self.bangun_tab_batalkan),
                ("5. Laporan", self.bangun_tab_laporan),
            ]
        else:
            daftar_tab = [
                ("1. Lihat Fasilitas", self.bangun_tab_fasilitas),
                ("2. Cek Ketersediaan Jadwal", self.bangun_tab_cek_jadwal),
                ("3. Booking Fasilitas", self.bangun_tab_booking),
                ("4. Riwayat Booking", self.bangun_tab_riwayat),
                ("5. Pembayaran", self.bangun_tab_pembayaran),
            ]

        for judul_tab, fungsi_bangun in daftar_tab:
            tab = tk.Frame(self.notebook, bg=LIGHT_PINK)
            self.notebook.add(tab, text=judul_tab)
            fungsi_bangun(tab)

        self.notebook.bind("<<NotebookTabChanged>>", self.refresh_semua)
        self.refresh_semua()

    # =====================================================
    # TAB FASILITAS (USER: LIHAT | ADMIN: KELOLA)
    # =====================================================
    def bangun_tab_fasilitas(self, tab):
        admin = self.user["role"] == "admin"

        frame, self.tree_fasilitas = buat_tree(tab, [
            ("id", "ID", 60, "center"),
            ("nama", "Nama Fasilitas", 320, "w"),
            ("jenis", "Jenis", 160, "center"),
            ("harga", "Harga per Jam", 160, "e"),
        ], tinggi=18)
        frame.pack(fill="both", expand=True, padx=10, pady=(12, 5))

        if admin:
            bawah = tk.Frame(tab, bg=LIGHT_PINK)
            bawah.pack(fill="x", padx=10, pady=10)
            tombol(bawah, "Tambah Fasilitas", self.form_tambah_fasilitas,
                   GREEN).pack(side="left", padx=(0, 8))
            tombol(bawah, "Ubah Fasilitas", self.form_ubah_fasilitas
                   ).pack(side="left", padx=8)
            tombol(bawah, "Hapus Fasilitas", self.proses_hapus_fasilitas,
                   RED).pack(side="left", padx=8)

        self.refreshers.append(self.refresh_tabel_fasilitas)

    def refresh_tabel_fasilitas(self):
        kosongkan_tree(self.tree_fasilitas)
        for f in ambil_semua_fasilitas():
            self.tree_fasilitas.insert(
                "", "end", iid=str(f["id"]),
                values=(f["id"], f["nama_fasilitas"], f["jenis"],
                        rupiah(f["harga_per_jam"])))

    def dialog_fasilitas(self, judul, data=None):
        """Form tambah/ubah fasilitas. data = Row fasilitas (mode ubah)."""
        win = tk.Toplevel(self)
        win.title(judul)
        win.configure(bg=WHITE, padx=25, pady=20)
        win.transient(self)
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win, text=judul, font=("Arial", 15, "bold"),
                 bg=WHITE, fg=DARK_PINK).grid(row=0, column=0, columnspan=2,
                                              pady=(0, 15))

        label_form(win, "Nama Fasilitas", 1)
        ent_nama = tk.Entry(win, font=("Arial", 11), width=28)
        ent_nama.grid(row=1, column=1, pady=6)

        label_form(win, "Jenis", 2)
        cmb_jenis = ttk.Combobox(win, values=["Olahraga", "Coworking"],
                                 font=("Arial", 11), width=26)
        cmb_jenis.grid(row=2, column=1, pady=6)

        label_form(win, "Harga per Jam", 3)
        ent_harga = tk.Entry(win, font=("Arial", 11), width=28)
        ent_harga.grid(row=3, column=1, pady=6)

        if data is not None:
            ent_nama.insert(0, data["nama_fasilitas"])
            cmb_jenis.set(data["jenis"])
            ent_harga.insert(0, data["harga_per_jam"])

        def simpan():
            id_f = None if data is None else data["id"]
            berhasil, pesan = simpan_fasilitas(
                id_f, ent_nama.get(), cmb_jenis.get(), ent_harga.get())
            if berhasil:
                win.destroy()
                self.refresh_semua()
                messagebox.showinfo("Berhasil", pesan)
            else:
                messagebox.showerror("Error", pesan, parent=win)

        tombol(win, "SIMPAN", simpan, GREEN).grid(
            row=4, column=0, columnspan=2, pady=(15, 0), sticky="ew")
        ent_nama.focus()

    def form_tambah_fasilitas(self):
        self.dialog_fasilitas("Tambah Fasilitas")

    def fasilitas_terpilih(self):
        pilih = self.tree_fasilitas.selection()
        if not pilih:
            messagebox.showwarning("Peringatan", "Pilih fasilitas di tabel dulu!")
            return None
        return ambil_fasilitas(int(pilih[0]))

    def form_ubah_fasilitas(self):
        fas = self.fasilitas_terpilih()
        if fas is not None:
            self.dialog_fasilitas("Ubah Fasilitas", fas)

    def proses_hapus_fasilitas(self):
        fas = self.fasilitas_terpilih()
        if fas is None:
            return
        if not messagebox.askyesno(
                "Konfirmasi",
                f"Yakin menghapus fasilitas?\n\n{fas['nama_fasilitas']}\n(Y/T)"):
            return
        berhasil, pesan = hapus_fasilitas(fas["id"])
        if berhasil:
            self.refresh_semua()
            messagebox.showinfo("Berhasil", pesan)
        else:
            messagebox.showerror("Gagal", pesan)

    # =====================================================
    # TAB CEK KETERSEDIAAN JADWAL (USER)
    # =====================================================
    def bangun_tab_cek_jadwal(self, tab):
        kiri = tk.Frame(tab, bg=WHITE, bd=1, relief="solid", padx=20, pady=15)
        kiri.pack(side="left", fill="y", padx=(10, 5), pady=10)
        kanan = tk.Frame(tab, bg=WHITE, bd=1, relief="solid")
        kanan.pack(side="left", fill="both", expand=True, padx=(5, 10), pady=10)

        # ---------- kiri: form ----------
        tk.Label(kiri, text="CEK KETERSEDIAAN", font=("Arial", 15, "bold"),
                 bg=WHITE, fg=DARK_PINK).grid(row=0, column=0, columnspan=2,
                                              pady=(0, 10))

        label_form(kiri, "Fasilitas", 1)
        self.cmb_cek_fas = self.buat_combo_fasilitas(kiri, width=28)
        self.cmb_cek_fas.grid(row=1, column=1, pady=6, sticky="w")

        label_form(kiri, "Tanggal (DD-MM-YYYY)", 2)
        self.ent_cek_tgl = tk.Entry(kiri, font=("Arial", 11), width=14)
        self.ent_cek_tgl.insert(0, datetime.now().strftime("%d-%m-%Y"))
        self.ent_cek_tgl.grid(row=2, column=1, pady=6, sticky="w")

        label_form(kiri, "Jam Mulai", 3)
        self.cmb_cek_mulai = self.buat_combo_jam(kiri, mulai=True)
        self.cmb_cek_mulai.grid(row=3, column=1, pady=6, sticky="w")

        label_form(kiri, "Jam Selesai", 4)
        self.cmb_cek_selesai = self.buat_combo_jam(kiri, mulai=False)
        self.cmb_cek_selesai.grid(row=4, column=1, pady=6, sticky="w")

        tombol(kiri, "CEK KETERSEDIAAN", self.proses_cek_jadwal).grid(
            row=5, column=0, columnspan=2, pady=(12, 8), sticky="ew")

        self.lbl_hasil_cek = tk.Label(kiri, text="", bg=WHITE, fg=TEXT,
                                      font=("Arial", 11, "bold"),
                                      justify="left", wraplength=330)
        self.lbl_hasil_cek.grid(row=6, column=0, columnspan=2, sticky="w")

        # ---------- kanan: jadwal harian ----------
        self.lbl_judul_jadwal = tk.Label(
            kanan, text="JADWAL HARIAN", font=("Arial", 15, "bold"),
            bg=WHITE, fg=DARK_PINK)
        self.lbl_judul_jadwal.pack(pady=(10, 5))

        frame, self.tree_jadwal = buat_tree(kanan, [
            ("jam", "Jam", 200, "center"),
            ("status", "Status", 200, "center"),
        ], tinggi=14)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree_jadwal.tag_configure("booked", foreground=RED)
        self.tree_jadwal.tag_configure("kosong", foreground=GREEN)

    def tampil_jadwal_di_tree(self, id_f, tanggal):
        kosongkan_tree(self.tree_jadwal)
        for label, status in jadwal_harian(id_f, tanggal):
            tag = "booked" if status == "BOOKED" else "kosong"
            self.tree_jadwal.insert("", "end", values=(label, status),
                                    tags=(tag,))
        self.lbl_judul_jadwal.config(text=f"JADWAL {tanggal}")

    def proses_cek_jadwal(self):
        id_f = id_dari_combo(self.cmb_cek_fas.get())
        if id_f is None:
            messagebox.showwarning("Peringatan", "Pilih fasilitas terlebih dahulu!")
            return

        valid, tanggal = cek_format_tanggal(self.ent_cek_tgl.get())
        if not valid:
            messagebox.showerror("ERROR", tanggal)
            return

        mulai = self.cmb_cek_mulai.get()
        selesai = self.cmb_cek_selesai.get()

        valid, pesan = validasi_jam(tanggal, mulai, selesai)
        if not valid:
            self.lbl_hasil_cek.config(text=f"ERROR\n\n{pesan}", fg=RED)
        elif cek_bentrok(id_f, tanggal, mulai, selesai):
            self.lbl_hasil_cek.config(
                text="ERROR\n\nJadwal sudah digunakan.\nSilakan pilih jam lain.\n\n"
                     + teks_rekomendasi(id_f, tanggal), fg=RED)
        else:
            self.lbl_hasil_cek.config(
                text=f"Jadwal {mulai} - {selesai} TERSEDIA.\n"
                     "Silakan lakukan booking di tab 3.", fg=GREEN)

        self.tampil_jadwal_di_tree(id_f, tanggal)

    # =====================================================
    # TAB BOOKING FASILITAS (USER)
    # =====================================================
    def bangun_tab_booking(self, tab):
        box = tk.Frame(tab, bg=WHITE, bd=1, relief="solid", padx=30, pady=20)
        box.pack(padx=10, pady=10, anchor="n")

        tk.Label(box, text="BOOKING FASILITAS", font=("Arial", 15, "bold"),
                 bg=WHITE, fg=DARK_PINK).grid(row=0, column=0, columnspan=2,
                                              pady=(0, 10))

        label_form(box, "Fasilitas", 1)
        self.cmb_book_fas = self.buat_combo_fasilitas(box)
        self.cmb_book_fas.grid(row=1, column=1, pady=6, sticky="w")

        label_form(box, "Tanggal (DD-MM-YYYY)", 2)
        self.ent_book_tgl = tk.Entry(box, font=("Arial", 11), width=16)
        self.ent_book_tgl.insert(0, datetime.now().strftime("%d-%m-%Y"))
        self.ent_book_tgl.grid(row=2, column=1, pady=6, sticky="w")

        label_form(box, "Jam Mulai", 3)
        self.cmb_book_mulai = self.buat_combo_jam(box, mulai=True)
        self.cmb_book_mulai.grid(row=3, column=1, pady=6, sticky="w")

        label_form(box, "Jam Selesai", 4)
        self.cmb_book_selesai = self.buat_combo_jam(box, mulai=False)
        self.cmb_book_selesai.grid(row=4, column=1, pady=6, sticky="w")

        label_form(box, "Nama Penyewa", 5)
        self.ent_book_nama = tk.Entry(box, font=("Arial", 11), width=36)
        self.ent_book_nama.insert(0, self.user["nama"])
        self.ent_book_nama.grid(row=5, column=1, pady=6, sticky="w")

        label_form(box, "Nomor HP", 6)
        self.ent_book_hp = tk.Entry(box, font=("Arial", 11), width=36)
        self.ent_book_hp.insert(0, self.user["no_hp"])
        self.ent_book_hp.grid(row=6, column=1, pady=6, sticky="w")

        label_form(box, "Catatan Tambahan", 7)
        self.ent_book_catatan = tk.Entry(box, font=("Arial", 11), width=36)
        self.ent_book_catatan.grid(row=7, column=1, pady=6, sticky="w")

        tk.Label(box, text="Jam operasional 08:00 - 22:00, durasi minimal 1 jam.",
                 bg=WHITE, fg=GRAY, font=("Arial", 9)
                 ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(4, 0))

        tombol(box, "BOOKING SEKARANG", self.proses_booking, GREEN).grid(
            row=9, column=0, columnspan=2, pady=(15, 0), sticky="ew")

    def proses_booking(self):
        id_f = id_dari_combo(self.cmb_book_fas.get())
        if id_f is None:
            messagebox.showwarning("Peringatan", "Pilih fasilitas terlebih dahulu!")
            return

        berhasil, pesan = buat_booking(
            self.user, id_f, self.ent_book_tgl.get(),
            self.cmb_book_mulai.get(), self.cmb_book_selesai.get(),
            self.ent_book_nama.get(), self.ent_book_hp.get(),
            self.ent_book_catatan.get())

        if berhasil:
            self.ent_book_catatan.delete(0, "end")
            self.refresh_semua()
            messagebox.showinfo("Booking Berhasil", pesan)
        else:
            messagebox.showerror("ERROR", pesan)

    # =====================================================
    # TAB RIWAYAT BOOKING (USER)
    # =====================================================
    def bangun_tab_riwayat(self, tab):
        tk.Label(tab, text="Riwayat booking milik akun Anda",
                 bg=LIGHT_PINK, fg=GRAY, font=("Arial", 10)
                 ).pack(anchor="w", padx=12, pady=(10, 0))

        frame, self.tree_riwayat = buat_tree(tab, [
            ("kode", "Kode", 80, "center"),
            ("fasilitas", "Fasilitas", 200, "w"),
            ("tanggal", "Tanggal", 100, "center"),
            ("jam", "Jam", 110, "center"),
            ("total", "Total", 110, "e"),
            ("status", "Status Booking", 170, "center"),
            ("bayar", "Pembayaran", 150, "center"),
        ], tinggi=20)
        frame.pack(fill="both", expand=True, padx=10, pady=8)
        self.refreshers.append(self.refresh_riwayat)

    def refresh_riwayat(self):
        kosongkan_tree(self.tree_riwayat)
        data = ambil_booking("WHERE b.id_user = ?", (self.user["id"],))
        for b in data:
            self.tree_riwayat.insert(
                "", "end", iid=str(b["id"]),
                values=(kode_booking(b["id"]), b["nama_fasilitas"], b["tanggal"],
                        f"{b['jam_mulai']}-{b['jam_selesai']}",
                        rupiah(total_booking(b)), b["status_booking"],
                        b["status_bayar"]))

    # =====================================================
    # TAB PEMBAYARAN (USER)
    # =====================================================
    def bangun_tab_pembayaran(self, tab):
        tk.Label(tab, text="Pilih booking yang akan dibayar (status MENUNGGU PEMBAYARAN)",
                 bg=LIGHT_PINK, fg=GRAY, font=("Arial", 10)
                 ).pack(anchor="w", padx=12, pady=(10, 0))

        frame, self.tree_bayar = buat_tree(tab, [
            ("kode", "Kode", 80, "center"),
            ("fasilitas", "Fasilitas", 220, "w"),
            ("tanggal", "Tanggal", 110, "center"),
            ("jam", "Jam", 120, "center"),
            ("total", "Total", 120, "e"),
            ("bayar", "Pembayaran", 150, "center"),
        ], tinggi=8)
        frame.pack(fill="x", padx=10, pady=8)

        box = tk.Frame(tab, bg=WHITE, bd=1, relief="solid", padx=25, pady=15)
        box.pack(fill="x", padx=10, pady=5)

        tk.Label(box, text="METODE PEMBAYARAN", font=("Arial", 13, "bold"),
                 bg=WHITE, fg=DARK_PINK).grid(row=0, column=0, columnspan=2,
                                              sticky="w", pady=(0, 8))

        self.var_metode = tk.IntVar(value=1)
        tk.Radiobutton(box, text="1. Transfer Bank", variable=self.var_metode,
                       value=1, bg=WHITE, font=("Arial", 11),
                       command=self.atur_metode).grid(row=1, column=0,
                                                      columnspan=2, sticky="w")
        tk.Radiobutton(box, text="2. Bayar di Tempat", variable=self.var_metode,
                       value=2, bg=WHITE, font=("Arial", 11),
                       command=self.atur_metode).grid(row=2, column=0,
                                                      columnspan=2, sticky="w")

        label_form(box, "Nama Bank", 3)
        self.ent_bank = tk.Entry(box, font=("Arial", 11), width=28)
        self.ent_bank.grid(row=3, column=1, pady=6, sticky="w")

        label_form(box, "Nomor Referensi", 4)
        self.ent_ref = tk.Entry(box, font=("Arial", 11), width=28)
        self.ent_ref.grid(row=4, column=1, pady=6, sticky="w")

        tombol(box, "BAYAR", self.proses_bayar, GREEN).grid(
            row=5, column=0, columnspan=2, pady=(10, 0), sticky="ew")

        self.refreshers.append(self.refresh_bayar)

    def atur_metode(self):
        """Isian bank & referensi hanya aktif untuk Transfer Bank."""
        status = "normal" if self.var_metode.get() == 1 else "disabled"
        self.ent_bank.config(state=status)
        self.ent_ref.config(state=status)

    def refresh_bayar(self):
        kosongkan_tree(self.tree_bayar)
        data = ambil_booking("WHERE b.id_user = ? AND b.status_booking = ?",
                             (self.user["id"], MENUNGGU_BAYAR))
        for b in data:
            self.tree_bayar.insert(
                "", "end", iid=str(b["id"]),
                values=(kode_booking(b["id"]), b["nama_fasilitas"], b["tanggal"],
                        f"{b['jam_mulai']}-{b['jam_selesai']}",
                        rupiah(total_booking(b)), b["status_bayar"]))

    def proses_bayar(self):
        pilih = self.tree_bayar.selection()
        if not pilih:
            messagebox.showwarning("Peringatan", "Pilih booking yang akan dibayar!")
            return

        berhasil, pesan = bayar_booking(
            int(pilih[0]), self.var_metode.get(),
            self.ent_bank.get(), self.ent_ref.get())

        if berhasil:
            self.ent_bank.delete(0, "end")
            self.ent_ref.delete(0, "end")
            self.refresh_semua()
            messagebox.showinfo("Pembayaran", pesan)
        else:
            messagebox.showerror("ERROR", pesan)

    # =====================================================
    # TAB LIHAT BOOKING (ADMIN)
    # =====================================================
    def bangun_tab_lihat_booking(self, tab):
        atas = tk.Frame(tab, bg=LIGHT_PINK)
        atas.pack(fill="x", padx=10, pady=(10, 5))
        tk.Label(atas, text="Filter status:", bg=LIGHT_PINK, fg=TEXT,
                 font=("Arial", 11, "bold")).pack(side="left")
        self.cmb_filter = ttk.Combobox(
            atas, values=["SEMUA"] + SEMUA_STATUS, state="readonly",
            width=24, font=("Arial", 11))
        self.cmb_filter.set("SEMUA")
        self.cmb_filter.pack(side="left", padx=10)
        self.cmb_filter.bind("<<ComboboxSelected>>",
                             lambda e: self.refresh_lihat_booking())

        frame, self.tree_semua = buat_tree(tab, [
            ("kode", "Kode", 75, "center"),
            ("penyewa", "Penyewa", 150, "w"),
            ("fasilitas", "Fasilitas", 170, "w"),
            ("tanggal", "Tanggal", 95, "center"),
            ("jam", "Jam", 105, "center"),
            ("total", "Total", 105, "e"),
            ("status", "Status Booking", 160, "center"),
            ("bayar", "Pembayaran", 130, "center"),
        ], tinggi=20)
        frame.pack(fill="both", expand=True, padx=10, pady=8)
        self.refreshers.append(self.refresh_lihat_booking)

    def refresh_lihat_booking(self):
        kosongkan_tree(self.tree_semua)
        filter_status = self.cmb_filter.get()
        if filter_status in ("", "SEMUA"):
            data = ambil_booking()
        else:
            data = ambil_booking("WHERE b.status_booking = ?", (filter_status,))

        for b in data:
            self.tree_semua.insert(
                "", "end", iid=str(b["id"]),
                values=(kode_booking(b["id"]), b["nama_penyewa"],
                        b["nama_fasilitas"], b["tanggal"],
                        f"{b['jam_mulai']}-{b['jam_selesai']}",
                        rupiah(total_booking(b)), b["status_booking"],
                        b["status_bayar"]))

    # =====================================================
    # TAB VALIDASI PEMBAYARAN (ADMIN)
    # =====================================================
    def bangun_tab_validasi(self, tab):
        tk.Label(tab, text="Booking yang menunggu verifikasi pembayaran",
                 bg=LIGHT_PINK, fg=GRAY, font=("Arial", 10)
                 ).pack(anchor="w", padx=12, pady=(10, 0))

        frame, self.tree_validasi = buat_tree(tab, [
            ("kode", "Kode", 75, "center"),
            ("penyewa", "Penyewa", 150, "w"),
            ("fasilitas", "Fasilitas", 170, "w"),
            ("total", "Total", 105, "e"),
            ("metode", "Metode", 120, "center"),
            ("referensi", "Referensi", 170, "w"),
            ("bayar", "Status Bayar", 130, "center"),
        ], tinggi=18)
        frame.pack(fill="both", expand=True, padx=10, pady=8)

        bawah = tk.Frame(tab, bg=LIGHT_PINK)
        bawah.pack(fill="x", padx=10, pady=10)
        tombol(bawah, "Setujui (LUNAS)", lambda: self.proses_validasi(True),
               GREEN).pack(side="left", padx=(0, 8))
        tombol(bawah, "Tolak (DITOLAK)", lambda: self.proses_validasi(False),
               RED).pack(side="left", padx=8)

        self.refreshers.append(self.refresh_validasi)

    def refresh_validasi(self):
        kosongkan_tree(self.tree_validasi)
        for b in ambil_booking("WHERE b.status_booking = ?", (MENUNGGU_VERIF,)):
            bayar = query_one(
                "SELECT metode, referensi FROM pembayaran WHERE id_booking = ? "
                "ORDER BY id DESC LIMIT 1", (b["id"],))
            self.tree_validasi.insert(
                "", "end", iid=str(b["id"]),
                values=(kode_booking(b["id"]), b["nama_penyewa"],
                        b["nama_fasilitas"], rupiah(total_booking(b)),
                        bayar["metode"] if bayar else "-",
                        bayar["referensi"] if bayar else "-",
                        b["status_bayar"]))

    def proses_validasi(self, setuju):
        pilih = self.tree_validasi.selection()
        if not pilih:
            messagebox.showwarning("Peringatan", "Pilih booking di tabel dulu!")
            return
        berhasil, pesan = validasi_pembayaran(int(pilih[0]), setuju)
        self.refresh_semua()
        if berhasil:
            messagebox.showinfo("Validasi Pembayaran", pesan)
        else:
            messagebox.showerror("ERROR", pesan)

    # =====================================================
    # TAB BATALKAN BOOKING (ADMIN)
    # =====================================================
    def bangun_tab_batalkan(self, tab):
        tk.Label(tab, text="Hanya booking berstatus MENUNGGU PEMBAYARAN yang dapat dibatalkan",
                 bg=LIGHT_PINK, fg=GRAY, font=("Arial", 10)
                 ).pack(anchor="w", padx=12, pady=(10, 0))

        frame, self.tree_batal = buat_tree(tab, [
            ("kode", "Kode", 75, "center"),
            ("penyewa", "Penyewa", 170, "w"),
            ("fasilitas", "Fasilitas", 190, "w"),
            ("tanggal", "Tanggal", 105, "center"),
            ("jam", "Jam", 115, "center"),
            ("total", "Total", 110, "e"),
        ], tinggi=18)
        frame.pack(fill="both", expand=True, padx=10, pady=8)

        bawah = tk.Frame(tab, bg=LIGHT_PINK)
        bawah.pack(fill="x", padx=10, pady=10)
        tombol(bawah, "Batalkan Booking", self.proses_batalkan, RED
               ).pack(side="left")

        self.refreshers.append(self.refresh_batal)

    def refresh_batal(self):
        kosongkan_tree(self.tree_batal)
        for b in ambil_booking("WHERE b.status_booking = ?", (MENUNGGU_BAYAR,)):
            self.tree_batal.insert(
                "", "end", iid=str(b["id"]),
                values=(kode_booking(b["id"]), b["nama_penyewa"],
                        b["nama_fasilitas"], b["tanggal"],
                        f"{b['jam_mulai']}-{b['jam_selesai']}",
                        rupiah(total_booking(b))))

    def proses_batalkan(self):
        pilih = self.tree_batal.selection()
        if not pilih:
            messagebox.showwarning("Peringatan", "Pilih booking di tabel dulu!")
            return
        id_booking = int(pilih[0])
        if not messagebox.askyesno(
                "Konfirmasi",
                f"Yakin membatalkan booking {kode_booking(id_booking)}?\n(Y/T)"):
            return
        berhasil, pesan = batalkan_booking(id_booking)
        self.refresh_semua()
        if berhasil:
            messagebox.showinfo("Berhasil", pesan)
        else:
            messagebox.showerror("ERROR", pesan)

    # =====================================================
    # TAB LAPORAN PENGGUNAAN (ADMIN)
    # =====================================================
    def bangun_tab_laporan(self, tab):
        atas = tk.Frame(tab, bg=WHITE, bd=1, relief="solid")
        atas.pack(fill="x", padx=12, pady=12)

        self.lbl_total = tk.Label(atas, font=("Arial", 14, "bold"),
                                  bg=WHITE, fg=TEXT, anchor="w")
        self.lbl_total.pack(fill="x", padx=15, pady=(12, 2))
        self.lbl_aktif = tk.Label(atas, font=("Arial", 14, "bold"),
                                  bg=WHITE, fg=TEXT, anchor="w")
        self.lbl_aktif.pack(fill="x", padx=15, pady=2)
        self.lbl_selesai = tk.Label(atas, font=("Arial", 14, "bold"),
                                    bg=WHITE, fg=TEXT, anchor="w")
        self.lbl_selesai.pack(fill="x", padx=15, pady=2)
        self.lbl_pendapatan = tk.Label(atas, font=("Arial", 14, "bold"),
                                       bg=WHITE, fg=TEXT, anchor="w")
        self.lbl_pendapatan.pack(fill="x", padx=15, pady=2)
        self.lbl_populer = tk.Label(atas, font=("Arial", 14, "bold"),
                                    bg=WHITE, fg=DARK_PINK, anchor="w")
        self.lbl_populer.pack(fill="x", padx=15, pady=(2, 12))

        tk.Label(tab, text="Statistik penggunaan per fasilitas:",
                 bg=LIGHT_PINK, fg=DARK_PINK, font=("Arial", 12, "bold")
                 ).pack(anchor="w", padx=14)

        frame, self.tree_stat = buat_tree(tab, [
            ("nama", "Fasilitas", 300, "w"),
            ("jumlah", "Jumlah Booking", 150, "center"),
            ("pendapatan", "Pendapatan", 170, "e"),
        ], tinggi=8)
        frame.pack(fill="both", expand=True, padx=12, pady=8)

        bawah = tk.Frame(tab, bg=LIGHT_PINK)
        bawah.pack(fill="x", padx=12, pady=(0, 12))
        tombol(bawah, "Refresh", self.refresh_semua).pack(side="left", padx=(0, 8))
        tombol(bawah, "Export ke CSV", self.proses_export_csv, GREEN
               ).pack(side="left", padx=8)

        self.refreshers.append(self.refresh_laporan)

    def refresh_laporan(self):
        lap = ambil_laporan()
        self.lbl_total.config(text=f"Total Booking     : {lap['total']} Booking")
        self.lbl_aktif.config(text=f"Booking Aktif     : {lap['aktif']} Booking")
        self.lbl_selesai.config(text=f"Booking Selesai   : {lap['selesai']} Booking")
        self.lbl_pendapatan.config(
            text=f"Total Pendapatan  : {rupiah(lap['pendapatan'])}")

        if lap["populer"]:
            nama, jumlah = lap["populer"]
            self.lbl_populer.config(
                text=f"Fasilitas Terpopuler : {nama} ({jumlah} Booking)")
        else:
            self.lbl_populer.config(
                text="Fasilitas Terpopuler : - (belum ada booking)")

        kosongkan_tree(self.tree_stat)
        for nama, (jumlah, pendapatan) in lap["per_fasilitas"].items():
            self.tree_stat.insert("", "end",
                                  values=(nama, jumlah, rupiah(pendapatan)))

    def proses_export_csv(self):
        path = filedialog.asksaveasfilename(
            title="Simpan laporan CSV",
            defaultextension=".csv",
            initialfile="laporan_booking.csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            jumlah = export_laporan_csv(path)
        except PermissionError:
            messagebox.showerror(
                "Gagal",
                "File tidak bisa ditulis. Tutup dulu file CSV yang sedang "
                "terbuka di Excel, lalu coba lagi.")
            return
        messagebox.showinfo("Export CSV",
                            f"Berhasil mengekspor {jumlah} baris ke:\n{path}")


# =========================================================
# PROGRAM UTAMA
# =========================================================
def main():
    init_db()
    app = SpaceBookApp()
    app.mainloop()


if __name__ == "__main__":
    main()

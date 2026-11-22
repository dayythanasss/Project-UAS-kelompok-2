import csv
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path


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

# Status pembayaran
BELUM_BAYAR = "BELUM BAYAR"
BELUM_LUNAS = "BELUM LUNAS"
DITOLAK = "DITOLAK"


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


def parse_kode(teks):
    """'BK0001' / 'bk1' / '1' -> 1. Mengembalikan None jika tidak valid."""
    angka = teks.strip().upper().replace("BK", "")
    if angka.isdigit():
        return int(angka)
    return None


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


def cetak_tabel(kolom, baris):
    """Cetak tabel teks sederhana dengan lebar kolom otomatis."""
    lebar = [len(k) for k in kolom]
    for r in baris:
        for i, sel in enumerate(r):
            lebar[i] = max(lebar[i], len(str(sel)))

    print(" | ".join(k.ljust(lebar[i]) for i, k in enumerate(kolom)))
    print("-+-".join("-" * w for w in lebar))
    for r in baris:
        print(" | ".join(str(sel).ljust(lebar[i]) for i, sel in enumerate(r)))


def input_angka(prompt):
    """Minta input bilangan bulat, ulangi sampai valid."""
    while True:
        teks = input(prompt).strip()
        if teks.lstrip("-").isdigit():
            return int(teks)
        print("Input harus berupa angka!")


def input_tanggal(prompt):
    """Minta tanggal format DD-MM-YYYY (tidak boleh sebelum hari ini)."""
    while True:
        teks = input(prompt).strip()
        try:
            tgl = datetime.strptime(teks, "%d-%m-%Y")
        except ValueError:
            print("Format tanggal salah! Gunakan DD-MM-YYYY, contoh 10-06-2026")
            continue
        if tgl.date() < datetime.now().date():
            print("Tanggal tidak boleh sebelum hari ini!")
            continue
        return tgl.strftime("%d-%m-%Y")


def input_jam(prompt):
    """Minta jam format HH:MM (boleh juga HH.MM)."""
    while True:
        teks = input(prompt).strip().replace(".", ":")
        try:
            return datetime.strptime(teks, "%H:%M").strftime("%H:%M")
        except ValueError:
            print("Format jam salah! Gunakan HH:MM, contoh 18:00")


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
# LOGIKA: USER (REGISTRASI & LOGIN)
# =========================================================
def registrasi_user():
    """Daftar akun penyewa baru dengan validasi nomor HP dan password."""
    print("\n=== REGISTRASI AKUN ===")
    nama = input("Nama Lengkap : ").strip()
    no_hp = input("No HP        : ").strip()
    username = input("Username     : ").strip()
    password = input("Password     : ").strip()

    if nama == "" or username == "":
        print("ERROR: Nama dan username wajib diisi!")
    elif not no_hp.isdigit() or len(no_hp) < 10:
        print("ERROR: Nomor HP minimal 10 digit dan hanya berisi angka!")
    elif len(password) < 6:
        print("ERROR: Password minimal 6 karakter!")
    elif query_one("SELECT id FROM users WHERE username = ?", (username,)):
        print("ERROR: Username sudah dipakai, pilih username lain!")
    else:
        execute(
            "INSERT INTO users (nama, no_hp, username, password, role) "
            "VALUES (?, ?, ?, ?, 'user')",
            (nama, no_hp, username, hash_password(password)),
        )
        print("Registrasi berhasil. Silakan login.")


def cek_login(username, password):
    """Mengembalikan data user (Row) jika benar, None jika salah."""
    return query_one(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, hash_password(password)),
    )


# =========================================================
# LOGIKA: FASILITAS
# =========================================================
def ambil_fasilitas(id_fasilitas):
    return query_one("SELECT * FROM fasilitas WHERE id = ?", (id_fasilitas,))


def tampil_fasilitas():
    """Tampilkan seluruh fasilitas dalam bentuk tabel."""
    data = query_all("SELECT * FROM fasilitas ORDER BY id")
    print("\n=== DAFTAR FASILITAS ===")
    if not data:
        print("Belum ada fasilitas.")
        return
    cetak_tabel(
        ["ID", "Nama Fasilitas", "Jenis", "Harga/Jam"],
        [(f["id"], f["nama_fasilitas"], f["jenis"], rupiah(f["harga_per_jam"]))
         for f in data],
    )


# =========================================================
# LOGIKA: JADWAL & VALIDASI BENTROK
# =========================================================
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


def tampil_rekomendasi(id_fasilitas, tanggal):
    print("\nSlot tidak tersedia.")
    print("Jadwal sudah digunakan. Silakan pilih jam lain.")
    slot = cari_slot_kosong(id_fasilitas, tanggal)
    if slot:
        print("\nRekomendasi:")
        for a, b in slot:
            print(f"{a} - {b}")
    else:
        print("\nTidak ada slot kosong pada tanggal tersebut.")


def tampil_jadwal_harian(id_fasilitas, tanggal):
    """Tampilan jadwal per jam (KOSONG / BOOKED)."""
    print(f"\nJadwal {tanggal}\n")
    for awal in range(JAM_BUKA, JAM_TUTUP, 60):
        a = dari_menit(awal)
        b = dari_menit(awal + 60)
        status = "BOOKED" if cek_bentrok(id_fasilitas, tanggal, a, b) else "KOSONG"
        print(f"{a.replace(':', '.')}-{b.replace(':', '.')}  {status}")


def cek_ketersediaan():
    """Menu 2 (user): cek apakah jadwal tertentu masih kosong."""
    tampil_fasilitas()
    print("\n=== CEK KETERSEDIAAN JADWAL ===")
    id_f = input_angka("ID Fasilitas : ")
    if ambil_fasilitas(id_f) is None:
        print("ERROR: Fasilitas tidak ditemukan!")
        return

    tanggal = input_tanggal("Tanggal (DD-MM-YYYY) : ")
    mulai = input_jam("Jam Mulai (HH:MM)     : ")
    selesai = input_jam("Jam Selesai (HH:MM)   : ")

    valid, pesan = validasi_jam(tanggal, mulai, selesai)
    if not valid:
        print(f"\nERROR: {pesan}")
    elif cek_bentrok(id_f, tanggal, mulai, selesai):
        print("\nERROR")
        tampil_rekomendasi(id_f, tanggal)
    else:
        print(f"\nJadwal {mulai} - {selesai} TERSEDIA. Silakan lakukan booking.")

    tampil_jadwal_harian(id_f, tanggal)


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


def proses_booking(user):
    """Menu 3 (user): booking fasilitas (dengan validasi bentrok)."""
    tampil_fasilitas()
    print("\n=== BOOKING FASILITAS ===")
    id_f = input_angka("ID Fasilitas : ")
    fas = ambil_fasilitas(id_f)
    if fas is None:
        print("ERROR: Fasilitas tidak ditemukan!")
        return

    tanggal = input_tanggal("Tanggal (DD-MM-YYYY) : ")
    mulai = input_jam("Jam Mulai (HH:MM)     : ")
    selesai = input_jam("Jam Selesai (HH:MM)   : ")

    valid, pesan = validasi_jam(tanggal, mulai, selesai)
    if not valid:
        print(f"\nERROR: {pesan}")
        return

    if cek_bentrok(id_f, tanggal, mulai, selesai):
        print("\nERROR")
        tampil_rekomendasi(id_f, tanggal)
        return

    # Jadwal tersedia -> isi data penyewa (kosongkan = pakai data akun)
    print("\nJadwal tersedia. Lengkapi data penyewa "
          "(kosongkan untuk memakai data akun).")
    nama = input(f"Nama Penyewa [{user['nama']}] : ").strip() or user["nama"]
    no_hp = input(f"Nomor HP [{user['no_hp']}] : ").strip() or user["no_hp"]
    catatan = input("Catatan Tambahan : ").strip()

    if not no_hp.isdigit() or len(no_hp) < 10:
        print("ERROR: Nomor HP minimal 10 digit dan hanya berisi angka!")
        return

    id_booking = execute(
        "INSERT INTO booking (id_fasilitas, id_user, tanggal, jam_mulai, "
        "jam_selesai, nama_penyewa, no_hp_penyewa, catatan, status_booking, "
        "status_bayar) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (id_f, user["id"], tanggal, mulai, selesai, nama, no_hp, catatan,
         MENUNGGU_BAYAR, BELUM_BAYAR),
    )

    total = hitung_total(fas["harga_per_jam"], mulai, selesai)
    print("\nBooking Berhasil")
    print(f"\nKode Booking : {kode_booking(id_booking)}")
    print(f"Fasilitas    : {fas['nama_fasilitas']}")
    print(f"Jadwal       : {tanggal}  {mulai} - {selesai}")
    print(f"Total Biaya  : {rupiah(total)}")
    print(f"Status       : {MENUNGGU_BAYAR}")


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


def tampil_riwayat(user):
    """Menu 4 (user): riwayat booking milik user yang login."""
    data = ambil_booking("WHERE b.id_user = ?", (user["id"],))
    print("\n=== RIWAYAT BOOKING ===")
    if not data:
        print("Belum ada riwayat booking.")
        return
    cetak_tabel(
        ["Kode", "Fasilitas", "Tanggal", "Jam", "Total", "Status", "Pembayaran"],
        [(kode_booking(b["id"]), b["nama_fasilitas"], b["tanggal"],
          f"{b['jam_mulai']}-{b['jam_selesai']}",
          rupiah(hitung_total(b["harga_per_jam"], b["jam_mulai"], b["jam_selesai"])),
          b["status_booking"], b["status_bayar"]) for b in data],
    )


# =========================================================
# LOGIKA: PEMBAYARAN
# =========================================================
def menu_pembayaran(user):
    """Menu 5 (user): simulasi pembayaran (Transfer Bank / Bayar di Tempat)."""
    daftar = ambil_booking(
        "WHERE b.id_user = ? AND b.status_booking = ?",
        (user["id"], MENUNGGU_BAYAR),
    )
    print("\n=== PEMBAYARAN ===")
    if not daftar:
        print("Tidak ada booking yang menunggu pembayaran.")
        return

    cetak_tabel(
        ["Kode", "Fasilitas", "Tanggal", "Jam", "Total", "Pembayaran"],
        [(kode_booking(b["id"]), b["nama_fasilitas"], b["tanggal"],
          f"{b['jam_mulai']}-{b['jam_selesai']}",
          rupiah(hitung_total(b["harga_per_jam"], b["jam_mulai"], b["jam_selesai"])),
          b["status_bayar"]) for b in daftar],
    )

    id_booking = parse_kode(input("\nKode booking yang dibayar (0 = batal): "))
    if id_booking is None or id_booking == 0:
        return
    if id_booking not in [b["id"] for b in daftar]:
        print("ERROR: Kode booking tidak ada di daftar di atas!")
        return

    print("\nMetode Pembayaran:")
    print("1. Transfer Bank")
    print("2. Bayar di Tempat")
    metode = input("Pilih metode (1-2): ").strip()

    if metode == "1":
        bank = input("Nama Bank        : ").strip()
        referensi = input("Nomor Referensi : ").strip()
        if bank == "" or referensi == "":
            print("ERROR: Nama bank dan nomor referensi wajib diisi!")
            return
        simpan_pembayaran(id_booking, "Transfer Bank", f"{bank} - {referensi}")
        ubah_status(id_booking, MENUNGGU_VERIF, MENUNGGU_VERIF)
        print(f"\nStatus: {MENUNGGU_VERIF}")
    elif metode == "2":
        simpan_pembayaran(id_booking, "Bayar di Tempat", "-")
        ubah_status(id_booking, MENUNGGU_VERIF, BELUM_LUNAS)
        print(f"\nStatus: {BELUM_LUNAS}")
    else:
        print("Pilihan tidak valid!")


def simpan_pembayaran(id_booking, metode, referensi):
    execute(
        "INSERT INTO pembayaran (id_booking, metode, referensi, tanggal_bayar) "
        "VALUES (?, ?, ?, ?)",
        (id_booking, metode, referensi,
         datetime.now().strftime("%d-%m-%Y %H:%M")),
    )


# =========================================================
# LOGIKA: ADMIN
# =========================================================
def kelola_fasilitas():
    """Menu 1 (admin): lihat, tambah, ubah, dan hapus fasilitas."""
    while True:
        tampil_fasilitas()
        print("\n1. Tambah Fasilitas")
        print("2. Ubah Fasilitas")
        print("3. Hapus Fasilitas")
        print("0. Kembali")
        pilih = input("Pilih menu: ").strip()

        if pilih == "1":
            nama = input("Nama Fasilitas : ").strip()
            jenis = input("Jenis (Olahraga/Coworking) : ").strip()
            harga = input_angka("Harga per Jam : ")
            if nama == "" or jenis == "" or harga < 0:
                print("ERROR: Data tidak valid!")
            else:
                execute(
                    "INSERT INTO fasilitas (nama_fasilitas, jenis, harga_per_jam) "
                    "VALUES (?, ?, ?)", (nama, jenis, harga))
                print("Fasilitas berhasil ditambahkan.")

        elif pilih == "2":
            fas = ambil_fasilitas(input_angka("ID Fasilitas yang diubah : "))
            if fas is None:
                print("ERROR: Fasilitas tidak ditemukan!")
                continue
            print("(kosongkan jika tidak ingin mengubah)")
            nama = input(f"Nama [{fas['nama_fasilitas']}] : ").strip() or fas["nama_fasilitas"]
            jenis = input(f"Jenis [{fas['jenis']}] : ").strip() or fas["jenis"]
            teks_harga = input(f"Harga per Jam [{fas['harga_per_jam']}] : ").strip()
            if teks_harga == "":
                harga = fas["harga_per_jam"]
            elif teks_harga.isdigit():
                harga = int(teks_harga)
            else:
                print("ERROR: Harga harus berupa angka!")
                continue
            execute(
                "UPDATE fasilitas SET nama_fasilitas = ?, jenis = ?, "
                "harga_per_jam = ? WHERE id = ?",
                (nama, jenis, harga, fas["id"]))
            print("Fasilitas berhasil diubah.")

        elif pilih == "3":
            fas = ambil_fasilitas(input_angka("ID Fasilitas yang dihapus : "))
            if fas is None:
                print("ERROR: Fasilitas tidak ditemukan!")
            elif query_one("SELECT id FROM booking WHERE id_fasilitas = ?",
                           (fas["id"],)):
                print("ERROR: Fasilitas sudah punya riwayat booking, "
                      "tidak bisa dihapus.")
            else:
                execute("DELETE FROM fasilitas WHERE id = ?", (fas["id"],))
                print("Fasilitas berhasil dihapus.")

        elif pilih == "0":
            break
        else:
            print("Pilihan tidak valid!")


def lihat_semua_booking():
    """Menu 2 (admin): tampilkan seluruh booking."""
    data = ambil_booking()
    print("\n=== SEMUA BOOKING ===")
    if not data:
        print("Belum ada booking.")
        return
    cetak_tabel(
        ["Kode", "Penyewa", "Fasilitas", "Tanggal", "Jam", "Total", "Status"],
        [(kode_booking(b["id"]), b["nama_penyewa"], b["nama_fasilitas"],
          b["tanggal"], f"{b['jam_mulai']}-{b['jam_selesai']}",
          rupiah(hitung_total(b["harga_per_jam"], b["jam_mulai"], b["jam_selesai"])),
          b["status_booking"]) for b in data],
    )


def validasi_pembayaran():
    """Menu 3 (admin): ubah status pembayaran menjadi LUNAS atau DITOLAK."""
    daftar = ambil_booking("WHERE b.status_booking = ?", (MENUNGGU_VERIF,))
    print("\n=== VALIDASI PEMBAYARAN ===")
    if not daftar:
        print("Tidak ada pembayaran yang menunggu verifikasi.")
        return

    baris = []
    for b in daftar:
        bayar = query_one(
            "SELECT metode, referensi FROM pembayaran WHERE id_booking = ? "
            "ORDER BY id DESC LIMIT 1", (b["id"],))
        baris.append((
            kode_booking(b["id"]), b["nama_penyewa"], b["nama_fasilitas"],
            rupiah(hitung_total(b["harga_per_jam"], b["jam_mulai"], b["jam_selesai"])),
            bayar["metode"] if bayar else "-",
            bayar["referensi"] if bayar else "-",
        ))
    cetak_tabel(["Kode", "Penyewa", "Fasilitas", "Total", "Metode", "Referensi"],
                baris)

    id_booking = parse_kode(input("\nKode booking yang divalidasi (0 = batal): "))
    if id_booking is None or id_booking == 0:
        return
    if id_booking not in [b["id"] for b in daftar]:
        print("ERROR: Kode booking tidak ada di daftar di atas!")
        return

    print("\n1. LUNAS")
    print("2. DITOLAK")
    pilih = input("Pilih status (1-2): ").strip()

    if pilih == "1":
        berhasil, pesan = ubah_status(id_booking, LUNAS, LUNAS)
    elif pilih == "2":
        # Ditolak: kembali ke MENUNGGU PEMBAYARAN agar user bisa bayar ulang
        berhasil, pesan = ubah_status(id_booking, MENUNGGU_BAYAR, DITOLAK)
        if berhasil:
            execute("DELETE FROM pembayaran WHERE id_booking = ?", (id_booking,))
            pesan = (f"Pembayaran {kode_booking(id_booking)} DITOLAK. "
                     "Penyewa dapat melakukan pembayaran ulang.")
    else:
        print("Pilihan tidak valid!")
        return
    print(pesan)


def batalkan_booking():
    """Menu 4 (admin): batalkan booking (hanya yang MENUNGGU PEMBAYARAN)."""
    daftar = ambil_booking("WHERE b.status_booking = ?", (MENUNGGU_BAYAR,))
    print("\n=== BATALKAN BOOKING ===")
    if not daftar:
        print("Tidak ada booking yang bisa dibatalkan.")
        return

    cetak_tabel(
        ["Kode", "Penyewa", "Fasilitas", "Tanggal", "Jam"],
        [(kode_booking(b["id"]), b["nama_penyewa"], b["nama_fasilitas"],
          b["tanggal"], f"{b['jam_mulai']}-{b['jam_selesai']}") for b in daftar],
    )

    id_booking = parse_kode(input("\nKode booking yang dibatalkan (0 = batal): "))
    if id_booking is None or id_booking == 0:
        return

    jawab = input(f"Yakin membatalkan {kode_booking(id_booking)}? (Y/T): ").strip().upper()
    if jawab != "Y":
        print("Pembatalan dibatalkan.")
        return

    berhasil, pesan = ubah_status(id_booking, DIBATALKAN)
    print(pesan)


def ambil_laporan():
    """Hitung data laporan penggunaan fasilitas."""
    semua = ambil_booking()
    aktif = 0
    selesai = 0
    pendapatan = 0

    for b in semua:
        status = b["status_booking"]
        if status in (MENUNGGU_BAYAR, MENUNGGU_VERIF, LUNAS):
            aktif += 1
        elif status == SELESAI:
            selesai += 1

        if status in (LUNAS, SELESAI):
            pendapatan += hitung_total(
                b["harga_per_jam"], b["jam_mulai"], b["jam_selesai"])

    populer = query_one(
        "SELECT f.nama_fasilitas, COUNT(*) AS jumlah FROM booking b "
        "JOIN fasilitas f ON f.id = b.id_fasilitas "
        "WHERE b.status_booking != ? GROUP BY f.id "
        "ORDER BY jumlah DESC LIMIT 1", (DIBATALKAN,))

    return {
        "total": len(semua),
        "aktif": aktif,
        "selesai": selesai,
        "pendapatan": pendapatan,
        "populer": populer,
    }


def export_laporan_csv(path):
    """Bonus: export seluruh booking ke CSV. Mengembalikan jumlah baris."""
    data = ambil_booking()
    # utf-8-sig supaya Excel membaca huruf dengan benar; ; = pemisah Excel Indonesia
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Kode", "Penyewa", "No HP", "Fasilitas", "Tanggal",
                         "Jam Mulai", "Jam Selesai", "Total", "Status Booking",
                         "Status Bayar"])
        for b in data:
            writer.writerow([
                kode_booking(b["id"]), b["nama_penyewa"], b["no_hp_penyewa"],
                b["nama_fasilitas"], b["tanggal"], b["jam_mulai"],
                b["jam_selesai"],
                hitung_total(b["harga_per_jam"], b["jam_mulai"], b["jam_selesai"]),
                b["status_booking"], b["status_bayar"]])
    return len(data)


def tampil_laporan():
    """Menu 5 (admin): laporan penggunaan fasilitas."""
    perbarui_status_selesai()
    lap = ambil_laporan()

    print("\n=== LAPORAN PENGGUNAAN ===")
    print(f"\nTotal Booking\n{lap['total']} Booking")
    print(f"\nBooking Aktif\n{lap['aktif']} Booking")
    print(f"\nBooking Selesai\n{lap['selesai']} Booking")
    print(f"\nTotal Pendapatan\n{rupiah(lap['pendapatan'])}")
    if lap["populer"]:
        print(f"\nFasilitas Terpopuler\n{lap['populer']['nama_fasilitas']}"
              f"\n\n{lap['populer']['jumlah']} Booking")
    else:
        print("\nFasilitas Terpopuler\n- (belum ada booking)")

    jawab = input("\nExport laporan ke CSV? (Y/T): ").strip().upper()
    if jawab == "Y":
        path = BASE_DIR / "laporan_booking.csv"
        try:
            jumlah = export_laporan_csv(path)
            print(f"Berhasil mengekspor {jumlah} baris ke: {path}")
        except PermissionError:
            print("ERROR: File tidak bisa ditulis. Tutup dulu file CSV "
                  "yang sedang terbuka di Excel.")


# =========================================================
# MENU
# =========================================================
def menu_user(user):
    """Menu utama penyewa. Berulang sampai user memilih Logout."""
    perbarui_status_selesai()
    while True:
        print("\n===== SPACE BOOK =====")
        print(f"Login: {user['nama']} ({user['username']})\n")
        print("1. Lihat Fasilitas")
        print("2. Cek Ketersediaan Jadwal")
        print("3. Booking Fasilitas")
        print("4. Riwayat Booking")
        print("5. Pembayaran")
        print("6. Logout")
        pilih = input("Pilih menu (1-6): ").strip()

        if pilih == "1":
            tampil_fasilitas()
        elif pilih == "2":
            cek_ketersediaan()
        elif pilih == "3":
            proses_booking(user)
        elif pilih == "4":
            tampil_riwayat(user)
        elif pilih == "5":
            menu_pembayaran(user)
        elif pilih == "6":
            print("Logout berhasil.")
            break
        else:
            print("Pilihan tidak valid, coba lagi!")


def menu_admin(user):
    """Dashboard admin. Berulang sampai admin memilih Logout."""
    perbarui_status_selesai()
    while True:
        print("\n===== DASHBOARD ADMIN =====")
        print(f"Login: {user['nama']} ({user['username']})\n")
        print("1. Kelola Fasilitas")
        print("2. Lihat Booking")
        print("3. Validasi Pembayaran")
        print("4. Batalkan Booking")
        print("5. Laporan")
        print("6. Logout")
        pilih = input("Pilih menu (1-6): ").strip()

        if pilih == "1":
            kelola_fasilitas()
        elif pilih == "2":
            lihat_semua_booking()
        elif pilih == "3":
            validasi_pembayaran()
        elif pilih == "4":
            batalkan_booking()
        elif pilih == "5":
            tampil_laporan()
        elif pilih == "6":
            print("Logout berhasil.")
            break
        else:
            print("Pilihan tidak valid, coba lagi!")


def proses_login():
    print("\n=== LOGIN ===")
    username = input("Username : ").strip()
    password = input("Password : ").strip()

    user = cek_login(username, password)
    if user is None:
        print("Username atau Password Salah")
        return

    print("Login Berhasil")
    if user["role"] == "admin":
        menu_admin(user)
    else:
        menu_user(user)


# =========================================================
# PROGRAM UTAMA
# =========================================================
def main():
    init_db()
    while True:
        print("\n===== SELAMAT DATANG DI SPACE BOOK =====")
        print("1. Login")
        print("2. Registrasi")
        print("3. Keluar")
        pilih = input("Pilih menu (1-3): ").strip()

        if pilih == "1":
            proses_login()
        elif pilih == "2":
            registrasi_user()
        elif pilih == "3":
            print("Terima kasih telah menggunakan SPACE BOOK!")
            break
        else:
            print("Pilihan tidak valid, coba lagi!")


if __name__ == "__main__":
    main()

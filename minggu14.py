"""
╔══════════════════════════════════════════════════════════════╗
║         NOTE-TAKING APP — ADVANCED DATA STRUCTURES          ║
║                                                              ║
║  Features:                                                   ║
║  ✦ Multiple Tags per Note  (Multi-linked via Tag Index)      ║
║  ✦ Chronological View      (Doubly Linked List by date)      ║
║  ✦ Alphabetical View       (Doubly Linked List by title)     ║
║  ✦ Sync Status Tracking    (Circular Buffer recent changes)  ║
╚══════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
import uuid


# ─────────────────────────────────────────────────────────────
#  SECTION 1 — NODE DEFINITIONS
# ─────────────────────────────────────────────────────────────

class NoteNode:
    """
    Satu node merepresentasikan satu catatan (note).
    Memiliki dua pasang pointer doubly-linked:
      - chrono_prev / chrono_next  → urutan berdasarkan waktu dibuat
      - alpha_prev  / alpha_next   → urutan berdasarkan judul (A–Z)
    Dan satu pointer ke TagLinkNode pertama di linked list tag-nya.
    """

    def __init__(self, title: str, content: str):
        # ── Identitas ──────────────────────────────────────────
        self.id: str = str(uuid.uuid4())[:8]          # ID pendek 8 karakter
        self.title: str = title
        self.content: str = content
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()

        # ── Doubly Linked: Chronological View ─────────────────
        self.chrono_prev: Optional[NoteNode] = None
        self.chrono_next: Optional[NoteNode] = None

        # ── Doubly Linked: Alphabetical View ──────────────────
        self.alpha_prev: Optional[NoteNode] = None
        self.alpha_next: Optional[NoteNode] = None

        # ── Multi-linked Tags ──────────────────────────────────
        # Pointer ke TagLinkNode pertama milik note ini
        self.first_tag_link: Optional[TagLinkNode] = None

    def __repr__(self) -> str:
        tags = self._collect_tags()
        tag_str = ", ".join(f"#{t}" for t in tags) if tags else "(no tags)"
        return (
            f"NoteNode(id={self.id!r}, title={self.title!r}, "
            f"created={self.created_at.strftime('%Y-%m-%d %H:%M')}, "
            f"tags=[{tag_str}])"
        )

    def _collect_tags(self) -> list[str]:
        tags = []
        cur = self.first_tag_link
        while cur:
            tags.append(cur.tag_node.name)
            cur = cur.next_tag_of_note
        return tags


class TagNode:
    """
    Merepresentasikan satu tag (label).
    Menyimpan pointer ke TagLinkNode pertama dari semua note
    yang menggunakan tag ini.
    """

    def __init__(self, name: str):
        self.name: str = name.lower().strip()
        # Pointer ke TagLinkNode pertama note yang pakai tag ini
        self.first_note_link: Optional[TagLinkNode] = None
        self.note_count: int = 0

    def __repr__(self) -> str:
        return f"TagNode(name={self.name!r}, notes={self.note_count})"


class TagLinkNode:
    """
    NODE PENGHUBUNG — Multi-linked list.

    Setiap TagLinkNode mewakili relasi antara SATU note dan SATU tag.
    Memiliki 4 pointer:

      Dari sisi NOTE  → telusuri semua tag milik note ini
        next_tag_of_note / prev_tag_of_note

      Dari sisi TAG   → telusuri semua note yang punya tag ini
        next_note_of_tag / prev_note_of_tag

    Visualisasi:
                   NoteA ──── TagLinkNode(A,#python) ──── TagLinkNode(A,#ai)
                                     │                            │
                   NoteB ──── TagLinkNode(B,#python) ──── TagLinkNode(B,#web)
                                     │
                   NoteC ──── TagLinkNode(C,#python)
    """

    def __init__(self, note_node: NoteNode, tag_node: TagNode):
        self.note_node: NoteNode = note_node
        self.tag_node: TagNode = tag_node

        # Pointer dalam "rantai tag milik note ini"
        self.next_tag_of_note: Optional[TagLinkNode] = None
        self.prev_tag_of_note: Optional[TagLinkNode] = None

        # Pointer dalam "rantai note yang pakai tag ini"
        self.next_note_of_tag: Optional[TagLinkNode] = None
        self.prev_note_of_tag: Optional[TagLinkNode] = None

    def __repr__(self) -> str:
        return (
            f"TagLink(note={self.note_node.title!r}, "
            f"tag=#{self.tag_node.name})"
        )


# ─────────────────────────────────────────────────────────────
#  SECTION 2 — CIRCULAR BUFFER (Sync Status Tracking)
# ─────────────────────────────────────────────────────────────

class SyncEvent:
    """Merepresentasikan satu kejadian perubahan yang perlu di-sync."""

    OPERATIONS = {"CREATE", "UPDATE", "DELETE", "TAG_ADD", "TAG_REMOVE"}

    def __init__(self, note_id: str, operation: str, detail: str = ""):
        if operation not in self.OPERATIONS:
            raise ValueError(f"Operasi tidak valid: {operation}. Pilih dari {self.OPERATIONS}")
        self.note_id: str = note_id
        self.operation: str = operation
        self.detail: str = detail
        self.timestamp: datetime = datetime.now()
        self.synced: bool = False

    def __repr__(self) -> str:
        status = "✓ synced" if self.synced else "⏳ pending"
        return (
            f"SyncEvent({self.operation} note={self.note_id!r} "
            f"@ {self.timestamp.strftime('%H:%M:%S')} [{status}])"
        )


class CircularSyncBuffer:
    """
    Buffer melingkar (ring buffer) berkapasitas tetap untuk melacak
    perubahan terbaru yang harus di-sinkronisasi.

    Struktur:
      ┌───┬───┬───┬───┬───┐
      │ 0 │ 1 │ 2 │ 3 │ 4 │   ← slot array
      └───┴───┴───┴───┴───┘
            ↑           ↑
          head         tail
    Ketika buffer penuh, entri terlama ditimpa (overwrite).
    """

    def __init__(self, capacity: int = 20):
        if capacity < 2:
            raise ValueError("Kapasitas buffer minimal 2")
        self.capacity: int = capacity
        self._buffer: list[Optional[SyncEvent]] = [None] * capacity
        self._head: int = 0   # indeks untuk membaca (terlama)
        self._tail: int = 0   # indeks untuk menulis berikutnya
        self._size: int = 0   # jumlah item aktif

    # ── Write ────────────────────────────────────────────────
    def push(self, event: SyncEvent) -> None:
        """Tambahkan event baru. Jika penuh, timpa entri terlama."""
        self._buffer[self._tail] = event
        self._tail = (self._tail + 1) % self.capacity

        if self._size < self.capacity:
            self._size += 1
        else:
            # Buffer penuh → geser head maju (terlama hilang)
            self._head = (self._head + 1) % self.capacity

    # ── Read ─────────────────────────────────────────────────
    def peek_all(self) -> list[SyncEvent]:
        """Kembalikan semua event dari terlama ke terbaru (tidak menghapus)."""
        result = []
        for i in range(self._size):
            idx = (self._head + i) % self.capacity
            if self._buffer[idx] is not None:
                result.append(self._buffer[idx])
        return result

    def pop_oldest(self) -> Optional[SyncEvent]:
        """Ambil dan hapus event terlama dari buffer."""
        if self._size == 0:
            return None
        event = self._buffer[self._head]
        self._buffer[self._head] = None
        self._head = (self._head + 1) % self.capacity
        self._size -= 1
        return event

    def pending_events(self) -> list[SyncEvent]:
        """Kembalikan hanya event yang belum di-sync."""
        return [e for e in self.peek_all() if not e.synced]

    def mark_synced(self, note_id: str) -> int:
        """Tandai semua event milik note_id sebagai sudah di-sync. Return jumlah yang ditandai."""
        count = 0
        for event in self.peek_all():
            if event.note_id == note_id and not event.synced:
                event.synced = True
                count += 1
        return count

    @property
    def size(self) -> int:
        return self._size

    @property
    def is_full(self) -> bool:
        return self._size == self.capacity

    def __repr__(self) -> str:
        return (
            f"CircularSyncBuffer(capacity={self.capacity}, "
            f"size={self._size}, pending={len(self.pending_events())})"
        )


# ─────────────────────────────────────────────────────────────
#  SECTION 3 — NOTE MANAGER (Orkestrasi Semua Struktur)
# ─────────────────────────────────────────────────────────────

class NoteManager:
    """
    Kelas utama yang mengelola semua note, tag, dan sync buffer.

    Menyimpan:
      - note_index   : dict[id → NoteNode]
      - tag_index    : dict[name → TagNode]
      - chrono_head  : NoteNode terlama (doubly linked chronological)
      - alpha_head   : NoteNode pertama A–Z (doubly linked alphabetical)
      - sync_buffer  : CircularSyncBuffer
    """

    def __init__(self, sync_buffer_size: int = 20):
        self.note_index: dict[str, NoteNode] = {}
        self.tag_index: dict[str, TagNode] = {}

        # Kepala doubly linked lists
        self.chrono_head: Optional[NoteNode] = None
        self.alpha_head: Optional[NoteNode] = None

        # Circular buffer untuk sync
        self.sync_buffer = CircularSyncBuffer(capacity=sync_buffer_size)

    # ────────────────────────────────────────────────────────
    #  CREATE NOTE
    # ────────────────────────────────────────────────────────
    def create_note(self, title: str, content: str, tags: list[str] = None) -> NoteNode:
        """Buat note baru, daftarkan ke semua struktur data."""
        note = NoteNode(title, content)
        self.note_index[note.id] = note

        # Sisipkan ke doubly linked list chronological (tambah di akhir = terbaru)
        self._insert_chrono(note)

        # Sisipkan ke doubly linked list alphabetical (sorted by title)
        self._insert_alpha(note)

        # Tambahkan tags jika ada
        for tag_name in (tags or []):
            self._link_tag(note, tag_name)

        # Catat ke sync buffer
        self.sync_buffer.push(SyncEvent(note.id, "CREATE", f"title={title!r}"))

        print(f"  [+] Note dibuat: {note}")
        return note

    # ────────────────────────────────────────────────────────
    #  UPDATE NOTE
    # ────────────────────────────────────────────────────────
    def update_note(self, note_id: str, title: str = None, content: str = None) -> NoteNode:
        """Update judul/konten note. Re-sort alphabetical jika judul berubah."""
        note = self._get_note(note_id)
        old_title = note.title

        if content:
            note.content = content
        if title:
            note.title = title
            # Judul berubah → posisi alphabetical bisa bergeser
            self._remove_alpha(note)
            self._insert_alpha(note)

        note.updated_at = datetime.now()
        detail = f"title: {old_title!r} → {note.title!r}" if title else "content updated"
        self.sync_buffer.push(SyncEvent(note.id, "UPDATE", detail))

        print(f"  [~] Note diupdate: {note}")
        return note

    # ────────────────────────────────────────────────────────
    #  DELETE NOTE
    # ────────────────────────────────────────────────────────
    def delete_note(self, note_id: str) -> None:
        """Hapus note beserta semua link tag-nya."""
        note = self._get_note(note_id)

        # Lepaskan semua tag links
        cur = note.first_tag_link
        while cur:
            nxt = cur.next_tag_of_note
            self._unlink_tag_node(cur)
            cur = nxt

        # Lepaskan dari doubly linked lists
        self._remove_chrono(note)
        self._remove_alpha(note)

        # Hapus dari index
        del self.note_index[note_id]

        self.sync_buffer.push(SyncEvent(note_id, "DELETE"))
        print(f"  [-] Note dihapus: id={note_id!r}, title={note.title!r}")

    # ────────────────────────────────────────────────────────
    #  TAG OPERATIONS
    # ────────────────────────────────────────────────────────
    def add_tag(self, note_id: str, tag_name: str) -> None:
        """Tambahkan tag ke note yang sudah ada."""
        note = self._get_note(note_id)
        self._link_tag(note, tag_name)
        self.sync_buffer.push(SyncEvent(note_id, "TAG_ADD", f"#{tag_name}"))
        print(f"  [+] Tag #{tag_name} ditambahkan ke note {note_id!r}")

    def remove_tag(self, note_id: str, tag_name: str) -> None:
        """Hapus tag dari note."""
        note = self._get_note(note_id)
        tag_name = tag_name.lower().strip()

        cur = note.first_tag_link
        while cur:
            if cur.tag_node.name == tag_name:
                self._unlink_tag_node(cur)
                self.sync_buffer.push(SyncEvent(note_id, "TAG_REMOVE", f"#{tag_name}"))
                print(f"  [-] Tag #{tag_name} dihapus dari note {note_id!r}")
                return
            cur = cur.next_tag_of_note
        print(f"  [!] Tag #{tag_name} tidak ditemukan di note {note_id!r}")

    # ────────────────────────────────────────────────────────
    #  VIEWS
    # ────────────────────────────────────────────────────────
    def view_chronological(self, reverse: bool = False) -> list[NoteNode]:
        """Tampilkan semua note urut waktu dibuat (terlama → terbaru atau sebaliknya)."""
        result = []
        cur = self.chrono_head
        while cur:
            result.append(cur)
            cur = cur.chrono_next
        return result[::-1] if reverse else result

    def view_alphabetical(self) -> list[NoteNode]:
        """Tampilkan semua note urut judul A–Z."""
        result = []
        cur = self.alpha_head
        while cur:
            result.append(cur)
            cur = cur.alpha_next
        return result

    def notes_by_tag(self, tag_name: str) -> list[NoteNode]:
        """Kembalikan semua note yang memiliki tag tertentu."""
        tag_name = tag_name.lower().strip()
        if tag_name not in self.tag_index:
            return []
        tag_node = self.tag_index[tag_name]
        result = []
        cur = tag_node.first_note_link
        while cur:
            result.append(cur.note_node)
            cur = cur.next_note_of_tag
        return result

    # ────────────────────────────────────────────────────────
    #  SYNC STATUS
    # ────────────────────────────────────────────────────────
    def sync_status(self) -> None:
        """Tampilkan isi sync buffer."""
        events = self.sync_buffer.peek_all()
        print(f"\n  ── Sync Buffer ({self.sync_buffer}) ──")
        if not events:
            print("    (kosong)")
        for i, e in enumerate(events):
            print(f"    [{i:02d}] {e}")

    def process_sync(self) -> int:
        """Simulasi proses sync: tandai semua pending event sebagai synced."""
        pending = self.sync_buffer.pending_events()
        ids = {e.note_id for e in pending}
        total = 0
        for note_id in ids:
            total += self.sync_buffer.mark_synced(note_id)
        print(f"  [↑] Sync selesai: {total} event ditandai synced")
        return total

    # ────────────────────────────────────────────────────────
    #  INTERNAL HELPERS — Doubly Linked: Chronological
    # ────────────────────────────────────────────────────────
    def _insert_chrono(self, note: NoteNode) -> None:
        """Tambah note di akhir list chronological (terbaru di akhir)."""
        if self.chrono_head is None:
            self.chrono_head = note
            return
        cur = self.chrono_head
        while cur.chrono_next:
            cur = cur.chrono_next
        cur.chrono_next = note
        note.chrono_prev = cur

    def _remove_chrono(self, note: NoteNode) -> None:
        """Cabut note dari list chronological."""
        if note.chrono_prev:
            note.chrono_prev.chrono_next = note.chrono_next
        else:
            self.chrono_head = note.chrono_next
        if note.chrono_next:
            note.chrono_next.chrono_prev = note.chrono_prev
        note.chrono_prev = note.chrono_next = None

    # ────────────────────────────────────────────────────────
    #  INTERNAL HELPERS — Doubly Linked: Alphabetical
    # ────────────────────────────────────────────────────────
    def _insert_alpha(self, note: NoteNode) -> None:
        """Sisipkan note ke posisi yang tepat (sorted A–Z by title)."""
        if self.alpha_head is None:
            self.alpha_head = note
            return
        # Cari posisi
        cur = self.alpha_head
        while cur and cur.title.lower() <= note.title.lower():
            cur = cur.alpha_next
        # Sisipkan sebelum cur
        if cur is None:
            # Tambah di akhir
            tail = self.alpha_head
            while tail.alpha_next:
                tail = tail.alpha_next
            tail.alpha_next = note
            note.alpha_prev = tail
        elif cur.alpha_prev is None:
            # Sisip di awal
            note.alpha_next = self.alpha_head
            self.alpha_head.alpha_prev = note
            self.alpha_head = note
        else:
            # Sisip di tengah
            prev = cur.alpha_prev
            prev.alpha_next = note
            note.alpha_prev = prev
            note.alpha_next = cur
            cur.alpha_prev = note

    def _remove_alpha(self, note: NoteNode) -> None:
        """Cabut note dari list alphabetical."""
        if note.alpha_prev:
            note.alpha_prev.alpha_next = note.alpha_next
        else:
            self.alpha_head = note.alpha_next
        if note.alpha_next:
            note.alpha_next.alpha_prev = note.alpha_prev
        note.alpha_prev = note.alpha_next = None

    # ────────────────────────────────────────────────────────
    #  INTERNAL HELPERS — Multi-linked Tags
    # ────────────────────────────────────────────────────────
    def _link_tag(self, note: NoteNode, tag_name: str) -> None:
        """Buat relasi antara note dan tag (buat TagNode jika belum ada)."""
        tag_name = tag_name.lower().strip()

        # Cek duplikat
        cur = note.first_tag_link
        while cur:
            if cur.tag_node.name == tag_name:
                return  # sudah ada, lewati
            cur = cur.next_tag_of_note

        # Dapatkan atau buat TagNode
        if tag_name not in self.tag_index:
            self.tag_index[tag_name] = TagNode(tag_name)
        tag_node = self.tag_index[tag_name]

        # Buat TagLinkNode baru
        link = TagLinkNode(note, tag_node)

        # Sambungkan ke rantai tag note ini (tambah di awal)
        if note.first_tag_link:
            link.next_tag_of_note = note.first_tag_link
            note.first_tag_link.prev_tag_of_note = link
        note.first_tag_link = link

        # Sambungkan ke rantai note yang pakai tag ini (tambah di awal)
        if tag_node.first_note_link:
            link.next_note_of_tag = tag_node.first_note_link
            tag_node.first_note_link.prev_note_of_tag = link
        tag_node.first_note_link = link

        tag_node.note_count += 1

    def _unlink_tag_node(self, link: TagLinkNode) -> None:
        """Cabut satu TagLinkNode dari kedua rantai (note & tag)."""
        note = link.note_node
        tag = link.tag_node

        # Cabut dari rantai tag milik note
        if link.prev_tag_of_note:
            link.prev_tag_of_note.next_tag_of_note = link.next_tag_of_note
        else:
            note.first_tag_link = link.next_tag_of_note
        if link.next_tag_of_note:
            link.next_tag_of_note.prev_tag_of_note = link.prev_tag_of_note

        # Cabut dari rantai note yang pakai tag
        if link.prev_note_of_tag:
            link.prev_note_of_tag.next_note_of_tag = link.next_note_of_tag
        else:
            tag.first_note_link = link.next_note_of_tag
        if link.next_note_of_tag:
            link.next_note_of_tag.prev_note_of_tag = link.prev_note_of_tag

        tag.note_count -= 1

    def _get_note(self, note_id: str) -> NoteNode:
        note = self.note_index.get(note_id)
        if not note:
            raise KeyError(f"Note dengan id={note_id!r} tidak ditemukan")
        return note

    # ────────────────────────────────────────────────────────
    #  STATS
    # ────────────────────────────────────────────────────────
    def stats(self) -> None:
        print(f"\n  ── Statistik NoteManager ──")
        print(f"    Total notes : {len(self.note_index)}")
        print(f"    Total tags  : {len(self.tag_index)}")
        for tag_name, tag_node in sorted(self.tag_index.items()):
            print(f"      #{tag_name:20s} → {tag_node.note_count} note(s)")
        print(f"    {self.sync_buffer}")


# ─────────────────────────────────────────────────────────────
#  SECTION 4 — DEMO / MAIN
# ─────────────────────────────────────────────────────────────

def separator(label: str) -> None:
    width = 62
    print(f"\n{'─' * width}")
    print(f"  {label}")
    print(f"{'─' * width}")


def print_list(notes: list[NoteNode], label: str) -> None:
    print(f"\n  ── {label} ──")
    if not notes:
        print("    (kosong)")
    for i, n in enumerate(notes, 1):
        tags = n._collect_tags()
        tag_str = " ".join(f"#{t}" for t in tags) if tags else "(no tags)"
        print(f"    {i:2d}. [{n.id}] {n.title:30s} {tag_str}")


if __name__ == "__main__":
    print(__doc__)

    # ── Inisialisasi ───────────────────────────────────────────
    separator("1. INISIALISASI NOTE MANAGER")
    manager = NoteManager(sync_buffer_size=10)

    # ── Buat beberapa note ─────────────────────────────────────
    separator("2. MEMBUAT NOTES")
    n1 = manager.create_note("Belajar Python",
                              "Python adalah bahasa pemrograman yang powerful.",
                              tags=["python", "programming", "belajar"])

    n2 = manager.create_note("Algoritma Sorting",
                              "Quick sort, merge sort, bubble sort...",
                              tags=["algorithm", "programming", "cs"])

    n3 = manager.create_note("Arsitektur Microservice",
                              "Desain sistem terdistribusi dengan service kecil.",
                              tags=["architecture", "backend", "system-design"])

    n4 = manager.create_note("Async Python",
                              "asyncio, coroutines, event loop.",
                              tags=["python", "async", "programming"])

    n5 = manager.create_note("Database Indexing",
                              "B-tree, hash index, dan composite index.",
                              tags=["database", "performance", "cs"])

    # ── Tampilkan views ────────────────────────────────────────
    separator("3. CHRONOLOGICAL VIEW (terlama → terbaru)")
    print_list(manager.view_chronological(), "Chronological (Ascending)")

    separator("4. ALPHABETICAL VIEW (A → Z)")
    print_list(manager.view_alphabetical(), "Alphabetical")

    # ── Filter by tag ──────────────────────────────────────────
    separator("5. FILTER NOTES BY TAG")
    for tag in ["python", "programming", "cs"]:
        notes = manager.notes_by_tag(tag)
        print_list(notes, f"Notes dengan tag #{tag}")

    # ── Tambah / hapus tag ─────────────────────────────────────
    separator("6. OPERASI TAG DINAMIS")
    manager.add_tag(n1.id, "favorite")
    manager.add_tag(n3.id, "python")       # note baru dapat tag python
    manager.remove_tag(n2.id, "cs")

    print_list(manager.notes_by_tag("python"), "Notes #python setelah perubahan")

    # ── Update note (alphabetical re-sort) ─────────────────────
    separator("7. UPDATE NOTE (judul berubah → re-sort alpha)")
    manager.update_note(n1.id, title="Aaaa Python Dasar")   # akan naik ke paling atas
    print_list(manager.view_alphabetical(), "Alphabetical setelah update")

    # ── Delete note ────────────────────────────────────────────
    separator("8. HAPUS NOTE")
    manager.delete_note(n5.id)
    print_list(manager.view_chronological(), "Chronological setelah delete")

    # ── Sync buffer ────────────────────────────────────────────
    separator("9. SYNC BUFFER STATUS")
    manager.sync_status()

    # Proses sync
    separator("10. PROCESS SYNC")
    manager.process_sync()
    manager.sync_status()

    # ── Statistik akhir ────────────────────────────────────────
    separator("11. STATISTIK AKHIR")
    manager.stats()

    separator("SELESAI ✓")
import ctypes

import pymem
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QColor

from .memory_structs import (
    MEM_COMMIT,
    MEMORY_BASIC_INFORMATION,
    PAGE_EXECUTE_READWRITE,
    PAGE_READWRITE,
    SYSTEM_INFO,
)

from config import (
    FAST_SCAN,
    FAST_SCAN_START_ADDRESS,
    OFFSETS,
    PADDING_LENGTH,
    PRECEDING_ZEROES,
    PROCESS_NAME,
    STRUCT_SIZE,
)


class GameProcess:
    """Represents the target game process and memory operations."""

    def __init__(self, process_name=PROCESS_NAME):
        self.pm = None
        self.process_name = process_name

    # ----------------- Process Handling -----------------
    def attach(self):
        """Attach to the target process."""
        try:
            self.pm = pymem.Pymem(self.process_name)
            return True
        except Exception:
            self.pm = None
            return False

    def close(self):
        """Close the process handle if attached."""
        if self.pm:
            self.pm.close_process()
            self.pm = None

    def ensure_attached(self):
        """Raise an error if no process is attached."""
        if not self.pm:
            raise RuntimeError("Process not attached. Call attach() first.")

    # ----------------- Helper / Private Methods -----------------
    def _matches_pattern(self, data, start, pattern_bytes):
        """Check if a memory region matches a pattern; None acts as a wildcard."""
        return all(
            b is None or data[start + i] == b for i, b in enumerate(pattern_bytes)
        )

    def get_memory_bounds(self):
        """Return the minimum and maximum memory addresses for the system."""
        self.ensure_attached()
        sys_info = SYSTEM_INFO()
        ctypes.windll.kernel32.GetSystemInfo(ctypes.byref(sys_info))
        return (
            sys_info.lpMinimumApplicationAddress,
            sys_info.lpMaximumApplicationAddress,
        )

    # ----------------- Generic Struct Field Access -----------------
    def read_struct_field(self, base_address, field_name):
        """Read a field from a struct based on OFFSETS."""
        self.ensure_attached()
        field_info = OFFSETS[field_name]
        field_address = base_address + field_info["offset"]
        field_type = field_info["type"]

        if field_type == "byte":
            return self.pm.read_uchar(field_address)
        elif field_type == "bool":
            return self.pm.read_uchar(field_address) == 0x80
        elif field_type == "int32":
            raw = self.pm.read_bytes(field_address, 4)
            return int.from_bytes(raw, "big", signed=True)
        else:
            raise ValueError(f"Unsupported field type: {field_type}")

    def write_struct_field(self, base_address, field_name, value):
        """Write a field to a struct based on OFFSETS."""
        self.ensure_attached()
        field_info = OFFSETS[field_name]
        field_address = base_address + field_info["offset"]
        field_type = field_info["type"]

        if field_type == "byte":
            self.pm.write_uchar(field_address, value)
        elif field_type == "bool":
            self.pm.write_uchar(field_address, 0x80 if value else 0x00)
        elif field_type == "int32":
            self.pm.write_bytes(field_address, value.to_bytes(4, "big", signed=True), 4)
        else:
            raise ValueError(f"Unsupported field type: {field_type}")

    # ----------------- Memory Scanning -----------------
    def find_first_character_address(self):
        """Scan memory for the first character struct.

        Scan pattern details:
            - First byte (0x80) = f_IsCharacterUnlocked
            - Middle bytes = wildcards (None), length = STRUCT_SIZE - 1 - PADDING_LENGTH
            - Last bytes = zeros, length = PADDING_LENGTH
        """
        self.ensure_attached()
        pattern_bytes = (
            [0x80]
            + ([None] * (STRUCT_SIZE - 1 - PADDING_LENGTH))
            + ([0x00] * PADDING_LENGTH)
        )

        process_handle = self.pm.process_handle
        address = FAST_SCAN_START_ADDRESS if FAST_SCAN else 0
        _, max_address = self.get_memory_bounds()
        chunk_size = (
            0x1000  # Always advance by one memory page on VirtualQueryEx failure
        )

        while address < max_address:
            mbi = MEMORY_BASIC_INFORMATION()
            if (
                ctypes.windll.kernel32.VirtualQueryEx(
                    process_handle,
                    ctypes.c_void_p(address),
                    ctypes.byref(mbi),
                    ctypes.sizeof(mbi),
                )
                == 0
            ):
                address += chunk_size
                continue

            if mbi.State == MEM_COMMIT and mbi.Protect in (
                PAGE_READWRITE,
                PAGE_EXECUTE_READWRITE,
            ):
                try:
                    read_size = min(mbi.RegionSize, max_address - address)
                    chunk = self.pm.read_bytes(address, read_size)
                except pymem.exception.MemoryReadError:
                    address += mbi.RegionSize
                    continue

                for i in range(PRECEDING_ZEROES, len(chunk) - (STRUCT_SIZE * 4) + 1):
                    if any(b != 0x00 for b in chunk[i - PRECEDING_ZEROES : i]):
                        continue
                    if all(
                        self._matches_pattern(
                            chunk, i + (j * STRUCT_SIZE), pattern_bytes
                        )
                        for j in range(4)
                    ):
                        return address + i

            address += mbi.RegionSize

        return None

    # ----------------- Character Methods -----------------
    def get_character_data(self, base_address):
        """Return all field values for a single character struct."""
        self.ensure_attached()
        return {
            field_name: self.read_struct_field(base_address, field_name)
            for field_name in OFFSETS
        }

    def get_character_addresses(self, max_characters=42):
        """Return base addresses for all character structs."""
        self.ensure_attached()
        first_address = self.find_first_character_address()
        if first_address is None:
            return []

        addresses = []
        for i in range(max_characters):
            # Calculate the address of the i-th candidate struct
            address = first_address + (i * STRUCT_SIZE)

            # Read the struct's first byte (flag field)
            first_byte = self.pm.read_uchar(address)

            # Only 0x00 ("locked") or 0x80 ("unlocked") are valid values.
            # If we see anything else, assume that we have gone past the valid list of characters.
            if first_byte not in (0x00, 0x80):
                break

            addresses.append(address)

        return addresses

    def get_all_character_data(self, max_characters=42):
        """Return a list of dictionaries with all character data."""
        self.ensure_attached()
        return [
            self.get_character_data(address)
            for address in self.get_character_addresses(max_characters)
        ]


# ----------------- Character Scanner Thread -----------------
class CharacterScannerThread(QThread):
    status_update = pyqtSignal(str, QColor)
    scan_finished = pyqtSignal(list)

    def __init__(self, game_process: GameProcess, max_characters=42):
        super().__init__()
        self.pm = game_process
        self.max_characters = max_characters

    def run(self):
        try:
            self.status_update.emit(
                "Scanning memory for character structs...", QColor("#f0f0f0")
            )
            data = self.pm.get_all_character_data(self.max_characters)
            self.scan_finished.emit(data)
        except Exception as e:
            self.status_update.emit(f"Error scanning memory: {e}", QColor("#ff5555"))
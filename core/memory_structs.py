import ctypes

# ======================
# Memory Constants
# ======================

# Memory State
MEM_COMMIT = 0x1000

# Memory Protection
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40

# ======================
# Windows API Structures
# ======================


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    """
    Structure returned by VirtualQueryEx.
    Describes a region of memory in the target process.
    """

    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_ulong),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
    ]


class SYSTEM_INFO(ctypes.Structure):
    """
    Structure returned by GetSystemInfo.
    Describes system memory boundaries and processor information.
    """

    _fields_ = [
        ("wProcessorArchitecture", ctypes.c_uint16),
        ("wReserved", ctypes.c_uint16),
        ("dwPageSize", ctypes.c_uint32),
        ("lpMinimumApplicationAddress", ctypes.c_void_p),
        ("lpMaximumApplicationAddress", ctypes.c_void_p),
        ("dwActiveProcessorMask", ctypes.c_void_p),
        ("dwNumberOfProcessors", ctypes.c_uint32),
        ("dwProcessorType", ctypes.c_uint32),
        ("dwAllocationGranularity", ctypes.c_uint32),
        ("wProcessorLevel", ctypes.c_uint16),
        ("wProcessorRevision", ctypes.c_uint16),
    ]
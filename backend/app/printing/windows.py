"""Windows RAW spool transport for installed ESC/POS queues; no third-party driver install."""
import ctypes
from ctypes import wintypes
import os


class PrinterInfo4(ctypes.Structure):
    _fields_ = [('name', wintypes.LPWSTR), ('server', wintypes.LPWSTR), ('attributes', wintypes.DWORD)]


class DocInfo1(ctypes.Structure):
    _fields_ = [('name', wintypes.LPWSTR), ('output', wintypes.LPWSTR), ('datatype', wintypes.LPWSTR)]


def spooler():
    if os.name != 'nt':
        raise OSError('Windows USB printing requires the POS server to run on Windows')
    api = ctypes.WinDLL('winspool.drv', use_last_error=True)
    api.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    api.OpenPrinterW.restype = wintypes.BOOL
    api.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p]
    api.StartDocPrinterW.restype = wintypes.DWORD
    api.WritePrinter.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    api.WritePrinter.restype = wintypes.BOOL
    api.EnumPrintersW.argtypes = [wintypes.DWORD, wintypes.LPWSTR, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
    api.EnumPrintersW.restype = wintypes.BOOL
    for name in ('StartPagePrinter', 'EndPagePrinter', 'EndDocPrinter', 'ClosePrinter', 'AbortPrinter'):
        function = getattr(api, name)
        function.argtypes = [wintypes.HANDLE]
        function.restype = wintypes.BOOL
    return api


def installed_printers():
    if os.name != 'nt':
        return []
    api = spooler()
    needed, count = wintypes.DWORD(), wintypes.DWORD()
    api.EnumPrintersW(6, None, 4, None, 0, ctypes.byref(needed), ctypes.byref(count))
    if not needed.value:
        return []
    buffer = ctypes.create_string_buffer(needed.value)
    if not api.EnumPrintersW(6, None, 4, buffer, len(buffer), ctypes.byref(needed), ctypes.byref(count)):
        raise ctypes.WinError(ctypes.get_last_error())
    records = ctypes.cast(buffer, ctypes.POINTER(PrinterInfo4))
    return sorted({records[index].name for index in range(count.value)})


class WindowsRawPrinter:
    def __init__(self, name, api=None):
        self.api = api or spooler()
        self.handle = wintypes.HANDLE()
        self.page_started = False
        self.document_started = False
        if not self.api.OpenPrinterW(name, ctypes.byref(self.handle), None):
            raise OSError('Unable to open the configured Windows printer')
        try:
            document = DocInfo1('KOKO customer receipt', None, 'RAW')
            if not self.api.StartDocPrinterW(self.handle, 1, ctypes.byref(document)):
                raise OSError('Windows print spooler could not start the receipt')
            self.document_started = True
            if not self.api.StartPagePrinter(self.handle):
                raise OSError('Windows print spooler could not start the page')
            self.page_started = True
        except Exception:
            if self.document_started:
                self.api.AbortPrinter(self.handle)
            self.api.ClosePrinter(self.handle)
            self.handle = None
            raise

    def sendall(self, payload):
        buffer = ctypes.create_string_buffer(payload)
        written = wintypes.DWORD()
        if not self.api.WritePrinter(self.handle, buffer, len(payload), ctypes.byref(written)) or written.value != len(payload):
            raise OSError('Windows receipt delivery is uncertain; check the printer before reprinting')

    def close(self):
        if self.handle is None:
            return
        failed = False
        if self.page_started:
            failed = not self.api.EndPagePrinter(self.handle)
        if self.document_started:
            failed = not self.api.EndDocPrinter(self.handle) or failed
        failed = not self.api.ClosePrinter(self.handle) or failed
        self.handle = None
        if failed:
            raise OSError('Windows print spooler completion is uncertain; check the printer')

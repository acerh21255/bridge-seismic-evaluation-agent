"""Small ctypes wrapper around PDFium for rendering and page metadata."""

from __future__ import annotations

import ctypes
import io
import os
import threading
from ctypes import c_char_p, c_float, c_int, c_uint, c_void_p, create_string_buffer
from pathlib import Path
from typing import Iterator

from PIL import Image

from .utils import ensure_dir, sha256_bytes

FPDF_ANNOT = 0x01
FPDF_LCD_TEXT = 0x02
FPDF_GRAYSCALE = 0x08
FPDF_REVERSE_BYTE_ORDER = 0x10
FPDF_BITMAP_GRAY = 1
FPDF_BITMAP_BGRX = 4


class PdfiumUnavailable(RuntimeError):
    pass


def find_pdfium_library(explicit: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("PDFIUM_DLL"):
        candidates.append(Path(os.environ["PDFIUM_DLL"]))
    package_root = Path(__file__).resolve().parents[2]
    candidates.extend([
        package_root / "vendor" / "pdfium" / "pdfium.dll",
        package_root / "vendor" / "pdfium" / "libpdfium.so",
        Path("/usr/lib/libpdfium.so"),
        Path("/usr/local/lib/libpdfium.so"),
        Path(r"C:\Program Files\Windows Defender Advanced Threat Protection\Classification\Dprt\pdfium.dll"),
    ])
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    try:
        import pypdfium2_raw

        raw_root = Path(pypdfium2_raw.__file__).resolve().parent
        for pattern in ("pdfium.dll", "libpdfium.so", "libpdfium.dylib"):
            for candidate in raw_root.rglob(pattern):
                if candidate.is_file():
                    return candidate.resolve()
    except ImportError:
        pass

    for root in (Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")):
        if root.exists():
            try:
                for candidate in root.glob("**/pdfium.dll"):
                    if candidate.is_file():
                        return candidate.resolve()
            except OSError:
                continue
    raise PdfiumUnavailable(
        "未找到 PDFium。请设置 PDFIUM_DLL，安装 pypdfium2，或放置 vendor/pdfium/pdfium.dll。"
    )


class Pdfium:
    _instance: "Pdfium | None" = None
    _instance_lock = threading.Lock()

    def __init__(self, library_path: str | Path | None = None):
        self.library_path = find_pdfium_library(library_path)
        self.lock = threading.RLock()
        try:
            self.lib = ctypes.WinDLL(str(self.library_path))
        except AttributeError:
            self.lib = ctypes.CDLL(str(self.library_path))
        self._configure()
        with self.lock:
            self.lib.FPDF_InitLibrary()

    @classmethod
    def instance(cls, library_path: str | Path | None = None) -> "Pdfium":
        with cls._instance_lock:
            if cls._instance is None or (
                library_path and Path(library_path) != cls._instance.library_path
            ):
                cls._instance = cls(library_path)
            return cls._instance

    def _configure(self) -> None:
        lib = self.lib
        lib.FPDF_GetLastError.restype = ctypes.c_ulong
        lib.FPDF_LoadMemDocument.argtypes = [c_void_p, c_int, c_char_p]
        lib.FPDF_LoadMemDocument.restype = c_void_p
        lib.FPDF_GetPageCount.argtypes = [c_void_p]
        lib.FPDF_GetPageCount.restype = c_int
        lib.FPDF_LoadPage.argtypes = [c_void_p, c_int]
        lib.FPDF_LoadPage.restype = c_void_p
        lib.FPDF_GetPageWidthF.argtypes = [c_void_p]
        lib.FPDF_GetPageWidthF.restype = c_float
        lib.FPDF_GetPageHeightF.argtypes = [c_void_p]
        lib.FPDF_GetPageHeightF.restype = c_float
        if hasattr(lib, "FPDF_GetPageRotation"):
            lib.FPDF_GetPageRotation.argtypes = [c_void_p]
            lib.FPDF_GetPageRotation.restype = c_int
        lib.FPDFBitmap_CreateEx.argtypes = [c_int, c_int, c_int, c_void_p, c_int]
        lib.FPDFBitmap_CreateEx.restype = c_void_p
        lib.FPDFBitmap_FillRect.argtypes = [c_void_p, c_int, c_int, c_int, c_int, c_uint]
        lib.FPDF_RenderPageBitmap.argtypes = [
            c_void_p, c_void_p, c_int, c_int, c_int, c_int, c_int, c_int
        ]
        lib.FPDFBitmap_Destroy.argtypes = [c_void_p]
        lib.FPDF_ClosePage.argtypes = [c_void_p]
        lib.FPDF_CloseDocument.argtypes = [c_void_p]

class PdfDocument:
    """Own a PDF byte buffer for the lifetime of the PDFium document."""

    def __init__(self, path: str | Path, library_path: str | Path | None = None):
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        self.pdfium = Pdfium.instance(library_path)
        self._raw = self.path.read_bytes()
        self._buffer = create_string_buffer(self._raw)
        with self.pdfium.lock:
            self._document = self.pdfium.lib.FPDF_LoadMemDocument(
                self._buffer, len(self._raw), None
            )
        if not self._document:
            raise RuntimeError(f"PDFium 无法打开文档: {self.path}")

    def close(self) -> None:
        if getattr(self, "_document", None):
            with self.pdfium.lock:
                self.pdfium.lib.FPDF_CloseDocument(self._document)
            self._document = None

    def __enter__(self) -> "PdfDocument":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    @property
    def page_count(self) -> int:
        if not self._document:
            raise RuntimeError("PDF document is closed")
        with self.pdfium.lock:
            return int(self.pdfium.lib.FPDF_GetPageCount(self._document))

    def _page_handle(self, page_index: int) -> c_void_p:
        if page_index < 0 or page_index >= self.page_count:
            raise IndexError(f"Page index out of range: {page_index}")
        with self.pdfium.lock:
            handle = self.pdfium.lib.FPDF_LoadPage(self._document, page_index)
        if not handle:
            raise RuntimeError(f"PDFium 无法加载页面 {page_index + 1}: {self.path}")
        return handle

    def page_info(self, page_index: int) -> dict[str, object]:
        handle = self._page_handle(page_index)
        try:
            with self.pdfium.lock:
                width = float(self.pdfium.lib.FPDF_GetPageWidthF(handle))
                height = float(self.pdfium.lib.FPDF_GetPageHeightF(handle))
                rotation = int(self.pdfium.lib.FPDF_GetPageRotation(handle)) if hasattr(self.pdfium.lib, "FPDF_GetPageRotation") else 0
            return {
                "page_index": page_index,
                "page_number": page_index + 1,
                "width_points": width,
                "height_points": height,
                "rotation": rotation,
            }
        finally:
            with self.pdfium.lock:
                self.pdfium.lib.FPDF_ClosePage(handle)

    def iter_page_info(self) -> Iterator[dict[str, object]]:
        for page_index in range(self.page_count):
            yield self.page_info(page_index)

    def render(
        self,
        page_index: int,
        *,
        target_width: int | None = None,
        target_height: int | None = None,
        scale: float | None = None,
        grayscale: bool = False,
    ) -> Image.Image:
        """Render a PDF page to a Pillow image."""
        handle = self._page_handle(page_index)
        try:
            with self.pdfium.lock:
                width_points = float(self.pdfium.lib.FPDF_GetPageWidthF(handle))
                height_points = float(self.pdfium.lib.FPDF_GetPageHeightF(handle))
            if width_points <= 0 or height_points <= 0:
                raise RuntimeError(f"非法页面尺寸: {width_points}x{height_points}")
            if scale is None:
                if target_width:
                    scale = target_width / width_points
                elif target_height:
                    scale = target_height / height_points
                else:
                    raise ValueError("请指定 target_width、target_height 或 scale")
            pixel_width = max(1, round(width_points * scale))
            pixel_height = max(1, round(height_points * scale))
            if grayscale:
                bitmap_format = FPDF_BITMAP_GRAY
                stride = pixel_width
                raw_mode = "L"
                render_flags = FPDF_GRAYSCALE | FPDF_ANNOT | FPDF_LCD_TEXT
            else:
                bitmap_format = FPDF_BITMAP_BGRX
                stride = pixel_width * 4
                raw_mode = "BGRX"
                render_flags = FPDF_REVERSE_BYTE_ORDER | FPDF_ANNOT | FPDF_LCD_TEXT
            buffer = create_string_buffer(stride * pixel_height)
            with self.pdfium.lock:
                bitmap = self.pdfium.lib.FPDFBitmap_CreateEx(
                    pixel_width, pixel_height, bitmap_format, buffer, stride
                )
                if not bitmap:
                    raise RuntimeError("PDFium 无法创建位图")
                try:
                    self.pdfium.lib.FPDFBitmap_FillRect(
                        bitmap, 0, 0, pixel_width, pixel_height, 0xFFFFFFFF
                    )
                    self.pdfium.lib.FPDF_RenderPageBitmap(
                        bitmap, handle, 0, 0, pixel_width, pixel_height, 0, render_flags
                    )
                finally:
                    self.pdfium.lib.FPDFBitmap_Destroy(bitmap)
            image = Image.frombuffer(
                "L" if grayscale else "RGB",
                (pixel_width, pixel_height),
                buffer,
                "raw",
                raw_mode,
                stride,
                1,
            )
            return image.copy()
        finally:
            with self.pdfium.lock:
                self.pdfium.lib.FPDF_ClosePage(handle)

    def thumbnail(self, page_index: int, width: int = 320, quality: int = 82) -> tuple[Image.Image, bytes]:
        image = self.render(page_index, target_width=width, grayscale=True)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True)
        return image, output.getvalue()

    def save_thumbnail(
        self, page_index: int, output: str | Path, width: int = 320, quality: int = 82
    ) -> dict[str, object]:
        output_path = Path(output)
        ensure_dir(output_path.parent)
        image, payload = self.thumbnail(page_index, width=width, quality=quality)
        output_path.write_bytes(payload)
        return {
            "path": str(output_path),
            "width": image.width,
            "height": image.height,
            "sha256": sha256_bytes(payload),
            "bytes": len(payload),
        }


def pdfium_available(library_path: str | Path | None = None) -> bool:
    try:
        find_pdfium_library(library_path)
        return True
    except PdfiumUnavailable:
        return False

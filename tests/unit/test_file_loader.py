"""Tests for src/utils/file_loader.py."""

import sys
import pytest

from src.utils.file_loader import (
    load_file,
    FileLoadError,
    UnsupportedFormatError,
    EncodingError,
)
from src.utils.file_loader import FileNotFoundError as CustomFileNotFoundError


class TestLoadFile:
    """Tests for load_file dispatch and error handling."""

    def test_file_not_found(self, tmp_path):
        with pytest.raises(CustomFileNotFoundError) as exc_info:
            load_file(tmp_path / "nonexistent.md")
        assert "文件不存在" in str(exc_info.value)

    def test_unsupported_format(self, tmp_path):
        p = tmp_path / "file.doc"
        p.write_text("x", encoding="utf-8")
        with pytest.raises(UnsupportedFormatError) as exc_info:
            load_file(str(p))
        assert ".doc" in str(exc_info.value)

    def test_load_utf8_md(self, tmp_path):
        p = tmp_path / "test.md"
        p.write_text("hello world", encoding="utf-8")
        assert load_file(str(p)) == "hello world"

    def test_load_utf8_txt(self, tmp_path):
        p = tmp_path / "test.txt"
        p.write_text("line1\nline2", encoding="utf-8")
        assert load_file(str(p)) == "line1\nline2"

    def test_load_gbk_fallback(self, tmp_path):
        p = tmp_path / "test.txt"
        p.write_bytes("你好GBK".encode("gbk"))
        assert load_file(str(p)) == "你好GBK"

    def test_load_utf16_fallback(self, tmp_path):
        p = tmp_path / "test.txt"
        p.write_bytes("Hello UTF16".encode("utf-16"))
        assert load_file(str(p)) == "Hello UTF16"

    def test_load_latin1_fallback(self, tmp_path):
        p = tmp_path / "test.txt"
        # bytes that fail utf-8, gbk, utf-16 but work with latin-1
        p.write_bytes(b"\x80\x81\x82")
        result = load_file(str(p))
        assert result == "\x80\x81\x82"

    def test_all_encodings_fail_not_possible(self, tmp_path):
        # latin-1 can decode any byte sequence, so EncodingError
        # is effectively unreachable for real files. This test
        # documents that boundary.
        pass


class TestLoadPdf:
    """Tests for PDF loading."""

    def test_pypdf_not_installed(self, tmp_path, monkeypatch):
        """Test that missing pypdf raises FileLoadError."""
        p = tmp_path / "test.pdf"
        p.write_bytes(b"%PDF-1.4 fake content")
        # Setting sys.modules entry to None makes import raise ModuleNotFoundError
        monkeypatch.setitem(sys.modules, "pypdf", None)
        with pytest.raises(FileLoadError) as exc_info:
            load_file(str(p))
        assert "pypdf" in str(exc_info.value)

    def test_pypdf_success(self, tmp_path, monkeypatch):
        """Test successful PDF text extraction with mocked pypdf."""
        import sys
        from unittest.mock import MagicMock

        p = tmp_path / "test.pdf"
        p.write_bytes(b"%PDF-1.4")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 text"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pypdf = MagicMock()
        mock_pypdf.PdfReader.return_value = mock_reader

        monkeypatch.setitem(sys.modules, "pypdf", mock_pypdf)
        result = load_file(str(p))
        assert result == "Page 1 text"
        mock_pypdf.PdfReader.assert_called_once_with(str(p))

    def test_pypdf_multi_page(self, tmp_path, monkeypatch):
        """Test PDF with multiple pages."""
        import sys
        from unittest.mock import MagicMock

        p = tmp_path / "test.pdf"
        p.write_bytes(b"%PDF-1.4")

        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page one"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page two"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page1, mock_page2]
        mock_pypdf = MagicMock()
        mock_pypdf.PdfReader.return_value = mock_reader

        monkeypatch.setitem(sys.modules, "pypdf", mock_pypdf)
        result = load_file(str(p))
        assert result == "Page one\n\nPage two"

    def test_pypdf_empty_page(self, tmp_path, monkeypatch):
        """Test PDF with empty page text (None)."""
        import sys
        from unittest.mock import MagicMock

        p = tmp_path / "test.pdf"
        p.write_bytes(b"%PDF-1.4")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = None
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pypdf = MagicMock()
        mock_pypdf.PdfReader.return_value = mock_reader

        monkeypatch.setitem(sys.modules, "pypdf", mock_pypdf)
        result = load_file(str(p))
        assert result == ""

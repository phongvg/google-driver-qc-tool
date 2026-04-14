import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[1] / "clients" / "drive_links.py"
_SPEC = spec_from_file_location("test_drive_links_module", _MODULE_PATH)
_MODULE = module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_MODULE)

extract_folder_id = _MODULE.extract_folder_id
is_supported_drive_folder_link = _MODULE.is_supported_drive_folder_link


FOLDER_ID = "16beFKvdMBNhUT6HK4Qb15yb7BCUJZ27P"


class DriveLinksTest(unittest.TestCase):
    def test_extracts_supported_folder_link_variants(self):
        cases = [
            FOLDER_ID,
            f"https://drive.google.com/drive/folders/{FOLDER_ID}",
            f"https://drive.google.com/drive/folders/{FOLDER_ID}/",
            f"https://drive.google.com/drive/folders/{FOLDER_ID}?usp=drive_link",
            f"https://drive.google.com/drive/u/0/folders/{FOLDER_ID}",
            f"https://drive.google.com/drive/u/1/folders/{FOLDER_ID}?usp=sharing",
            f"https://drive.google.com/drive/mobile/folders/{FOLDER_ID}",
            f"https://drive.google.com/open?id={FOLDER_ID}",
            f"https://drive.google.com/u/0/open?id={FOLDER_ID}&usp=drive_link",
            f"https://drive.google.com/folderview?id={FOLDER_ID}",
            f"https://drive.google.com/embeddedfolderview?id={FOLDER_ID}#list",
            f"<https://drive.google.com/drive/u/0/folders/{FOLDER_ID}>",
        ]

        for value in cases:
            with self.subTest(value=value):
                self.assertEqual(extract_folder_id(value), FOLDER_ID)
                self.assertTrue(is_supported_drive_folder_link(value))

    def test_rejects_non_folder_links(self):
        cases = [
            "",
            "https://example.com/drive/folders/16beFKvdMBNhUT6HK4Qb15yb7BCUJZ27P",
            "https://drive.google.com/file/d/16beFKvdMBNhUT6HK4Qb15yb7BCUJZ27P/view",
            "https://drive.google.com/uc?id=16beFKvdMBNhUT6HK4Qb15yb7BCUJZ27P",
            "not-a-drive-link",
        ]

        for value in cases:
            with self.subTest(value=value):
                self.assertFalse(is_supported_drive_folder_link(value))
                with self.assertRaises(ValueError):
                    extract_folder_id(value)


if __name__ == "__main__":
    unittest.main()

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import download_model


class DownloadTests(unittest.TestCase):
    def test_chunk_download_checksum_and_existing_model(self):
        contents = {
            f"qwen2.5-7b-instruct-q4_k_m-0000{i}-of-00002.gguf": bytes([i]) * 11
            for i in (1, 2)
        }
        metadata = {"sha": "test-revision", "siblings": [
            {"rfilename": name, "size": len(data), "lfs": {"sha256": hashlib.sha256(data).hexdigest()}}
            for name, data in contents.items()
        ]}

        def open_url(request, timeout):
            if isinstance(request, str):
                return io.BytesIO(json.dumps(metadata).encode())
            name = request.full_url.split("?")[0].rsplit("/", 1)[-1]
            start, end = map(int, request.get_header("Range").removeprefix("bytes=").split("-"))
            response = io.BytesIO(contents[name][start:end + 1])
            response.status = 206
            response.headers = {"Content-Range": f"bytes {start}-{end}/{len(contents[name])}"}
            return response

        with tempfile.TemporaryDirectory() as folder, \
                patch.object(download_model, "ROOT", Path(folder)), \
                patch.object(download_model, "CHUNK", 4), \
                patch.object(download_model.urllib.request, "urlopen", side_effect=open_url) as fetch:
            download_model.download()
            for name, data in contents.items():
                self.assertEqual((Path(folder) / name).read_bytes(), data)
            count = fetch.call_count
            download_model.download()
            self.assertEqual(fetch.call_count, count + 1)
            (Path(folder) / next(iter(contents))).write_bytes(b"corrupt")
            with self.assertRaisesRegex(RuntimeError, "failed verification"):
                download_model.download()

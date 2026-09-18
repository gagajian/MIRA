#!/usr/bin/env python3
"""Serve the homepage with HTTP Range support so <video> seeking works."""
import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))


class RangeRequestHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            index = os.path.join(path, "index.html")
            if os.path.isfile(index):
                path = index
            else:
                return super().send_head()
        try:
            file_obj = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        fs = os.fstat(file_obj.fileno())
        size = fs.st_size
        ctype = self.guess_type(path)
        self._range = (0, size - 1, size)

        range_header = self.headers.get("Range")
        if range_header:
            match = re.match(r"bytes=(\d*)-(\d*)", range_header.strip())
            if not match:
                file_obj.close()
                self.send_error(416, "Invalid Range")
                return None
            start = int(match.group(1)) if match.group(1) else 0
            end = int(match.group(2)) if match.group(2) else size - 1
            if start >= size or start > end:
                file_obj.close()
                self.send_error(416, "Requested Range Not Satisfiable")
                return None
            end = min(end, size - 1)
            self._range = (start, end, size)
            file_obj.seek(start)
            self.send_response(206)
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
            self.send_header("Content-Length", str(end - start + 1))
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(size))

        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return file_obj

    def copyfile(self, source, outputfile):
        if not hasattr(self, "_range"):
            return SimpleHTTPRequestHandler.copyfile(self, source, outputfile)
        start, end, _size = self._range
        remaining = end - start + 1
        while remaining > 0:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", port), RangeRequestHandler)
    print("Serving %s at http://127.0.0.1:%d/" % (ROOT, port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")

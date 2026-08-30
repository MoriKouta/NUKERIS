from __future__ import print_function

import hashlib
import zlib

PATH = "nukeris.py"
EXPECTED_BLOB = "cb5843ecb0e42393ac63c2e17494518d76a2cad7"


def git_blob_sha(data):
    header = ("blob %d\0" % len(data)).encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def main():
    with open(PATH, "rb") as handle:
        raw = handle.read()

    print("raw bytes:", len(raw), repr(raw[:16]))
    print("raw blob:", git_blob_sha(raw))

    try:
        source = zlib.decompress(raw)
        print("zlib decompressed bytes:", len(source))
    except zlib.error as exc:
        print("zlib error:", repr(exc))
        raise

    sha = git_blob_sha(source)
    print("materialized blob:", sha)
    if sha != EXPECTED_BLOB:
        raise RuntimeError("Unexpected nukeris.py blob after materialization: %s" % sha)

    with open(PATH, "wb") as handle:
        handle.write(source)
    print("Materialized %s (%d bytes, blob %s)" % (PATH, len(source), sha))


if __name__ == "__main__":
    main()

from __future__ import print_function

import base64
import hashlib
import zlib

PATH = "nukeris.py"
EXPECTED_BLOB = "cb5843ecb0e42393ac63c2e17494518d76a2cad7"
CHUNKS = ["tools/payload_%02d.txt" % i for i in range(6)]


def git_blob_sha(data):
    header = ("blob %d\0" % len(data)).encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def main():
    parts = []
    for path in CHUNKS:
        with open(path, "rb") as handle:
            parts.append(handle.read().strip())
    payload = b"".join(parts)
    print("payload chars:", len(payload))

    packed = base64.b64decode(payload)
    source = zlib.decompress(packed)
    sha = git_blob_sha(source)
    print("materialized bytes:", len(source))
    print("materialized blob:", sha)

    if sha != EXPECTED_BLOB:
        raise RuntimeError("Unexpected nukeris.py blob after materialization: %s" % sha)

    with open(PATH, "wb") as handle:
        handle.write(source)
    print("Materialized %s" % PATH)


if __name__ == "__main__":
    main()

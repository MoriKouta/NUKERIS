from __future__ import print_function

import hashlib
import os
import zlib

PATH = "nukeris.py"
EXPECTED_BLOB = "cb5843ecb0e42393ac63c2e17494518d76a2cad7"


def git_blob_sha(data):
    header = ("blob %d\0" % len(data)).encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def main():
    with open(PATH, "rb") as handle:
        raw = handle.read()

    try:
        source = zlib.decompress(raw)
        changed = True
    except zlib.error:
        source = raw
        changed = False

    sha = git_blob_sha(source)
    if sha != EXPECTED_BLOB:
        raise RuntimeError("Unexpected nukeris.py blob after materialization: %s" % sha)

    if changed:
        with open(PATH, "wb") as handle:
            handle.write(source)
        print("Materialized %s (%d bytes, blob %s)" % (PATH, len(source), sha))
    else:
        print("%s is already materialized (blob %s)" % (PATH, sha))


if __name__ == "__main__":
    main()

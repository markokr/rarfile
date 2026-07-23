"""Setup script for rarfile."""

import os
import sys
import sysconfig

from setuptools import setup, Extension

REQUIRE_CRYPTO_EXTENSION = (
    os.environ.get("CIBUILDWHEEL") == "1"
    or os.environ.get("RARFILE_REQUIRE_EXTENSION") == "1"
)

# Always build against the limited/stable ABI (abi3) so a single build works
# across CPython versions and source builds exercise the same API surface we
# ship in CI wheels. The extension only uses stable-ABI symbols available since
# 3.10 (the project's minimum). The stable ABI does not cover free-threaded
# builds, so those fall back to a regular version-specific build.
limited = (
    sys.version_info >= (3, 10)
    and not sysconfig.get_config_var("Py_GIL_DISABLED")
)

setup(
    ext_modules=[
        Extension(
            name="rarfile._crypto",
            sources=["src/rarfile/_crypto.c"],
            py_limited_api=limited,
            define_macros=[("Py_LIMITED_API", "0x030A0000")] if limited else [],
            # CI wheels must contain the C extension; elsewhere a failed
            # build falls back to the pure-python rarfile.crypto at runtime
            optional=not REQUIRE_CRYPTO_EXTENSION,
        ),
    ],
    options={"bdist_wheel": {"py_limited_api": "cp310"} if limited else {}},
)

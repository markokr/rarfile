"""Setup script for rarfile."""

import os
import sys
import sysconfig

from setuptools import Extension, setup

# C extension is optional by default
REQUIRE_CRYPTO_EXTENSION = (
    os.environ.get("CIBUILDWHEEL") == "1"
    or os.environ.get("RARFILE_REQUIRE_EXTENSION") == "1"
)

# If possible build against the limited/stable ABI (abi3)
limited = (
    sys.version_info >= (3, 10)
    and not sysconfig.get_config_var("Py_GIL_DISABLED")
)

setup(
    ext_modules=[
        Extension(
            name="rarfile._crypto",
            sources=["src/crypto/module.c", "src/crypto/rar3_s2k_core.c", "src/crypto/bhash.c"],
            py_limited_api=limited,
            define_macros=[("Py_LIMITED_API", "0x030A0000")] if limited else [],
            optional=not REQUIRE_CRYPTO_EXTENSION,
        ),
    ],
    options={"bdist_wheel": {"py_limited_api": "cp310"} if limited else {}},
)

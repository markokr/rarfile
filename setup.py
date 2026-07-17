"""Setup script for rarfile."""

import os
import sys
import sysconfig

from setuptools import setup, Extension

IS_CIBUILDWHEEL = os.environ.get("CIBUILDWHEEL", "0") == "1"

# Only the CI built wheels use the limited ABI
# It is only supported on Python 3.11 or later, and not for 3.14 Free-threaded builds.
limited = (
    IS_CIBUILDWHEEL
    and sys.version_info >= (3, 11)
    and not sysconfig.get_config_var("Py_GIL_DISABLED")
)

setup(
    ext_modules=[
        Extension(
            name="rarfile._crypto",
            sources=["src/rarfile/_crypto.c"],
            py_limited_api=limited,
            define_macros=[("Py_LIMITED_API", "0x030B0000")] if limited else [],
            # CI wheels must contain the C extension; elsewhere a failed
            # build falls back to the pure-python rarfile.crypto at runtime
            optional=not IS_CIBUILDWHEEL,
        ),
    ],
    options={"bdist_wheel": {"py_limited_api": "cp311"} if limited else {}},
)

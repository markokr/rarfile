"""Setup script for rarfile."""

import os
import sys
import sysconfig

from setuptools import setup, Extension

# Only the CI built wheels use the limited ABI
# It is only supported on Python 3.11 or later, and not for 3.14 Free-threaded builds.
limited = (
    os.environ.get("CIBUILDWHEEL", "0") == "1"
    and sys.version_info >= (3, 11)
    and not sysconfig.get_config_var("Py_GIL_DISABLED")
)

setup(
    ext_modules=[
        Extension(
            name="rarfile._rarfile",
            sources=["src/rarfile/rarfile.c"],
            py_limited_api=limited,
            define_macros=[("Py_LIMITED_API", "0x030B0000")] if limited else [],
        ),
    ],
    options={"bdist_wheel": {"py_limited_api": "cp311"} if limited else {}},
)

"""Setup script for rarfile.
"""

import os
import sysconfig

from setuptools import setup, Extension

# Free-threaded builds have no stable ABI yet (PEP 803)
limited = "ABI3" in os.environ and not sysconfig.get_config_var("Py_GIL_DISABLED")

setup(
    ext_modules=[
        Extension(
            name="rarfile._rarfile",
            sources=["src/rarfile/rarfile.c"],
            py_limited_api=limited,
            define_macros=[
                ("Py_LIMITED_API", "0x030B0000")
            ] if limited else [],
        ),
    ],
    options={"bdist_wheel": {"py_limited_api": "cp311"} if limited else {}},
)

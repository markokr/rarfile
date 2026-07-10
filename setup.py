"""Setup script for rarfile.
"""

import os
import sysconfig

from setuptools import setup, Extension

def description_short():
    with open("README.rst") as readme:
        ldesc = readme.read().strip()
        sdesc = ldesc.split('\n')[0].split(' - ')[1].strip()
        return sdesc

def description_long():
    with open("README.rst") as readme:
        return readme.read().strip()

# Free-threaded builds have no stable ABI yet (PEP 803)
limited = "ABI3" in os.environ and not sysconfig.get_config_var("Py_GIL_DISABLED")

setup(
    description=description_short(),
    long_description=description_long(),
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

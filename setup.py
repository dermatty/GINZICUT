import os
import sys

from setuptools import find_packages, setup

VERSION = "1.3"

setup(
    name="Ginzicut",
    version=VERSION,
    description="nntp test server for ginzicut",
    author="dermatty",
    author_email="stephan@untergrabner.at",
    url="https://github.com/dermatty/GINZICUT",
    platforms="posix",
    packages=find_packages(),
    include_package_data=True,
    #package_data={'ginzicut': ['config/ginzicut_settings.py']},                   # for pip
    #data_files=[('ginzicut/config', ['ginzicut/config/ginzicut_settings.py'])],   # for setup.py install
    entry_points={"console_scripts": ["ginzicut = ginzicut.__main__:run"]},
    install_requires=["redis>=3.2.0"],
    keywords=["usenet", "nntp"],
    python_requires=">=3.7.1",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Programming Language :: Python :: 3.7",
    ])

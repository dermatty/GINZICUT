import os
import sys

from setuptools import find_packages, setup

VERSION = "1.0"

setup(
    name="Ginzicut",
    version=VERSION,
    description="nntp test server for ginzicut",
    author="dermatty",
    author_email="stephan@untergrabner.at",
    url="https://github.com/dermatty/GINZICUT",
    # download_url=("https://pypi.python.org/packages/source/R/Radicale/Radicale-%s.tar.gz" % VERSION),
    license="GNU GPL v3",
    platforms="posix",
    packages=find_packages(),
    entry_points={"console_scripts": ["ginzicut = ginzicut.__main__:run"]},
    install_requires=["redis>=3.2.0", "python-dateutil>=2.7.3"],
    keywords=["usenet", "nntp"],
    python_requires=">=3.7.1",
    classifiers=[
        "Development Status :: 5 - Production/Stable"])
        #"Environment :: Console",
        #"Environment :: Web Environment",
        #"Intended Audience :: End Users/Desktop",
        #"Intended Audience :: Information Technology",
        #"License :: OSI Approved :: GNU General Public License (GPL)",
        #"Operating System :: OS Independent",
        #"Programming Language :: Python :: 3",
        #"Programming Language :: Python :: 3.5",
        #"Programming Language :: Python :: 3.6",
        #"Programming Language :: Python :: 3.7",
	#"Topic :: Office/Business :: Groupware"])

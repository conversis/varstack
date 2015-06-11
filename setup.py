import os, sys
from setuptools import setup, find_packages

version = '0.4'

install_requires = ['setuptools', 'PyYAML']
if sys.version_info < (2, 7):
    install_requires.append('simplejson')
    install_requires.append('argparse')

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='varstack',
    version=version,
    description='A tool to create stacked configuration structures',
    url = 'https://github.com/conversis/varstack',
    license = 'MIT',
    author='Dennis Jacobfeuerborn',
    author_email='d.jacobfeuerborn@conversis.de',
    packages=['varstack'],
    scripts=['bin/varstack'],
    install_requires=install_requires,
)

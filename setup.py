from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='pyapitest',
    version='0.0.1.dev4',
    description='Simple API testing in Python',
    long_description=long_description,
    url='https://github.com/danielatdattrixdotcom/pyapitest',
    author='Daniel Anderson',
    author_email='daniel@dattrix.com',
    license='BSD',
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
    ],
    keywords='api testing json',
    packages=['pyapitest'],
    install_requires=['requests', 'cerberus', 'six'],
)

.. image:: https://travis-ci.org/danielatdattrixdotcom/pyapitest.svg?branch=master
    :target: https://travis-ci.org/danielatdattrixdotcom/pyapitest

.. image:: https://badge.fury.io/py/pyapitest.svg
    :target: https://badge.fury.io/py/pyapitest


pyapitest
=========
Test HTTP APIs using plain configuration in JSON.


Objectives
==========
- Create a HTTP request testing tool that is uses tests written soley in JSON.
- Make configurations simple, non-repetitive and matched to parameters passed to requests
- Be a tool to use within the testing framework of the users' choice, not provide a standalone solution.


Status
======
Currently in development. I am building it along side writing tests for an existing application, features will be added on an as-needed basis. Specifically the use of the modules jsonschema and jmespath will be implemented after the basics are all addressed. JSON is going to be the default supported config and request/response format, but will be written so that anything that can become a dict can be used.


Development/Testing
===================
::

    pip install pytest bottle six requests cerberus

You'll find a script for running tests, and a test HTTP server in the root of the repo.


Acknowledgements
================
I thought the YAML configs used for `pyresttest <https://github.com/svanoort/pyresttest>`_ were a clean way to write tests for API endpoints, but wanted to make a tool more easily maintained.

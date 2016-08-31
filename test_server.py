# -*- coding: utf-8 -*-
from bottle import Bottle, run, abort, HTTPResponse, request, HTTP_CODES
from six import iteritems

app = Bottle()

accepted_methods = ['HEAD', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE']
slugified_http_codes = {name.lower().replace(' ', '_'): code for code, name in iteritems(HTTP_CODES)}


@app.route('/', method=accepted_methods)
def root():
    return {}


@app.route('/echo', method=accepted_methods)
def root():
    return request.body


@app.route('/return_status/<status_code>', method=accepted_methods)
def return_status(status_code):
    return HTTPResponse(status=int(status_code), body={})


@app.route('/return_named/<name>', method=accepted_methods)
def return_named(name):
    try:
        return HTTPResponse(status=int(slugified_http_codes[name]), body={})
    except KeyError:
        abort(500, 'Name given not found in bottle.HTTP_CODES.\nSlugged names that I know of:\n\n%s' % '\n'.join(
            slugified_http_codes.keys()))

run(app, host='localhost', port=8080)

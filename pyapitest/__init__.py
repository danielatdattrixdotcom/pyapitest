# -*- coding: utf-8 -*-
from __future__ import print_function

import collections
import logging
import os
import json
from requests import Request, Session
from requests.structures import CaseInsensitiveDict
from six import iteritems

logger = logging.getLogger(__name__)

'''

'''


class CommonTestProperties(object):
    def __init__(self, data, **kwargs):
        self.label = data.get('label', None)
        self.items = data.get('items', [])
        self.data = data.get('data', {})
        self.parent = kwargs.get('parent')

    def __getitem__(self, item):
        return self.data[item]


class Suite(object):
    def __init__(self, suite_file):
        self.items = operations.open_file(suite_file)

    def __iter__(self):
        for i in self.items:
            yield Group(i)


class Group(CommonTestProperties):
    def __init__(self, data):
        super(Group, self).__init__(data)
        self._init_items()
        self._session = data.get('session', False)
        if self._session:
            self._session_obj = Session()

    def session(self):
        if self._session:
            return self._session_obj
        else:
            return Session()

    def _init_items(self):
        obj_items = []
        for i in self.items:
            obj_items.append(GroupTests(operations.open_file(i), parent=self))
        self.items = obj_items

    def run(self):
        for gt in self.items:
            gt.run()


class GroupTests(object):
    def __init__(self, data, parent):
        self.parent = parent
        self.tests = []
        for i in data:
            obj = operations.item_to_object(i, parent=self)
            if isinstance(obj, Test):
                self.tests.append(obj)
            else:
                setattr(self, i['type'], obj)

    def run(self):
        for t in self.tests:
            logger.info('Test: %s' % t.label)
            try:
                all_passed = t.run()
                if all_passed is False:
                    logger.error('INCOMPLETE')
                else:
                    logger.info('PASS')
            except FailedTest as e:
                logger.error('FAIL: %s' % e.message)


class Vars(CommonTestProperties):
    pass


class FailedTest(Exception):
    pass


class Test(CommonTestProperties):
    def __init__(self, data, **kwargs):
        super(Test, self).__init__(data, **kwargs)
        self.request_config = {}
        self.response_config = {}

    @property
    def session(self):
        return self.parent.parent.session()

    def _inherit_config(self):
        for k in ['request', 'response']:
            r_config = CaseInsensitiveDict()
            r_config.update(self.parent.parent[k])
            r_config = operations.recursive_update(r_config, self[k])
            setattr(self, '%s_config' % k, r_config)

    def _var_replace(self, find_str):
        if str != 'null' and getattr(self.parent, 'vars', None):
            v_rep = {k: v for k, v in iteritems(self.parent.vars.data)}
            v_rep.update({'cookies__%s' % k: v for k, v in self.session.cookies.items()})
            return find_str % v_rep
        else:
            return find_str

    def _build_url(self, path):
        return ''.join([self.request_config['host']['scheme'],
                        self.request_config['host']['address'],
                        '/',
                        operations.url_clean(self._var_replace(path)), ])

    def _get_headers(self):
        headers = self.request_config.get('headers')
        if headers:
            headers = {k: self._var_replace(v) for k, v in headers.items()}
        return headers

    def _get_data(self):
        body = self.request_config.get('body')
        data = None
        if body is not None:
            if isinstance(body, (dict, list)):
                # If body data is a dict or list this is a formatted request in the test file itself.
                data = self._var_replace(operations.to_str(body))
            elif isinstance(body, str):
                # If body is a str, the assumption will be made it is a file reference.
                data = self._var_replace(operations.to_str(operations.open_file(body)))
        return data

    def _make_request(self, **kwargs):
        req = Request(self.request_config['method'],
                      self._build_url(path=kwargs.get('path', self.request_config['host']['path'])),
                      headers=self._get_headers(),
                      data=self._get_data())

        prep_req = self.session.prepare_request(req)
        # Set this up to prepare for some type of pre-send hook

        self.response = self.session.send(prep_req)
        self._validate()

    def _validate(self):
        if int(self.response.status_code) != int(self.response_config['headers']['status']):
            raise FailedTest('Returned status %s, when %s was expected' % (self.response.status_code,
                                                                           self.response_config['headers']['status']))

    def run(self):
        self._inherit_config()
        if isinstance(self.request_config['host']['path'], list):
            all_passed = True
            for url_path in self.request_config['host']['path']:
                try:
                    self._make_request(path=url_path)
                    logger.info('PASS [%s]' % url_path)
                except FailedTest as e:
                    all_passed = False
                    logger.error('FAIL: %s [%s]' % (e.message, url_path))
            return all_passed
        else:
            self._make_request()


class ErrorLoghandler(logging.Handler):
    def __init__(self):
        super(ErrorLoghandler, self).__init__()
        self.output = []
        self.error_count = 0

    def emit(self, record):
        self.output.append(self.format(record))
        if record.levelno == logging.ERROR:
            self.error_count += 1


class BaseOperations(object):
    @staticmethod
    def url_clean(url):
        url_parts = [part for part in url.split('/') if part != '']
        if url.endswith('/'):
            url_parts.append(' ')
        return '/'.join(url_parts).strip()

    @staticmethod
    def recursive_update(d, u):
        for k, v in iteritems(u):
            if isinstance(v, collections.Mapping):
                r = operations.recursive_update(d.get(k, {}), v)
                d[k] = r
            else:
                d[k] = u[k]
        return d

    @staticmethod
    def item_to_object(item, **kwargs):
        types = {'group': Group,
                 'vars': Vars,
                 'test': Test,}
        return types[item['type']](item, parent=kwargs.get('parent'))

    @staticmethod
    def open_file(input_file):
        raise NotImplementedError

    @staticmethod
    def to_str(data):
        raise NotImplementedError


class JSONOperations(BaseOperations):
    @staticmethod
    def open_file(json_file):
        """
        Opens a json file, only a file and will try adding a .json extension. Absolute and relative paths are fine.
        :param json_file: Path or name of JSON file to open.
        :return:
        """
        open_file = None
        json_file = os.path.abspath(json_file)
        file_with_json = '.'.join([json_file, 'json'])
        if os.path.exists(json_file) and os.path.isfile(json_file):
            open_file = json_file
        elif os.path.exists(file_with_json) and os.path.isfile(file_with_json):
            open_file = file_with_json

        if open_file is None:
            raise IOError('File %s not located' % json_file)
        else:
            return json.load(open(open_file))

    @staticmethod
    def to_str(data):
        return json.dumps(data)


operations = JSONOperations


def run(suite_file, operations_obj=None):
    global operations
    if operations_obj:
        operations = operations_obj

    h = ErrorLoghandler()
    logger.addHandler(h)
    logger.setLevel(logging.DEBUG)
    suite = Suite(suite_file)
    os.chdir(os.path.dirname(os.path.abspath(suite_file)))
    for i in suite:
        logger.info('Group: %s' % i.label)
        i.run()

    return h.error_count, h.output

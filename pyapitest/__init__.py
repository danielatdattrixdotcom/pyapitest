# -*- coding: utf-8 -*-
from __future__ import print_function

import collections
import copy
import json
import logging

import os
from cerberus import Validator, SchemaError
from requests import Request, Session
from requests.structures import CaseInsensitiveDict
from six import iteritems, string_types

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
                logger.error('FAIL: %s' % str(e))


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
        """Inherit request and response config from Group and update this object."""
        for k in ['request', 'response']:
            r_config = CaseInsensitiveDict()
            r_config.update(copy.deepcopy(self.parent.parent[k]))
            try:
                r_config = operations.recursive_update(r_config, self[k])
            except KeyError:
                pass
            setattr(self, '%s_config' % k, r_config)

    def _var_replace(self, find_str):
        """Takes any string that may contain formatting and applies vars from config. Will apply cookies if session is True.

        :param find_str: String from a config file to apply any substitutions to.
        :return: Resulting string that has had replacements carried out from var and/or cookies.
        """
        if str != 'null' and getattr(self.parent, 'vars', None):
            v_rep = {k: v for k, v in iteritems(self.parent.vars.data)}
            v_rep.update({'cookies__%s' % k: v for k, v in self.session.cookies.items()})
            return find_str % v_rep
        else:
            return find_str

    def _build_url(self, path):
        """Builds request URL from self.request_config and given path (with variable substitutions run on it).

        :param path: URL path
        :return: Full URL ready for request.
        """
        return ''.join([self.request_config['host']['scheme'],
                        self.request_config['host']['address'],
                        '/',
                        operations.url_clean(self._var_replace(path)), ])

    def _get_headers(self):
        """Uses self.request_config to populate headers in dict. Variable substitutions performed on values.

        :rtype: dict
        :return: Dict of headers ready for request.
        """
        headers = self.request_config.get('headers')
        if headers:
            headers = {k: self._var_replace(v) for k, v in headers.items()}
        return headers

    def _get_data(self):
        """Uses self.request_config to get body with variable substitutions performed on the body as a whole.

        :rtype: str
        :return: Request body ready for request.
        """
        body = self.request_config.get('body')
        data = None
        if body is not None:
            if isinstance(body, (dict, list)):
                # If body data is a dict or list this is a formatted request in the test file itself.
                data = self._var_replace(operations.to_str(body))
            elif isinstance(body, string_types):
                # If body is a str, the assumption will be made it is a file reference.
                try:
                    data = self._var_replace(operations.to_str(operations.open_file(body)))
                except IOError:
                    # Fall back to just treating the string as a literal serialized form of the object.
                    data = self._var_replace(operations.to_str(body))
        return data

    def _make_request(self, **kwargs):
        """Prepares and performs the request. Uses path from self.request_config or from kwarg "path".
        Wraps it all up by calling self._validate which will raise :class:`pyapitest.FailedTest`.

        :param kwargs:
        :raises: FailedTest
        """
        req = Request(self.request_config['method'],
                      self._build_url(path=kwargs.get('path', self.request_config['host']['path'])),
                      headers=self._get_headers(),
                      data=self._get_data())

        prep_req = self.session.prepare_request(req)
        # Set this up to prepare for some type of pre-send hook

        self.response = self.session.send(prep_req)
        self._validate()

    def _validate(self):
        """Compare response to expected from self.response_config

        :raises: FailedTest
        """
        if self.response_config.get('status') and int(self.response.status_code) != int(self.response_config['status']):
            raise FailedTest('Returned status %s, when %s was expected' % (self.response.status_code,
                                                                           self.response_config['status']))

        if self.response_config.get('headers'):
            for name, value in iteritems(self.response_config['headers']):
                if str(self.response.headers.get(name)) != str(value):
                    raise FailedTest('Header %s is "%s", when "%s" was expected' % (name,
                                                                                    self.response.headers.get(name),
                                                                                    value))

        if self.response_config.get('body'):
            operations.validate_response_body(self.response, self.response_config.get('body'),
                                              validator_kwargs=self.response_config.get('validator', {}))

    def run(self):
        self._inherit_config()
        if isinstance(self.request_config['host']['path'], list):
            # It's possible for path to be a list of paths instead of a string. This make it easier to specify many
            # paths need the same expected test response.
            all_passed = True
            for url_path in self.request_config['host']['path']:
                try:
                    self._make_request(path=url_path)
                    logger.info('PASS [%s]' % url_path)
                except FailedTest as e:
                    all_passed = False
                    logger.error('FAIL: %s [%s]' % (str(e), url_path))
            return all_passed
        else:
            self._make_request()


class ErrorLogHandler(logging.Handler):
    """logging handler that stores outputs in a list, and total errors as int."""

    def __init__(self):
        super(ErrorLogHandler, self).__init__()
        self.output = []
        self.error_count = 0

    def emit(self, record):
        self.output.append(self.format(record))
        if record.levelno == logging.ERROR:
            self.error_count += 1


class BaseOperations(object):
    @staticmethod
    def url_clean(url_path):
        """Cleans up the path of a URL by remove excess forward slashes.

        :param url_path: Path portion of a URL
        :type url_path: str
        :rtype: str
        :return: A URL path cleaned of excess forward slashes.
        """
        url_parts = [part for part in url_path.split('/') if part != '']
        if url_path.endswith('/'):
            url_parts.append(' ')
        return '/'.join(url_parts).strip()

    @staticmethod
    def recursive_update(base_dict, dict_updates):
        """Apply updates to a dict recursively"""
        for k, v in iteritems(dict_updates):
            if isinstance(v, collections.Mapping):
                r = operations.recursive_update(base_dict.get(k, {}), v)
                base_dict[k] = r
            else:
                base_dict[k] = dict_updates[k]
        return base_dict

    @staticmethod
    def item_to_object(item, **kwargs):
        """Takes a representation of a group, test, vars from config file and initializes their object.

        :param item: Representation of group, test, vars, etc.
        :type item: dict
        :param kwargs: Accepts optional keyword parameter parent
        :return: Returns an object that inherits from CommonTestProperties
        """
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

    @classmethod
    def _validate_literal_response(cls, data, expected_value):
        raise NotImplementedError

    @classmethod
    def _validate_object_response(cls, data, expected_data, **kwargs):
        raise NotImplementedError

    @classmethod
    def validate_response_body(cls, response, response_config_body, **kwargs):
        raise NotImplementedError


class JSONOperations(BaseOperations):
    @staticmethod
    def open_file(json_file):
        """Opens a JSON file, only a file and will try adding a .json extension. Absolute and relative paths are fine.

        :param json_file: Path to JSON file to open
        :type json_file: str
        :rtype: dict
        :raises: IOError
        :return: dict representing data contained in given JSON file
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
        """Takes a dict, return a string via json.dumps

        :param data: dict to make into string
        :type: data: dict
        :rtype: str
        :return: String from dict passed in
        """
        return json.dumps(data)

    @classmethod
    def _validate_literal_response(cls, data, expected_value):
        """Validates response body purely as identical strings.

        :param data: String of response text
        :param expected_value: Expected response text
        """
        if str(data) != str(expected_value):
            raise FailedTest('Literal string response failure.')

    @classmethod
    def _validate_object_response(cls, data, expected_data, **kwargs):
        """Validates the literal string representation of a response, or uses Cerberus to validate.

        :param data: Response data to validate
        :param expected_data: Dict to validate via Cerberus or literal comparison
        :param kwargs: Accpts validator_kwargs to pass along to cerberus.Validator
        :return: None
        :raises: FailedTest
        """
        try:
            v = Validator(**kwargs.get('validator_kwargs', {}))
            if not v.validate(data, schema=expected_data):
                raise FailedTest('Validated schema failure (%s).' % str(v.errors))
        except SchemaError:
            if cls.to_str(data) != cls.to_str(expected_data):
                raise FailedTest('Literal serialized object match failure.')

    @classmethod
    def validate_response_body(cls, response, response_config_body, **kwargs):
        """Takes response object, and response

        :param response: Response object from requests
        :param response_config_body: Value from response_config['body']  from Test object
        :param kwargs: Accepts validator_kwargs to pass along to cerberus.Validator
        :return: None
        :raises: FailedTest
        """
        if isinstance(response_config_body, string_types):
            try:
                # Assume most strings are a file reference, validate.
                json_file_validation = cls.open_file(response_config_body)
                return cls._validate_object_response(response.json(), json_file_validation,
                                                     validator_kwargs=kwargs.get('validator_kwargs', {}))
            except IOError:
                # Not a file, so we treat it as a literal response.
                return cls._validate_literal_response(response.text, response_config_body)
        elif isinstance(response_config_body, dict):
            return cls._validate_object_response(response.json(), response_config_body,
                                                 validator_kwargs=kwargs.get('validator_kwargs', {}))

        raise FailedTest('No validations performed on body, but validate_response_body() called, why?')


operations = JSONOperations


def run(suite_file, operations_obj=None):
    global operations

    if operations_obj:
        operations = operations_obj

    h = ErrorLogHandler()
    logger.addHandler(h)
    logger.setLevel(logging.DEBUG)

    suite = Suite(suite_file)
    os.chdir(os.path.dirname(os.path.abspath(suite_file)))
    for i in suite:
        logger.info('Group: %s' % i.label)
        i.run()

    return h.error_count, h.output

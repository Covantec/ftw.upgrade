from path import Path
import os
import re
import requests
import socket
import sys


class NoRunningInstanceFound(Exception):
    pass


class APIRequestor(object):

    def __init__(self, username, password):
        self.session = requests.Session()
        self.session.auth = (username, password)

    def GET(self, action, site=None, **kwargs):
        return self._make_request('GET', action, site=site, **kwargs)

    def _make_request(self, method, action, site=None, **kwargs):
        url = get_api_url(action, site=site)
        response = self.session.request(method.upper(), url, **kwargs)
        response.raise_for_status()
        return response


def add_requestor_authentication_argument(argparse_command):
    argparse_command.add_argument(
        '--auth',
        help='Authentication information: "<username>:<password>"')


def with_api_requestor(func):
    def func_wrapper(args):
        default_auth = os.environ.get('UPGRADE_AUTHENTICATION', None)
        auth_value = args.auth or default_auth
        if not auth_value:
            print 'ERROR: No authentication information provided.'
            print 'Use either the --auth param or the UPGRADE_AUTHENTICATION' + \
                ' environment variable for providing authentication information' + \
                ' in the form "<username>:<password>".'
            sys.exit(1)

        if len(auth_value.split(':')) != 2:
            print 'ERROR: Invalid authentication information "{0}".'.format(
                auth_value)
            print 'A string of form "<username>:<password>" is required.'
            sys.exit(1)

        requestor = APIRequestor(*auth_value.split(':'))
        return func(args, requestor)
    func_wrapper.__name__ = func.__name__
    func_wrapper.__doc__ = func.__doc__
    return func_wrapper


def error_handling(func):
    def func_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except NoRunningInstanceFound:
            print 'ERROR: No running Plone instance detected.'
            sys.exit(1)

    func_wrapper.__name__ = func.__name__
    func_wrapper.__doc__ = func.__doc__
    return func_wrapper


def get_api_url(action, site=None):
    url = get_zope_url()
    if site:
        url += site.rstrip('/').strip('/') + '/'
    url += 'upgrades-api/'
    url += action
    return url


def get_zope_url():
    instance = get_running_instance(Path.getcwd())
    if not instance:
        raise NoRunningInstanceFound()
    return 'http://localhost:{0}/'.format(instance['port'])


def get_running_instance(buildout_path):
    for zconf in find_instance_zconfs(buildout_path):
        port = get_instance_port(zconf)
        if not port:
            continue
        if is_port_open(port):
            return {'port': port,
                    'path': zconf.dirname().dirname()}
    return None


def find_instance_zconfs(buildout_path):
    return sorted(buildout_path.glob('parts/instance*/etc/zope.conf'))


def get_instance_port(zconf):
    match = re.search(r'address (\d+)', zconf.text())
    if match:
        return int(match.group(1))
    return None


def is_port_open(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    return result == 0

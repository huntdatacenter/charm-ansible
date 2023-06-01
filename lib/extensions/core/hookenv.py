# Copyright 2014-2015 Canonical Limited.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"Interactions with the Juju environment"
# Copyright 2013 Canonical Ltd.
#
# Authors:
#  Charm Helpers Developers <juju@lists.ubuntu.com>

from __future__ import print_function

import json
import os
import subprocess
from functools import wraps

from yaml import safe_load

cache = {}


def cached(func):
    """Cache return values for multiple executions of func + args
    For example::
        @cached
        def unit_get(attribute):
            pass
        unit_get('test')
    will cache the result of unit_get + 'test' for future calls.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        global cache
        key = json.dumps((func, args, kwargs), sort_keys=True, default=str)
        try:
            return cache[key]
        except KeyError:
            pass  # Drop out of the exception handler scope.
        res = func(*args, **kwargs)
        cache[key] = res
        return res
    wrapper._wrapped = func
    return wrapper


def flush(key):
    """Flushes any entries from function cache where the
    key is found in the function+args """
    flush_list = []
    for item in cache:
        if key in item:
            flush_list.append(item)
    for item in flush_list:
        del cache[item]


def local_unit():
    """Local unit ID"""
    return os.environ['JUJU_UNIT_NAME']


def _port_op(op_name, port, protocol="TCP"):
    """Open or close a service network port"""
    _args = [op_name]
    icmp = protocol.upper() == "ICMP"
    if icmp:
        _args.append(protocol)
    else:
        _args.append('{}/{}'.format(port, protocol))
    try:
        subprocess.check_call(_args)
    except subprocess.CalledProcessError:
        # Older Juju pre 2.3 doesn't support ICMP
        # so treat it as a no-op if it fails.
        if not icmp:
            raise


def open_port(port, protocol="TCP"):
    """Open a service network port"""
    _port_op('open-port', port, protocol)


def close_port(port, protocol="TCP"):
    """Close a service network port"""
    _port_op('close-port', port, protocol)


def open_ports(start, end, protocol="TCP"):
    """Opens a range of service network ports"""
    _args = ['open-port']
    _args.append('{}-{}/{}'.format(start, end, protocol))
    subprocess.check_call(_args)


def close_ports(start, end, protocol="TCP"):
    """Close a range of service network ports"""
    _args = ['close-port']
    _args.append('{}-{}/{}'.format(start, end, protocol))
    subprocess.check_call(_args)


def opened_ports():
    """Get the opened ports
    *Note that this will only show ports opened in a previous hook*
    :returns: Opened ports as a list of strings: ``['8080/tcp', '8081-8083/tcp']``
    """
    _args = ['opened-ports', '--format=json']
    return json.loads(subprocess.check_output(_args).decode('UTF-8'))


@cached
def unit_get(attribute):
    """Get the unit ID for the remote unit"""
    _args = ['unit-get', '--format=json', attribute]
    try:
        return json.loads(subprocess.check_output(_args).decode('UTF-8'))
    except ValueError:
        return None


def charm_dir():
    """Return the root directory of the current charm"""
    d = os.environ.get('JUJU_CHARM_DIR')
    if d is not None:
        return d
    return os.environ.get('CHARM_DIR')


@cached
def metadata():
    """Get the current charm metadata.yaml contents as a python object"""
    with open(os.path.join(charm_dir(), 'metadata.yaml')) as md:
        return safe_load(md)


@cached
def charm_name():
    """Get the name of the current charm as is specified on metadata.yaml"""
    return metadata().get('name')


def unit_public_ip():
    """Get this unit's public IP address"""
    return unit_get('public-address')


def unit_private_ip():
    """Get this unit's private IP address"""
    return unit_get('private-address')

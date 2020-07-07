#!/usr/bin/env python
"""
LDAP synchronisation script. It takes a configuration file, from
which it reads necessary values for a source LDAP. These
values include: url, basedn, binddn and bind password.

The configuration file clould also lists the necessary info
for synchronization with JumpCloud.

The script sill synchronise from LDAP to JumpClound of People and Group memberhips from
a given subtree of the source LDAP.
"""

import sys
import yaml
import re
import ldap

from connection import Connection
from jumpcloud import JumpCloud

import json

global jumpcloud

def show(label, data):
    print(label)
    print(json.dumps(data, indent=4, sort_keys=True))


class ConfigItemNotFound(Exception):
    """A configuration item could not be found."""
    def __init__(self, config_item):
        self.config_item = config_item


def extract_error_msg_from_ldap_exeception(e):
    """
    When the LDAP library raises an exeption the error message
    contains a descrition and additional info. Return those seperately
    instead of a single string.
    """
    s = str(e)
    d = eval(s)
    return d['desc'], d['info']


def read_config_file():
    """Read a YAML config file."""

    if len(sys.argv) < 2:
        print("Missing config file.")
        print("usage: {} <config_file.yml>".format(sys.argv[0]))
        sys.exit(2)

    filename = sys.argv[1]
    with open(filename) as fd:
        config = yaml.safe_load(fd)

    return config, filename


def get_value_from_config(config, *keys):
    """
    Get the value that belongs to the keys combination from the config file.
    This function is called recursively until either the key path delivers a
    value, or the key path is invalid, in which case the ConfigItemNotFound
    exception is raised. Otherwise the found value is returned.
    """

    try:
        if len(keys) == 1:
            return config[keys[0]]
        else:
            return get_value_from_config(config[keys[0]], *keys[1:])
    except KeyError:
        raise ConfigItemNotFound(keys[0])
    except ConfigItemNotFound as e:
        config_item = f'{keys[0]}/{e.config_item}'
        raise ConfigItemNotFound(config_item)


def init_jumpcloud(config):
    #  Enable code below for jumpcloud synchronization
    if 'api' in config:
        return JumpCloud(
            get_value_from_config(config, 'api', 'url'),
            get_value_from_config(config, 'api', 'key')
        )
    else:
        print(f'Skipping JumpCloud as it is not configured.')

    return None

def dn2rdns(dn):
    rdns = {}
    r = ldap.dn.str2dn(dn)
    for rdn in r:
        (a, v, t) = rdn[0]
        rdns.setdefault(a, []).append(v)
    return rdns

def get_people(ldap_connection):
    """
    Given the 'ldap_connection', return all people
    """
    r = ldap_connection.rfind(
        f'ou=People',
        "(&(ObjectClass=person)(uid=*))",
        None,
        ldap.SCOPE_ONELEVEL
    )

    uids = {}

    for attributes in r.values():
        show('User Attributes:', attributes)

        uid = attributes['uid'][0]
        uids[uid] = attributes

    return uids


def sync(src_ldap):

    src_people = get_people(src_ldap)

    for uid in src_people:
        jumpcloud.person(**src_people[uid])

    group_dns = src_ldap.rfind(
        f'ou=Groups',
        'ObjectClass=posixGroup',
        ['cn', 'sczMember']
    )

    for dn, attributes in group_dns.items():
        show('Group Attributes:', attributes)
    
        group = dn2rdns(dn)['cn'][0]

        members = []
        if 'sczMember' in attributes:
            for i in attributes['sczMember']:
                rdns = dn2rdns(i)
                if 'uid' in  rdns:
                    members.append(rdns['uid'][0])

            jumpcloud.group(group, members)

if __name__ == "__main__":

    config, config_filename = read_config_file()

    try:
        src_ldap = Connection(get_value_from_config(config, 'ldap'), 'SRAM services')
        
        jumpcloud = init_jumpcloud(config)

        sync(src_ldap)

        jumpcloud.cleanup()

    except ConfigItemNotFound as e:
        print(f'Config error: key \'{e.config_item}\' does not exist in config file {config_filename}.')
    except ldap.SERVER_DOWN as e:
        desc, info = extract_error_msg_from_ldap_exeception(e)
        print(f'{desc} ({info})')

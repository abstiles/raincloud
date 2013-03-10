#!/usr/bin/env python

import socket
from getpass import getpass
from telnetlib import Telnet
from inspect import getargspec
from functools import wraps


__all__ = ['EAccess']

HOST = 'eaccess.play.net'
PORT = 7900


class AuthenticationError(Exception):
    pass

# Automatic argument assignment function borrowed from stackoverflow.com
# http://stackoverflow.com/a/3653049
def autoargs(*include,**kwargs):
    def _autoargs(func):
        attrs,varargs,varkw,defaults=getargspec(func)
        def sieve(attr):
            if kwargs and attr in kwargs['exclude']: return False
            if not include or attr in include: return True
            else: return False
        @wraps(func)
        def wrapper(self,*args,**kwargs):
            # handle default values
            for attr,val in zip(reversed(attrs),reversed(defaults)):
                if sieve(attr): setattr(self, attr, val)
            # handle positional arguments
            positional_attrs=attrs[1:]
            for attr,val in zip(positional_attrs,args):
                if sieve(attr): setattr(self, attr, val)
            # handle varargs
            if varargs:
                remaining_args=args[len(positional_attrs):]
                if sieve(varargs): setattr(self, varargs, remaining_args)
            # handle varkw
            if kwargs:
                for attr,val in kwargs.iteritems():
                    if sieve(attr): setattr(self,attr,val)
            return func(self,*args,**kwargs)
        return wrapper
    return _autoargs

class EAccess:
    version = 'AL4334 SGE16 1 14'
    @autoargs()
    def __init__(self, game='DR', host=HOST, port=PORT, tries=1, timeout=5):
        pass

    def login(self, username, password, character):
        response = None
        try:
            self.connect()
            #self.conn.write(EAccess.version + '\n')
            #response = self.conn.read_until('CURRENT', self.timeout)
            #if 'CURRENT' not in response:
            #    print('Unexpectedly not current eaccess version.')
            #    raise RuntimeError()
            response = self.get_key()
            self.hash_key = response
            #print('Got the key: ' + repr(self.hash_key))
            response = self.send_auth(username, password)
            _, auth_details = _parse_line_syntax(response)
            if len(auth_details) == 4:
                ret_user, _, auth_key, full_name = auth_details
                #print('Success! ' + auth_key)
            elif len(auth_details) == 2:
                _, err = auth_details
                if err == 'NORECORD':
                    raise AuthenticationError('Bad user name ' + username)
                elif err == 'PASSWORD':
                    raise AuthenticationError('Bad password')
                raise AuthenticationError('Unknown server response: ' +
                                          ', '.join(auth_details))
            else:
                raise AuthenticationError('Unknown server response: ' +
                                          ', '.join(auth_details))
            self.get_sub_type()
            self.choose_game()
            self.get_pricing()
            response = self.get_characters()
            _, details = _parse_line_syntax(response)
            if character not in details:
                raise AuthenticationError("Character not found!" +
                                          ', '.join(details))
            else:
                char_code = details[details.index(character) - 1]

            #print("Character code:", char_code)
            response = self.choose_character(char_code)
            _, connect_details = _parse_line_syntax(response)
            #print 'Success!', '\n'.join(connect_details)
            #print(repr(connect_details))
            for item, value in [info.split('=') for info in connect_details
                                if '=' in info]:
                if item == 'KEY':
                    return value
        except (EOFError, socket.error):
            print('Connection closed unexpectedly. Last server response: ' +
                  str(response))
            raise
        except Exception as e:
            print('Something happened. Last server response: ' +
                  str(response))
            print(e.args)
            raise
        finally:
            self.conn.close()

    def connect(self):
        self.conn = Telnet(self.host, self.port)

    def get_key(self):
        self.conn.write(_format_line_syntax('K'))
        return self.conn.read_until('\n', self.timeout).strip()

    def send_auth(self, username, password):
        hashed_pass = _sge_hash(password, self.hash_key)
        auth_line = _format_line_syntax('A', [username, hashed_pass])
        self.conn.write(auth_line)
        return self.conn.read_until('\n', self.timeout).strip()

    def get_sub_type(self):
        self.conn.write(_format_line_syntax('F', [self.game]))
        self.get_server_response()

    def choose_game(self):
        # Also gets some links?
        self.conn.write(_format_line_syntax('G', [self.game]))
        self.get_server_response()

    def get_pricing(self):
        # Totally a guess as to what this does
        self.conn.write(_format_line_syntax('P', [self.game]))
        self.get_server_response()

    def get_characters(self):
        self.conn.write(_format_line_syntax('C'))
        return self.conn.read_until('\n', self.timeout).strip()

    def choose_character(self, character):
        self.conn.write(_format_line_syntax('L', [character, 'STORM']))
        return self.conn.read_until('\n', self.timeout).strip()

    def get_server_response(self):
        line = self.conn.read_until('\n', self.timeout)
        return _parse_line_syntax(line)


def _format_line_syntax(action, properties=[]):
    if action not in 'KAMNGCLFBP':
        raise ValueError(action + ' is not a known action.')
    retval = action
    if properties:
        retval += '\t' + '\t'.join(properties)
    retval += '\r\n'
    return retval

def _parse_line_syntax(line):
    components = line.rstrip('\n').split('\t')
    return components[0], components[1:]

def _sge_hash(password, hash_key):
    return ''.join((chr((ord(hash_key[i]) ^ (ord(password[i]) - 32)) + 32))
                   for i in range(len(password)))


if __name__ == '__main__':
    eaccess = EAccess()
    username = raw_input('Enter your username: ')
    password = getpass()
    character = raw_input('Enter your character: ')
    eaccess.login(username, password, character)

# ESPER Waveform and Variable viewer

from __future__ import print_function
from builtins import str as text

import os
import sys
import requests
import argparse
import cmd
import time
import getpass
import platform
from .version import __version__

if(platform.system() == u'Windows'):
    import ctypes
    import pyreadline as readline
else:
    import readline

here = os.path.abspath(os.path.dirname(__file__))

version = __version__

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def request_get_with_auth(url, params, user, password):
    if(user):
        return requests.get(url, params=params, auth=(user, password))
    else:
        return requests.get(url, params=params)

def request_post_with_auth(url, params, payload, user, password):
    if(user):
        return requests.post(url, params=params, data=payload, auth=(user, password))
    else:
        return requests.post(url, params=params, data=payload)

def set_default_subparser(self, name, args=None):
    """default subparser selection. Call after setup, just before parse_args()
    name: is the name of the subparser to call by default
    args: if set is the argument list handed to parse_args()

    , tested with 2.7, 3.2, 3.3, 3.4
    it works with 2.6 assuming argparse is installed
    """
    subparser_found = False
    for arg in sys.argv[1:]:
        if arg in ['-h', '--help']:  # global help if no subparser
            break
    else:
        for x in self._subparsers._actions:
            if not isinstance(x, argparse._SubParsersAction):
                continue
            for sp_name in x._name_parser_map.keys():
                if sp_name in sys.argv[1:]:
                    subparser_found = True
        if not subparser_found:
            # insert default in first position, this implies no
            # global options without a sub_parsers specified
            if args is None:
                sys.argv.insert(1, name)
            else:
                args.insert(0, name)

class Esper(object):
    ESPER_TYPE_NULL = 0

    def getTypeString(self,esper_type):
        options = {
            0: "null",
            1: "uint8",
            2: "uint16",
            3: "uint32",
            4: "uint64",
            5: "sint8",
            6: "sint16",
            7: "sint32",
            8: "sint64",
            9: "float32",
            10: "float64",
            11: "ascii",
            12: "bool",
            13: "raw"
        }
        return options.get(esper_type, "unknown")

    def getOptionString(self, esper_option):
        retStr = ""
        if(esper_option & 0x01):
            retStr = retStr + "R"
        else:
            retStr = retStr + " "

        if(esper_option & 0x02):
            retStr = retStr + "W"
        else:
            retStr = retStr + " "

        if(esper_option & 0x04):
            retStr = retStr + "H"
        else:
            retStr = retStr + " "

        if(esper_option & 0x08):
            retStr = retStr + "S"
        else:
            retStr = retStr + " "

        if(esper_option & 0x10):
            retStr = retStr + "L"
        else:
            retStr = retStr + " "

        if(esper_option & 0x20):
            retStr = retStr + "W"
        else:
            retStr = retStr + " "

        return retStr

    def getStatusString(self, esper_status):
        retStr = ""
        if(esper_status & 0x01):
            retStr = retStr + "L"
        else:
            retStr = retStr + " "

        if(esper_status & 0x02):
            retStr = retStr + "S"
        else:
            retStr = retStr + " "

        if(esper_status & 0x04):
            retStr = retStr + "D"
        else:
            retStr = retStr + " "

        return retStr

def main():
    try:
        prog='esper-wave'    

        if(platform.system() == u'Windows'):
            if not is_admin():
                # Re-run the program with admin rights
                ctypes.windll.shell32.ShellExecuteW(None, u"runas", text(sys.executable), text(sys.argv), None, 1)        

        argparse.ArgumentParser.set_default_subparser = set_default_subparser

        parser = argparse.ArgumentParser(prog=prog)

        # Verbose, because sometimes you want feedback
        parser.add_argument('-v','--verbose', help="Verbose output", default=False, action='store_true')
        parser.add_argument('--version', action='version', version='%(prog)s ' + version)

        # Sub parser for write,read
        subparsers = parser.add_subparsers(title='commands', dest='command', description='Available Commands', help='Type '+prog+' [command] -h to see additional options')

        # Experiment Mode
        parser_experiment = subparsers.add_parser('experiment', help='<url>')
        parser_experiment.add_argument("url", help="Node URL. ie: 'http://<hostname>:<port>'")
        parser_experiment.add_argument("mid", nargs='?', default='0', help="Module Id or Key")
        parser_experiment.add_argument("-u","--user", default=False, help="User for Auth")
        parser_experiment.add_argument("-p","--password", default=False, help="Password for Auth")

        # Put the arguments passed into args
        parser.set_default_subparser('experiment')
        args = parser.parse_args()

        # Strip trailing / off args.url
        if(args.url[-1:] == '/'):
            args.url = args.url[0:-1]
        
        # if url is missing 'http', add it
        if((args.url[0:7] != 'http://') and (args.url[0:8] != 'https://')):
            args.url = 'http://' + args.url

        if(args.user):
            if(not args.password):
                args.password = getpass.getpass("Insert your password: ") 

        # Attempt to connect to verify the ESPER service is reachable
        querystring = {'mid': 'system'}
        r = request_get_with_auth(args.url + '/read_module', querystring, args.user, args.password)
        if(r.status_code == 200): 
            try:
                resp = r.json()
            except:
                print("Invalid response from ESPER service. Exiting")
                sys.exit(1)

            if(not 'key' in resp):
                print("Old response from ESPER service. Exiting")
                sys.exit(1)

        else:
            try:
                err = r.json()
                print('\tStatus: ' + str(err['error']['status']) + '\n\tCode: ' + str(err['error']['code']) + '\n\tMeaning: ' + err['error']['meaning'] + '\n\tMessage: ' + err['error']['message'] + '\n')
                sys.exit(1)
            except:
                print("Non-JSON response from ESPER service. Exiting")
                print(r.content)             
                sys.exit(1)

        try: 
            if(args.command == 'experiment'):
                interactive = InteractiveMode()
                interactive.url = args.url
                interactive.prog = prog
                interactive.user = args.user
                interactive.password = args.password
                
                try:
                    querystring = {'mid': 'system', 'vid': 'device', 'dataOnly':'y'}
                    r = request_get_with_auth(args.url + '/read_var', querystring, args.user, args.password)
                    if(r.status_code == 200): 
                        interactive.host = r.json()
                    else:
                        err = r.json()
                        print('\tStatus: ' + str(err['error']['status']) + '\n\tCode: ' + str(err['error']['code']) + '\n\tMeaning: ' + err['error']['meaning'] + '\n\tMessage: ' + err['error']['message'] + '\n')
                        sys.exit(1)

                    querystring = {'mid': args.mid }
                    r = request_get_with_auth(args.url + '/read_module', querystring, args.user, args.password)

                    if(r.status_code == 200): 
                        interactive.module = r.json()['key']
                    else:
                        querystring = {'mid': 'system' }
                        r = request_get_with_auth(args.url + '/read_module', querystring, args.user, args.password)

                        if(r.status_code == 200): 
                            interactive.module = r.json()['key']
                        else:
                            err = r.json()
                            print('\tStatus: ' + str(err['error']['status']) + '\n\tCode: ' + str(err['error']['code']) + '\n\tMeaning: ' + err['error']['meaning'] + '\n\tMessage: ' + err['error']['message'] + '\n')
                            sys.exit(1)

                    interactive.intro = "Connected to " + interactive.host +  "@" + args.url + "\nType 'help' for a list of available commands"
                    interactive.prompt = '['+args.url+':/'+interactive.module +']> '
                    interactive.get_modules()
                    interactive.get_module_variables()
                    interactive.cmdloop()
                    sys.exit(0)
                
                except requests.exceptions.RequestException as e:
                    print('Unable to connected to ESPER service at ' + args.url)
                    print("Error: {}".format(e))
                    sys.exit(1)
        
            else:
                # No options selected, this should never be reached
                sys.exit(0) 
        
        except requests.exceptions.Timeout:
            # Maybe set up for a retry, or continue in a retry loop
            print('Timed out attempting to communicate with ' + args.url + "\n")
            sys.exit(1)

        except requests.exceptions.TooManyRedirects:
            # Tell the user their URL was bad and try a different one
            print('Timed out attempting to communicate with ' + args.url + "\n")
            sys.exit(1)

        except requests.exceptions.RequestException as e:
            # catastrophic error. bail.
            print('Uncaught error: ')
            print(e)
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nExiting " + prog)
        sys.exit(0)

if __name__ == "__main__":
    main()
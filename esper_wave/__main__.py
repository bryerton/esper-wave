# Simple ESPER command line tool
# Allows reading and writing of ESPER variables

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

def pretty_time_delta(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return '%dd %dh %dm %ds' % (days, hours, minutes, seconds)
    elif hours > 0:
        return '0d %dh %dm %ds' % (hours, minutes, seconds)
    elif minutes > 0:
        return '0d 0h %dm %ds' % (minutes, seconds)
    else:
        return '0d 0h 0m %ds' % (seconds)

class InteractiveMode(cmd.Cmd):
    """Interactive Mode"""

    def print_esper_error(self,err_json):
        try:
            print("Error %d: %s (%d)" % (err_json['error']['status'], err_json['error']['meaning'], err_json['error']['code']))
        except:
            print("Unknown Error Format")

    def get_module_variables(self):
        querystring = {'mid': self.module, 'includeVars': 'y' }
        r = request_get_with_auth(self.url + '/read_module', querystring, self.user, self.password)
        self.var_completion = []        
        if(r.status_code == 200):
            resp = r.json()
            for i in range(0,len(resp['var'])):
                self.var_completion.append(resp['var'][i]['key'])

    def get_modules(self):
        querystring = {'includeMods': 'y' }
        r = request_get_with_auth(self.url + '/read_node', querystring, self.user, self.password)
        self.mod_completion = []        
        if(r.status_code == 200):
            resp = r.json()
            for i in range(0,len(resp['module'])):
                self.mod_completion.append(resp['module'][i]['key'])

    def do_version(self, line):
        """Purpose: Prints current version of esper-tool\nUsage: version\n"""
        print(self.prog + ' ' + __version__)

    def do_uptime(self, line):
        """Purpose: Get uptime of current ESPER service\nUsage: uptime\n"""
        querystring = {'mid': 'system', 'vid': 'uptime', 'dataOnly':'y'}
        try:
            r = request_get_with_auth(self.url + '/read_var', querystring, self.user, self.password)
            if(r.status_code == 200): 
                print('Uptime: ' + pretty_time_delta(r.json()[0]))
            else:
               self.print_esper_error(r.json())
        
        except requests.exceptions.RequestException as e:
            print("Error: {}".format(e))

    def do_list(self, line):
        """Purpose: Lists available modules\nUsage: list\n"""
        try:
            querystring = {'includeMods': 'y'}
            r = request_get_with_auth(self.url + '/read_node', querystring, self.user, self.password)

            if(r.status_code == 200): 
                resp = r.json()
                print('%-5s %-16s %-32s' % ('mid', 'key', 'name'))
                print('%-5s %-16s %-32s' % ('---', '---', '----'))
                for i in range(0,len(resp['module'])):
                    print('%-5s %-16s %-32s' % (str(resp['module'][i]['id']), resp['module'][i]['key'], resp['module'][i]['name'] ))
            else:
                self.print_esper_error(r.json())

        except requests.exceptions.RequestException as e:
            print("Error: {}".format(e))

    def complete_cd(self, text, line, begidx, endidx):
        if text:
            return [
                module for module in self.mod_completion
                if module.startswith(text)
            ]
        else:
            return self.mod_completion

    def do_cd(self,line):
        """Purpose: Sets current module\nUsage: cd <mid>\n"""
        self.do_module(line)

    def complete_module(self, text, line, begidx, endidx):
        if text:
            return [
                module for module in self.mod_completion
                if module.startswith(text)
            ]
        else:
            return self.mod_completion

    def do_module(self, line):
        """Purpose: Sets current module\nUsage: module <mid>\n"""
        if(line):
            line_args = str.split(line)
            querystring = {'mid': line_args[0].lower() }
            r = request_get_with_auth(self.url + '/read_module', querystring, self.user, self.password)

            if(r.status_code == 200):
                resp = r.json()
                self.module = resp['key']
                self.get_module_variables()
                self.prompt = '[' + self.url + ':/' + self.module + ']> '
            else:
                self.print_esper_error(r.json())
                
        else:
            print("Please select a module")
            self.do_list("")

    def complete_write(self, text, line, begidx, endidx):
        if text:
            return [
                variable for variable in self.var_completion
                if variable.startswith(text)
            ]
        else:
            return self.var_completion

    def do_write(self, line):
        """Purpose: Write module variable\nUsage: write <vid> <data> [offset]\n"""
        try:
            line_args = str.split(line,' ')
            if(line):
                vid = line_args[0].lower() 
            else:
                print("Please specify variable to write to\nwrite <vid> <data>")
                return

            if(len(line_args) > 1):
                payload = line_args[1]
            else:
                print("Please specify the data to write\nwrite %s <data>" % vid)
                return

            if(len(line_args) > 2):
                offset = line_args[2]
            else:
                offset = 0

            querystring = {'mid': self.module, 'vid': vid, 'offset': offset}
            r = request_post_with_auth(self.url + '/write_var', querystring, payload, self.user, self.password)

            if(r.status_code != 200): 
                self.print_esper_error(r.json())
        except:
            print("Invalid Arguments")

    def complete_ls(self, text, line, begidx, endidx):
        if text:
            return [
                variable for variable in self.var_completion
                if variable.startswith(text)
            ]
        else:
            return self.var_completion

    def do_ls(self, line):
        """Purpose: Read module variable(s)\nUsage: ls <vid> [offset] [length] [repeat]\n"""
        self.do_read(line)

    def complete_read(self, text, line, begidx, endidx):
        if text:
            return [
                variable for variable in self.var_completion
                if variable.startswith(text)
            ]
        else:
            return self.var_completion

    def do_read(self, line):
        """Purpose: Read module variable(s)\nUsage: read <vid> [offset] [length] [repeat]\n"""
        try:
            if(line): 
                line_args = str.split(line,' ')
        
                vid = line_args[0].lower() 
                offset = 0
                length = 0
                repeat = False

                if(len(line_args) > 1):
                    if((line_args[1].lower() == 'r') or (line_args[1].lower()  == 'repeat')):
                        repeat = True
                    else:
                        offset = line_args[1]
                
                if(len(line_args) > 2):
                    if((line_args[2].lower()  == 'r') or (line_args[2].lower()  == 'repeat')):
                        repeat = True
                    else:
                        length = line_args[2]

                if(len(line_args) > 3):
                    if((line_args[3].lower()  == 'r') or (line_args[3].lower()  == 'repeat')):
                        repeat = True
                    else:
                        repeat = False
                    
                try:
                    done = False
                    while done != True:
                        querystring = {'mid': self.module, 'vid': vid, 'offset': offset, 'len': length, 'includeData': 'y'}
                        r = request_get_with_auth(self.url + '/read_var', querystring, self.user, self.password)
                        if(r.status_code == 200): 
                            resp = r.json()
                            print(str(resp['d']))
                        else:
                            self.print_esper_error(r.json())

                        if(not repeat):
                            done = True
                        else:
                            time.sleep(1)

                except KeyboardInterrupt:
                    done = True
            else:
                querystring = {'mid': self.module, 'includeVars': 'y', 'includeData': 'y'}
                r = request_get_with_auth(self.url + '/read_module', querystring, self.user, self.password)
                if(r.status_code == 200): 
                    resp = r.json()
                    print('%-5s %-16s %-16s %-8s %-8s %-32s' % ('vid', 'key', 'type', 'options', 'status', 'data'))
                    print('%-5s %-16s %-16s %-8s %-8s %-32s' % ('---', '---', '----', '-------', '------', '----'))
                    for i in range(0,len(resp['var'])):
                        if(not resp['var'][i]['d']): 
                            print('%-5s %-16s %-16s %-8s %-8s %-32s' % (str(resp['var'][i]['id']), resp['var'][i]['key'], Esper().getTypeString(resp['var'][i]['type']), Esper().getOptionString(resp['var'][i]['opt']), Esper().getOptionString(resp['var'][i]['stat']), '%s[%d]' % ('Null',resp['var'][i]['len'])))
                        elif((len(resp['var'][i]['d']) > 1) and (resp['var'][i]['type'] != 11)):
                            print('%-5s %-16s %-16s %-8s %-8s %-32s' % (str(resp['var'][i]['id']), resp['var'][i]['key'], Esper().getTypeString(resp['var'][i]['type']), Esper().getOptionString(resp['var'][i]['opt']), Esper().getOptionString(resp['var'][i]['stat']), '%s[%d]' % ('Array',resp['var'][i]['len'])))
                        elif(resp['var'][i]['type'] == 11):
                            print('%-5s %-16s %-16s %-8s %-8s %-32s' % (str(resp['var'][i]['id']), resp['var'][i]['key'], Esper().getTypeString(resp['var'][i]['type']), Esper().getOptionString(resp['var'][i]['opt']), Esper().getOptionString(resp['var'][i]['stat']), '"%s"' % str(resp['var'][i]['d'])))
                        else:
                            print('%-5s %-16s %-16s %-8s %-8s %-32s' % (str(resp['var'][i]['id']), resp['var'][i]['key'], Esper().getTypeString(resp['var'][i]['type']), Esper().getOptionString(resp['var'][i]['opt']), Esper().getOptionString(resp['var'][i]['stat']), '%s' % str(resp['var'][i]['d'])))
                else:
                    self.print_esper_error(r.json())

        except requests.exceptions.RequestException as e:
            print("Error: {}".format(e))        

    def complete_upload(self, text, line, begidx, endidx):
        if text:
            return [
                variable for variable in self.var_completion
                if variable.startswith(text)
            ]
        else:
            return self.var_completion

    def do_upload(self,line):
        """Purpose: Upload a binary file to variable\nUsage: upload <vid> <file>"""
        try:
            if(line): 
                line_args = str.split(line,' ')

                if(len(line_args) < 1):
                    print("Missing [vid] and [file]")
                    return

                if(len(line_args) < 2):
                    print("Missing [file]")
                    return

                vid = line_args[0].lower() 
                
                try:
                    upload_file = open(line_args[1], 'rb')
                except:
                    print("Error opening file for reading")
                    return
            else:
                print("Missing arugments")
                return

            querystring = {'mid': self.module, 'vid': vid }
            r = requests.get(self.url + '/read_var', params=querystring)
            if(r.status_code == 200):
                # Var found, lets see what we got!
                vinfo = r.json()
                # Always use the 'max_req_size', otherwise certain flash devices like EPCQs may have issue with multiple chunks to the same block..
                chunk_size = vinfo['max_req_size']
                # Get the size of the file and then return to the start
                upload_file.seek(0, os.SEEK_END)
                file_size = upload_file.tell()
                upload_file.seek(0, os.SEEK_SET)
                
                #print('Chunk size: ' + str(chunk_size))
                #print('File size: ' + str(file_size))
                print("Uploading [%-50s]" % (" "),end="")
                    
                # Get the first chunk of the file
                payload = upload_file.read(chunk_size)
                chunk_size = len(payload)
                file_offset = 0
                retry_count = 0
                max_retries = 3
                while(chunk_size > 0):
                    sys.stdout.flush()
                    # transmit payload using binary methods
                    querystring = {'mid': self.module, 'vid': vid, 'offset': file_offset, 'len': chunk_size, 'binary': 'y'}
                    r = request_post_with_auth(self.url + '/write_var', querystring, payload, self.user, self.password)

                    # Did we transfer successfully?
                    if(r.status_code == 200):
                        # update offset to write to, based on last chunk_size written
                        file_offset += chunk_size
                        # Grab the next binary chunk
                        payload = upload_file.read(chunk_size)
                        # update chunk_size to match what was actually grabbed (may be less if chunk_size was less than remaining length)
                        chunk_size = len(payload)
                                                
                        strCompleteness = '#' * int(file_offset / float(file_size) * 50)
                        print("\rUploading [%-50s]" % (strCompleteness),end="")
                    # Retry up to X times
                    elif(retry_count < max_retries):
                        retry_count += 1
                        print("\nUpload attempt failed, retrying...")
                    else:
                        print("Failed to upload " + os.path.basename(upload_file.name))

                print("\nDone uploading " + os.path.basename(upload_file.name))

            else:
                self.print_esper_error(r.json())

        except:
            print("Unknown error uploading file")

    def complete_download(self, text, line, begidx, endidx):
        if text:
            return [
                variable for variable in self.var_completion
                if variable.startswith(text)
            ]
        else:
            return self.var_completion

    def do_download(self,line):
        """Purpose: Download a variable to a binary file\nUsage: download <vid> <file>"""
        # Keys should always be lower case
        try:
            if(line): 
                line_args = str.split(line,' ')

                if(len(line_args) < 1):
                    print("Missing <vid> and <file>")
                    return

                if(len(line_args) < 2):
                    print("Missing <file>")
                    return

                vid = line_args[0].lower() 
                
                try:
                    download_file = open(line_args[1], 'wb')
                except:
                    print("Error opening file for writing")
                    return
            else:
                print("Missing arugments")
                return

            querystring = {'mid': self.module, 'vid': vid }
            r = request_get_with_auth(self.url + '/read_var', querystring, self.user, self.password)

            if(r.status_code == 200):
                # Var found, lets see what we got!
                vinfo = r.json()
                # Always use the 'max_req_size', otherwise certain flash devices like EPCQs may have issue with multiple chunks to the same block..
                chunk_size = vinfo['max_req_size']
                # Get the size of the file and then return to the start
                file_size = vinfo['len']
                
                #print('Chunk size: ' + str(chunk_size))
                #print('File size: ' + str(file_size))
                print("Downloading [%-50s]" % (" "),end="")
                    
                # Get the first chunk of the file
                file_offset = 0
                retry_count = 0
                max_retries = 3
                while(file_offset < file_size):
                    sys.stdout.flush()

                    if(chunk_size > (file_size - file_offset)):
                        chunk_size = file_size - file_offset

                    # transmit payload using binary methods
                    querystring = {'mid': self.module, 'vid': vid, 'offset': file_offset, 'len': chunk_size, 'binary': 'y', 'dataOnly': 'y'}
                    r = request_get_with_auth(self.url + '/read_var', querystring, self.user, self.password)

                    # Did we transfer successfully?
                    if(r.status_code == 200):
                        # update offset to write to, based on last chunk_size written
                        file_offset += len(r.content)

                        # Grab the next binary chunk
                        download_file.write(r.content)
                                                
                        strCompleteness = '#' * int(file_offset / float(file_size) * 50)
                        print("\rDownloading [%-50s]" % (strCompleteness),end="")

                    # Retry up to X times
                    elif(retry_count < max_retries):
                        retry_count += 1
                        print("\nDownload attempt failed, retrying...")
                    else:
                        print("Failed to download " + os.path.basename(download_file.name))

                print("\nDone download to " + os.path.basename(download_file.name))

            else:
                self.print_esper_error(r.json())
        except:
            print("Unknown error downloading file")

    def do_exit(self, line):
        """Purpose: Quit esper-tool\nUsage: exit\n"""
        return True

    def do_quit(self, line):
        """Purpose: Quit esper-tool\nUsage: quit\n"""
        return True

def main():
    try:
        prog='esper-tool'    

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

        # Interactive Mode
        parser_interactive = subparsers.add_parser('interactive', help='<url>')
        parser_interactive.add_argument("url", help="Node URL. ie: 'http://<hostname>:<port>'")
        parser_interactive.add_argument("mid", nargs='?', default='0', help="Module Id or Key")
        parser_interactive.add_argument("-u","--user", default=False, help="User for Auth")
        parser_interactive.add_argument("-p","--password", default=False, help="Password for Auth")

        # Write arguments
        parser_write = subparsers.add_parser('write', help='[-o <offset>] [-d <json value/array>]  <url> <mid> <vid>')
        parser_write.add_argument('-d','--data', help="JSON data to write")
        parser_write.add_argument('-f','--file', type=argparse.FileType('r'), help="JSON file to write from")    
        parser_write.add_argument('-o','--offset', default='0',dest='offset', help='offset to write to')
        parser_write.add_argument("-u","--user", default=False, help="User for Auth")
        parser_write.add_argument("-p","--password", default=False, help="Password for Auth")
        parser_write.add_argument("url", help="Node URL. ie: 'http://<hostname>:<port>'")
        parser_write.add_argument("mid", help="Module Id or Key")
        parser_write.add_argument("vid", help="Variable Id or Key")
        
        # Read arguments
        parser_read = subparsers.add_parser('read', help='[-o <offset>] [-l <length>] <url> <mid> <vid>')
        parser_read.add_argument('-o','--offset', default='0', help='element offset to read from')
        parser_read.add_argument('-l','--len', default='0', help='elements to read')
        parser_read.add_argument("-u","--user", default=False, help="User for Auth")
        parser_read.add_argument("-p","--password", default=False, help="Password for Auth")
        parser_read.add_argument("url", help="Node URL. ie: 'http://<hostname>:<port>'")
        parser_read.add_argument("mid", help="Module Id or Key")
        parser_read.add_argument("vid", help="Variable Id or Key")

        # Upload arguments
        parser_upload = subparsers.add_parser('upload', help='[-f <file>] <url> <mid> <vid>')
        parser_upload.add_argument('-f','--file', required='true', type=argparse.FileType('rb'), help="binary file to upload")    
        parser_upload.add_argument('-r','--retry', default='3', help='number of retries to attempt')
        parser_upload.add_argument("-u","--user", default=False, help="User for Auth")
        parser_upload.add_argument("-p","--password", default=False, help="Password for Auth")
        parser_upload.add_argument("url", help="Node URL. ie: 'http://<hostname>:<port>'")
        parser_upload.add_argument("mid", help="Module Id or Key")
        parser_upload.add_argument("vid", help="Variable Id or Key")

        # Download arguments
        parser_download = subparsers.add_parser('download', help='[-f <file>] <url> <mid> <vid>')
        parser_download.add_argument('-f','--file', required='true', type=argparse.FileType('wb'), help="binary file to download to")    
        parser_download.add_argument('-r','--retry', default='3', help='number of retries to attempt')
        parser_download.add_argument("-u","--user", default=False, help="User for Auth")
        parser_download.add_argument("-p","--password", default=False, help="Password for Auth")
        parser_download.add_argument("url", help="Node URL. ie: 'http://<hostname>:<port>'")
        parser_download.add_argument("mid", help="Module Id or Key")
        parser_download.add_argument("vid", help="Variable Id or Key")

        # Put the arguments passed into args
        parser.set_default_subparser('interactive')
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
            if(args.command == 'interactive'):
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

            # Handle write
            elif(args.command == 'write'): 
                # Keys should always be lower case
                args.mid = args.mid.lower()
                args.vid = args.vid.lower()
                querystring = {'mid': args.mid, 'vid': args.vid, 'offset': args.offset}

                # if -d is set, we will write what is passed on the command line
                # ESPER is expecting either a JSON array [], a JSON string " ", or a single JSON primitive
                if args.data is not None:
                    payload = args.data

                # if -f is set, we will write in file that contains JSON in the above format
                elif args.file is not None:
                    with args.file as upload_file:
                        payload = upload_file.read()
                else:
                    # No data specified to send on write, just bail out. Argparser should ensure this branch never gets reached
                    print("No data specified to send, exitting\n")
                    # It didn't fail, so return 0 
                    sys.exit(0) 
                
                # Send POST request
                r = request_post_with_auth(args.url + '/read_module', querystring, payload, args.user, args.password)
                if(r.status_code == 200):
                    if(args.verbose): 
                        err = r.json()
                        print('Successfully wrote data')
                        print('\tModule: ' + str(err['mid']) + '\n\tVariable: ' + str(err['id']) + '\n\tTimestamp: ' + str(err['ts']) + '\n\tWrite count: ' + str(err['wc']) + '\n\tStatus: ' + str(err['stat']))
                    sys.exit   (0)
                else:
                    if(args.verbose): 
                        err = r.json()
                        print('\tStatus: ' + str(err['error']['status']) + '\n\tCode: ' + str(err['error']['code']) + '\n\tMeaning: ' + err['error']['meaning'] + '\n\tMessage: ' + err['error']['message'] + '\n')
                    sys.exit(1)
            # Handle read
            elif(args.command == 'read'): 
                # Keys should always be lower case
                args.mid = args.mid.lower()
                args.vid = args.vid.lower()
                querystring = {'mid': args.mid, 'vid': args.vid, 'offset': args.offset, 'len': args.len, 'dataOnly':'y'}
                # Send GET request
                r = request_get_with_auth(args.url + '/read_var', querystring, args.user, args.password)

                if(r.status_code == 200): 
                    print(r.content)
                    sys.exit(0)
                else:
                    if(args.verbose): 
                        err = r.json()
                        print('\tStatus: ' + str(err['error']['status']) + '\n\tCode: ' + str(err['error']['code']) + '\n\tMeaning: ' + err['error']['meaning'] + '\n\tMessage: ' + err['error']['message'] + '\n')
                    sys.exit(1)
            # Handle file uploading
            elif(args.command == 'upload'):
                # Keys should always be lower case
                args.mid = args.mid.lower()
                args.vid = args.vid.lower()
                # Get var info first, need to know max chunk size of file to send
                with args.file as upload_file:
                    querystring = {'mid': args.mid, 'vid': args.vid }
                    r = request_get_with_auth(args.url + '/read_var', querystring, args.user, args.password)
                    if(r.status_code == 200):
                        # Var found, lets see what we got!
                        vinfo = r.json()
                        # Always use the 'max_req_size', otherwise certain flash devices like EPCQs may have issue with multiple chunks to the same block..
                        chunk_size = vinfo['max_req_size']
                        # Get the size of the file and then return to the start
                        upload_file.seek(0, os.SEEK_END)
                        file_size = upload_file.tell()
                        upload_file.seek(0, os.SEEK_SET)
                        
                        if(args.verbose): 
                            #print('Chunk size: ' + str(chunk_size))
                            #print('File size: ' + str(file_size))
                            print("Uploading [%-50s]" % (" "),end="")
                            
                        # Get the first chunk of the file
                        payload = upload_file.read(chunk_size)
                        chunk_size = len(payload)
                        file_offset = 0
                        retry_count = 0
                        max_retries = args.retry
                        while(chunk_size > 0):
                            sys.stdout.flush()
                            # transmit payload using binary methods
                            querystring = {'mid': args.mid, 'vid': args.vid, 'offset': file_offset, 'len': chunk_size, 'binary': 'y'}
                            r = request_post_with_auth(args.url + '/write_var', querystring, payload, args.user, args.password)

                            # Did we transfer successfully?
                            if(r.status_code == 200):
                                # update offset to write to, based on last chunk_size written
                                file_offset += chunk_size
                                # Grab the next binary chunk
                                payload = upload_file.read(chunk_size)
                                # update chunk_size to match what was actually grabbed (may be less if chunk_size was less than remaining length)
                                chunk_size = len(payload)
                                                        
                                if(args.verbose):
                                    strCompleteness = '#' * int(file_offset / float(file_size) * 50)
                                    print("\rUploading [%-50s]" % (strCompleteness),end="")
                            # Retry up to X times
                            elif(retry_count < max_retries):
                                retry_count += 1
                                print("\nUpload attempt failed, retrying...")
                            else:
                                print("Failed to upload " + os.path.basename(upload_file.name))
                                sys.exit(1)

                        if(args.verbose):
                            print("\nDone uploading " + os.path.basename(upload_file.name))

                        # All done uploading file, exit
                        sys.exit(0)

                    else:
                        if(args.verbose):
                            err = r.json()
                            print('\tStatus: ' + str(err['error']['status']) + '\n\tCode: ' + str(err['error']['code']) + '\n\tMeaning: ' + err['error']['meaning'] + '\n\tMessage: ' + err['error']['message'] + '\n')
                        sys.exit(1)
                
            elif(args.command == 'download'):
                # Keys should always be lower case
                args.mid = args.mid.lower()
                args.vid = args.vid.lower()
                # Get var info first, need to know max chunk size of file to send
                with args.file as download_file:

                    querystring = {'mid': args.mid, 'vid': args.vid }
                    r = request_get_with_auth(args.url + '/read_var', querystring, args.user, args.password)

                    if(r.status_code == 200):
                        # Var found, lets see what we got!
                        vinfo = r.json()
                        # Always use the 'max_req_size', otherwise certain flash devices like EPCQs may have issue with multiple chunks to the same block..
                        chunk_size = vinfo['max_req_size']
                        # Get the size of the file and then return to the start
                        file_size = vinfo['len']
                        
                        if(args.verbose): 
                            #print('Chunk size: ' + str(chunk_size))
                            #print('File size: ' + str(file_size))
                            print("Downloading [%-50s]" % (" "),end="")
                            
                        # Get the first chunk of the file
                        file_offset = 0
                        retry_count = 0
                        max_retries = args.retry
                        while(file_offset < file_size):
                            sys.stdout.flush()

                            if(chunk_size > (file_size - file_offset)):
                                chunk_size = file_size - file_offset

                            # transmit payload using binary methods
                            querystring = {'mid': args.mid, 'vid': args.vid, 'offset': file_offset, 'len': chunk_size, 'binary': 'y', 'dataOnly': 'y'}
                            r = request_get_with_auth(args.url + '/read_var', querystring, args.user, args.password)

                            # Did we transfer successfully?
                            if(r.status_code == 200):
                                # update offset to write to, based on last chunk_size written
                                file_offset += len(r.content)

                                # Grab the next binary chunk
                                download_file.write(r.content)
                                                        
                                if(args.verbose):
                                    strCompleteness = '#' * int(file_offset / float(file_size) * 50)
                                    print("\rDownloading [%-50s]" % (strCompleteness),end="")

                            # Retry up to X times
                            elif(retry_count < max_retries):
                                retry_count += 1
                                print("\nDownload attempt failed, retrying...")
                            else:
                                print("Failed to download " + os.path.basename(download_file.name))
                                sys.exit(1)

                        if(args.verbose):
                            print("\nDone download to " + os.path.basename(download_file.name))

                        # All done uploading file, exit
                        sys.exit(0)

                    else:
                        if(args.verbose):
                            err = r.json()
                            print('\tStatus: ' + str(err['error']['status']) + '\n\tCode: ' + str(err['error']['code']) + '\n\tMeaning: ' + err['error']['meaning'] + '\n\tMessage: ' + err['error']['message'] + '\n')
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
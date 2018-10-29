#!/home/stephan/.virtualenvs/nntp/bin/python

''' GINZICUT: Test server for ginzibix
    (c) 2018 Stephan Untergrabner <stephan@untergrabner.at>

    This is light-weight & stripped down pyhton3 re-implementation of

                  https://github.com/jpm/papercut

    see copyright notice for papercut below.


*** Copyright (c) 2002 Joao Prado Maia <jpm@impleo.net>

    Permission is hereby granted, free of charge, to any person obtaining a copy of
    this software and associated documentation files (the "Software"), to deal in
    the Software without restriction, including without limitation the rights to
    use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
    of the Software, and to permit persons to whom the Software is furnished to do
    so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
    FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
    COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
    IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
    CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE. ***
'''

import settings_secret as settings
import socketserver
import dill
import signal
import sys
import time
import ssl
import nntplib
from pymemcache.client.base import Client as pymemClient

__version__ = "0.1"
TIMEOUT = 180
CRLF = "\r\n"
DB_DIR = "./db/"
forward_nntp = []
bodycount = 0
use_memcached = True

ERR_NOTCAPABLE = '500 command not recognized'
ERR_CMDSYNTAXERROR = '501 command syntax error (or un-implemented option)'
ERR_NOSUCHGROUP = '411 no such news group'
ERR_NOGROUPSELECTED = '412 no newsgroup has been selected'
ERR_NOARTICLESELECTED = '420 no current article has been selected'
ERR_NOARTICLERETURNED = '420 No article(s) selected'
ERR_NOPREVIOUSARTICLE = '422 no previous article in this group'
ERR_NONEXTARTICLE = '421 no next article in this group'
ERR_NOSUCHARTICLENUM = '423 no such article in this group'
ERR_NOSUCHARTICLE = '430 no such article'
ERR_NOIHAVEHERE = '435 article not wanted - do not send it'
ERR_NOSTREAM = '500 Command not understood'
ERR_TIMEOUT = '503 Timeout after %s seconds, closing connection.'
ERR_NOTPERFORMED = '503 program error, function not performed'
ERR_POSTINGFAILED = '441 Posting failed'
ERR_AUTH_NO_PERMISSION = '502 No permission'
ERR_NODESCAVAILABLE = '481 Groups and descriptions unavailable'
STATUS_SLAVE = '202 slave status noted'
STATUS_POSTMODE = '200 Hello, you can post'
STATUS_NOPOSTMODE = '201 Hello, you can\'t post'
STATUS_HELPMSG = '100 help text follows'
STATUS_GROUPSELECTED = '211 %s %s %s %s group selected'
STATUS_LIST = '215 list of newsgroups follows'
STATUS_STAT = '223 %s %s article retrieved - request text separately'
STATUS_ARTICLE = '220 %s %s All of the article follows'
STATUS_NEWGROUPS = '231 list of new newsgroups follows'
STATUS_NEWNEWS = '230 list of new articles by message-id follows'
STATUS_HEAD = '221 %s %s article retrieved - head follows'
STATUS_BODY = '222 %s %s article retrieved - body follows'
STATUS_READYNOPOST = '201 %s Ginzicut %s server ready (no posting allowed)'
STATUS_READYOKPOST = '200 %s Ginzicut %s server ready (posting allowed)'
STATUS_CLOSING = '205 closing connection - goodbye!'
STATUS_XOVER = '224 Overview information follows'
STATUS_XPAT = '221 Header follows'
STATUS_LISTGROUP = '211 %s %s %s %s Article numbers follow (multiline)'
STATUS_XGTITLE = '282 list of groups and descriptions follows'
STATUS_LISTNEWSGROUPS = '215 information follows'
STATUS_XHDR = '221 Header follows'
STATUS_DATE = '111 %s'
STATUS_OVERVIEWFMT = '215 information follows'
STATUS_EXTENSIONS = '215 Extensions supported by server.'
STATUS_SENDARTICLE = '340 Send article to be posted'
STATUS_READONLYSERVER = '440 Posting not allowed'
STATUS_POSTSUCCESSFULL = '240 Article received ok'
STATUS_AUTH_REQUIRED = '480 Authentication required'
STATUS_AUTH_ACCEPTED = '281 Authentication accepted'
STATUS_AUTH_CONTINUE = '381 More authentication information required'
STATUS_SERVER_VERSION = '200 Ginzicut %s' % (__version__)
STATUS_CAPABILITIES = "101 Capabilities"

headers = ("Date", "From", "Message-ID", "Newsgroups", "Path", "Subject", "Bytes"
           "Approved", "Archive", "Control", "Distribution", "Expires", "Followup-To",
           "Injection-Date", "Injection-Info", "Organization", "References",
           "Summary", "Supersedes", "User-Agent", "Xref", "Lines", "Sender", "Content-Type")


def sighandler(signum, frame):
    global server
    global forward_nntp
    for fo in forward_nntp:
        if fo:
            fo.quit()
    server.socket.close()
    time.sleep(1)
    sys.exit(0)


class NNTPRequestHandler(socketserver.StreamRequestHandler):

    def __init__(self, request, client_address, server):
        self.commands = ("CAPABILITIES", "ARTICLE", "BODY", "QUIT", "POST", "STAT", "HEAD")
        self.terminated = False
        self.nntpobj = None
        self.timeout = TIMEOUT
        socketserver.StreamRequestHandler.__init__(self, request, client_address, server)

    def handle_timeout(self, signum, frame):
        self.terminated = True

    def handle(self):
        global use_memcached

        if use_memcached:
            try:
                self.pymemclient = pymemClient(('localhost', 11211))
            except Exception as e:
                print("memcached connection error: " + str(e))
                use_memcached = False

        if settings.server_type == 'read-only':
            self.send_response(STATUS_READYNOPOST % (settings.nntp_hostname, __version__))
        else:
            self.send_response(STATUS_READYOKPOST % (settings.nntp_hostname, __version__))

        self.sending_article = False
        self.article_lines = []

        while not self.terminated:

            try:
                self.inputline = self.rfile.readline()
            except IOError:
                continue

            if not self.sending_article:
                cmd = self.inputline.decode().strip()
                self.params = cmd.split(" ")
                cmd0 = self.params[0].upper()
            else:
                cmd = self.inputline.decode()
                cmd0 = "posting ...", cmd

            if cmd0:
                if cmd0 == "POST":
                    self.sending_article = True
                    self.send_response(STATUS_SENDARTICLE)
                else:
                    if self.sending_article:
                        if cmd == ".\r\n":
                            self.sending_article = False
                            self.article_lines = []
                            self.do_POST()
                            continue
                        self.article_lines.append(cmd.rstrip())
                    else:
                        if cmd0 in self.commands:
                            eval("self.do_" + cmd0 + "()")
                            # getattr(self, "do_" + cmd0)()
                        else:
                            self.send_response(ERR_NOTCAPABLE)

    def open_connection(self):
        global forward_nntp
        if not settings.do_forwarding:
            return None
        sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS)
        if settings.forward_server_ssl:
            nntp_obj = nntplib.NNTP_SSL(settings.forward_server_url, user=settings.forward_server_user,
                                        password=settings.forward_server_pass, ssl_context=sslcontext,
                                        port=settings.forward_server_port, readermode=True, timeout=5)
        else:
            nntp_obj = nntplib.NNTP(settings.forward_server_url, user=settings.forward_server_user,
                                    password=settings.forward_server_pass, ssl_context=sslcontext,
                                    port=settings.forward_server_port, readermode=True, timeout=5)
        forward_nntp.append(nntp_obj)
        return nntp_obj

    def close_connection(self):
        global forward_nntp
        if self.nntpobj:
            try:
                forward_nntp.remove(self.nntpobj)
            except Exception as e:
                print(str(e))
            self.nntpobj.quit()

    def list_to_crlf_str(self, list0, decoding=False):
        if decoding:
            strres = ""
            for l in list0:
                if decoding:
                    strres += l.decode() + CRLF
            return strres
        else:
            return CRLF.join(list0)

    def retry_connect(self):
        global forward_nntp
        try:
            forward_nntp.remove(self.nntpobj)
            self.nntpobj.quit()
        except Exception as e:
            print(str(e))
        idx = 0
        while idx < 5:
            self.nntpobj = self.open_connection()
            if self.nntpobj:
                return True
            time.sleep(5)
            idx += 1
        return False

    def forward_get_article(self, id):
        idx = 0
        if not self.nntpobj:
            connected = self.retry_connect()
            if not connected:
                return None, None
        while idx < 5:
            art_head = None
            art_body = None
            try:
                # head
                resp, info = self.nntpobj.head(id)
                if resp[:3] != "221":
                    break
                else:
                    info0 = [inf for inf in info.lines]
                    art_head = info0
                # body
                resp, info = self.nntpobj.body(id)
                if resp[:3] != "222":
                    break
                else:
                    info0 = [inf for inf in info.lines]
                    art_body = info0
                break
            except nntplib.NNTPTemporaryError:
                break
            except KeyboardInterrupt:
                break
            except Exception as e:
                pass
            retry_success = self.retry_connect()
            if not retry_success:
                break
            idx += 1
        return art_head, art_body

    def backend_stat(self, id):
        id0 = self.get_correct_id(id)
        if use_memcached:
            # first search in memcached
            mc_key_head = id0 + ":head"
            try:
                head0 = dill.loads(self.pymemclient.get(mc_key_head))
                return 1
            except Exception as e:
                return None
        # just look in db directory
        try:
            f = open(DB_DIR + id0, "r")
        except FileNotFoundError:
            return None
        f.close()
        return 1

    def get_correct_id(self, id):
        id0 = id.rstrip().lstrip()
        if id0[0] != "<":
            id0 = "<" + id0
        if id[-1] != ">":
            id0 += ">"
        return id0

    def backend_get_article(self, id, onlybody=False, onlyhead=False):
        id0 = self.get_correct_id(id)
        if use_memcached:
            # first search in memcached
            mc_key_head = id0 + ":head"
            mc_key_body = id0 + ":body"
            try:
                if onlybody:
                    body0 = dill.loads(self.pymemclient.get(mc_key_body))
                    conv_body = CRLF.join(body0)
                    return id0, None, conv_body
                elif onlyhead:
                    head0 = dill.loads(self.pymemclient.get(mc_key_head))
                    conv_head = CRLF.join(head0)
                    return id0, conv_head, None
                else:
                    head0 = dill.loads(self.pymemclient.get(mc_key_head))
                    body0 = dill.loads(self.pymemclient.get(mc_key_body))
                    conv_head = CRLF.join(head0)
                    conv_body = CRLF.join(body0)
                    # print("found in memcached")
                    return id0, conv_head, conv_body
            except Exception as e:
                # print(str(e), "not found in memcached")
                pass
        # then in in db directory:
        art_found_in_db = True
        try:
            f = open(DB_DIR + id0, "r")
        except FileNotFoundError:
            art_found_in_db = False
        if art_found_in_db:
            art_head = []
            art_body = []
            art = f.readlines()

            for a in art:
                a0 = a.rstrip("\n")
                found_in_headers = False
                for h in headers:
                    h0 = h + ":"
                    if a0[:len(h)+1] == h0:
                        art_head.append(a0)
                        found_in_headers = True
                        break
                if not found_in_headers:
                    art_body.append(a0)
            f.close()
            print("found in db!")
            conv_head = self.list_to_crlf_str(art_head)
            conv_body = self.list_to_crlf_str(art_body)
            if use_memcached:
                # save in cache
                try:
                    art_body_dill = dill.dumps(art_body)
                    art_head_dill = dill.dumps(art_head)
                    self.pymemclient.set(id0 + ":head", art_head_dill)
                    self.pymemclient.set(id0 + ":body", art_body_dill)
                except Exception as e:
                    pass
            return id0, conv_head, conv_body
        else:
            if settings.do_forwarding:
                art_head, art_body = self.forward_get_article(id0)
                if not art_head:
                    return id0, None, None
                print("found on forwarding news server!")
                # convert b'' to CRLF separated string
                art_body0 = ""
                for ab in art_body:
                    ab0 = "".join(chr(x) for x in ab)
                    art_body0 += ab0 + CRLF
                art_head0 = self.list_to_crlf_str(art_head, decoding=True)
                if use_memcached:
                    # save in cache
                    try:
                        art_body_dill = dill.dumps(art_body0)
                        art_head_dill = dill.dumps(art_head0)
                        self.pymemclient.set(id0 + ":head", art_head_dill)
                        self.pymemclient.set(id0 + ":body", art_body_dill)
                    except Exception as e:
                        pass
                # write to file in db dir
                f = open(DB_DIR + id0, "wb")
                ah0 = ""
                for ah in art_head:
                    ah0 += ah.decode() + CRLF
                f.write(ah0.encode())
                ab0 = ""
                for ab in art_body:
                    ab0 += "".join(chr(x) for x in ab) + CRLF
                f.write(ab0.encode())
                f.flush()
                f.close()
                return id0, art_head0, art_body0
        return id0, None, None

    # NNTP responses

    def do_POST(self):
        self.send_response(STATUS_POSTSUCCESSFULL)
        message_ID = None
        for a in self.article_lines:
            if "Message-ID" == a[:10]:
                message_ID = a.split("Message-ID:")[1].lstrip()
                break
        if message_ID:
            f = open(DB_DIR + message_ID + ".bak", "wb")
            for a in self.article_lines:
                a += CRLF
                f.write(a.encode())
            f.flush()
            f.close()

    def do_CAPABILITIES(self):
        cap = (STATUS_CAPABILITIES, "VERSION 2", "ARTICLE", ".")
        for c in cap:
            self.send_response(c)

    def do_ARTICLE(self):
        param1 = self.params[1]
        message_id, article_head, article_body = self.backend_get_article(param1)
        if not article_head:
            self.send_response(ERR_NOSUCHARTICLENUM)
        else:
            response = STATUS_ARTICLE % (1, message_id)
            self.send_response("%s\r\n%s\r\n\r\n%s\r\n." % (response, article_head, article_body))

    def do_HEAD(self):
        global bodycount
        param1 = self.params[1]
        message_id, article_head, article_body = self.backend_get_article(param1, onlyhead=True)
        if not article_head:
            self.send_response(ERR_NOSUCHARTICLENUM)
        else:
            bodycount += 1
            print("HEAD ", param1, bodycount)
            response = STATUS_HEAD % (1, message_id)
            self.send_response("%s\r\n%s\r\n." % (response, article_head))

    def do_BODY(self):
        global bodycount
        param1 = self.params[1]
        message_id, article_head, article_body = self.backend_get_article(param1, onlybody=True)
        if not article_body:
            self.send_response(ERR_NOSUCHARTICLENUM)
        else:
            bodycount += 1
            print("BODY ", param1, bodycount)
            response = STATUS_BODY % (1, message_id)
            self.send_response("%s\r\n%s\r\n." % (response, article_body))

    def do_STAT(self):
        param1 = self.params[1]
        art_exists = self.backend_stat(param1)
        if not art_exists:
            self.send_response(ERR_NOSUCHARTICLENUM)
        else:
            self.send_response(STATUS_STAT % (1, param1))

    def do_QUIT(self):
        self.terminated = True
        self.send_response(STATUS_CLOSING)

    def send_response(self, message):
        msg0 = message + "\r\n"
        self.wfile.write(msg0.encode())
        self.wfile.flush()


class NNTPServer(socketserver.ForkingTCPServer):
    allow_reuse_address = True
    request_queue_size = 128
    if settings.max_connections:
        max_children = settings.max_connections


if __name__ == '__main__':

    signal.signal(signal.SIGINT, sighandler)
    signal.signal(signal.SIGTERM, sighandler)

    server = NNTPServer((settings.nntp_hostname, settings.nntp_port), NNTPRequestHandler)
    server.serve_forever()

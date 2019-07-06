#!/home/stephan/.virtualenvs/gzbx/bin/python

''' GINZICUT: Test server for ginzibix
    (c) 2018 Stephan Untergrabner <stephan@untergrabner.at>

    This is light-weight & stripped down (read-only )pyhton3 re-implementation of

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

import threading
import socketserver
import pickle
import signal
import sys
import time
import ssl
import nntplib
import redis
import logging
import logging.handlers
import os
import shutil
from os.path import expanduser

__version__ = "1.0"

settings = None
DB_DIR = None
LOG_DIR = None
SERVER = None
TIMEOUT = 180
CRLF = "\r\n"
HEADER_BODY_SEPARATOR = "***---sep---***"
FORWARD_NNTP = []
SERVER = None
REDISCLIENT = None
CRLF_ENC = "\r\n".encode("latin-1")
ENDART_ENC = "\r\n.\r\n".encode("latin-1")
LOGGER = None

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


def sighandler(signum, frame):
    global SERVER
    global FORWARD_NNTP
    print("Shutting down ginzicut ...")
    for fo in FORWARD_NNTP:
        if fo:
            fo.quit()
    SERVER.socket.close()
    SERVER.shutdown()
    print("... done!")
    time.sleep(1)


class NNTPRequestHandler(socketserver.StreamRequestHandler):

    def __init__(self, request, client_address, server):
        socketserver.StreamRequestHandler.__init__(self, request, client_address, server)

    def handle_timeout(self, signum, frame):
        self.terminated = True

    def handle(self):
        global LOGGER
        self.logger = LOGGER

        global REDISCLIENT
        self.redisclient = REDISCLIENT

        self.commands = ("CAPABILITIES", "ARTICLE", "BODY", "QUIT", "STAT", "HEAD")
        self.terminated = False
        self.nntpobj = None
        self.timeout = TIMEOUT

        if settings.server_type == 'read-only':
            self.send_response(STATUS_READYNOPOST % (settings.nntp_hostname, __version__))
        else:
            self.send_response(STATUS_READYOKPOST % (settings.nntp_hostname, __version__))

        self.logger.info("finished init for " + str(self.client_address))

        while not self.terminated:

            try:
                self.inputline = self.rfile.readline()
            except IOError as e:
                self.logger.warning(str(e) + ": tcp readline error")
                continue

            cmd = self.inputline.decode().strip()
            self.params = cmd.split(" ")
            cmd0 = self.params[0].upper()

            if cmd0:
                self.logger.debug("received " + cmd0 + " from " + str(self.client_address))
                if cmd0 in self.commands:
                    try:
                        eval("self.do_" + cmd0 + "()")
                    except Exception as e:
                        self.logger.error(str(e) + ": this should not occur - do not know command " + cmd0)
                        self.send_response(ERR_NOTCAPABLE)
                else:
                    self.send_response(ERR_NOTCAPABLE)
        self.logger.info("closing handler for " + str(self.client_address))

    def open_connection(self):
        global FORWARD_NNTP
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
        FORWARD_NNTP.append(nntp_obj)
        return nntp_obj

    def close_connection(self):
        global FORWARD_NNTP
        if self.nntpobj:
            try:
                FORWARD_NNTP.remove(self.nntpobj)
            except Exception as e:
                self.logger.error(str(e) + ": connection close error")
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
        global FORWARD_NNTP
        try:
            FORWARD_NNTP.remove(self.nntpobj)
            self.nntpobj.quit()
        except Exception as e:
            self.logger.warning(str(e) + ": retry connect warning")
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
        if settings.use_redis:
            # first search in memcached
            mc_key_head = id0 + ":head"
            try:
                head0 = self.redisclient.lrange(mc_key_head, 0, -1)[0]
                if head0:
                    return 1
                else:
                    return None
            except Exception:
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
        id0 = id0 + '>' if not id0.endswith('>') else id0
        id0 = "<" + id0 if not id0.startswith('<') else id0
        return id0

    def backend_get_article(self, id, onlybody=False, onlyhead=False):
        id0 = self.get_correct_id(id)
        if settings.use_redis:
            # first search in memcached
            mc_key_head = id0 + ":head"
            mc_key_body = id0 + ":body"
            try:
                if onlybody:
                    body0 = self.redisclient.lrange(mc_key_body, 0, -1)[0]
                    if body0:
                        self.logger.debug(id0 + ": body found on redis!")
                        return id0, None, body0, "redis"
                elif onlyhead:
                    head0 = self.redisclient.lrange(mc_key_head, 0, -1)[0]
                    if head0:
                        self.logger.debug(id0 + ": head found on redis!")
                        return id0, head0, None, "redis"
                else:
                    body0 = self.redisclient.lrange(mc_key_body, 0, -1)[0]
                    head0 = self.redisclient.lrange(mc_key_head, 0, -1)[0]
                    if head0 and body0:
                        self.logger.debug(id0 + ": head & body found on redis!")
                        return id0, head0, body0, "redis"
            except Exception as e:
                self.logger.warning(str(e) + ": " + id0 + " not found in redis")
                pass
        # then in in db directory:
        if settings.savefiles:
            art_found_in_db = True
            try:
                f = open(DB_DIR + id0, "rb")
            except FileNotFoundError:
                art_found_in_db = False
            if art_found_in_db:
                self.logger.debug("reading body " + id0 + " from db")
                data01 = pickle.loads(f.read())
                art_head = []
                art_body = []
                separator_found = False
                for d0 in data01:
                    if d0 == HEADER_BODY_SEPARATOR:
                        separator_found = True
                        continue
                    if not separator_found:
                        art_head.append(d0.encode("latin-1"))
                    else:
                        art_body.append(d0.encode("latin-1"))

                f.close()
                self.logger.debug(id0 + " found in db!")
                conv_head = self.bytelist_to_latin_crlf_str(art_head)
                conv_body = self.bytelist_to_latin_crlf_str(art_body)
                if settings.use_redis:
                    # save in cache
                    try:
                        self.redisclient.rpush(id0 + ":head", conv_head.encode("latin-1"))
                        self.redisclient.rpush(id0 + ":body", conv_body.encode("latin-1"))
                    except Exception as e:
                        self.logger.error(str(e) + ": redis push error")
                return id0, conv_head.encode("latin-1"), conv_body.encode("latin-1"), "file-db"
        # finally on forwarding server
        if settings.do_forwarding:
            art_head, art_body = self.forward_get_article(id0)
            if not art_head:
                return id0, None, None
            self.logger.debug(id0 + " found on forwarding news server!")
            # convert b'' to CRLF separated string
            art_body0 = self.bytelist_to_latin_crlf_str(art_body)
            art_head0 = self.bytelist_to_latin_crlf_str(art_head)
            if settings.use_redis:
                # save in cache
                try:
                    self.redisclient.rpush(id0 + ":head", art_head0.encode("latin-1"))
                    self.redisclient.rpush(id0 + ":body", art_body0.encode("latin-1"))
                except Exception as e:
                    self.logger.error(str(e) + ": redis push error")
            # write to file in db dir
            if settings.savefiles:
                try:
                    f = open(DB_DIR + id0, "wb")
                    data0 = [ah.decode("latin-1") for ah in art_head]
                    data0.append(HEADER_BODY_SEPARATOR)
                    data0.extend([ab.decode("latin-1") for ab in art_body])
                    f.write(pickle.dumps(data0))
                    f.flush()
                    f.close()
                except Exception as e:
                    self.logger.error(str(e) + ": write to file error")
            return id0, art_head0.encode("latin-1"), art_body0.encode("latin-1"), "forwarding-host"
        return id0, None, None

    def bytelist_to_latin_crlf_str(self, bytelist0):
        return CRLF.join(b.decode("latin-1") for b in bytelist0)

    # NNTP responses

    def do_CAPABILITIES(self):
        for c in (STATUS_CAPABILITIES, "VERSION 2", "ARTICLE", "."):
            self.send_response(c)

    def do_ARTICLE(self):
        param1 = self.params[1]
        message_id, article_head, article_body, from_db = self.backend_get_article(param1)
        if not article_head:
            self.send_response(ERR_NOSUCHARTICLENUM)
        else:
            response = STATUS_ARTICLE % (1, message_id)
            self.logger.debug("response: ARTICLE " + str(param1) + " " + str(from_db))
            self.send_response("%s\r\n%s\r\n\r\n%s\r\n." % (response, article_head, article_body))

    def do_HEAD(self):
        param1 = self.params[1]
        message_id, article_head, article_body, from_db = self.backend_get_article(param1, onlyhead=True)
        if not article_head:
            self.send_response(ERR_NOSUCHARTICLENUM)
        else:
            self.logger.debug("response: HEAD " + str(param1) + " " + str(from_db))
            response = STATUS_HEAD % (1, message_id)
            self.send_response("%s\r\n%s\r\n." % (response, article_head))

    def do_BODY(self):
        param1 = self.params[1]
        message_id, article_head, article_body, from_db = self.backend_get_article(param1, onlybody=True)
        if not article_body:
            self.send_response(ERR_NOSUCHARTICLENUM)
        else:
            self.logger.debug("response: BODY " + str(param1) + " " + str(from_db))
            # for performance reasons
            response = STATUS_BODY % (1, message_id)
            resp1 = b''.join([response.encode("latin-1"), CRLF_ENC, article_body, ENDART_ENC])
            self.wfile.write(resp1)
            self.wfile.flush()

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
        self.wfile.write(msg0.encode("latin-1"))
        self.wfile.flush()


class NNTPServer(socketserver.ForkingTCPServer):
    global settings
    allow_reuse_address = True
    request_queue_size = 12
    if settings:
        if settings.max_connections:
            max_children = settings.max_connections


def run():
    global settings
    global DB_DIR
    global LOG_DIR
    global SERVER
    global SERVER_THREAD
    global REDISCLIENT
    global LOGGER

    INSTALL_DIR = os.path.dirname(os.path.realpath(__file__))

    # read / create dirs + config file
    ginzicut_dir = expanduser("~") + "/.ginzicut/"
    DB_DIR = ginzicut_dir + "db/"
    LOG_DIR = ginzicut_dir + "log/"
    if not os.path.exists(ginzicut_dir):
        try:
            os.mkdir(ginzicut_dir)
            shutil.copy(INSTALL_DIR + "/config/ginzicut_settings.py", ginzicut_dir + "ginzicut_settings.py")
            os.mkdir(DB_DIR)
            os.mkdir(LOG_DIR)
            print("/home/$USER/.ginzicut dir initialized, new please edit ginzicut_settings.py to your likes ...")
            return -1
        except Exception as e:
            print(str(e) + ": cannot initialize .ginzicut dir, exiting ...")
            return -1

    if not os.path.exists(DB_DIR):
        try:
            os.mkdir(DB_DIR)
        except Exception as e:
            print(str(e) + ": cannot create db_dir, exiting")
            return -1

    if not os.path.exists(LOG_DIR):
        try:
            os.mkdir(LOG_DIR)
        except Exception as e:
            print(str(e) + ": cannot create log_dir, exiting")
            return -1

    sys.path.append(ginzicut_dir)
    try:
        import ginzicut_settings as settings
    except Exception as e:
        print(str(e) + ": no ginzicut_settings.py file found, pls create one, exiting ...")
        return -1

    # test unix_socket_path for permissions
    if settings.use_redis:
        if settings.redis_unix:
            try:
                ustat = os.stat(settings.unix_socket_path)
            except Exception as e:
                print(str(e) + ": redis is not started, exiting ...")
                return -1
            oct_perm = str(oct(ustat.st_mode))
            if not oct_perm.endswith("777"):
                print("Please do chmod 777 " + settings.unix_socket_path + ", exiting ...")
                return -1

    LOGGER = logging.getLogger("ginzicut")
    if settings.debug_level == "debug":
        LOGGER.setLevel(logging.DEBUG)
    elif settings.debug_level == "warning":
        LOGGER.setLevel(logging.WARNING)
    elif settings.debug_level == "error":
        LOGGER.setLevel(logging.ERROR)
    else:
        LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
    fh = logging.FileHandler(LOG_DIR + "ginzicut.log", mode="w")
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    LOGGER.addHandler(fh)

    if settings.use_redis:
        try:
            if settings.redis_unix:
                REDISCLIENT = redis.StrictRedis(unix_socket_path=settings.unix_socket_path, db=0)
                LOGGER.info("starting ginzicut NNTP server on unix socket " + settings.unix_socket_path)
            elif settings.redis_tcp:
                REDISCLIENT = redis.StrictRedis(host=settings.host, port=settings.port, db=0)
                LOGGER.info("starting ginzicut NNTP server on port " + str(settings.nntp_port))
            else:
                raise("use-redis = True but no socket option given!")
        except Exception as e:
            LOGGER.error("redis connection error: " + str(e))
            settings.use_redis = False

    signal.signal(signal.SIGINT, sighandler)
    signal.signal(signal.SIGTERM, sighandler)

    SERVER = NNTPServer((settings.nntp_hostname, settings.nntp_port), NNTPRequestHandler)
    SERVER_THREAD = threading.Thread(target=SERVER.serve_forever)
    SERVER_THREAD.daemon = True
    print("ginzicut running now, press Ctrl-C to stop!")
    SERVER_THREAD.start()
    SERVER_THREAD.join()
    SERVER.server_close()
    print("ByeBye!")
    return 0



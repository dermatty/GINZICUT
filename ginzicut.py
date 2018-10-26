#!/home/stephan/.virtualenvs/nntp/bin/python
import settings_secret as settings
import socketserver
import re
import signal
import sys
import time

__version__ = "0.1"
TIMEOUT = 180
CRLF = "\r\n"
DB_DIR = "./db/"


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

# the currently supported overview headers
overview_headers = ('Subject', 'From', 'Date', 'Message-ID', 'References', 'Bytes', 'Lines', 'Xref')

# we don't need to create the regular expression objects for every request, 
# so let's create them just once and re-use as needed
newsgroups_regexp = re.compile("^Newsgroups:(.*)", re.M)
contenttype_regexp = re.compile("^Content-Type:(.*);", re.M)
authinfo_regexp = re.compile("AUTHINFO PASS")

ART0_HEAD = ("Path: news.myisp.se!newsfeed.internetmci.com!news.spam.egg",
             "From: user@spam.egg",
             "Newsgroups: comp.lang.python",
             "Subject: Re: Where's the bacon?",
             "Date: 17 Jul 1999 09:25:53 -0400",
             "Lines: 12",
             "Sender: user@spam.egg",
             "Message-ID: <lqsoxd95em.ach@news.spam.egg>",
             "References: <199907152100.RAA14304@foobar.spam.egg>",
             "Xref: news.spam.egg comp.lang.python:14304")
ART0_BODY = ("Fredrik wrote:",
             '> Havent got a clue. Maybe someone else knows more.')


def sighandler(signum, frame):
    global server
    server.socket.close()
    time.sleep(1)
    sys.exit(0)


class NNTPRequestHandler(socketserver.StreamRequestHandler):

    commands = ("CAPABILITIES", "ARTICLE", "BODY", "QUIT", "POST", "STAT")
    ''' 'BODY', 'HEAD', 'STAT', 'GROUP', 'LIST', 'POST',
                'HELP', 'LAST', 'NEWGROUPS', 'NEWNEWS', 'NEXT', 'QUIT',
                'MODE', 'XOVER', 'XPAT', 'LISTGROUP', 'XGTITLE', 'XHDR',
                'SLAVE', 'DATE', 'IHAVE', 'OVER', 'HDR', 'AUTHINFO',
                'XROVER', 'XVERSION', "CAPABILITIES")'''
    extensions = ('XOVER', 'XPAT', 'LISTGROUP', 'XGTITLE', 'XHDR', 'MODE',
                  'OVER', 'HDR', 'AUTHINFO', 'XROVER', 'XVERSION')
    terminated = False

    def handle_timeout(self, signum, frame):
        self.terminated = True

    def handle(self):
        if settings.server_type == 'read-only':
            self.send_response(STATUS_READYNOPOST % (settings.nntp_hostname, __version__))
        else:
            self.send_response(STATUS_READYOKPOST % (settings.nntp_hostname, __version__))

        self.sending_article = False

        while not self.terminated:

            if not self.sending_article:
                self.article_lines = []

            signal.signal(signal.SIGALRM, self.handle_timeout)
            signal.alarm(TIMEOUT)

            try:
                self.inputline = self.rfile.readline()
            except IOError:
                continue

            signal.alarm(0)

            if not self.sending_article:
                cmd = self.inputline.decode().strip()
                self.params = cmd.split(" ")
                cmd0 = self.params[0].upper()
            else:
                cmd = self.inputline.decode()
                cmd0 = "posting ...", cmd

            if cmd0:
                print(cmd0)
                if cmd0 == "POST":
                    self.sending_article = True
                    self.send_response(STATUS_SENDARTICLE)
                else:
                    if self.sending_article:
                        if cmd == ".\r\n":
                            self.sending_article = False
                            self.do_POST()
                            continue
                        self.article_lines.append(cmd.rstrip())
                    else:
                        if cmd0 in self.commands:
                            getattr(self, "do_" + cmd0)()
                        else:
                            self.send_response(ERR_NOTCAPABLE)

            time.sleep(0.02)

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
        # for l in lines:
        #     print(l)'''

    def list_to_crlf_str(self, list0):
        strres = ""
        for l in list0:
            strres += l + CRLF
        return strres

    def do_CAPABILITIES(self):
        cap = (STATUS_CAPABILITIES, "VERSION 2", "ARTICLE", ".")
        for c in cap:
            self.send_response(c)

    def do_ARTICLE(self):
        param1 = self.params[1]
        message_id, article_head, article_body = backend_get_article(param1)
        if not article_head:
            self.send_response(ERR_NOSUCHARTICLENUM)
        else:
            response = STATUS_ARTICLE % (1, message_id)
            self.send_response("%s\r\n%s\r\n\r\n%s\r\n." % (response, article_head, article_body))

    def do_BODY(self):
        param1 = self.params[1]
        message_id, article_head, article_body = backend_get_article(param1)
        if not article_head:
            self.send_response(ERR_NOSUCHARTICLENUM)
        else:
            response = STATUS_BODY % (1, message_id)
            self.send_response("%s\r\n%s\r\n." % (response, article_body))

    def do_STAT(self):
        param1 = self.params[1]
        art_exists = backend_stat(param1)
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


def list_to_crlf_str(list0):
    strres = ""
    for l in list0:
        strres += l + CRLF
    return strres


def backend_stat(id):
    id0 = id.rstrip().lstrip()
    if id0[0] != "<" or id0[-1] != ">":
        return None
    # first search in db directory:
    try:
        f = open(DB_DIR + id0, "r")
    except FileNotFoundError:
        return None
    f.close()
    return 1


def backend_get_article(id):
    id0 = id.rstrip().lstrip()
    if id0[0] != "<" or id0[-1] != ">":
        return id0, None, None
    # first search in db directory:
    try:
        f = open(DB_DIR + id0, "r")
    except FileNotFoundError:
        return id0, None, None
    art_head = []
    art_body = []
    art = f.readlines()
    headers = ("Date", "From", "Message-ID", "Newsgroups", "Path", "Subject",
               "Approved", "Archive", "Control", "Distribution", "Expires", "Followup-To",
               "Injection-Date", "Injection-Info", "Organization", "References",
               "Summary", "Supersedes", "User-Agent", "Xref", "Lines", "Sender")

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
    return id0, list_to_crlf_str(art_head), list_to_crlf_str(art_body)


if __name__ == '__main__':

    signal.signal(signal.SIGINT, sighandler)
    signal.signal(signal.SIGTERM, sighandler)

    socketserver.ForkingTCPServer.allow_reuse_address = True
    server = socketserver.ForkingTCPServer((settings.nntp_hostname, settings.nntp_port), NNTPRequestHandler)
    server.serve_forever()

import nntplib

CRLF = b'\r\n'

_LONGRESP = {
    '100',   # HELP
    '101',   # CAPABILITIES
    '211',   # LISTGROUP   (also not multi-line with GROUP)
    '215',   # LIST
    '220',   # ARTICLE
    '221',   # HEAD, XHDR
    '222',   # BODY
    '224',   # OVER, XOVER
    '225',   # HDR
    '230',   # NEWNEWS
    '231',   # NEWGROUPS
    '282',   # XGTITLE
}


def _getlongresp_monkey(self, file=None):
        """Internal: get a response plus following text from the server.
        Raise various errors if the response indicates an error.
        Returns a (response, lines) tuple where `response` is a unicode
        string and `lines` is a list of bytes objects.
        If `file` is a file-like object, it must be open in binary mode.
        """

        openedFile = None
        try:
            # If a string was passed then open a file with that name
            if isinstance(file, (str, bytes)):
                openedFile = file = open(file, "wb")

            resp = self._getresp()
            if resp[:3] not in _LONGRESP:
                raise "OASCH!"

            lines = []
            if file is not None:
                # XXX lines = None instead?
                terminators = (b'.' + CRLF, b'.\n')
                while 1:
                    print("waiting")
                    line = self._getline(False)
                    if line in terminators:
                        break
                    if line.startswith(b'..'):
                        line = line[1:]
                    file.write(line)
            else:
                terminator = b'.'
                while 1:
                    line = self._getline()
                    if line == terminator:
                        break
                    if line.startswith(b'..'):
                        line = line[1:]
                    lines.append(line)
                    print(line)
        finally:
            # If this method created the file, then it must close it
            if openedFile:
                openedFile.close()

        return resp, lines


# nntplib._getlongresp = _getlongresp_monkey

s = nntplib.NNTP('etec.iv.at', port=7016)

art0 = "<lqsoxd95em.ach@news.spam.egg>"

'''art0 = "<lqsoxd95em.ach@news.spam.egg>"
resp, info = s.body(art0)
print(resp)
print("number: ", info.number)
print("message_id", info.message_id)
for inf in info.lines:
    print("***********")
    print(inf)'''

art0 = "./db/<lqsoxd95em.ach@news.spam.egg>"
f = open(art0, 'rb')
s.post(f)

s.quit()

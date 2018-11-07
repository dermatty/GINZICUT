import nntplib, time, sys
import threading
from threading import Thread
import settings_secret as settings
import ssl

f = open("articles.txt", "r")
lines = f.readlines()
f.close()
artlist = []
dllist = []
print("... reading article list")
for l1 in lines:
        try:
                la = l1.rstrip().lstrip()
                ll = la.split("<segment bytes=")[1]
                l0 = la.split(">")[1]
                l0 = l0.split("</segment")[0]
                artlist.append(l0)
                dllist.append(False)
        except:
                pass

print("done", len(artlist))

# artlist = ["<part9of131.mVhZUeNfjvVQg2z1CJLq@powerpost2000AA.local>"]

bytesdownloaded = 0
info_ginzicut = None
info_eweka = None


class Nntpthread(Thread):
        def __init__(self, artlist, lock):
                Thread.__init__(self)
                self.daemon = True
                self.lock = lock
                self.artlist = artlist
                self.s = nntplib.NNTP('127.0.0.1', port=7016)

        def run(self):
                global bytesdownloaded
                global info_ginzicut
                bytesdl = 0
                for a in self.artlist:
                        try:
                                resp, info = self.s.body(a)
                                info_ginzicut = info
                                bytesdl += sum(len(i) for i in info.lines)
                                # print(i, a, " ---> ", resp)
                        except Exception as e:
                                print("*" * 30, a, e)
                with self.lock:
                        bytesdownloaded += bytesdl


maxconn = 12
clientthreads = []

lock = threading.Lock()
for i in range(maxconn):
        nntp = Nntpthread(artlist, lock)
        clientthreads.append(nntp)

t0 = time.time()
for nntp in clientthreads:
        nntp.start()
for n in clientthreads:
        n.join()

bytespersec = bytesdownloaded / (time.time() - t0)
kbpersec = bytespersec / 1024
mbpersec = kbpersec / 1024
print("Mbit/sec:", int(mbpersec * 8))

for n in clientthreads:
        n.s.quit()

# print(info_ginzicut.lines[0:3])

sys.exit()

sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS)
nntp_obj = nntplib.NNTP_SSL(settings.forward_server_url, user=settings.forward_server_user,
                            password=settings.forward_server_pass, ssl_context=sslcontext,
                            port=settings.forward_server_port, readermode=True, timeout=5)
for a in artlist:
        print(a)
        resp, info = nntp_obj.body(a)
        print("-----------------", resp)
        info_eweka = info

# i0 = [i for i, j in zip(info_eweka, info_ginzicut) if i != j]

print("... read from eweka directly")
print(info_eweka.lines[-5:])
print("... read from ginzicut")
print(info_ginzicut.lines[-5:])

for n in clientthreads:
        n.s.quit()

sys.exit()

### todo: bei ginzicut ist noch ein b'' dran ###
### peewee instead of redis ####

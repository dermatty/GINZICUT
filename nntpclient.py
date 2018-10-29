import nntplib, time, sys
import threading
from threading import Thread

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

bytesdownloaded = 0


class Nntpthread(Thread):
        def __init__(self, artlist, lock):
                Thread.__init__(self)
                self.daemon = True
                self.lock = lock
                self.artlist = artlist
                self.s = nntplib.NNTP('etec.iv.at', port=7016)

        def run(self):
                global bytesdownloaded
                i = 1
                for a in self.artlist:
                        try:
                                resp, info = self.s.body(a)
                                print(resp)
                                info0 = [inf for inf in info.lines]
                                with self.lock:
                                        bytesdownloaded += sum(len(i) for i in info0)
                                print(i, a, " ---> ", resp)
                                i += 1
                        except Exception as e:
                                print("*" * 30, a, e)


maxconn = 8
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

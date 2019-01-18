import nntplib, time, sys
import threading
from threading import Thread
import settings_secret as settings
import ssl
import sabyenc
import yenc
import re
import difflib
import asyncio
import queue
import psutil
from statistics import mean
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


lock = threading.Lock()
maxconn = 12

f = open("articles.txt", "r")
lines = f.readlines()
infolist = []
f.close()
artlist = []
dllist = []
articlequeue = queue.Queue()
articlequeue_async = asyncio.Queue()
print("... reading article list")
for _ in range(20):
        for l1 in lines:
                try:
                        la = l1.rstrip().lstrip()
                        ll = la.split("<segment bytes=")[1]
                        l0 = la.split(">")[1]
                        l0 = l0.split("</segment")[0]
                        artlist.append(l0)
                        articlequeue.put(l0)
                        articlequeue_async.put_nowait(l0)
                        dllist.append(False)
                except:
                        pass

print("done", len(artlist))

# artlist = ["BvH7yENlUkNMGqRbt2Ir@JBinUp.local"]

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
                                #infolist.append(info)
                                #info_ginzicut = info
                                bytesdl += sum(len(i) for i in info.lines)
                        except Exception as e:
                                print("*" * 30, a, e)
                with self.lock:
                        bytesdownloaded += bytesdl
                self.s.quit()


class Nntpthread_Queue(Thread):
        def __init__(self, artqueue, lock):
                Thread.__init__(self)
                self.daemon = True
                self.lock = lock
                self.artqueue = artqueue
                self.s = nntplib.NNTP('127.0.0.1', port=7016)

        def run(self):
                global bytesdownloaded
                global info_ginzicut
                bytesdl = 0
                while True:
                        try:
                                a = self.artqueue.get_nowait()
                                self.artqueue.task_done()
                        except (queue.Empty, EOFError):
                                break
                        try:
                                resp, info = self.s.body(a)
                                bytesdl += sum(len(i) for i in info.lines)
                        except Exception as e:
                                print("*" * 30, a, e)
                with self.lock:
                        bytesdownloaded += bytesdl
                self.s.quit()


class CPUSensor(Thread):
        def __init__(self):
                Thread.__init__(self)
                self.daemon = True
                self.stopped = False
                self.cpulist = []
                self.cpuvalue = 0

        def stop(self):
                self.stopped = True

        def run(self):
                while not self.stopped:
                        cpu_perc0 = mean(psutil.cpu_percent(interval=0.25, percpu=True))
                        self.cpulist.append(cpu_perc0)
                self.cpuvalue = sum([c for c in self.cpulist])/len(self.cpulist)


class ConnectionThreads(Thread):
    def __init__(self, artqueue, maxconn):
        Thread.__init__(self)
        self.daemon = True
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.artqueue = artqueue
        self.workers = []
        self.maxconn = maxconn
        self.conns = []

    def stop(self):
        print("stopping all workers")
        for cw in self.workers:
            cw.stop()
        del self.workers
        self.workers = []

    async def getbody(self, s, a):
            await asyncio.sleep(0)
            resp, info = s.body(a)
            return resp, info

    async def download_article(self, x, s):
        bytesdl = 0
        while True:
                try:
                        a = self.artqueue.get_nowait()
                        self.artqueue.task_done()
                except (asyncio.QueueEmpty, EOFError):
                        break
                await asyncio.sleep(0)
                resp, info = s.body(a)
                bytesdl += sum(len(i) for i in info.lines)
        return bytesdl

    async def start_downloads(self):
        input_coroutines = []
        for i in range(self.maxconn):
                conn = nntplib.NNTP('127.0.0.1', port=7016)
                self.conns.append(conn)
                # 5 greenlets per server
                for x in range(1):
                    cw = self.download_article(i, conn)
                    self.workers.append(cw)
                    input_coroutines.append(cw)
        result = await asyncio.gather(*input_coroutines, return_exceptions=True)
        for s in self.conns:
                s.quit()
        return result

    def run(self):
        try:
            self.result = self.loop.run_until_complete(self.start_downloads())
        except (KeyboardInterrupt, RuntimeError) as e:
            print(str(e))
        self.loop.stop()
        self.loop.close()
        print("shutdown done")


# --------------------------------------------------------------------------------------------------------------

TESTTHREADS = False

# get cpu base load
print("Init. cpu load sensor ...")
c = CPUSensor()
c.start()
time.sleep(2)
c.stop()
c.join()
cpubaseload = c.cpuvalue
print("... done (", cpubaseload, "%)")

# test via Threads + Queue
mbpersec_thread = 0
dt_thread = 0
cpuvalue_thread = 0
if TESTTHREADS:
        clientthreads = []
        lock = threading.Lock()
        for i in range(maxconn):
                nntp = Nntpthread_Queue(articlequeue, lock)
                clientthreads.append(nntp)

        t0 = time.time()
        c = CPUSensor()
        c.start()
        for nntp in clientthreads:
                nntp.start()
        for nntp in clientthreads:
                nntp.join()
        c.stop()
        c.join()

        dt = time.time() - t0
        bytespersec = bytesdownloaded / (dt)
        kbpersec = bytespersec / 1024
        mbpersec_thread = kbpersec / 1024
        dt_thread = dt
        cpuvalue_thread = c.cpuvalue - cpubaseload

# test via async
t0 = time.time()
maxconn = 20
t = ConnectionThreads(articlequeue_async, maxconn)
c = CPUSensor()
c.start()
t.start()
t.join()
c.stop()
c.join()

bytesdownloaded = sum([r for r in t.result])
dt = time.time() - t0
bytespersec = bytesdownloaded / (dt)
kbpersec = bytespersec / 1024
mbpersec = kbpersec / 1024
print("---- ASYNCIO ----")
print("Mbit/sec:", int(mbpersec * 8))
print("dt:", dt)
print("cpu:", c.cpuvalue - cpubaseload)
print("---- THREADS ----")
print("Mbit/sec:", int(mbpersec_thread * 8))
print("dt:", dt_thread)
print("cpu:", cpuvalue_thread)

sys.exit()



bytesfinal_sab = bytearray()
bytesfinal_yenc = bytearray()
for info in infolist:
        # sab
        data = info[-1]
        lastline = data[-1].decode("latin-1")
        m = re.search('size=(.\d+?) ', lastline)
        if m:
                size = int(m.group(1))
        decoded_sab = None
        data0 = []
        for d in data:
                ditem = d
                if not d.endswith(b"\r\n"):
                        ditem += b"\r\n"
                data0.append(ditem)
        decoded_sab, output_filename, crc, crc_yenc, crc_correct = sabyenc.decode_usenet_chunks(data0, size)
        print("!-->", len(decoded_sab))
        bytesfinal_sab.extend(decoded_sab)

        bytes_yenc = bytearray()
        # yenc
        for inf in info[-1]:
                inf_str = inf.decode("latin-1")
                if inf_str == "":
                        continue
                if inf_str.startswith("=ybegin") or inf_str.startswith("=ypart") or inf_str.startswith("=yend"):
                        continue
                bytes_yenc.extend(inf)
        _, _, decoded_yenc = yenc.decode(bytes_yenc)
        bytesfinal_yenc.extend(decoded_yenc)
        print("-" * 50)
        if bytesfinal_sab != bytesfinal_yenc:
                for a,b in zip(bytesfinal_sab, bytesfinal_yenc):
                        if a != b:
                                print(chr(a).encode("latin-1"), chr(b).encode("latin-1"))
                                ch = input()

print(len(bytesfinal_sab), len(bytesfinal_yenc))

f = open("sab", "wb")
f.write(bytesfinal_sab)
f.close()

f = open("yenc", "wb")
f.write(bytesfinal_yenc)
f.close()

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

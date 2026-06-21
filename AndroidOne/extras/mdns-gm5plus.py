#!/data/data/com.termux/files/usr/bin/python
# gm5plus.local mDNS yayini (root'suz). avahi Termux'ta yok; zeroconf 5353'u normal app baglar.
# Calistir:  nohup python ~/mdns-gm5plus.py >/dev/null 2>&1 &   (boot script'inde de var)
# Durum:     ~/mdns.log
import socket, time
from zeroconf import Zeroconf, ServiceInfo

HOME = "/data/data/com.termux/files/home"
def log(m):
    f = open(HOME + "/mdns.log", "a"); f.write(str(m) + "\n"); f.flush(); f.close()

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); return s.getsockname()[0]
    finally:
        s.close()

try:
    ip = get_ip(); log("ip=" + ip)
    info = ServiceInfo(
        "_ssh._tcp.local.", "gm5plus._ssh._tcp.local.",
        addresses=[socket.inet_aton(ip)], port=8022,
        server="gm5plus.local.", properties={"info": "GM5 Plus server"},
    )
    # Sadece wlan0 IP'sine bind — dustuk Zeroconf() (tum arayuzler) Android rmnet/dummy'de takiliyor.
    zc = Zeroconf(interfaces=[ip])
    zc.register_service(info)
    log("REGISTERED gm5plus.local -> %s:8022" % ip)
    while True:
        time.sleep(3600)
except Exception as e:
    import traceback
    log("ERR: " + repr(e)); log(traceback.format_exc())

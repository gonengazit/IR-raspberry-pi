import serial, time,random,struct,sys
from lz4.frame import decompress,compress
from contextlib import closing
import numpy as np
# import commpy.channelcoding.convcode as cc
# from commpy.utilities import *
from bitstring import BitArray
from Queue import Queue
import threading
import socket
import RPi.GPIO as gpio

gpio.setmode(gpio.BCM)
gpio.setup(18,gpio.OUT)
gpio.setup(23,gpio.OUT)

gpio.output(18, False)
gpio.output(23, False)

ser = serial.Serial(port="/dev/serial0", baudrate=115200)

socket.setdefaulttimeout(3)
def blink(port):
    gpio.output(port, True)
    time.sleep(.01)
    gpio.output(port, False)

def deinterlieve(bits,n):
    cutoff=bits.size-(len(bits)%n)
    return np.concatenate((bits[:cutoff].reshape(n,bits[:cutoff].size/n).transpose().flatten(), bits[cutoff:]))

def deinterlieve2(a):
    return a[::2],a[1::2]

def rep_decode(bits,n):
    bitsmat=np.sum(bits.reshape(bits.size/n,n),axis=1)>=2
    return bitsmat.astype(int)

def decode(byteData):
    if byteData==b"":
        return
    # generator_matrix = np.array([[04, 05, 07]])
    # M = np.array([3])
    # trellis = cc.Trellis(M, generator_matrix)
    # tb_depth = 5 * (M.sum() + 1)
    # message_bits = deinterlieve(np.array(map(int, dataformats.bin))[7:],3)
    # decoded_bits = cc.viterbi_decode(message_bits.astype(float), trellis, tb_depth)[:-M]
    # print(len(bytesNew))
    # byteData=decompress(bytesNew)


    dataformats = BitArray(hex=byteData.encode("hex"))
    message_bits = deinterlieve(np.array(map(int, dataformats.bin)), 3)
    decoded_bits = rep_decode(message_bits, 3)
    newMessage = "".join(map(str,decoded_bits))
    bytesNew = b""
    for i in xrange(0, len(newMessage), 8):
        bytesNew += (struct.pack("B", int(newMessage[i:i + 8],2)))
    return bytesNew

def check(payload):
    random.seed("gonen")
    if payload==b"".join(struct.pack("B",random.randrange(16)) for _ in xrange(20)):
        # print("heartbeat recieved")
        return False
    # random.seed("gonen")
    # #data = b"".join(struct.pack("B",random.randrange(16)) for _ in range(len(payload)))
    # data=b"".join(struct.pack("B",i) for i in range(len(payload)))
    # print ("data length: %d"%(len(payload)))
    # print(payload == data)
    else:
        print(payload.decode("utf-8"))
        return True

def messageUnpackerSender(packed,pcktsize,counterqueue,tcpQueue):
    if not packed:
        return
    if len(packed)<pcktsize:
        packed+=struct.pack("B",0)*(pcktsize-len(packed))
    decoded=decode(packed[:pcktsize])
    try:
        finalData = decompress(decoded)
    except:
        blink(18)
        print("error %s" % sys.exc_info()[0])
    else:
        counterqueue.get()
        counterqueue.put(time.time())
        if check(finalData):
            tcpQueue.put(finalData)

class reciever(object):
    def __init__(self, frmsize, frmsync):
        self.buffer = b""
        self.framesize = frmsize
        self.framesync=struct.pack("I",int(frmsync,2))[1:]
        self.packetnumber=struct.pack("B",0)
    def recieve(self,counterqueue,tcpQueue):
        idx=0
        mode="framesync"
        pcktsize=0
        while True:
            if mode=="framesync":
                while idx!=len(self.framesync):
                    a=ser.read(1)
                    if a==self.framesync[idx]:
                        idx+=1
                    else:
                        if a==self.framesync[0]:
                            idx=1
                        else:
                            idx=0
                idx=0
                mode = "message"
            elif mode=="message":
                message=ser.read(self.framesize*2)
                blink(23)
                header,payload=deinterlieve2(message)
                decoded_header=decode(header)
                pcktnum=decoded_header[0]
                if pcktnum!=self.packetnumber:

                    #decode the buffer to see if you have enough info to make a messege
                    messageUnpackerSender(self.buffer, pcktsize, counterqueue,tcpQueue)
                    self.packetnumber=pcktnum
                    self.buffer=b""
                pcktsize = struct.unpack("H",decoded_header[1:3])[0]
                offset   = struct.unpack("H",decoded_header[3:5])[0]
                self.buffer+=struct.pack("B",0)*(offset-len(self.buffer))
                self.buffer+=payload
                if len(self.buffer)>=pcktsize:
                    # print(len(self.buffer),pcktsize*2)
                    # check(decompress(decode(self.buffer[:pcktsize])))
                    messageUnpackerSender(self.buffer,pcktsize,counterqueue,tcpQueue)
                    self.buffer=b""
                    self.packetnumber = b"-1"
                mode="framesync"

def HB(counterqueue):
    while True:
        gcounter=counterqueue.get()
        counterqueue.put(gcounter)
        if time.time()-gcounter>5:
            # print("error, no heartbeat recieved %d"%(time.time()-gcounter))
            gpio.output(18, True)
        else:
            gpio.output(18, False)
        time.sleep(.1)

def send(tcpQueue):
    TCP_IP = '20.0.0.3'
    TCP_PORT = 8000
    BUFFER_SIZE = 4096
    counter=0
    while True:
        MESSAGE=tcpQueue.get()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # MESSAGE = b"GET /foo2.html HTTP/1.1\r\nHost: 192.168.1.14:8000\r\nConnection: keep-alive\r\nCache-Control: max-age=0\r\nUpgrade-Insecure-Requests: 1\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36\r\nAccept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8\r\nAccept-Encoding: gzip, deflate, br\r\nAccept-Language: en-US,en;q=0.8,he;q=0.6\r\nIf-Modified-Since: Fri, 08 Sep 2017 22:46:30 GMT\r\n\r\n"

        for i in xrange(3):
            try:
                s.connect((TCP_IP, TCP_PORT))
            except (socket.error,socket.timeout) as e:
                blink(18)
                print("error")
                print(str(e))
            else:
                break
        else:
            s.close()
            continue
        with closing(s):
            for i in xrange(3):
                try:
                    s.send(MESSAGE)

                    data=s.recv(BUFFER_SIZE)
                except (socket.timeout,socket.error) as e:
                    blink(18)
                    print(str(e))
                else:
                    counter += 1
                    print(counter)
                    if data[9:17]==b"200 OK\r\n":
                        blink(23)
                        print("OK recieved")
                        print(data.decode("utf-8"))
                        break
                    else:
                        blink(18)
                        print("no OK")
                        print(data.decode("utf-8"))
            else:
                pass
                #flash  red led
    # s.close()


a=reciever(15,"01"*4+"0011"*2+"11"*4)
# a.recieve(time.time())

globalqueue=Queue()
tcpQueue=Queue()
globalqueue.put(time.time())
recieverThread=threading.Thread(target=a.recieve,args=(globalqueue,tcpQueue),name="reciever-thread")
recieverThread.daemon=True
HBThread=threading.Thread(target=HB,args=(globalqueue,),name="heartbeat-thread")
HBThread.daemon=True
tcpThread=threading.Thread(target=send,args=(tcpQueue,),name="TCP-thread")
tcpThread.daemon=True

recieverThread.start()
HBThread.start()
tcpThread.start()
while True:
    for i in (tcpThread,recieverThread,HBThread):
        try:
            i.join(1)
            if not i.isAlive():
                break
        except KeyboardInterrupt:
            gpio.cleanup()
            print("\nGoodBye")
            break
        except:
            print("error")
            gpio.output(18, True)
            break
    else:
        continue
    break

# while True:
# 	a=ser.in_waiting
# 	if a:
# 		b = ser.read(a)
# 		print(a)
# 		print(b)
# 	time.sleep(1)

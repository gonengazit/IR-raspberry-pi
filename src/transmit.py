import serial,time,string,random,struct,datetime,pytz
from lz4.frame import compress,decompress
import numpy as np
from numpy.matlib import repmat
from contextlib import closing

# from commpy.channelcoding.convcode import Trellis,conv_encode,viterbi_decode
# from commpy.utilities import *
from bitstring import BitArray
import socket
ser = serial.Serial(port="/dev/serial0", baudrate=115200)
#ser.flushInput()
#ser.flushOutput()

def interlieve(bits,n):
    cutoff=bits.size-(len(bits)%n)
    return np.concatenate((bits[:cutoff].reshape(cutoff / n, n).transpose().flatten(), bits[cutoff:]))

def interlieve2(a1,a2):
    return b"".join(j for i in zip(a1,a2) for j in i)

def rep_encode(bits,n):
    return np.repeat(bits,n)

def encode(data):
    compressedData = data
    # print(len(compressedData))
    # generator_matrix = np.array([[04, 05, 07]])
    # M = np.array([3])
    # trellis = Trellis(M, generator_matrix)
    # coded_bits = interlieve(conv_encode(message_bits, trellis),3)
    # newMessage="0"*((8-len(coded_bits)%8)%8)+ "".join(map(str,coded_bits))
    # thing =  np.array(map(int, newMessage))[4:]
    # print(np.array_equal(message_bits, viterbi_decode(thing, trellis, 5 * (M.sum() + 1))[:-M]))


    dataformats=BitArray(hex=compressedData.encode("hex"))
    message_bits=np.array(map(int,dataformats.bin))
    coded_bits = interlieve(rep_encode(message_bits, 3), 3)
    newMessage = "".join(map(str,coded_bits))
    encodedNew=b""
    for i in xrange(0,len(newMessage),8):
        encodedNew+=(struct.pack("B",int(newMessage[i:i+8],2)))
    return encodedNew

class fragmenter(object):
    def __init__(self,framesize,framesync):
        self.framesize=framesize
        self.framesync=int(framesync,2)
        self.packetnumber=0
    def fragment(self,data):
        pcktsize = len(data)
        data+=struct.pack("B",0)*((self.framesize-len(data)%self.framesize)%self.framesize)
        newdata=  [struct.pack("I",self.framesync)[1:]
                  +interlieve2(encode(
                   struct.pack("B",self.packetnumber)
                  +struct.pack("H",pcktsize)
                  +struct.pack("H",i)
                  )
                  ,data[i:i+self.framesize]) for i in xrange(0,len(data),self.framesize)]
        self.packetnumber =(self.packetnumber+1)%256
        # print([(len(i),self.framesize+8) for i in newdata ])
        return newdata
#all bytes of framesync must be unique
a=fragmenter(15,"01"*4+"0011"*2+"11"*4)
socket.setdefaulttimeout(1)
HOST = '0.0.0.0'    # The remote host
PORT = 80
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(1)
# msglen=255

# data=b"".join(struct.pack("B",i) for i in range(msglen))
ID=1754122158
dateFormat="%a, %d %b %Y %H:%M:%S %Z"
HTTPrequest=b"HTTP/1.1 200 OK\r\nCache-Control: no-cache, no-store\r\nPragma: no-cache\r\nContent-Length: 30\r\nContent-Type: text/html; charset=iso-8859-8\r\nExpires: -1\r\nServer: Microsoft-IIS/8.5\r\nX-AspNet-Version: 4.0.30319\r\nSet-Cookie: ASP.NET_SessionId=5jxc42k1m04pa30weih5y43s; path=/; HttpOnly\r\nX-Powered-By: ASP.NET\r\nDate: {date:%a, %d %b %Y %H:%M:%S %Z}\r\n\r\n0: Message sent, ID={id}"

with closing(s):
    while True:
        heartbeat=False
        try:
            conn, addr = s.accept()
            print("accepted")
            data = conn.recv(2048)
        except socket.timeout:
            random.seed("gonen")
            data=b"".join(struct.pack("B",random.randrange(16)) for _ in xrange(20))
            heartbeat=True
        else:
            try:
                conn.send(HTTPrequest.format(date=datetime.datetime.now(pytz.timezone("GMT")),id=ID))
            except (socket.error,socket.timeout) as e:
                print(str(e))
            else:
                ID+=1
            finally:
                conn.close()
        if data:
            compressedData=compress(data, content_checksum=1)
            encodedData=encode(compressedData)
            # encodedData=encode(data)

            for i in a.fragment(encodedData):
                ser.write(i)
            if not heartbeat:
                print("sent messege of %d bytes"%len(compressedData))
# while True:
#     ser.write(raw_input("what do you what to transmit?   "))

import asyncio
import re
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(sys.argv[0]))
from py_ntlm_mg import NtlmMessageGenerator
from log_template import log

headers_re = re.compile(rb'^([A-Z]+)\s.+Host:\s*(\S*)\s*', re.I|re.S)
def get_method_host(data):
    method,host = None,None
    ret = headers_re.search(data)
    if ret:
        method,host = ret.group(1),ret.group(2)
    return method,host 

challenge_re = re.compile(rb'Proxy-Authenticate: NTLM (\S*)\r\n', re.I)
def get_challenge(data):
    ret = challenge_re.search(data)
    if ret:
        return ret.group(1)
    return None

port_re = re.compile(rb'\S*:(\d+)$')
def get_port(host):
    ret = port_re.search(host)
    if ret:
        return ret.group(1)
    return None


class ProxyClientProtocol(asyncio.Protocol):
    def __init__(self, server_protocol, loop):
        self.loop = loop
        self.server_protocol = server_protocol
        self.is_ready = False
        
    def fmt(self,*args):
        return self.server_protocol.fmt(*args)

    def connection_made(self, transport):
        try:
            log.info(self.fmt('client connection_made!'))
            self.transport = transport
            self.ntlm = NtlmMessageGenerator()
            self.try_auth_ntlm()
        except Exception as e:
            log.exception(self.fmt(e))
            self.transport.close()
            self.server_protocol.transport.close()

    def hand_connect(self,data):
        http_code = data.split(maxsplit=2)[1]
        if http_code == b'407':
            challenge = get_challenge(data)
            if challenge:
                self.try_auth_ntlm(challenge)
                return
            else:
                log.error(self.fmt('auth failed ! data: ',data))
                self.transport.close()
                self.server_protocol.transport.close()

        self.is_ready = True
        self.server_protocol.transport.write(data)
        log.debug(self.fmt('response write : ',data))

    def data_received(self, data):
        try:
            log.debug(self.fmt('client receive : ',data))
            if not self.is_ready :
                return self.hand_connect(data)
            
            if self.server_protocol.transport.is_closing() :
                log.info(self.fmt('server transport is closing !'))
                self.transport.close()
                return

            log.debug(self.fmt('response write : ',data))
            self.server_protocol.transport.write(data)
        except Exception as e:
            log.exception(self.fmt(e,data))
            self.server_protocol.transport.close()
            self.transport.close()

    def connection_lost(self, exc):
        try:
            log.info(self.fmt('client connection_lost'))
            if not self.server_protocol.transport.is_closing():
                self.server_protocol.transport.close()
        except Exception as e:
            log.exception(self.fmt(e))


    def eof_received(self):
        try:
            log.info(self.fmt('client eof_received'))
            self.transport.close()
            if self.server_protocol.transport.can_write_eof() :
                self.server_protocol.transport.write_eof() 
        except Exception as e:
            log.exception(self.fmt(e))


    def try_auth_ntlm(self,challenge = b''):
        append_tmp = b'\r\nproxy-Authorization: NTLM %s\r\n\r\n'
        rep = self.ntlm.get_response(challenge.decode()).encode()
        append = append_tmp%(rep)      
        tmp = self.server_protocol.cache.split(b'\r\n\r\n',1)
        
        auth_data = tmp[0] + append
        if len(auth_data) == 2:
            auth_data += tmp[1]       
        log.debug(self.fmt('auth send : ',auth_data))
        self.transport.write(auth_data)


class ProxyServerProtocol(asyncio.Protocol):
    def __init__(self, loop):
        self.loop = loop
        self.cache = b''
        self.method = None
        self.host = None
        self.transport = None
        self.client_protocol = None
        self.peername = ''

    def fmt(self,*args):
        tmp = '{} '*(len(args)+1)
        return tmp.format(self.peername,*args)

    def client_connetc_cb(self,future):
        log.debug(self.fmt('server client_connetc_cb'))
        _, self.client_protocol = future.result()


    def connection_made(self, transport):
        self.transport = transport
        self.peername = self.transport.get_extra_info('peername')
        log.info(self.fmt('server connection_made'))
        connect_dict[self.peername] = datetime.now()

    def first_request_hand(self,data):
        self.method,self.host = get_method_host(data)
        if not self.method:
            log.error(self.fmt('request data error! ',data))
            self.transport.close()
            return
        if not get_port(self.host):
            port = b''
            line1 = data.split(maxsplit=2)[1]
            if b'http://' in line1:
                port = b':80'
            if b'https://' in line1:
                port = b':443'
            self.host += port
        # creat client connection in loop
        coro = self.loop.create_connection(lambda: ProxyClientProtocol(self, loop), PROXY_IP, PROXY_PORT)
        self.con_future = asyncio.ensure_future(coro)
        self.con_future.add_done_callback(self.client_connetc_cb)

    def data_received(self, data):
        try:
            log.debug(self.fmt('server receive : ',data))
            if not self.method :
                self.first_request_hand(data)

            if not self.client_protocol or not self.client_protocol.is_ready:
                self.cache += data
            else :
                log.debug(self.fmt('request write : ',data))
                self.client_protocol.transport.write(data)
        except Exception as e:
            log.exception(self.fmt(e,data))
            self.transport.close()
            

    def connection_lost(self, exc):
        try:
            log.info(self.fmt('server connection_lost'))
            del connect_dict[self.peername]
            if self.client_protocol and not self.client_protocol.transport.is_closing():
                self.client_protocol.transport.close()
        except Exception as e:
            log.exception(self.fmt(e))
 
    def eof_received(self):
        try:
            log.info(self.fmt('server eof_received'))
            if self.client_protocol and self.client_protocol.transport.can_write_eof():
                self.client_protocol.transport.write_eof()
        except Exception as e:
            log.exception(self.fmt(e))

connect_dict = {}
async def statistic():
    while server.sockets :
        log.warning('server state :   socket num {}'.format(len(connect_dict)))
        endtime = datetime.now()
        for k,v in connect_dict.items():
            usetime = (endtime - v).seconds
            if usetime > 120 :
                log.warning('{} in connecting time : {} s'.format(k,usetime))
        await asyncio.sleep(60)


PROXY_IP = 'proxyhk.com'
PROXY_PORT = 8080
LISTEN_IP = '127.0.0.1'
LISTEN_PORT = 3128


def prase_args():
    global PROXY_IP,PROXY_PORT,LISTEN_IP,LISTEN_PORT
    for i in range(len(sys.argv)):
        if "--proxy" in sys.argv[i]:
            k,v = sys.argv[i].split("=")
            PROXY_IP, PROXY_PORT = v.split(':')
            PROXY_PORT = int(PROXY_PORT)
        elif "--listen" in sys.argv[i]:
            k,v = sys.argv[i].split("=")
            LISTEN_IP, LISTEN_PORT = v.split(':')
            LISTEN_PORT = int(LISTEN_PORT)


if __name__ == "__main__":
    try:
        prase_args()
        loop = asyncio.ProactorEventLoop()
        # Each client connection will create a new protocol instance
        coro = loop.create_server(lambda: ProxyServerProtocol(loop), LISTEN_IP, LISTEN_PORT)
        server = loop.run_until_complete(coro)

        loop.create_task(statistic())
        # Serve requests until Ctrl+C is pressed
        log.warning('Serving on {} , proxy {}:{}'.format(server.sockets[0].getsockname(),PROXY_IP,LISTEN_PORT))
    except Exception as e:
        log.exception(e)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    # Close the server
    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()

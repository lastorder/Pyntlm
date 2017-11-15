# Pyntlm

Refer to [Px](https://github.com/genotrance/px) , use coroutine(asycio) to build a single thread proxy server.

Pyntlm is a HTTP proxy server that allows applications to authenticate through an NTLM proxy 
server, typically used in corporate deployments, without having to deal with the actual NTLM 
handshake. It is primarily designed to run on Windows systems and authenticates on behalf 
of the application using the currently logged in Windows user account.


### require
win7 or newer  
python 3.5 or newer  
winkerberos or pywin32(only python 3.5)  

	pip install winkerberos

### useage
	python py_ntlm.py --proxy=proxyserver.com:80 --listen=127.0.0.1:3128

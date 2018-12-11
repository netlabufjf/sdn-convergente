# API para envio de informacoes de aplicacoes paralelas ao controlador POX

import socket
from socket import error

SERVER_ADDR = '127.0.0.1'
SERVER_PORT = 7790
CHANNEL = 'upper'

class HPCMessenger:

        def __init__(self,addr=SERVER_ADDR,port=SERVER_PORT):
		self.addr = addr
		self.port = port
		self.data = ''

	def addAppData(self,app_type,port_ini,port_fin):
		self.data = 'add:' + app_type.lower() + ':' + str(port_ini) + ':' + str(port_fin)
		_sendData(self)

	def removeAppData(self,port_ini,port_fin):
		self.data = 'remove::' + str(port_ini) + ':' + str(port_fin)
		_sendData(self)

	def clearAppData(self):
		self.data = 'clear:::'
		_sendData(self)

	def setAlgAppMapping(self,app_type,alg):
		self.data = 'map:' + app_type.lower() + ':' + alg.lower() + ':'
		_sendData(self)

	def setAlgDefault(self,alg):
		self.data = 'alg:' + alg.lower() + '::'
		_sendData(self)

def _sendData(object):
	try:
		con = socket.create_connection((object.addr,object.port))
	except error as e:
		quit(e)
	msg = '{"CHANNEL":"' + CHANNEL + '","msg":"' + object.data + '"}'
	con.send(msg)
	con.close()

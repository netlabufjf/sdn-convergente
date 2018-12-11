# Modulo de tratamento de mensagens externas ao POX
# Administra o servico de recebimento de mensagens externas atraves de canal especifico

from pox.core import core
from pox.messenger import *

log = core.getLogger()

CHANNEL = 'upper'		# Canal de recebimento de mensagens externas

class UpperService(object):

        '''
        Manipula o recebimento de mensagens externas
        '''

        def __init__(self,parent,con,event):
                self.con = con
                self.parent = parent
                self.listeners = con.addListeners(self)

                self._handle_MessageReceived(event,event.msg)

        def _handle_ConnectionClosed(self,event):
                self.con.removeListeners(self.listeners)
                self.parent.clients.pop(self.con,None)

        def _handle_MessageReceived(self,event,msg):
		(command,param1,param2,param3) = msg['msg'].split(':')
		if command == 'add':
			for p in range(int(param2),int(param3)+1):
				core.L2_hpc.app_ports[p] = param1
		if command == 'remove':
			for p in range(int(param1),int(param2)+1):
				if core.L2_hpc.app_ports.has_key(p):
					del core.L2_hpc.app_ports[p]
		if command == 'clear':
			core.L2_hpc.app_ports.clear()
		if command == 'map':
			core.L2_hpc.alg_app[param1] = param2
		if command == 'alg':
			core.L2_hpc.alg_default = param1

class UpperBot(ChannelBot):

        '''
        Controla o servico de recebimento de mensagens externas
        '''

        def _init(self,extra):
                self.clients = {}

        def _unhandled(self,event):
                connection = event.con
                if connection not in self.clients:
                        self.clients[connection] = UpperService(self,connection,event)

def launch ():

	'''
	Inicia a instancia da classe UpperBot que controla
	o servico de recebimento de mensagens externas
	'''

	UpperBot(core.MessengerNexus.get_channel(CHANNEL))
	log.info('upper_hpc ready')

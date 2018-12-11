# Modulo de encaminhamento de trafego L2 POX
# Encaminha pacotes em ambientes convergentes com base em varios algoritmos de agendamento dinamico

from pox.core import core
import pox.openflow.libopenflow_01 as of
import pox.lib.packet as pkt
from pox.lib.addresses import EthAddr,IPAddr
from pox.lib.util import dpid_to_str
from pox.lib.recoco import Timer
import math
import hashlib
import dijkstra

log = core.getLogger()

############ Variaveis customizaveis ############
FLOW_IDLE_TIMEOUT = 20					# Tempo para exclusao de regras de encaminhamento ociosas
FLOW_HARD_TIMEOUT = 60					# Tempo para exclusao de regras de encaminhamento
TIMER = 20						# Tempo para inicio do calculo dos caminhos
ALG_DEFAULT = 'stp'					# Algoritmo default de agendamento
ALG_APP_MAP = {'mpi':'isolated','hadoop':'ecmp'}	# Mapeamento default de algoritmos e tipos de aplicacoes
#################################################

class L2_hpc(object):

	'''
	Encaminha pacotes em ambientes HPC com base
	em varios algoritmos de agendamento dinamico
	'''

	def __init__(self):
		self.hosts = {}			# Dicionario de hosts, cada qual contendo IP, switch e porta ao qual esta conectado, e MAC
		self.n_hosts = 0		# Numero de hosts considerando a topologia
		self.switches = {}		# Dicionario de switches, cada qual contendo ID, portas e respectivas taxas de trafego (TX + RX)
		self.adj = {}			# Dicionario de adjacencias, com chaves Link, contendo sw_src/port_src - sw_dst/port_dst
		self.paths = []			# Matriz que contem todos os caminhos, representados por listas, entre todos os switches
		self.inactive_paths = []	# Lista que contem os caminhos inativados temporariamente
		self.alg_default = ALG_DEFAULT	# Algoritmo de agendamento dinamico default
		self.alg_app = ALG_APP_MAP	# Dicionario de aplicacoes, cada qual contendo o algoritmo de agendamento
		self.app_ports = {}		# Dicionario de portas, cada qual contendo o tipo de aplicacao

		Timer(TIMER,self.setPATH,recurring=False)
		core.openflow.addListenerByName('PacketIn',self._handle_PacketIn)
		core.openflow.addListenerByName('PortStatus',self._handle_PortStatus)

	def _handle_PacketIn(self,event):
		packet = event.parsed

		# Funcao que atualiza a lista de hosts
		def updateHosts():
			for h in core.host_tracker.entryByMAC.keys():
				self.hosts[core.host_tracker.entryByMAC[h].ipAddrs.keys()[0]] = \
					[{'macaddr':core.host_tracker.entryByMAC[h].macaddr},\
					{'dpid':core.host_tracker.entryByMAC[h].dpid},\
					{'port':core.host_tracker.entryByMAC[h].port}]
		
		# Funcao que retorna um MAC conhecido a partir de um endereco IP
		def getMAC(ip):
			if len(self.hosts) < self.n_hosts:
				updateHosts()
			if self.hosts.has_key(ip):
				return self.hosts[ip][0]['macaddr']
			return False

		# Funcao que retorna o switch e a porta de um host a partir de um endereco IP
		def getSwitchPort(ip):
			if len(self.hosts) < self.n_hosts:
				updateHosts()
			if self.hosts.has_key(ip):	
				return (self.hosts[ip][1]['dpid'],self.hosts[ip][2]['port'])
			return False

		# Funcao que retorna a porta de conexao entre dois switches
		def getConnectionPort(sw_src,sw_dst):
			for a in self.adj.keys():
				if a.dpid1 == sw_src and a.dpid2 == sw_dst:
					return a.port1

		# Funcao que define o algoritmo de agendamento dinamico a partir da porta do pacote considerando o tipo de aplicacao
		def getAlgorithm():
			app = self.app_ports.get(packet.next.next.srcport)
			if not app:
				app = self.app_ports.get(packet.next.next.dstport)
				if not app:
					return self.alg_default
			return self.alg_app[app]

		# Funcao que ativa um caminho inativo
		def activatePATH(path):
			self.inactive_paths.remove(path)

		# Funcao que escolhe o melhor caminho entre dois switches a partir do trafego dos seus enlaces
		def getTrafficPATH(routes):
			rate = {}
			for i in range(len(routes)):
				rate[i] = 0		
				for j in range(len(routes[i])-1):
					sw_src = routes[i][j]
					sw_dst = routes[i][j+1]
					port = getConnectionPort(sw_src,sw_dst)
					_,traffic = self.switches[sw_src][port]
					rate[i] += traffic
			min_rate = rate[0]
			index = 0
			for i in range(len(routes)):
				if rate[i] < min_rate:
					min_rate = rate[i]
					index = i
			return routes[index]

		# Funcao que escolhe o melhor caminho entre dois switches considerando os caminhos inativos e uma funcao de hash
		def getIsolatedPATH(routes):
			rotas = routes[:]
			path = []
			while len(rotas):
				path = rotas[packet.next.id % len(rotas)]
				if path not in self.inactive_paths:
					self.inactive_paths.append(path)
					Timer(FLOW_HARD_TIMEOUT,activatePATH,args=[path],recurring=False)
					break
				rotas.remove(path)
			return path

		# Funcao que cria um ARP_REPLY a partir de um MAC conhecido
		def replyARP(a,mac):
			r = pkt.arp()
			r.hwtype = a.hwtype
			r.prototype = a.prototype
			r.hwlen = a.hwlen
			r.protolen = a.protolen
			r.opcode = pkt.arp.REPLY
			r.hwdst = a.hwsrc
			r.hwsrc = mac
			r.protodst = a.protosrc
			r.protosrc = a.protodst
       			e = pkt.ethernet(type=packet.type,dst=a.hwsrc)
			e.payload = r
			log.info('Switch %d answering ARP_REPLY for %s to port %s' %(event.dpid,str(a.protodst),event.port))
			msg = of.ofp_packet_out()
			msg.data = e.pack()
			msg.actions.append(of.ofp_action_output(port=event.port))
			event.connection.send(msg)

		# Funcao que encaminha um ARP_REQUEST aos hosts
		def forwardARP(a):
			for s in self.switches.keys():
				for p in self.switches[s].keys():
					if s == event.dpid and p == event.port:
						continue
					if p < 1000 and core.openflow_discovery.is_edge_port(s,p):
			       			e = pkt.ethernet(type=packet.type,src=a.hwsrc,dst=EthAddr('ff:ff:ff:ff:ff:ff'))
						log.info('Switch %d forwarding ARP_REQUEST for %s to port %s' %(s,str(a.protodst),p))
						e.payload = a
						msg = of.ofp_packet_out()
						msg.data = e.pack()
						msg.actions.append(of.ofp_action_output(port=p))
						core.openflow.getConnection(s).send(msg)

		# Funcao que encaminha um ARP_REPLY a partir de um ARP_REQUEST
		def sendARP(a):
			s,p = getSwitchPort(a.protodst)
			e = pkt.ethernet(type=packet.type,src=a.hwsrc,dst=a.hwdst)
			e.payload = a
			log.info('Switch %d answering ARP_REPLY for %s to port %s' %(s,str(a.protosrc),p))
			msg = of.ofp_packet_out()
			msg.data = e.pack()
			msg.actions.append(of.ofp_action_output(port=p))
			core.openflow.getConnection(s).send(msg)

		# Funcao que instala as regras de encaminhamento dos fluxos de pacotes nos respectivos switches				
		def forward():
			sw_dst,port_dst = getSwitchPort(packet.next.dstip)
			routes = self.getPATH(event.dpid,sw_dst)

			# Seleciona o algoritmo de agendamento dinamico
			alg = ''
			if packet.type == packet.IP_TYPE and packet.next.protocol != 1:
				alg = getAlgorithm()
			else:
				alg = self.alg_default

			# Seleciona o caminho de acordo com o algoritmo de agendamento dinamico aplicado
			if alg == 'stp':
				path = routes[0]
			elif alg == 'traffic':
				path = getTrafficPATH(routes)
			elif alg == 'ecmp':
				path = routes[packet.next.id % len(routes)]
			elif alg == 'isolated':
				path = getIsolatedPATH(routes)
			else:
				log.error('Unrecognized algorithm: %s. Applying first route' %alg)
				path = routes[0]
			if packet.type == packet.IP_TYPE and packet.next.protocol != 1:
				log.warning('Origem: %s:%d - Destino: %s:%d - %s route applied: %s' %(packet.next.srcip,packet.next.next.srcport,packet.next.dstip,packet.next.next.dstport,alg,path))
			else:
				log.warning('%s route applied: %s' %(alg,path))

			# Instala as regras de encaminhamento de pacotes
			for i in range(len(path)):
				if path[i] == sw_dst:
					out_port = port_dst
				else:
					out_port = getConnectionPort(path[i],path[i+1])
				msg = of.ofp_flow_mod()
			        msg.match = of.ofp_match.from_packet(packet)
				msg.idle_timeout = FLOW_IDLE_TIMEOUT
			        msg.hard_timeout = FLOW_HARD_TIMEOUT
				msg.actions.append(of.ofp_action_output(port=out_port))
				log.info('Installing flow in Switch %d - Port %s' %(path[i],str(out_port)))
				core.openflow.getConnection(path[i]).send(msg)

			# Encaminha os pacotes
			if len(path) == 1:
				out_port = port_dst
			else:
				out_port = getConnectionPort(path[0],path[1])
			msg = of.ofp_packet_out()
			msg.data = event.ofp
			msg.actions.append(of.ofp_action_output(port=out_port))
			event.connection.send(msg)

		##### Inicio do tratamento do PacketIn #####
		if packet.type == packet.ARP_TYPE:
			a = packet.find('arp')
			if a.opcode == pkt.arp.REQUEST:
				log.info('Switch %d receiving ARP_REQUEST for %s from port %s' %(event.dpid,str(a.protodst),event.port))
				mac = getMAC(a.protodst)
				if mac:
					replyARP(a,mac)
				else:
					forwardARP(a)
			else:
				log.info('Switch %d receiving ARP_REPLY for %s from port %s' %(event.dpid,str(a.protosrc),event.port))
				sendARP(a)
		elif packet.type == packet.IP_TYPE and packet.next.protocol == 17 and (packet.next.next.srcport == 67 or packet.next.next.srcport == 68):
			log.info('Switch %d receiving DHCP packet' %event.dpid)
		else:
			forward()

	def _handle_PortStatus(self,event):
		#Timer(TIMER,self.setPATH,recurring=False)
		pass

	# Funcao que preenche a lista de caminhos entre os switches
	def setPATH(self):
		cost = 1
	        adj_list = {}
		self.switches = core.Traffic.switches
		self.adj = core.openflow_discovery.adjacency.copy()
        	for s in self.switches.keys():
                	adj_list[s] = {}
	        for l in self.adj.keys():
        	        adj_list[l.dpid1][l.dpid2] = cost
		self.paths = dijkstra.dijkstra(adj_list)
		self.n_hosts = int((((math.sqrt((len(self.switches)*4)/5))**3)/4)+1)	# Numero de hosts para fat-tree de 3 niveis e 1 srv
		log.warning('Paths OK...')

	# Funcao que retorna uma lista com todos os caminhos entre dois switches
	def getPATH(self,sw_src,sw_dst):
		return self.paths[sw_src-1][sw_dst-1]

def launch():

	'''
	Registra a instancia da classe l2_hpc que
	encaminha trafego L2 em ambientes HPC
	'''

	def start():
		core.registerNew(L2_hpc)
		log.info('l2_hpc ready')

	core.call_when_ready(start,['openflow_discovery','host_tracker','MessengerNexus','Traffic'])
	if core._waiters:
		log.warning('Missing component... Shut down POX')
		core.quit()

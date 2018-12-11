# Modulo de inicializacao de componentes POX em ambientes convergentes

def launch(time='1'):

	from pox.openflow.discovery import launch
	launch()

	from pox.host_tracker import launch
	launch()

	from pox.messenger import launch
	launch()

	from pox.messenger.tcp_transport import launch
	launch()

	from upper_hpc import launch
	launch()

	from traffic import launch
	launch(time=time)

	from l2_hpc import launch
	launch()

	from pox.samples.pretty_log import launch
	launch()

	from pox.log.level import launch
	launch(WARNING=True)

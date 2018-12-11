#!/usr/bin/python

import time
from hpc_messenger import *

if __name__=='__main__':		#Funcao principal

	m = HPCMessenger()

	m.addAppData('mpi',22,22)
	time.sleep(0.01)
	m.addAppData('mpi',1024,1044)
	time.sleep(0.01)

	m.addAppData('hadoop',13562,13562)
	time.sleep(0.01)
	m.addAppData('hadoop',9000,9000)
	time.sleep(0.01)
	m.addAppData('hadoop',50010,50010)
	time.sleep(0.01)
	m.addAppData('hadoop',50020,50020)
	time.sleep(0.01)
	m.addAppData('hadoop',8030,8040)
	time.sleep(0.01)
	m.addAppData('hadoop',8480,8490)
	time.sleep(0.01)

	#m.removeAppData(1024,1044)
	#m.clearAppData()

	#m.setAlgAppMapping('mpi','isolated')
	#m.setAlgDefault('stp')

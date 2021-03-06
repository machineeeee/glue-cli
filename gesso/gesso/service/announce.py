# Send UDP broadcast packets
import os, sys
import time
import subprocess, psutil, tempfile, portalocker
import socket
import uuid
import logging
from tinydb import TinyDB, Query
from datetime import datetime
import json
from ..util import util

def start():

	logger = util.logger(__name__)

	sys.stdout.write('Starting broadcast service.')
	current_file_path = os.getcwdu()
	p = subprocess.Popen(['gesso', 'announce', 'run'], cwd=current_file_path)
	sys.stdout.write(' OK.\n')

	# Log status
	logger.info('Started broadcast service.')

def run(port=4445, broadcast_address='192.168.1.255', broadcast_timeout=2000):

	logger = util.logger(__name__)

	addresses = util.get_inet_addresses()

	# Write pid into pidfile
	current_dir = os.getcwd()
	pidfile_path = os.path.join(tempfile.gettempdir(), '%s.pid' % __name__)
	# TODO: get name of file for naming "gesso.<filename>.pid"
	# TODO: tempfile.NamedTemporaryFile(prefix='gesso.broadcast.', suffix='.pid').name
	pidfile = open(pidfile_path, "w+")
	#portalocker.lock(pidfile, portalocker.LOCK_EX) # lock the pidfile
	pidfile.write('%s' % os.getpid())
	pidfile.close()

	device_uuid = uuid.uuid4()

	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	#s.bind(('', 0))
	s.bind(('', port))
	s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

	s.setblocking(0)
	#s.settimeout(2)

	# "\f<content_length>\t<content_checksum>\t<content_type>\t<content>"
	# e.g., "\f52	16561	text	announce device 002fffff-ffff-ffff-4e45-3158200a0015"
	# data = "\f52\t16561\ttext\tannounce device 002fffff-ffff-ffff-4e45-3158200a0015";
	# data = "\f52\t33439\ttext\tannounce device f1aceb8b-e8e9-4cda-b29c-de7bc7cc390f"
	gesso_config = util.load_gessofile()
	broadcast_message = 'announce\n\n%s' % json.dumps(gesso_config)
	logger.info('%s' % broadcast_message)
	#broadcast_message = "announce device %s" % device_uuid

	while True:

		current_time = 0
		response_start_time = int(round(time.time() * 1000))

		while current_time - response_start_time < broadcast_timeout:
			try:
				# Receive UDP message
				message, fromaddr = s.recvfrom(1000)

				if not fromaddr[0] in addresses: # Prevents reading packets from the host machine (i.e., broadcasts don't loop back)

					# TODO: abstract this out based on 'requests' library abstraction level, then put it up on github and pip!
					if message.startswith("announce"):
						# Log status
						logger.info("Response from %s:%s: %s" % (fromaddr[0], fromaddr[1], message))

						# HACK
						# TODO: rename 'device' to something better...
						# TODO: don't populate this data here... create the structure on the sender's side
						message = message[len('announce'):].strip()
						device = json.loads(message)
						device['address'] = {}
						device['address']['ip4'] = fromaddr[0]
						device['time_created'] = datetime.utcnow().isoformat()
						device['time_updated'] = datetime.utcnow().isoformat()

						# Save device status in registry (in SQLite database)
						gesso_db_path = util.get_database_path()
						db = TinyDB(gesso_db_path, default_table='gesso')
						device_table = db.table('device')

						Device = Query()
						device_element = device_table.search(Device.name == device['name'])
						if len(device_element) == 0:
							device_table.insert(device)
						else:
							del device['time_created']
							device_table.update(device, Device.name == device['name'])

						# Create device folder if doesn't already exist
						gesso_root = util.get_gesso_root()

						gesso_folder = os.path.join(gesso_root, '.gesso')
						if not os.path.exists(gesso_folder):
							print 'mkdir %s' % gesso_folder
							os.makedirs(gesso_folder)

						device_folder = os.path.join(gesso_root, '.gesso', 'devices')
						if not os.path.exists(device_folder):
							print 'mkdir %s' % device_folder 
							os.makedirs(device_folder)

						machine_folder = os.path.join(gesso_root, '.gesso', 'devices', device['name'])
						if not os.path.exists(machine_folder):
							print 'mkdir %s' % machine_folder
							os.makedirs(machine_folder)

					elif message.startswith("echo"):
						response_message = message[len("echo") + 1:] # remove "echo " from start of string
						serverSocket.sendto(response_message, address)
					else:
						# Undefined message
						None

			except:
				# Timeout
				# TODO: Log exception!
				None

			current_time = int(round(time.time() * 1000))

		# Send periodic broadcast
		s.sendto(broadcast_message, (broadcast_address, port)) # Works

	s.close()

def stop():

	sys.stdout.write('Stopping broadcast service.')

	# Log status
	logger = util.logger(__name__)
	logger.info('Stopped broadcast service.')

	# Locate pidfile (if it exists)
	current_dir = os.getcwd()
	pidfile_path = os.path.join(tempfile.gettempdir(), '%s.pid' % __name__)

	# Read pid from pidfile
	pidfile = open(pidfile_path, "r")
	content = pidfile.readlines()
	pidfile.close()
	content = [x.strip() for x in content] # remove whitespace characters like `\n` at the end of each line
	# print content
	pid = int(content[0])

	# Kill process
	util.kill_proc_tree(pid)

	# Delete pidfile
	os.remove(pidfile_path)

	# Status
	sys.stdout.write(' OK.\n')

if __name__ == "__main__":
	run()

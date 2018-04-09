#
# Copyright (C) 2018  Fernando Arnaboldi
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import os
import signal
import subprocess
import threading
import time
import compat


class Execute(object):
	"""Thread being executed by Fuzzer"""
	def __init__(self, settings, piece, testcase):
		self.kill_status = None
		self.settings = settings
		self.results = {}
		self.t = threading.Thread(target=self.run_subprocess, args=(piece, testcase))
		self.t.start()
		self.deleteme = testcase['data']

	def join(self):
		"""Join the results to the thread"""
		try:
			self.t.join()
		except:
			pass

	def get_output(self):
		"""Delete the file as part of getting the output"""
		if self.deleteme and os.path.isfile(self.deleteme[0]['datafile'][1]):
			os.remove(self.deleteme[0]['datafile'][1])
		return self.results

	def kill_process(self, process):
		"""After the defined timeout, try to kill the process"""
		self.kill_status = self.settings['kill_status']['requested']
		if process.poll() is None:  # don't send the signal unless it seems it is necessary
			try:
				# Unix
				os.killpg(os.getpgid(process.pid), signal.SIGTERM)
				# Windows/Unix
				# process.kill()
				self.kill_status = self.settings['kill_status']['killed']
			except OSError:  # ignore
				self.kill_status = self.settings['kill_status']['not_killed']
		self.settings['logger'].debug("Killed process status: %s" % str(self.kill_status))

	def run_subprocess(self, piece, testcase):
		"""Obtain the stdout and stderr when executing a piece of software using subprocess"""
		self.settings['logger'].debug("Input received: " + str(testcase))
		stdout = stderr = elapsed = returncode = ""
		self.kill_status = self.settings['kill_status']['not_killed']
		start_test = time.time()
		if "execute" in piece:
			try:
				if 'stdin' in testcase:
					# Unix
					p = subprocess.Popen(testcase['execute'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
					# Windows/Unix
					# p = subprocess.Popen(testcase['execute'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
				else:
					# Unix
					p = subprocess.Popen(testcase['execute'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
					# Windows/Unix
					# p = subprocess.Popen(testcase['execute'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
				t = threading.Timer(self.settings['timeout'], self.kill_process, [p])
				t.start()
				if 'stdin' in testcase:
					stdout, stderr = p.communicate(input=testcase['stdin'])
				else:
					stdout, stderr = p.communicate()
				t.cancel()
				returncode = p.returncode
				stdout = compat.unicode(stdout.strip(), errors='ignore')
				stderr = compat.unicode(stderr.strip(), errors='ignore')
				stdout, stderr = self.analyze_results(stdout, stderr)
			except OSError:
				stderr = "Exception: OSErrorException"
			except KeyboardInterrupt:
				stderr = "Exception: KeyboardInterruptException"
			except Exception as e:
				stderr = "Exception: " + str(e)
		elapsed = str(round(time.time() - start_test, 4))
		self.results = {"softwareid": piece['softwareid'], "testcaseid": testcase['testcaseid'], "stdout": stdout, "stderr": stderr, "network": None, "returncode": returncode, "elapsed": elapsed, "kill_status": self.kill_status}
		self.settings['logger'].debug("Output produced: " + str(self.results))

	def analyze_results(self, stdout, stderr):
		"""Save full results for certain specific special strings"""
		if 'soft_bypass' in self.settings:
			full = False
			if any([x in stdout for x in self.settings['soft_bypass']]):
				full = True
			elif any([x in stderr for x in self.settings['soft_bypass']]):
				full = True
			if not full:
				stdout = stdout[:self.settings['soft_limit']]
				stderr = stderr[:self.settings['soft_limit']]
		if 'hard_limit' in self.settings:
			stdout = stdout[:self.settings['hard_limit']]
			stderr = stderr[:self.settings['hard_limit']]
		if 'hard_limit_lines' in self.settings:
			stdout = stdout.split("\n")[0]
		return stdout, stderr

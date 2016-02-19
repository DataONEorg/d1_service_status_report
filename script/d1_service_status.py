#!/usr/bin/env python
'''Script to output a chunk of JSON showing CN state.

This should be run as a cron job on CNs, every 5 min or so.
It needs to be privileged to determine service statuses.

TODO: Replace most of this with psutil
  https://pythonhosted.org/psutil/
  
Installing on Ubuntu 12, need to use pip as the distribution is very old. For
Ubuntu 14 and later, use apt

On ubuntu 12::

  sudo easy_install pip==1.4.1
  sudo pip install -U psutil
  
On ubuntu 14::

  sudo apt-get install python-psutil

e.g. /etc/cron.d/d1
'''
import sys
import os
import socket
import re
import datetime
import json
import commands

def getFQDN():
  res = commands.getstatusoutput("hostname -f")
  return res[1]


def getCPUNow(pid):
  '''Return the percentage of CPU use by process id.
  Using top, which is a more instant measure than ps which is load for the 
  entire duration of the process.
  '''
  outp = commands.getstatusoutput("top -p " + pid + " -n1 | awk '/ " + pid + " /{print $10}'")
  return outp[1].strip();


def getProcesses():
  '''Return list of [pid, args] for all processes on system
  '''
  res = []
  outp = commands.getstatusoutput("ps ax -o pid,etime,pcpu,pmem,args")
  tmp = outp[1].split("\n")
  for row in tmp:
    pid = row[0:5].strip()
    etime = row[5:17].strip()
    pcpu = row[17:22].strip()
    pmem = row[22:27].strip()
    args = row[27:].strip()
    res.append([pid, etime, pcpu, pmem, args])
  return res


def getServicePids(processes, match):
  '''
  '''
  pids = []
  for service in processes:
    if re.search(match, service[4]) is not None:
      data = service[0:4]
      #data[2] = getCPUNow(data[0])
      pids.append(data)
  return pids
  

def getProcessingEnablement():
  '''examine processing properties files and see what's going on
  '''
  to_examine = {'synchronization.properties':'Synchronization.active',
                'replication.properties':'Replication.active',
                'logAggregation.properties': 'LogAggregator.active' }
  base_path = "/etc/dataone/process/"
  res = {}
  for prop in to_examine.keys():
    res[to_examine[prop]] = False
    outp = commands.getstatusoutput("grep {0} {1}".format(to_examine[prop], os.path.join(base_path, prop)))
    outp = outp[1][ outp[1].find("=")+1: ]
    outp = outp.strip().lower()
    if outp == "true":
      res[to_examine[prop]] = True
  return res
  

def getCNStatus():
  services = {
    'SLAPD':'slapd',
    'tomcat7':"tomcat-.*.jar",
    'zookeeper':"zookeeper", 
    'd1-processing':"d1-processing", 
    'd1-index-task-generator':"d1-index-task-generator",
    'd1-index-task-processor':"d1-index-task-processor",
    'postgresql':'postgres: metacat metacat',
    }
  res = {'time_stamp': datetime.datetime.utcnow().isoformat(),
         'fqdn': getFQDN(),
          }
  res['ip_address'] = socket.gethostbyname(res['fqdn'])
  res['service_entries'] = ['PID','eTime','pCPU','pMEM']
  res['services'] = {}
  processes = getProcesses()
  for name in services.keys():
    res['services'][name] = getServicePids(processes, services[name])
  res['processing'] = getProcessingEnablement() 
  return res


if __name__ == "__main__":
  dest = "/var/www/d1_service_status.json"
  if len(sys.argv) > 1:
    dest = sys.argv[1]
  status_report = getCNStatus()
  if dest == "-":
    print(json.dumps(status_report, indent=2))
    exit(0)
  with open(dest,"w") as fout:
    json.dump(status_report, fout, indent=2)


#!/usr/bin/env python
'''Script to output a chunk of JSON showing CN state.

This should be run as a cron job on CNs, every 5 min or so.
It needs to be privileged to determine service statuses.

TODO: Replace most of this with psutil
  https://pythonhosted.org/psutil/

Run as 

  d1_service_status.py -  

to get outout on stdout.
'''
import sys
import os
import socket
import re
import datetime
import json
import subprocess
import urllib.request, urllib.error, urllib.parse
import time
import ssl
from OpenSSL import crypto
import logging

date_match = re.compile("\d*\-\d*\-\d*\s\d*:\d*:\d*")

def pingSelf(address):
  '''Call /v2/monitor/ping and record the result.
  '''
  url = "https://{0}/cn/v2/monitor/ping".format(address)
  t0 = time.perf_counter()
  try:
    res = urllib.request.urlopen(url, timeout=5)
  except urllib.error.HTTPError as e:
    return "FAIL : %s" % str(e)
  except ssl.SSLError as e:
    return "FAIL : %s" % str(e)

  t1 = time.perf_counter()
  delta = t1 - t0
  try:
    return "%s (%.3f sec)" % (res.headers['date'], delta)
  except:
    pass
  return 'FAIL (%.3f sec)' % delta


def loadNodeProperties(prop_file='/etc/dataone/node.properties'):
  '''load node properties into a dictionary
  '''
  result = {}
  with open(prop_file, 'r') as pf:
    for entry in pf.readlines():
      entry = entry.strip()
      if not entry.startswith('#'):
        # Valid property?
        try:
          k,v = entry.split("=", 1)
          result[k.strip()] = v.strip()
        except:
          pass
  return result


def checkCertificate(cert_file):
  res = {'file':cert_file}
  with open(cert_file, "rb") as cfile:
    x509 = crypto.load_certificate(crypto.FILETYPE_PEM, cfile.read())
  res['expired'] = x509.has_expired()
  res['not_before'] = x509.get_notBefore().decode()
  res['not_after'] = x509.get_notAfter().decode()
  return res


def checkCertificates(props):
  res = {}
  le_fn = os.path.join("/etc/letsencrypt/live", props['cn.router.hostname'], "cert.pem")
  if os.path.exists( le_fn ):
    res['wildcard'] = checkCertificate( le_fn )
  else:
    res['wildcard'] = checkCertificate( props['cn.server.publiccert.filename'] )

  server_cert = os.path.join('/etc/dataone/client/certs', props['cn.hostname']+".pem")
  res['server_fqdn'] = checkCertificate(server_cert)
  client_cert = os.path.join(props['D1Client.certificate.directory'], props['D1Client.certificate.filename'])
  res['client'] = checkCertificate(client_cert)
  postgres_cert_paths = ['/var/lib/postgresql/9.1/main/server.crt',
                         '/var/lib/postgresql/9.3/main/server.crt',
                         '/var/lib/postgresql/9.3/server.crt']
  for pgpath in postgres_cert_paths:
    try:
      res['postgres'] = checkCertificate('/var/lib/postgresql/9.1/main/server.crt')
    except IOError as e:
      res['postgres'] = {'file': 'NOT FOUND',
                         'expired':True,
                         'not_before':'00000000000000Z',
                         'not_after':'00000000000000Z' }
  return res


def checkSyncLogActivity():
  '''Look at cn-synchronization log to check for activity.
  
  egrep "INFO]\s(.*)V2TransferObjectTask:createObject" \
    /var/log/dataone/synchronize/cn-synchronization.log | tail -n1
    
  [ INFO] 2016-04-04 15:53:36,403 (V2TransferObjectTask:createObject:693) Task-urn:node:NCEI-{A8C0744B-B58C-4D4D-AE9C-E241ADC67D42} Creating Object
  '''
  #cmd = "egrep \"INFO]\s(.*)V2TransferObjectTask:createObject\" /var/log/dataone/synchronize/cn-synchronization.log | tail -n1"
  cmd = "egrep \"INFO]\s(.*)\s\" /var/log/dataone/synchronize/cn-synchronization.log | tail -n1"
  outp = subprocess.getstatusoutput(cmd)
  if outp[0] == 0:
    match = date_match.search(outp[1])
    if match is not None:
      tstr = match.group(0)
      dt = datetime.datetime.strptime(tstr, "%Y-%m-%d %H:%M:%S")
      return dt.isoformat() + "Z"
  return ''


def checkIndexGeneratorActivity():
  '''
  '''
  cmd = "egrep \"INFO](.*):entryUpdated\" /var/log/dataone/index/cn-index-generator-daemon.log | tail -n1"
  logging.debug('checkIndexGeneratorActivity: ' + cmd)
  outp = subprocess.getstatusoutput(cmd)
  if outp[0] == 0:
    match = date_match.search(outp[1])
    if match is not None:
      tstr = match.group(0)
      dt = datetime.datetime.strptime(tstr, "%Y-%m-%d %H:%M:%S")
      return dt.isoformat() + "Z"
  return ''


def checkIndexProcessorActivity():
  '''
  Indexing complete for pid
  '''
  cmd = "egrep \"INFO](.*)Indexing complete for pid:\" /var/log/dataone/index/cn-index-processor-daemon.log | tail -n1"
  outp = subprocess.getstatusoutput(cmd)
  if outp[0] == 0:
    match = date_match.search(outp[1])
    if match is not None:
      tstr = match.group(0)
      dt = datetime.datetime.strptime(tstr, "%Y-%m-%d %H:%M:%S")
      return dt.isoformat() + "Z"
  return ''


def getFQDN():
  res = subprocess.getstatusoutput("hostname -f")
  return str(res[1])


def getCPUNow(pid):
  '''Return the percentage of CPU use by process id.
  Using top, which is a more instant measure than ps which is load for the 
  entire duration of the process.
  '''
  outp = subprocess.getstatusoutput("top -p " + pid + " -n1 | awk '/ " + pid + " /{print $10}'")
  return outp[1].strip();


def getProcesses():
  '''Return list of [pid, args] for all processes on system
  '''
  res = []
  outp = subprocess.getstatusoutput("ps ax -o pid,etime,pcpu,pmem,args")
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
  '''Get the matching services from the list of all processes
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
  for prop in list(to_examine.keys()):
    res[to_examine[prop]] = False
    outp = subprocess.getstatusoutput("grep {0} {1}".format(to_examine[prop], os.path.join(base_path, prop)))
    outp = outp[1][ outp[1].find("=")+1: ]
    outp = outp.strip().lower()
    if outp == "true":
      res[to_examine[prop]] = True
  return res


def getConnections():
  '''Return the current number of connections in CLOSE_WAIT, ESTABLISHED
  '''
  n_cw = 0
  n_es = 0
  outp = subprocess.getstatusoutput("lsof -i")
  tmp = outp[1].split("\n")
  for row in tmp:
    if re.search("CLOSE_WAIT", row):
      n_cw += 1
    elif re.search("ESTABLISHED", row):
      n_es += 1
  return n_cw, n_es


def getHazelcastMembership(port=5701):
  url = "http://localhost:%d/hazelcast/rest/cluster" % port
  data = {'cluster':port,
          'members':[]}
  try:
    res = urllib.request.urlopen(url, timeout=2)
  except (socket.timeout, urllib.error.URLError) as e:
    return data
  body = res.read().decode().split("\n")
  for line in body:
    nmatch = re.search('Member\s*\[(.*)\]', line)
    if not nmatch is None:
      data['members'].append(nmatch.group(1))
  return data


def getIndexQueueStats():
  res = {}
  PSQL = "/usr/bin/psql -h localhost -U dataone_readonly d1-index-queue -A -F , -X -t"
  SQL = "COPY (SELECT status,COUNT(*) AS cnt FROM index_task GROUP BY status ORDER BY status) TO STDOUT WITH CSV;"
  cmd = PSQL + " -c \"" + SQL + "\""
  outp = subprocess.getstatusoutput(cmd)
  try:
    tmp = outp[1].split("\n")
    for row in tmp:
      rowd = row.split(",")
      res[rowd[0]] = int(rowd[1])
  except Exception as e:
    logging.error(e)
  return res


def getCNStatus():
  '''Main method for gathering stats.
  '''
  # List of services to examine, key is used for output status, value is the string to match on
  services = {
    'SLAPD':'slapd',
    'tomcat7':"tomcat-.*.jar",
    'zookeeper':"zookeeper", 
    'd1-processing':"d1-processing", 
    'd1-index-task-generator':"d1-index-task-generator",
    'd1-index-task-processor':"d1-index-task-processor",
    'postgresql':'postgres: metacat metacat',
    }
  
  #Load the node properties
  properties = loadNodeProperties()
  fqdn = getFQDN()
  
  # Results are added to this structure, which is finally output as JSON
  res = {'time_stamp': datetime.datetime.utcnow().isoformat() + 'Z',
         'fqdn': fqdn,
          }
  res['ping'] = pingSelf(fqdn)
  res['close_waits'], res['established'] = getConnections()
  res['ip_address'] = socket.gethostbyname(res['fqdn'])
  res['service_entries'] = ['PID','eTime','pCPU','pMEM']
  res['services'] = {}
  processes = getProcesses()
  for name in list(services.keys()):
    res['services'][name] = getServicePids(processes, services[name])
  res['processing'] = getProcessingEnablement()
  res['certificates'] = checkCertificates(properties)
  res['logs'] = {'synchronization': '',
                 'replication':'',
                 'logaggregation':'',
                 'indexgenerator':'',
                 'indexprocessor': '',
                 }
  res['logs']['synchronization'] = checkSyncLogActivity()
  res['logs']['indexgenerator'] = checkIndexGeneratorActivity()
  res['logs']['indexprocessor'] = checkIndexProcessorActivity()
  res['hazelcast'] = []
  for port in [5701, 5702, 5703]:
    res['hazelcast'].append(getHazelcastMembership(port))
  #res['indexing'] = {'queue': getIndexQueueStats()}
  return res


if __name__ == "__main__":
  dest = "/var/www/d1_service_status.json"
  logging.basicConfig(level=logging.WARN)
  if len(sys.argv) > 1:
    dest = sys.argv[1]
  status_report = getCNStatus()
  if dest == "-":
    print((json.dumps(status_report, indent=2)))
    exit(0)
  with open(dest,"w") as fout:
    json.dump(status_report, fout, indent=2)


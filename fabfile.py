'''Fabric script to deploy d1_service_status.py script to CNs

For an initial deployment::

  export CN=cn-dev-unm-1.test.dataone.org
  fab -I -H ${CN} deployToCN
  

To update an existing deployment::

  export CN=cn-dev-unm-1.test.dataone.org
  fab -H ${CN} updateDeployedScript

'''
import os
from fabric.api import run, sudo, put, quiet

'''
HOSTS="cn-dev-ucsb-1.test.dataone.org,cn-dev-unm-1.test.dataone.org,cn-dev-orc-1.test.dataone.org"
fab -I -H ${HOSTS} updateDeployedScript
HOSTS="cn-dev-ucsb-2.test.dataone.org,cn-dev-unm-2.test.dataone.org"
fab -I -H ${HOSTS} updateDeployedScript
HOSTS="cn-sandbox-ucsb-1.test.dataone.org,cn-sandbox-unm-1.test.dataone.org,cn-sandbox-orc-1.test.dataone.org"
fab -I -H ${HOSTS} updateDeployedScript
HOSTS="cn-sandbox-ucsb-1.test.dataone.org"
fab -I -H ${HOSTS} updateDeployedScript
HOSTS="cn-stage-ucsb-1.test.dataone.org,cn-stage-unm-1.test.dataone.org,cn-stage-orc-1.test.dataone.org"
fab -I -H ${HOSTS} updateDeployedScript
HOSTS="cn-stage-unm-2.test.dataone.org"
fab -I -H ${HOSTS} updateDeployedScript
HOSTS="cn-ucsb-1.dataone.org,cn-unm-1.dataone.org,cn-orc-1.dataone.org"
fab -I -H ${HOSTS} updateDeployedScript
'''

SCRIPT_FILE = "d1_service_status.py"
CROND_FILE = "d1_service_status_cron" 

def updateDeployedScript():
  '''
  Overwrite the deployed script with the current one.
  '''
  put(os.path.join('script/',SCRIPT_FILE), "/usr/local/bin", use_sudo=True, mode=0755)
  sudo("/usr/local/bin/d1_service_status -")


def deployToCN():
  '''Deploy the script, create a symlink, and add to cron
  '''
  put(os.path.join('script/',SCRIPT_FILE), "/usr/local/bin", use_sudo=True)
  run( "chmod a+x /usr/local/bin/" + SCRIPT_FILE )
  with quiet():
    sudo( "rm /usr/local/bin/d1_service_status")
    sudo( "ln -s /usr/local/bin/" + SCRIPT_FILE + " /usr/local/bin/d1_service_status" )
  #cron.d file must be owned by root and writable only by root.
  put(os.path.join('script/', CROND_FILE), "/etc/cron.d/", use_sudo=True, mode=0644)
  sudo( "chown root:root /etc/cron.d/" + CROND_FILE)
  run("/usr/local/bin/d1_service_status -")

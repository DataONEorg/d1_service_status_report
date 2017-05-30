'''Fabric script to deploy d1_service_status.py script to CNs

For an initial deployment::

  export CN=cn-dev-unm-1.test.dataone.org
  fab -I -H ${CN} deployToCN
  

To update an existing deployment::

  export CN=cn-dev-unm-1.test.dataone.org
  fab -H ${CN} updateDeployedScript

'''
import os
from fabric.api import env, run, sudo, put, quiet, parallel
from fabric.contrib.project import rsync_project

SCRIPT_FILE = "d1_service_status.py"
CROND_FILE = "d1_service_status_cron" 


@parallel                                
def updateDeployedScript():
  '''
  Overwrite the deployed script with the current one.
  
  e.g. 
  
  fab -I -H cn-dev-unm-1.test.dataone.org updateDeployedScript
  '''
  put(os.path.join('script/',SCRIPT_FILE), "/usr/local/bin", use_sudo=True, mode=0755)
  sudo("/usr/local/bin/d1_service_status -")


def deployToCN():
  '''Deploy the script, create a symlink, and add to cron
  
  e.g.:
    fab -I -H cn-dev-unm-1.test.dataone.org deployToCN
  '''
  put(os.path.join('script/',SCRIPT_FILE), "/usr/local/bin", use_sudo=True)
  run( "chmod a+x /usr/local/bin/" + SCRIPT_FILE )
  with quiet():
    sudo( "rm /usr/local/bin/d1_service_status")
    sudo( "ln -s /usr/local/bin/" + SCRIPT_FILE + " /usr/local/bin/d1_service_status" )
  #cron.d file must be owned by root and writable only by root.
  put(os.path.join('script/', CROND_FILE), "/etc/cron.d/", use_sudo=True, mode=0644)
  sudo( "chown root:root /etc/cron.d/" + CROND_FILE)
  sudo("/usr/local/bin/d1_service_status -")
  
  
def updateWebSite():
  '''run rsync to update site on monitor.dataone.org
  
  e.g.:
    fab -I -H monitor.dataone.org updateWebSite
  '''
  rsync_project('/var/www/status/', 
                local_dir='www/')
  

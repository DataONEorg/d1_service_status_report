# d1_service_status_report

Generates a report on Coordinating Node services for DataONE administrators.

There are two parts to this product:

1. A python script that gathers information and outputs a JSON file to a web 
   accessible location.

2. A HTML + javascript page that loads the JSON from different CNs and renders
   the data to provide a general status per environment.
   

## Installation

To install the data collection script the simplest is to use the provided fabric
script like:

```
export HOSTS="cn-dev-ucsb-1.test.dataone.org,cn-dev-unm-1.test.dataone.org,cn-dev-orc-1.test.dataone.org"
fab -I -H ${HOSTS} deployToCN
``` 

Or alternatively, by hand, copy the d1_service_status.py script to the target
CN, then:

```
sudo cp d1_service_status.py /usr/local/bin
sudo chmod a+x /usr/local/bin/d1_service_status.py
sudo ln -s /usr/local/bin/d1_service_status.py /usr/local/bin/d1_service_status

# verify operation
d1_service_status -

# Install cron task
sudo vi /etc/cron.d/d1_service_status_cron
#contents:

# Generate some status info for admins
# Generates JSON file /var/www/d1_service_status.json
#
* * * * * root /usr/local/bin/d1_service_status

sudo chown root:root /etc/cron.d/d1_service_status_cron
sudo chmod 711 /etc/cron.d/d1_service_status_cron
```

The script should output to /var/www/d1_service_status.json which will be
accessible at https://domain.name/d1_service_status.json


To install the web page:

```
mkdir /var/www/status
# copy d1_service_status.html, css, and images into /var/www/status
ln -s /var/www/status/d1_service_status.html /var/www/status/index.html
```

Apache config:

```
RewriteEngine on
RewriteCond %{THE_REQUEST} "/status/__ajaxproxy/https://cn(.*)dataone.org(.*)"
RewriteRule "^/status/__ajaxproxy/(.*)$" "$1" [P,L,NE]
```

## Operation


```
               +--------------------------+
               |                          |
               |  d1_service_status.html  |
               |                          |
               +------------^-------------+
                            |
                            //
                            |
                +-----------+------------+
                |                        |
                | d1_service_status.json |
                |                        |
                +-----------^------------+
                            |
                            |
                 +----------+------------+
                 |                       |
            +----> d1_service_status.py  <--------+
            |    |                       |        |
            |    +-----------------------+        |
            |                                     |
            |                                     |
+-----------+-----------+     +-------------------+----------------+
|                       |     |                                    |
|  Processing Config    |     |           Process List             |
|                       |     |                                    |
| /etc/dataone/process  |     |  ps ax -o pid,etime,pcpu,pmem,args |
|                       |     |                                    |
+-----------------------+     +------------------------------------+

```

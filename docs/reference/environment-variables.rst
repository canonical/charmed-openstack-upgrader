=====================
Environment Variables
=====================

* **JUJU_DATA** - sets the path containing Juju configuration files (e.g. credentials.yaml).
  The default value is **~/.local/share/juju**
* **COU_TIMEOUT** - defines timeout for **COU** retry policy. The default value is 10 seconds.
* **COU_MODEL_RETRIES** - defines how many times to retry the connection to Juju model before
  giving up. The default value is 5 times.
* **COU_MODEL_RETRY_BACKOFF** - defines by how many seconds the wait between juju model
  connection retry attempts will be increased every time an attempt fails. The default value
  is 2 seconds.
* **COU_STANDARD_IDLE_TIMEOUT** - defines how long **COU** will wait for an application to settle
  to **active/idle** and declare the upgrade complete. The default value is 300 seconds.
* **COU_LONG_IDLE_TIMEOUT** - a longer version of **COU_STANDARD_IDLE_TIMEOUT** for applications
  that are known to need more time than usual to upgrade, such as Keystone and Octavia. The
  default value is 2400 seconds.

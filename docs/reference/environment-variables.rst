=====================
Environment Variables
=====================

* **JUJU_DATA** - sets the path containing Juju configuration files (e.g. credentials.yaml). Defaults to ~/.local/share/juju
* **COU_TIMEOUT** - define timeout for **COU** retry policy. Default value is 10 seconds.
* **COU_MODEL_RETRIES** - define how many times to retry the connection to Juju model before giving up. Default value is 5 times.
* **COU_MODEL_RETRY_BACKOFF** - define number of seconds to increase the wait between connection to the Juju model retry attempts. Default value is 2 seconds.
* **COU_STANDARD_IDLE_TIMEOUT** - define the idle timeout to check if the application has upgraded. Default value is 300 seconds.
* **COU_LONG_IDLE_TIMEOUT** - define the idle timeout for applications that take more time than usual to upgrade like, for example, Keystone and Octavia. Default value is 1800 seconds.

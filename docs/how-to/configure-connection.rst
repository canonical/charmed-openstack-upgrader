=================================
Change model connection behaviour
=================================

There are three variables through which the connection behaviour to the Juju model
can be tuned. This may be necessary if **COU** is run from behind a VPN or if the network
is heavily used.

* **COU_TIMEOUT** - sets the timeout of retries for any calls by Model to libjuju.
  It's unit-less and the number represents the number of seconds. Defaults to 10 seconds.

* **COU_MODEL_RETRIES** - sets how many times to retry connecting to the Juju model
  before giving up. Defaults to 5.

* **COU_MODEL_RETRY_BACKOFF** - sets the number of seconds in between connection retry
  attempts (for example, a backoff of 10 with 3 retries would wait 10s, 20s, and 30s).
  It's unit-less and the number represents the number of seconds. Defaults to 2 seconds.

Usage example
-------------

.. code:: bash

    COU_TIMEOUT=120 cou upgrade

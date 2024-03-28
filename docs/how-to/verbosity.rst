======================
Change verbosity level
======================

Using the **verbose** parameter enables the adjustment of verbosity levels. 
This parameter can be specified repeatedly, up to three times, to escalate the
verbosity from the warning level up to the debug log level.

The default verbosity level is **warning**.

Usage examples
--------------

The info level.

.. code:: bash

    cou upgrade -v

The debug level for all messages except **python-libjuju** and **websockets**.

.. code:: bash
    
    cou upgrade -vv

The debug level for all messages including the **python-libjuju** and **websockets**.

.. code:: bash

    cou upgrade -vvv

======================
Change verbosity level
======================

The verbose parameter can be used to increase the verbosity level. The parameter
can be used multiple times (up to four), increasing verbosity from error to debug
log level.

The default verbosity level is **error**.

Usage examples
~~~~~~~~~~~~~~

The warning level.

.. code:: 

    $ cou upgrade -v

The info level.

.. code:: 
    
    $ cou upgrade -vv

The debug level for all messages except **python-libjuju** and **websockets**.

.. code:: 

    $ cou upgrade -vvv

The debug level for all messages including the **python-libjuju** and **websockets**.

.. code:: 
    
    $ cou upgrade -vvvv
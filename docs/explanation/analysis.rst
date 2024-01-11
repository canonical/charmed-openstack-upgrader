========
Analysis
========

This phase is responsible for obtaining all the required OpenStack cloud information
from Juju: the model status and the configuration for each application is obtained
and stored in an Analysis object, divided into control and data plane. Each
application is represented by a generic **OpenStackApplication** class or by a custom
subclass, e.g. **Keystone(OpenStackApplication)**.

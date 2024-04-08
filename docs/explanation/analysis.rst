========
Analysis
========

This phase is responsible for gathering all essential information about the OpenStack
cloud from Juju. It collects the model status, details about each application including
its units and configurations, and information about machines hosting these applications.
These data are stored in an Analysis object, which organises applications into control-plane
and data-plane components.

Each application is represented by a generic **OpenStackApplication** class or by a custom
subclass, e.g. **Keystone(OpenStackApplication)**. Each unit is represented by a `Unit`
class. Each machine is represented by a `Machine` class.

"""EvolvXSI route policy: which model routes may process which data classes.

A *route kind* (local, private or cloud) is assigned to each registered model
provider. The policy lists, for each data class, the route kinds that may
process it. A request to a blocked route fails before any content is sent.
This package is EvolvXSI code, kept apart from the adapted upstream modules.
"""

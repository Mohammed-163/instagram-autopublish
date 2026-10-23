"""
Cross-cutting architecture pieces shared by the whole `database` layer:

- core.events        Domain Events (predefined, typed — never raw strings)
- core.event_bus      Event Bus (publish/subscribe; services never call each
                       other directly)
- core.container       Dependency Injection container (Service -> Injected
                       Repository -> Database)
- core.scheduler      Scheduler interface (no implementation yet on purpose)
"""

"""
Base class for the service mix-ins.
"""

import json
import logging
import importlib

from typing import Callable, Dict

_LOG = logging.getLogger(__name__)


class Service:
    """
    An abstract base of all environment services.
    """

    @classmethod
    def new(cls, class_name: str, config: dict, parent):
        """
        Factory method for a new service with a given config.

        Parameters
        ----------
        class_name: str
            FQN of a Python class to instantiate, e.g.,
            "mlos_bench.environment.azure.AzureVMService".
            Must be derived from the `Service` class.
        config : dict
            Free-format dictionary that contains the service configuration.
            It will be passed as a constructor parameter of the class
            specified by `class_name`.
        parent : Service
            A parent service that can provide mixin functions.

        Returns
        -------
        svc : Service
            An instance of the `Service` class initialized with `config`.
        """
        # We need to import mlos_bench to make the factory methods
        # like `Service.new()` work.
        class_name_split = class_name.split(".")
        module_name = ".".join(class_name_split[:-1])
        class_id = class_name_split[-1]

        env_module = importlib.import_module(module_name)
        svc_class = getattr(env_module, class_id)
        _LOG.info("Instantiating: %s :: %s", class_name, svc_class)

        assert issubclass(svc_class, cls)
        return svc_class(config, parent)

    def __init__(self, config: dict = None, parent=None):
        """
        Create a new service with a given config.

        Parameters
        ----------
        config : dict
            Free-format dictionary that contains the service configuration.
            It will be passed as a constructor parameter of the class
            specified by `class_name`.
        parent : Service
            An optional parent service that can provide mixin functions.
        """
        self.config = config or {}
        self._parent = parent
        self._services = {}

        if parent:
            self.register(parent.export())

        if _LOG.isEnabledFor(logging.DEBUG):
            _LOG.debug("Service: %s Config:\n%s",
                       self.__class__.__name__, json.dumps(self.config, indent=2))
            _LOG.debug("Service: %s Parent mixins: %s",
                       self.__class__.__name__,
                       [] if parent is None else list(parent._services.keys()))

    def register(self, services):
        """
        Register new mix-in services.

        Parameters
        ----------
        services : dict or list
            A dictionary of string -> function pairs.
        """
        if not isinstance(services, dict):
            services = {svc.__name__: svc for svc in services}

        if _LOG.isEnabledFor(logging.DEBUG):
            _LOG.debug("Service: %s Add methods: %s",
                       self.__class__.__name__, list(services.keys()))

        self._services.update(services)
        self.__dict__.update(self._services)

    def export(self) -> Dict[str, Callable]:
        """
        Return a dictionary of functions available in this service.

        Returns
        -------
        services : dict
            A dictionary of string -> function pairs.
        """
        return self._services

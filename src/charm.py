#!/usr/bin/env python3
# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

"""Simple, hacky charm to deploy Parca for monitoring a Juju controller."""

import logging
from subprocess import CalledProcessError, check_call

from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointConsumer
from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

from parca import Parca, ParcaInstallError

logger = logging.getLogger(__name__)


class ParcaOperatorCharm(CharmBase):
    """Simple, hacky charm to deploy Parca for monitoring a Juju controller."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._install)
        self.framework.observe(self.on.start, self._start)
        self.framework.observe(self.on.config_changed, self._config_changed)
        self.framework.observe(self.on.remove, self._remove)

        self.parca = Parca()

        self.metrics_consumer = MetricsEndpointConsumer(self)

        self.framework.observe(
            self.metrics_consumer.on.targets_changed, self._on_scrape_targets_changed
        )

    def _install(self, _):
        """Install dependencies for Parca and ensure initial configs are written."""
        self.unit.status = MaintenanceStatus("installing parca")
        try:
            self.parca.install()
        except ParcaInstallError as e:
            self.unit.status = BlockedStatus(str(e))

    def _start(self, _):
        """Start both the Parca service and the Juju Introspect service."""
        self.parca.start()
        self._open_port()
        self.unit.status = ActiveStatus()

    def _config_changed(self, _):
        """Update the configuration files, restart parca."""
        self.unit.status = MaintenanceStatus("reconfiguring parca")
        scrape_config = self.metrics_consumer.jobs()
        self.parca.configure(self.config, scrape_config)
        self.unit.status = ActiveStatus()

    def _remove(self, _):
        self.unit.status = MaintenanceStatus("removing parca and juju-introspect")
        self.parca.remove()

    def _on_scrape_targets_changed(self, _):
        self.unit.status = MaintenanceStatus("reconfiguring parca")
        self.parca.configure(self.config, self.metrics_consumer.jobs())
        self.unit.status = ActiveStatus()

    def _open_port(self) -> bool:
        """Ensure that Juju opens the correct TCP port for the Parca Dashboard."""
        try:
            check_call(["open-port", "7070/TCP"])
            return True
        except CalledProcessError as e:
            logger.error("error opening port: %s", str(e))
            logger.debug(e, exc_info=True)
            return False


if __name__ == "__main__":  # pragma: nocover
    main(ParcaOperatorCharm)

# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
VPCS device implementation.
"""

import os
import base64
from gns3.node import Node
from gns3.ports.port import Port
from gns3.ports.ethernet_port import EthernetPort

import logging
log = logging.getLogger(__name__)


class VPCSDevice(Node):
    """
    VPCS device.

    :param module: parent module for this node
    :param server: GNS3 server instance
    """

    def __init__(self, module, server):
        Node.__init__(self, server)

        log.info("VPCS instance is being created")
        self._vpcs_id = None
        self._defaults = {}
        self._inital_settings = None
        self._loading = False
        self._module = module
        self._ports = []
        self._settings = {"name": "",
                          "base_script_file": "",
                          "path":"",
                          "console": None}

        #self._occupied_slots = []
        self._addAdapters(1)

        # save the default settings
        self._defaults = self._settings.copy()

    def _addAdapters(self, nb_ethernet_adapters):
        """
        Adds ports based on what adapter is inserted in which slot.

        :param adapter: adapter name
        :param slot_number: slot number (integer)
        """

        nb_adapters = nb_ethernet_adapters
        for slot_number in range(0, nb_adapters):
#             if slot_number in self._occupied_slots:
#                 continue
            for port_number in range(0, 1):
                if slot_number < nb_ethernet_adapters:
                    port = EthernetPort
                port_name = port.longNameType() + str(slot_number) + "/" + str(port_number)
                new_port = port(port_name)
                new_port.setPortNumber(port_number)
                new_port.setSlotNumber(slot_number)
                #self._occupied_slots.append(slot_number)
                self._ports.append(new_port)
                log.debug("port {} has been added".format(port_name))

    def _removeAdapters(self, nb_ethernet_adapters):
        """
        Removes ports when an adapter is removed from a slot.

        :param slot_number: slot number (integer)
        """

        for port in self._ports.copy():
            if (port.slotNumber() >= nb_ethernet_adapters and port.linkType() == "Ethernet"):
                #self._occupied_slots.remove(port.slotNumber())
                self._ports.remove(port)
                log.info("port {} has been removed".format(port.name()))

    def setup(self, vpcs_path, name=None, base_script_file=None, initial_settings={}):
        """
        Setups this VPCS device.

        :param name: optional name
        """
        params = {"path": vpcs_path}

        if name:
            params["name"] = self._settings["name"] = name

        if base_script_file:
            params["base_script_file"] = self._settings["base_script_file"] = base_script_file
            params["base_script_file_base64"] = self._base64Config(base_script_file)

        # other initial settings will be applied when the router has been created
        if initial_settings:
            self._inital_settings = initial_settings

        self._server.send_message("vpcs.create", params, self._setupCallback)

    def _setupCallback(self, result, error=False):
        """
        Callback for setup.

        :param result: server response
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while setting up {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["code"], result["message"])
            return

        self._vpcs_id = result["id"]
        if not self._vpcs_id:
            self.error_signal.emit(self.id(), "returned ID from server is null")
            return

        # update the settings using the defaults sent by the server
        for name, value in result.items():
            if name in self._settings and self._settings[name] != value:
                log.info("VPCS instance setting up and updating {} from '{}' to '{}'".format(name, self._settings[name], value))
                self._settings[name] = value

        # update the node with setup initial settings if any
        if self._inital_settings:
            self.update(self._inital_settings)
        elif self._loading:
            self.updated_signal.emit()
        else:
            self.setInitialized(True)
            log.info("VPCS instance {} has been created".format(self.name()))
            self.created_signal.emit(self.id())
            self._module.addNode(self)

    def delete(self):
        """
        Deletes this VPCS instance.
        """

        log.debug("VPCS device {} is being deleted".format(self.name()))
        # first delete all the links attached to this node
        self.delete_links_signal.emit()
        if self._vpcs_id:
            self._server.send_message("vpcs.delete", {"id": self._vpcs_id}, self._deleteCallback)
        else:
            self.deleted_signal.emit()
            self._module.removeNode(self)

    def _deleteCallback(self, result, error=False):
        """
        Callback for delete.

        :param result: server response
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while deleting {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["code"], result["message"])
        log.info("{} has been deleted".format(self.name()))
        self.deleted_signal.emit()
        self._module.removeNode(self)

    def _base64Config(self, config_path):
        """
        Get the base64 encoded config from a file.

        :param config_path: path to the configuration file.

        :returns: base64 encoded string
        """

        try:
            with open(config_path, "r") as f:
                log.info("opening configuration file: {}".format(config_path))
                config = f.read()
                config = '!\n' + config.replace('\r', "")
                encoded = ("").join(base64.encodestring(config.encode("utf-8")).decode("utf-8").split())
                return encoded
        except OSError as e:
            log.warn("could not base64 encode {}: {}".format(config_path, e))
            return ""


    def update(self, new_settings):
        """
        Updates the settings for this VPCS device.

        :param new_settings: settings dictionary
        """

        params = {"id": self._vpcs_id}
        for name, value in new_settings.items():
            if name in self._settings and self._settings[name] != value:
                params[name] = value

        if "base_script_file" in new_settings and self._settings["base_script_file"] != new_settings["base_script_file"] \
        and os.path.isfile(new_settings["base_script_file"]):
            params["base_script_file_base64"] = self._base64Config(new_settings["base_script_file"])

        log.debug("{} is updating settings: {}".format(self.name(), params))
        self._server.send_message("vpcs.update", params, self._updateCallback)

    def _updateCallback(self, result, error=False):
        """
        Callback for update.

        :param result: server response
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while deleting {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["code"], result["message"])
            return

        updated = False
        nb_adapters_changed = False
        for name, value in result.items():
            if name in self._settings and self._settings[name] != value:
                log.info("{}: updating {} from '{}' to '{}'".format(self.name(), name, self._settings[name], value))
                updated = True
                if (name == "ethernet_adapters" or name == "serial_adapters"):
                    nb_adapters_changed = True
                self._settings[name] = value

        if nb_adapters_changed:
            log.debug("number of adapters has changed: Ethernet={} Serial={}".format(self._settings["ethernet_adapters"], self._settings["serial_adapters"]))
            #TODO: dynamically add/remove adapters
            self._ports.clear()
            self._addAdapters(self._settings["ethernet_adapters"], self._settings["serial_adapters"])

        if self._inital_settings and not self._loading:
            self.setInitialized(True)
            log.info("VPCS device {} has been created".format(self.name()))
            self.created_signal.emit(self.id())
            self._module.addNode(self)
            self._inital_settings = None
        elif updated or self._loading:
            log.info("VPCS device {} has been updated".format(self.name()))
            self.updated_signal.emit()

    def start(self):
        """
        Starts this VPCS instance.
        """

        log.debug("{} is starting".format(self.name()))
        self._server.send_message("vpcs.start", {"id": self._vpcs_id}, self._startCallback)

    def _startCallback(self, result, error=False):
        """
        Callback for start.

        :param result: server response
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while starting {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["code"], result["message"])
        else:
            log.info("{} has started".format(self.name()))
            self.setStatus(Node.started)
            for port in self._ports:
                # set ports as started
                port.setStatus(Port.started)
            self.started_signal.emit()

    def stop(self):
        """
        Stops this VPCS instance.
        """

        log.debug("{} is stopping".format(self.name()))
        self._server.send_message("vpcs.stop", {"id": self._vpcs_id}, self._stopCallback)

    def _stopCallback(self, result, error=False):
        """
        Callback for stop.

        :param result: server response
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while stopping {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["code"], result["message"])
        else:
            log.info("{} has stopped".format(self.name()))
            self.setStatus(Node.stopped)
            for port in self._ports:
                # set ports as stopped
                port.setStatus(Port.stopped)
            self.stopped_signal.emit()

    def reload(self):
        """
        Reloads this VPCS instance.
        """

        log.debug("{} is being reloaded".format(self.name()))
        self._server.send_message("vpcs.reload", {"id": self._vpcs_id}, self._reloadCallback)

    def _reloadCallback(self, result, error=False):
        """
        Callback for reload.

        :param result: server response
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while suspending {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["code"], result["message"])
        else:
            log.info("{} has reloaded".format(self.name()))

    def allocateUDPPort(self, port_id):
        """
        Requests an UDP port allocation.

        :param port_id: port identifier
        """

        log.debug("{} is requesting an UDP port allocation".format(self.name()))
        self._server.send_message("vpcs.allocate_udp_port", {"id": self._vpcs_id, "port_id": port_id}, self._allocateUDPPortCallback)

    def _allocateUDPPortCallback(self, result, error=False):
        """
        Callback for allocateUDPPort.

        :param result: server response
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while allocating an UDP port for {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["code"], result["message"])
        else:
            port_id = result["port_id"]
            lport = result["lport"]
            log.debug("{} has allocated UDP port {}".format(self.name(), port_id, lport))
            self.allocate_udp_nio_signal.emit(self.id(), port_id, lport)

    def addNIO(self, port, nio):
        """
        Adds a new NIO on the specified port for this VPCS instance.

        :param port: Port instance
        :param nio: NIO instance
        """

        params = {"id": self._vpcs_id,
                  "slot": port.slotNumber(),
                  "port": port.portNumber(),
                  "port_id": port.id()}

        params["nio"] = self.getNIOInfo(nio)
        log.debug("{} is adding an {}: {}".format(self.name(), nio, params))
        self._server.send_message("vpcs.add_nio", params, self._addNIOCallback)

    def _addNIOCallback(self, result, error=False):
        """
        Callback for addNIO.

        :param result: server response
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while adding an UDP NIO for {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["code"], result["message"])
            self.nio_cancel_signal.emit(self.id())
        else:
            self.nio_signal.emit(self.id(), result["port_id"])

    def deleteNIO(self, port):
        """
        Deletes an NIO from the specified port on this VPCS instance

        :param port: Port instance
        """

        params = {"id": self._vpcs_id,
                  "port": port.portNumber(),
                  "slot": port.slotNumber()}

        log.debug("{} is deleting an NIO: {}".format(self.name(), params))
        self._server.send_message("vpcs.delete_nio", params, self._deleteNIOCallback)

    def _deleteNIOCallback(self, result, error=False):
        """
        Callback for deleteNIO.

        :param result: server response
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while deleting NIO {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["code"], result["message"])
            return

        log.debug("{} has deleted a NIO: {}".format(self.name(), result))

    def info(self):
        """
        Returns information about this VPCS device.

        :returns: formated string
        """

        if self.status() == Node.started:
            state = "started"
        else:
            state = "stopped"

        info = """Device {name} is {state}
  Node ID is {id}, server's VPCS device ID is {vpcs_id}
  console is on port {console}
""".format(name=self.name(),
           id=self.id(),
           vpcs_id=self._vpcs_id,
           state=state,
           console=self._settings["console"])

        port_info = ""
        for port in self._ports:
            if port.isFree():
                port_info += "     {port_name} is empty\n".format(port_name=port.name())
            else:
                port_info += "     {port_name} {port_description}\n".format(port_name=port.name(),
                                                                            port_description=port.description())

        return info + port_info

    def dump(self):
        """
        Returns a representation of this VPCS device.
        (to be saved in a topology file).

        :returns: representation of the node (dictionary)
        """

        router = {"id": self.id(),
                  "type": self.__class__.__name__,
                  "description": str(self),
                  "properties": {},
                  "server_id": self._server.id()}

        # add the properties
        for name, value in self._settings.items():
            if name in self._defaults and self._defaults[name] != value:
                router["properties"][name] = value

        # add the ports
        if self._ports:
            ports = router["ports"] = []
            for port in self._ports:
                ports.append(port.dump())

        #TODO: handle the image path
        # router["properties"]["image"]

        return router

    def load(self, node_info):
        """
        Loads a VPCS device representation
        (from a topology file).

        :param node_info: representation of the node (dictionary)
        """

        self.node_info = node_info
        settings = node_info["properties"]
        name = settings.pop("name")
        path = settings.pop("path")
        base_script_file = settings.pop("base_script_file")
        self.updated_signal.connect(self._updatePortSettings)
        # block the created signal, it will be triggered when loading is completely done
        self._loading = True
        log.info("VPCS device {} is loading".format(name))
        self.setup(path, name, base_script_file, settings)

    def _updatePortSettings(self):
        """
        Updates port settings when loading a topology.
        """

        self.updated_signal.disconnect(self._updatePortSettings)
        # update the port with the correct names and IDs
        if "ports" in self.node_info:
            ports = self.node_info["ports"]
            for topology_port in ports:
                for port in self._ports:
                    if topology_port["port_number"] == port.portNumber() and topology_port["slot_number"] == port.slotNumber():
                        port.setName(topology_port["name"])
                        port.setId(topology_port["id"])

        # now we can set the node has initialized and trigger the signal
        self.setInitialized(True)
        log.info("router {} has been loaded".format(self.name()))
        self.created_signal.emit(self.id())
        self._module.addNode(self)
        self._inital_settings = None
        self._loading = False

    def name(self):
        """
        Returns the name of this VPCS device.

        :returns: name (string)
        """

        return self._settings["name"]

    def settings(self):
        """
        Returns all this VPCS device settings.

        :returns: settings dictionary
        """

        return self._settings

    def ports(self):
        """
        Returns all the ports for this VPCS device.

        :returns: list of Port instances
        """

        return self._ports

    def console(self):
        """
        Returns the console port for this VPCS device.

        :returns: port (integer)
        """

        return self._settings["console"]

    def configPage(self):
        """
        Returns the configuration page widget to be used by the node configurator.

        :returns: QWidget object
        """

        from .pages.vpcs_device_configuration_page import VPCSDeviceConfigurationPage
        return VPCSDeviceConfigurationPage

    @staticmethod
    def defaultSymbol():
        """
        Returns the default symbol path for this node.

        :returns: symbol path (or resource).
        """

        return ":/symbols/computer.normal.svg"

    @staticmethod
    def hoverSymbol():
        """
        Returns the symbol to use when this node is hovered.

        :returns: symbol path (or resource).
        """

        return ":/symbols/computer.selected.svg"

    @staticmethod
    def symbolName():

        return "VPCS"

    @staticmethod
    def categories():
        """
        Returns the node categories the node is part of (used by the device panel).

        :returns: list of node category (integer)
        """

        return [Node.end_devices]

    def __str__(self):

        return "VPCS device"

#!/usr/bin/env python
import argparse
from collections import namedtuple
import json
import logging
from logging import handlers
import os
import requests
from requests.exceptions import HTTPError,InvalidURL
import urllib.request, urllib.parse, urllib.error
import urllib3

Node = namedtuple('Node', ['name', 'mac', 'ilo_ip'])
urllib3.disable_warnings()
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)-6s get_devices: %(message)s')
log = logging.getLogger(__file__)
# syslog = handlers.RotatingFileHandler('get_devices.log') #SysLogHandler(address='/dev/log')
# syslog.setLevel(logging.INFO)
# syslog.setFormatter(logging.BASIC_FORMAT)
# log.addHandler(syslog)
TEN_Gb_PER_SECOND = 10240
ONE_Gb_PER_SECOND = 1000


class OME(object):
    """Class representing the OpenManage Enterprise (OME) server"""

    def __init__(self, logger):
        self._ome_ip = None
        self._ome_user = None
        self._auth_token = None
        self._session_url = None
        self._log = logger

    # Dell OME REST API documented here: https://dell.to/2ml8mar
    SESSION_SERVICE_API = "/api/SessionService/Sessions"
    GROUPS_SERVICE_API = "/api/GroupService/Groups"
    GROUP_DEVICES_URL_KEY = "AllLeafDevices@odata.navigationLink"
    INVENTORY_URL_KEY = "InventoryDetails@odata.navigationLink"

    def get_nodes(self, ome_ip=None, ome_user=None, ome_password=None, ome_group=None, ome_exclude_hosts=[]):
        """Queries the OpenManage Enterprise (OME) server to get the PXE boot MAC address, hostname and iDRAC IP
        details for each server managed by the OME.

        Args:
            ome_ip: The IP address of the OME.
            ome_user: The name of the user to use to login to the OME.
            ome_password: The password for ome_user.
            ome_group: The name of the group of servers in the OME.
            ome_exclude_hosts: A list of hostnames to exclude from the group.
    
        Returns:
            A list of dictionaries. Each dictionary is represents an individual server.
            Example:
               {
                   "ilo_ip": "10.10.53.177",
                   "mac": "E4:43:4B:59:D5:FA",
                   "name": "ieatosk1234ilo"
               }
  
        """
        self._ome_ip = ome_ip
        self._ome_user = ome_user
        self._ome_group = ome_group
        self._ome_exclude_hosts = ome_exclude_hosts
        try:
            self._login(ome_password)
            devices = self._get_devices()
            self._log.info("There are {0} devices in the {1} group.".format(len(devices),self._ome_group))
            self.nodes = self._get_device_information(devices)
            self._logout()
            return self._get_node_json()
        except KeyError as ke:
            log.error("Error retrieving key %s" % ke)
        except ValueError as ve:
            log.error(ve)
        except HTTPError as http_error:
            log.error("Error communicating with the OME REST API %s" %
                      http_error)
        finally:
            self._logout()

    def _login(self, ome_password):
        """Login to the OME to create a session."""
        login_data = {"UserName": self._ome_user,
                      "Password": ome_password, "SessionType": "API"}
 
        response = requests.post("https://{0}{1}".format(self._ome_ip, self.SESSION_SERVICE_API),
                                 headers={"Content-Type": "application/json"},
                                 json=login_data,
                                 verify=False)

        if response.status_code == requests.codes.created: # pylint: disable=no-member
            self._session_url = urllib.parse.quote(response.headers["Location"])
            self._auth_token = response.headers["X-Auth-Token"]
            self._headers = {"X-Auth-Token": self._auth_token,
                             "Content-Type": "application/json"}
            log.debug("curl -k -H \"X-Auth-Token: {0}\" -X DELETE https://{1}{2}".format(
                self._auth_token, self._ome_ip, self._session_url))
        else:
            log.error("There was a problem logging into the OME.")
            response.raise_for_status()

    def _get_groupdevices_url(self):
        """Get the URL to request the list of devices for a particular group."""
        return urllib.parse.quote(self._get_group()[self.GROUP_DEVICES_URL_KEY])

    def _get_group(self):
        """ Gets the group object for a group with a name matching the value of
        self._ome_group.
        Returns:
            A dictionary object representing the group.
        Raises:
            ValueError - if there are multiple groups with the same name
        """
        groups_url = "https://{0}{1}".format(self._ome_ip, self.GROUPS_SERVICE_API)
        response = requests.get(groups_url, headers=self._headers, verify=False)
        json_response = response.json()
        response.raise_for_status()
        groups = [group for group in json_response["value"] if group["Name"] == self._ome_group]
        if not groups:
            raise ValueError("Could not find a group named '%s'" % self._ome_group)
        if len(groups) > 1:
            raise ValueError("More than one group named {0} exists in the OME: {1}".format(self._ome_group, groups))
        return groups[0]

    def _get_devices(self):
        """Gets the list of devices in a particular group.
        Raises:
            HTTPError - raised if the HTTP request is unsuccessful
        Returns:
            A list of dictionaries. Each dictionary represents a device(server)
        """
        response = requests.get("https://{0}{1}".format(self._ome_ip, self._get_groupdevices_url()), headers=self._headers, verify=False)
        response.raise_for_status()
        return [device for device in response.json()["value"] if device["DeviceName"] not in self._ome_exclude_hosts]

    def _get_device_information(self, devices):
        """Queries the OME to get the inventory for each device(server).
        Raises:
            HTTPError - raised if the HTTP request is unsuccessful
        Returns:
            A list of Node objects. Each Node object corresponds to a particular server.
        """
        nodes = []
        for device in devices:
            device_url = device[self.INVENTORY_URL_KEY]
            response = requests.get("https://{0}{1}".format(self._ome_ip, device_url), headers=self._headers, verify=False)
            response.raise_for_status()
            nodes.append(Node(name=device["DeviceName"], mac=self._get_pxeboot_mac(response.json()["value"]),
                              ilo_ip=device["DeviceManagement"][0]["NetworkAddress"]))
        return sorted(nodes,key=lambda x:x.name)

    def _get_pxeboot_mac(self, inventory_json):
        """Parses the inventory for a particular server to get the MAC address of the NIC to use for PXE boot.
        The first port of the 10Gb NICs is chosen. A warning is logged if a NIC is found with a link speed other than 10Gb/s.
        """
        nics =  [j for j in inventory_json if j["InventoryType"] == "serverNetworkInterfaces"][0]["InventoryInfo"]
        macs = []
        for nic in nics:
            ports = [port for port in nic["Ports"] if port["LinkSpeed"] == ONE_Gb_PER_SECOND]
            if ports:
                macs.append(ports[0]["Partitions"][0]["CurrentMacAddress"])
            else:
                link_speed = nic["Ports"][0]["LinkSpeed"]
                link_state = nic["Ports"][0]["LinkStatus"]
                product_name = nic["Ports"][0]["ProductName"]
                log.warn("The NIC {0} is {1}. Link speed is {2}".format(product_name, link_state, link_speed))
        if macs:
            return macs[0]

    def _logout(self):
        """Deletes the session from the OME"""
        if self._auth_token:
            log.info("Attempting to logout of session....")
            response = requests.delete("https://{0}{1}".format(self._ome_ip, self._session_url), headers=self._headers,verify=False)
            response.raise_for_status()
            log.info("successfully logged out")
            self._session_url = None
            self._auth_token = None
            self._headers = {}

    def _get_node_json(self):
        return json.dumps([{"name": node.name, "mac": node.mac, "ilo_ip": node.ilo_ip} for node in self.nodes])


def setup_args():
    """Sets up the parser for the command line arguments"""

    script_description = """
        This script pulls information from the OME for each Dell server in the
        specified group and generates JSON. This JSON content is used by ansible playbooks to
        create the servers.yml (SuSE OpenStack) or instackenv.json (Red Hat OpenStack).

        The OME password is provided by setting the OME_PWD environment variable.
        Use 'export OME_PWD=<password>' to set it and then run the script.

        Example
        ================================================================================================
        $ export OME_PWD=passw0rd
        $ ./get_devices.py --ome 10.10.10.15 --user stack --group cloud-12 --director_host ieatosk7370ilo

        """
    parser = argparse.ArgumentParser(
        description=script_description, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--user', required=True, metavar='USER',
                        help="Username to login to the OME")
    parser.add_argument('--ome', required=True,
                        metavar='OME_IP', help="Hostname/IP address of OME")
    parser.add_argument('--group', required=True,
                        metavar='OME_GROUP', help="Group name of the OME")
    parser.add_argument('--director_host', required=False,
                        metavar='DIRECTOR_HOST', help="Name of the director host to exclude.")
    return parser



def main():
    try:
        args = setup_args().parse_args()
        password = os.environ['OME_PWD']
        if not password:
            raise SystemExit("The OME_PWD environment variable is empty")
        node_json = OME(log).get_nodes(args.ome, args.user, password, args.group, [args.director_host])
        if node_json:
            print(node_json)
        else:
            log.error('Error getting server details.')
            raise SystemExit(1)
    except KeyError as ke:
        message = "%s The OME_PWD environment variable is not set. Use 'export OME_PWD=<password> to set it." % ke
        log.error(message)
        raise SystemExit(message)

if __name__ == '__main__':
    main()

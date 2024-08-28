import argparse
import json
import math
import os
import re
import requests
from requests.exceptions import HTTPError, ConnectionError, ConnectTimeout
import urllib3
import logging
import sys
import yaml
from setuptools._vendor.packaging.version import Version


urllib3.disable_warnings()


class GetcENMVolumeInfo:
    RCD_INDEX_DATA = "https://resourceconfigurationdata.internal.ericsson.com/data/index.json"
    VERSION_PATTERN = re.compile(r'^\d{2}\.\d{2}\.\d+(?:-\d+)?$')
    LATEST_VERSION_PATTERN = re.compile(r'\.\d+(?:-\d+)?$')
    RCD_SIZE_MAP = {"small": "Small Cloud Native ENM",
                    "xlarge": "Extra-Large Cloud Native ENM"}
    RCD_URL_MAP = {"small": "https://resourceconfigurationdata.internal.ericsson.com/data/eric-enm-integration-production-values/",
                   "xlarge": "https://resourceconfigurationdata.internal.ericsson.com/data/eric-enm-integration-extra-large-production-values/"}
    DEPLOYMENT_SIZES = list(RCD_URL_MAP.keys())

    def __init__(self, logger, ps_version, deployment_size):
        self.log = logger
        self.version = ps_version
        self.deployment_size = deployment_size
        self.product_set_versions = set()

    def _is_version_valid(self):
        return re.match(self.VERSION_PATTERN, self.version)

    def _get_cenm_versions(self):
        try:
            response = requests.get(self.RCD_INDEX_DATA, headers={
                                    "Accept": "application/json"}, verify=False)
            response.raise_for_status()
            index_data = response.json()
            cenm_versions = list(filter(
                lambda x: x["name"] == self.RCD_SIZE_MAP[self.deployment_size], index_data))[0]["versions"]
            self.product_set_versions = set(
                [v["file"] for v in cenm_versions if v["targetAudience"] == "pdu"])
        except requests.HTTPError as h:
            pass

    def _get_closest_version(self):
        stripped_version = re.sub(self.LATEST_VERSION_PATTERN,"",self.version)
        log.info(f"{self.version} does not exist in Resource Configuration data. Finding the latest version starting with {stripped_version}")
        matching_version = sorted([Version(v) for v in list(self.product_set_versions) 
                                   if v.startswith(stripped_version)])[-1]
        if matching_version:
            major,minor,build = matching_version.release
            post_ver = f"-{matching_version.post}" if matching_version.post else ""
            self.version = f"{major}.{str(minor).zfill(2)}.{build}{post_ver}"
            log.info(f"Found cENM ProductSet version {self.version}")
        else:
            raise SystemExit(
                f"Cannot find a product set matching {self.version} or {stripped_version}")

    def _get_productset_json(self):
        try:
            url = f"{self.RCD_URL_MAP[self.deployment_size]}{self.version}.json"
            log.info(
                f"Downloading cENM {self.version} Product Set JSON. URL is {url}.")
            response = requests.get(
                url, headers={"Accept": "application/json"}, verify=False)
            response.raise_for_status()
            return response.json()
        except (HTTPError, ConnectionError, ConnectTimeout) as err:
            log.error("Error downloading Product Set JSON: %s", err)
            raise SystemExit("Error downloading Product Set JSON")

    def _get_rwx_volumes(self):
        ps_json = self._get_productset_json()
        try:
            rwx_volumes = [{"name": vol["name"], "size": vol["size"]}
                           for vol in ps_json["pvcs"] if vol["type"] == "RWX"]
            return rwx_volumes
        except KeyError as ke:
            pass

    def get_info(self):
        if self._is_version_valid():
            self._get_cenm_versions()
            if self.version not in self.product_set_versions:
                self._get_closest_version()
            return self._get_rwx_volumes()
        else:
            raise SystemExit(f"{self.version} is invalid")


class GetRWXValues:
    def __init__(self, values_file=None):
        self.values_file = values_file

    def _convert_to_gigabytes(self, v):
        unit = v[-2:]
        value = v[:-2]
        if unit == "Gi":
            value = float(value)
        elif unit == "Ti":
            value = float(value) * 1024
        elif unit == "Mi":
            value = float(value)/1024
        else:
            raise ValueError(f"{v} - units must be one of Mi,Gi or Ti")
        return value

    def _get_yaml(self):
        try:
            with open(self.values_file) as vf:
                y = yaml.safe_load(vf)
            rwx_values = [(k.lower().replace("size", ""), self._convert_to_gigabytes(v))
                          for k, v in y["global"]["rwx"].items()
                          if k.lower().endswith("size")]
            return rwx_values
        except yaml.YAMLError as ye:
            log.error(f"Error reading yaml from {self.values_file}: {ye}")
        except KeyError as ke:
            log.error(f"Error finding key in yaml: {ke}")

    def get(self, volumes):
        vol_pattern = re.compile(r"eric-enm-monitoring-master|eric-enm-rwxpvc")
        vols = [vol for vol in volumes if re.match(vol_pattern, vol["name"])]
        for vol_name, vol_size in self._get_yaml():
            for vol in vols:
                name = vol["name"].split("-")[-1]
                if vol_name == name and vol_size != vol["size"]:
                    if vol_size < vol["size"]:
                        log.warn(
                            f'{vol_size}Gi is less than {vol["size"]}. Reducing volume size is not supported.')
                    log.info(f'Updating the size of {vol["name"]} from {vol["size"]}'
                             f' to {vol_size} based on values file.')
                    vol["size"] = vol_size
                    break
        return volumes


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("--productset", metavar="VERSION",
                        help="Product Set version e.g. 22.05.123,22.06-43-4", required=True)
    parser.add_argument("--size", metavar="SIZE", help=f"Deployment size. Must be one of these values: "
                        "{', '.join(GetcENMVolumeInfo.DEPLOYMENT_SIZES)}", choices=GetcENMVolumeInfo.DEPLOYMENT_SIZES, required=True)
    parser.add_argument("--values", metavar='VALUES',
                        help="Absolute path to values file")
    parser.add_argument("--output", metavar='OUTPUT', help='output filename')
    args = parser.parse_args()

    log = logging.Logger('get_cenm_volume_info')
    formatter = logging.Formatter("%(asctime)s %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    log.addHandler(handler)
    rwx_volumes = GetcENMVolumeInfo(
        log, ps_version=args.productset, deployment_size=args.size).get_info()
    if args.values:
        rwx_volumes = GetRWXValues(values_file=os.path.abspath(args.values)).get(rwx_volumes)
    if not args.output:
        print(rwx_volumes)
    else:
        with open(args.output, 'w') as out:
            log.info(f"Writing RWX  volumes to {args.output}")
            json.dump(rwx_volumes, out)

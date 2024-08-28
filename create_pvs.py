import argparse
import os
import re
import sys
import tarfile
import yaml


CHART_VALUES_FILE="eric-enm-pre-deploy-integration/values.yaml"
RWX_CHART_VALUES_FILE = "eric-enm-pre-deploy-integration/charts/eric-enm-rwxpvc/values.yaml"
RWX_PVC_PATTERN=r"eric-enm-pre-deploy-integration/charts/eric-enm-rwxpvc/templates/rwx-.*-pv-pvc.yaml"

def get_pvc_details(reader,values):
        reader_no_braces = re.sub(r'{|}',"",reader.read().decode())
        y = yaml.safe_load(reader_no_braces)
        name = y["metadata"]["name"]
        size_param = y["spec"]["resources"]["requests"]["storage"].split(".")[-1]
        size = values["global"]["rwx"][size_param]
        return (name,size)

def get_values(archive,user_values):
    values = yaml.safe_load(archive.extractfile(RWX_CHART_VALUES_FILE).read().decode())
    root_values = yaml.safe_load(archive.extractfile(CHART_VALUES_FILE).read().decode())
    for key,val in root_values["global"]["rwx"].items():
        if key in user_values["global"]["rwx"]:
            values["global"]["rwx"][key] = user_values["global"]["rwx"][key]
        else:
            values["global"]["rwx"][key] = val
    return values

def get_rwx_params(archive, values):
    rwx_params = []
    for n in archive.getnames():
        if re.match(RWX_PVC_PATTERN,n):
            print("checking",n)
            reader = archive.extractfile(n)
            name, size = get_pvc_details(reader,values)
            capacity = size[:-2]
            units = size[-2:]
            rwx_params.append({ "name": name, "size": capacity, "units": units})
    return rwx_params


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chart',metavar='CHART',help="Absolute path to the helm chart file",required=True)
    parser.add_argument('--values',metavar='VALUES',help="Absolute path to values file",required=True)
    parser.add_argument("--output",metavar='OUTPUT',help='output filename')
    args = parser.parse_args()

    error = False
    for f in [ args.chart, args.values]:
        if not os.path.exists(f):
            print(f"{f} does not exist")
            error = True
    if error:
        sys.exit(1)
    
    with open(args.values) as u:
        user_values = yaml.safe_load(u.read())

    with tarfile.open(args.chart,mode='r:gz') as c:
        values = get_values(c,user_values)
        rwx_params = get_rwx_params(c, values)
        if args.output:
            with open(args.output,'w') as output:
                output.write(yaml.dump(rwx_params,indent=2))
        else:
            print(yaml.dump(rwx_params,indent=2))




if __name__ == '__main__':
    main()

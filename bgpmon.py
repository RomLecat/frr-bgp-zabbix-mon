#!/usr/bin/env python3
import re
import subprocess
import sys
import json
import argparse
import os
import time

VAL_MAP = {
    "Established": {"state": 0},
    "Idle (Admin)": {"state": -1},
    "Idle (PfxCt)": {"state": -2},
    "Idle": {"state": -3},
    "Connect": {"state": -4},
    "Active": {"state": -5},
    "OpenSent": {"state": -6},
    "OpenConfirm": {"state": -7}
}

JSONFILE = '/tmp/bgpmon.json'
CACHELIFE = 60

parser = argparse.ArgumentParser()
parser.add_argument("action", help="discovery | neighbor_settings ")
parser.add_argument("-n", help="neighbor")
args = parser.parse_args()


def run_config():
    neighbor_settings = {}
    try:
        process = subprocess.run(["vtysh", "-c", "show run"], stdout=subprocess.PIPE)
    except IOError:
        print("ZBX_NOTSUPPORTED")
        sys.exit(1)

    out = process.stdout.decode('utf-8')
    pattern = r'^\s+neighbor\s*([0-9a-fA-F.:]+)\s*(maximum-prefix|description|remote-as)\s*(.*)'
    neighbors = {}
    for line in out.split('\n'):
        neighbors = (re.findall(pattern, line))
        for neighbor in neighbors:
            if neighbor_settings.get(neighbor[0]):
                neighbor_settings[neighbor[0]].update({neighbor[1]: neighbor[2]})
            else:
                neighbor_settings[neighbor[0]] = {neighbor[1]: neighbor[2]}

    with open(JSONFILE, 'w') as f:
        json.dump({"neighbor_settings": neighbor_settings}, f)

    return {"neighbor_settings": neighbor_settings}


def bgp_neighbor_state(neighbor_addr):
    result = []
    try:
        process = subprocess.run(["vtysh", "-c", "show bgp nei " + neighbor_addr + " json"], stdout=subprocess.PIPE)
    except IOError:
        print("ZBX_NOTSUPPORTED")
        sys.exit(1)

    out = process.stdout.decode('utf-8')
    bgp_nei = json.loads(out)

    return bgp_nei[neighbor_addr]['bgpState']

if __name__ == '__main__':
    json_cache = None
    result = None
    if os.path.exists(JSONFILE):
        time_cur_json = os.path.getmtime(JSONFILE)
        if time.time() - time_cur_json <= CACHELIFE:
            with open(JSONFILE) as f:
                json_cache = json.load(f)

    if args.action == 'neighbor_state' and args.n:
        value = bgp_neighbor_state(args.n)
        result = VAL_MAP.get(value, value)

    if args.action == 'discovery':
        if not json_cache or not json_cache.get("neighbor_settings"):
            json_cache = run_config()

        result = {"data": []}
        for n in json_cache["neighbor_settings"].items():
            description = n[1].get("description", "No description")
            maximum_prefix = n[1].get("maximum-prefix", -1)
            value = {
                "{#PEER_IP}": n[0],
                "{#DESCRIPTION}": description,
                "{#MAX-PREFIX}": maximum_prefix}
            result["data"].append(value)

    if not result:
        print("ZBX_NOTSUPPORTED")
        sys.exit(1)

    print(json.dumps(result, indent=4, sort_keys=True))

import ansible_runner
import json
import logging          # professional logging (file & console)
import sys              # for console logger
import argparse         # argument parsing
from lib.helpers import *

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("optiver_ansible.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger=logging.getLogger('optiver-ansible')

# parse command line arguments
def init_argparse() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", type=str2bool, nargs='?', const=True, default=False, help="Run quiet")
    return parser

# main code
def main() -> None:

    logger.info("Reading arguments")
    parser = init_argparse()
    args = parser.parse_args()

    logger.info("Load repo from json")
    repo = json.load(open('./repo.json'))

    for c in repo["clusters"]:
        logger.info("Applying defaults to cluster {}".format(c["name"]))
        extravars = {
            "netapp_hostname": c["cluster_mgmt"],
            "netapp_username": "admin"
        }
        job = runplaybook('.','optiver_ontap_day1_defaults/main.yml',extravars,args.quiet)
        logger.info("Job was {}".format(job.status))


main()

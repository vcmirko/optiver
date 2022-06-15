import ansible_runner
import json
import logging          # professional logging (file & console)
import sys              # for console logger
import argparse         # argument parsing
import getpass          # prompt password input
from lib.helpers import *

class Error(Exception):
    """Base class for other exceptions"""
    pass

class PasswordsNotMatchError(Error):
    """Raised when password input does not match"""
    pass

def promptPass(prompt):
    p = getpass.getpass(prompt=prompt)
    p2 = getpass.getpass(prompt='Type the password again : ')

    if p!=p2:
        raise PasswordsNotMatchError
    else:
        return p

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
    parser.add_argument("--api-user-certpath",help="Path for api_user certificate",required=True)
    parser.add_argument("--quiet", type=str2bool, nargs='?', const=True, default=False, help="Run quiet")
    return parser

# main code
def main() -> None:

    logger.info("Reading arguments")
    parser = init_argparse()
    args = parser.parse_args()

    # admin_password = promptPass('Type the new password for the admin user :')
    admin_password="Netapp12"
    with open(args.api_user_certpath, "r") as f:
        api_user_certificate = f.readlines()


    logger.info("Load repo from json")
    repo = json.load(open('./repo.json'))

    for c in repo["clusters"]:
        logger.info("Applying defaults to cluster {}".format(c["name"]))
        extravars = {
            "cluster_name": c["name"],
            "netapp_hostname": c["cluster_mgmt"],
            "netapp_username": "admin",
            "api_user_certificate": api_user_certificate,
            "admin_password": admin_password
        }
        job = runplaybook('.','optiver_ontap_day1_defaults/main.yml',extravars,args.quiet)
        logger.info("Job was {}".format(job.status))


main()

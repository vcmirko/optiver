REST_USERNAME = "admin"
REST_PASSWORD = "Netapp12"

import json
import logging          # professional logging (file & console)
import sys              # for console logger
import argparse         # argument parsing
import pyjq             # json query language
from lib.helpers import *

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("optiver_ansible.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger=logging.getLogger('optiver-ansible')

restcreds = "{}:::{}".format(REST_USERNAME,REST_PASSWORD)

# get repo from intent
def getRepoFromIntent(host,cluster):
    url = "https://{}/api/?cluster={}".format(host,cluster)
    response = requests.get(url,verify=False)
    jsonresponse = response.json()
    whattoreturn = jsonresponse["maybesomesubset"]
    return whattoreturn

# parse command line arguments
def init_argparse() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser()
    # parser.add_argument("--tier", help="Tier")
    parser.add_argument("--force", type=str2bool, nargs='?', const=True, default=False, help="Force run, do not compare, check all lifs")
    parser.add_argument("--quiet", type=str2bool, nargs='?', const=True, default=False, help="Run quiet")
    parser.add_argument("--initiators", type=str2bool, nargs='?', const=True, default=False, help="Also check initiators")
    return parser

def makeExtraVars(svm,repo,force):

    # extract the easy parts
    cluster=svm["cluster"]
    svm_name=svm["name"]

    # json query to get the cluster mgmt ip/fqdn from repo
    cluster_obj = pyjq.first('.clusters[] | select(.name == "{}")'.format(cluster),repo)
    cluster_name = pyjq.first('.clusters[] | select(.name == "{}")  | .cluster_mgmt'.format(cluster),repo)

    # filter the svm object out of the repo
    svm_obj = pyjq.first('.clusters[] | select(.name == "{}")  | .svms[] | select(.name == "{}")'.format(cluster,svm_name),repo)
    lifslive = getLiveLifs(cluster_name,svm_name,restcreds)
    lifsrepo = getRepoLifs(svm_obj)

    # if we run with force => do all lifs anyhow
    if force:
        lifstomake = lifsrepo
    else:
        # check which lifs are missing
        lifstomake = diff(lifsrepo,lifslive)

    # get full lif info from repo
    lifs=[]
    for lif in lifstomake:
        tmplif = pyjq.first('.lifs[] | select(.name == "{}")'.format(lif["name"]),svm_obj)
        # check if mgmt lif
        if "-mgmt" in tmplif["name"]:
            tmplif["firewall_policy"]="mgmt"
            tmplif["role"]="data"
        else:
            tmplif["firewall_policy"]="data"
            tmplif["role"]="data"
        lifs.append(tmplif)

    svm = {
        "name": svm_name,
        "root_partition": svm_obj["root_partition"]
    }

    if "-fc" in svm_name:
        svm["allowed_protocols"] = "fcp"
        svm["root_volume_security_style"] = "unix"
    elif "-ad" in svm_name:
        svm["allowed_protocols"] = "cifs"
        svm["root_volume_security_style"] = "ntfs"
    else:
        svm["allowed_protocols"] = "nfs"
        svm["root_volume_security_style"] = "unix"
    svm["root_volume_aggregate"] = getBestAggregate(getAggregatesByCluster(cluster_name,restcreds))

    # build the extravars
    extravars = {
      "cluster_name": cluster_name,
      "svm": svm,
      "lifs": lifs
    }

    logger.debug(extravars)

    return extravars

# main code
def main() -> None:

    logger.debug("Reading arguments")
    parser = init_argparse()
    args = parser.parse_args()

    logger.info("Load repo from json")
    repo = json.load(open('./repo.json'))

    # logger.info("Load repo from intent")
    # repo2 = getRepoFromIntent("myintent.optiver.local","theclusterIwant")

    logger.info("Getting live rest info from all clusters known in repo")
    svmslive = getLiveSvms(repo["clusters"],restcreds)
    svmsrepo = getRepoSvms(repo["clusters"])

    # if we run with force => do all lifs anyhow
    if args.force:
        svmstomake = svmsrepo
    else:
        svmstomake = diff(svmsrepo,svmslive)

    logger.debug(svmstomake)

    logger.info("Creating svms")
    for svm in svmstomake:
        logger.info("Creating svm {} on cluster {}".format(svm["name"],svm["cluster"]))
        extravars = makeExtraVars(svm,repo,args.force)
        job = runplaybook('.','optiver_ontap_day1/main.yml',extravars,args.quiet)
        logger.info("Job was {}".format(job.status))


main()

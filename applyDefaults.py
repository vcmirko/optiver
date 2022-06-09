REST_USERNAME = "admin"
REST_PASSWORD = "Netapp12"

import ansible_runner
import json
import logging          # professional logging (file & console)
import sys              # for console logger
import argparse         # argument parsing
import requests         # for rest
import pyjq             # json query language
from requests.packages.urllib3.exceptions import InsecureRequestWarning # ignore certs

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("optiver_ansible.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger=logging.getLogger('optiver-ansible')

creds = "{}:::{}".format(REST_USERNAME,REST_PASSWORD)

def getCreds():
    return creds.split(':::')

# get repo from intent
def getRepoFromIntent(host,cluster):
    url = "https://{}/api/?cluster={}".format(host,cluster)
    response = requests.get(url,verify=False)
    jsonresponse = response.json()
    whattoreturn = jsonresponse["maybesomesubset"]
    return whattoreturn

# get volumes in a cluster
# def getVolumesByCluster(cluster):
#     url = "https://{}/api/storage/volumes?fields=svm,space&return_records=true&return_timeout=15".format(cluster)
#     user,pw = getCreds()
#     response = requests.get(url,auth=(user,pw),verify=False)
#     return response.json()['records']

# get luns in a cluster
def getLunsByCluster(cluster):
    url = "https://{}/api/storage/luns?fields=svm,space&return_records=true&return_timeout=15".format(cluster)
    user,pw = getCreds()
    response = requests.get(url,auth=(user,pw),verify=False)
    return response.json()['records']

# get luns in a cluster
# def getIgroupsByCluster(cluster):
#     url = "https://{}/api/protocols/san/igroups?fields=svm,os_type,protocol,lun_maps,initiators&return_records=true&return_timeout=15".format(cluster)
#     user,pw = getCreds()
#     response = requests.get(url,auth=(user,pw),verify=False)
#     return response.json()['records']

# get simplified list of luns live
def getLiveLifs(clusters):
    list = []
    for cluster in clusters:
        luns = getLunsByCluster(cluster["cluster_mgmt"])
        lunssimplified = pyjq.all('.[] | {path:.name,svm:.svm.name,cluster:"'+cluster["name"]+'"}',luns)
        list += lunssimplified
    return list
# get simplified list of luns in repo
def getRepoLifs(clusters):
    list = []
    for c in clusters:
        for s in c["svms"]:
            if("luns" in s):
                for l in s["luns"]:
                    list.append(
                        {
                            "cluster":c["name"],
                            "svm":s["name"],
                            "path":"/vol/{}/{}".format(l["name"],l["name"])
                        }
                    )
    return list

# to allow flags in argparse
def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

# parse command line arguments
def init_argparse() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser()
    # parser.add_argument("--tier", help="Tier")
    parser.add_argument("--force", type=str2bool, nargs='?', const=True, default=False, help="Force run, do not compare, check all luns")
    parser.add_argument("--quiet", type=str2bool, nargs='?', const=True, default=False, help="Run quiet")
    parser.add_argument("--initiators", type=str2bool, nargs='?', const=True, default=False, help="Also check initiators")
    return parser

# run playbook
def runplaybook(dir,playbook,extravars,quiet):

    job = ansible_runner.run(
        private_data_dir=dir,
        playbook=playbook,
        extravars=extravars,
        quiet=quiet,
    )
    return job

def diff(list1,list2):
    diff=[]
    for l1 in list1:
        if l1 not in list2:
            diff.append(l1)
    return diff

def makeExtraVars(lun,repo,addinitiators):

    # extract the easy parts
    cluster=lun["cluster"]
    svm_name=lun["svm"]
    lunpath=lun["path"]

    # split the lun path (lunpath = /vol/volumename/lunname)
    lunsplit = lunpath.split("/")
    volume_name=lunsplit[2]
    lun_name=lunsplit[3]

    # json query to get the cluster mgmt ip/fqdn from repo
    cluster_name = pyjq.first('.clusters[] | select(.name == "{}")  | .cluster_mgmt'.format(cluster),repo)

    # filter the svm object out of the repo
    svmobject = pyjq.first('.clusters[] | select(.name == "{}")  | .svms[] | select(.name == "{}")'.format(cluster,svm_name),repo)

    # json query to get the full lun object from repo
    lunobject = pyjq.first('.luns[] | select(.name == "{}")'.format(lun_name),svmobject)

    # get remaining info from repo lunobject
    igroup_name = lunobject["igroup"]
    lun_type = lunobject["os_type"]
    volume_size = lunobject["size"]
    volume_unit = lunobject["size_unit"]
    aggregate_name = lunobject["aggregate"]

    # get the igroup object and extract os_type
    igroupobject = pyjq.first('.igroups[] | select(.name == "{}")'.format(igroup_name),svmobject)
    igroup_type = igroupobject["os_type"]

    initiators = pyjq.all('.wwpns[]',igroupobject)

    # build the extravars
    extravars = {
      "cluster_name": cluster_name,
      "svm_name": svm_name,
      "volume_name": volume_name,
      "lun_name": lun_name,
      "igroup_name": igroup_name,
      "aggregate_name": aggregate_name,
      "volume_size": volume_size,
      "volume_unit": volume_unit,
      "export_policy": "none",
      "igroup_type": igroup_type,
      "lun_type": lun_type,
      "use": "fcp"
    }

    # if we need to add initiators, we add the initiators too
    if(addinitiators):
        extravars["initiator"]=",".join(initiators)
        extravars["add_initiator"]=True

    return extravars

# main code
def main() -> None:

    logger.info("Reading arguments")
    parser = init_argparse()
    args = parser.parse_args()

    logger.info("Load repo from json")
    repo = json.load(open('./repo.json'))

    # logger.info("Load repo from intent")
    # repo2 = getRepoFromIntent("myintent.optiver.local","theclusterIwant")

    logger.info("Getting live rest info from all clusters know in repo")
    lunslive = getLiveLuns(repo["clusters"])
    lunsrepo = getRepoLuns(repo["clusters"])

    # if we run with force => do all luns anyhow
    if args.force:
        lunstomake = lunsrepo
    else:
        lunstomake = diff(lunsrepo,lunslive)

    logger.info("Creating luns")
    for lun in lunstomake:
        logger.info("Creating lun {} on svm {} on cluster {}".format(lun["path"],lun["svm"],lun["cluster"]))
        extravars = makeExtraVars(lun,repo,False)
        job = runplaybook('.','optiver_ontap_day2/main.yml',extravars,args.quiet)
        logger.info("Job was {}".format(job.status))

    if(args.initiators):
        logger.info("Adding initiators")
        for lun in lunstomake:
            logger.info("Adding initiators to igroups for lun {} on svm {} on cluster {}".format(lun["path"],lun["svm"],lun["cluster"]))
            extravars = makeExtraVars(lun,repo,True)
            job = runplaybook('.','optiver_ontap_day2/main.yml',extravars,args.quiet)
            logger.info("Job was {}".format(job.status))

main()

import requests         # for rest
import json
import pyjq             # json query language
import ansible_runner
from operator import itemgetter   # filter object-arrays
from requests.packages.urllib3.exceptions import InsecureRequestWarning # ignore certs

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def getCreds(creds):
    return creds.split(':::')
# run playbook
def runplaybook(dir,playbook,extravars,quiet):
    job = ansible_runner.run(
        private_data_dir=dir,
        playbook=playbook,
        extravars=extravars,
        quiet=quiet,
    )
    return job
# diff between 2 lists
def diff(list1,list2):
    diff=[]
    for l1 in list1:
        if l1 not in list2:
            diff.append(l1)
    return diff
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
# get aggregates in a cluster
def getAggregatesByCluster(cluster,restcreds):
    url = "https://{}/api/storage/aggregates?fields=space.block_storage.available&return_records=true&return_timeout=15".format(cluster)
    user,pw = getCreds(restcreds)
    aggregates = []
    response = requests.get(url,auth=(user,pw),verify=False)
    for aggregate in response.json()['records']:
        aggr = {}
        aggr["name"] = aggregate['name']
        aggr["space"] = aggregate['space']['block_storage']['available']
        aggregates.append(aggr)
    return aggregates
# get aggregate with most space
def getBestAggregate(aggregates):
    if(len(aggregates)>0):
        temp = sorted(aggregates,key=itemgetter('space'),reverse=True)
        return temp[0]["name"]
    else:
        raise Exception('No aggregates found')
def getSvmsByCluster(cluster,restcreds):
    url = "https://{}/api/svm/svms?return_records=true&return_timeout=15".format(cluster)
    user,pw = getCreds(restcreds)
    response = requests.get(url,auth=(user,pw),verify=False)
    return response.json()['records']
def getIgroupsBySvm(cluster,svm,restcreds):
    url = "https://{}/api/protocols/san/igroups?svm.name={}&fields=os_type,protocol,lif_maps,initiators&return_records=true&return_timeout=15".format(cluster,svm)
    user,pw = getCreds(restcreds)
    response = requests.get(url,auth=(user,pw),verify=False)
    if(response.status_code==200):
        return response.json()['records']
    else:
        return []
def getFcLifsBySvm(cluster,svm,restcreds):
    url = "https://{}/api/network/fc/interfaces?svm.name={}&return_records=true&return_timeout=15".format(cluster,svm)
    user,pw = getCreds(restcreds)
    response = requests.get(url,auth=(user,pw),verify=False)
    if(response.status_code==200):
        return response.json()['records']
    else:
        return []
def getIpLifsBySvm(cluster,svm,restcreds):
    url = "https://{}/api/network/ip/interfaces?svm.name={}&return_records=true&return_timeout=15".format(cluster,svm)
    user,pw = getCreds(restcreds)
    response = requests.get(url,auth=(user,pw),verify=False)
    if(response.status_code==200):
        return response.json()['records']
    else:
        return []
# get simplified list of lifs live
def getLiveLifs(cluster,svm,restcreds):
    list = []
    lifs = getFcLifsBySvm(cluster,svm,restcreds)
    lifssimplified = pyjq.all('.[] | {name:.name}',lifs)
    list += lifssimplified
    lifs = getIpLifsBySvm(cluster,svm,restcreds)
    lifssimplified = pyjq.all('.[] | {name:.name}',lifs)
    list += lifssimplified
    return list
# get simplified list of lifs in repo
def getRepoLifs(svm):
    list = []
    if("lifs" in svm):
        for lif in svm["lifs"]:
            list.append(
                {
                    "name":lif["name"]
                }
            )
    return list
# get simplified list of svms live
def getLiveSvms(clusters,restcreds):
    list = []
    for cluster in clusters:
        svms = getSvmsByCluster(cluster["cluster_mgmt"],restcreds)
        svmssimplified = pyjq.all('.[] | {name:.name,cluster:"'+cluster["name"]+'"}',svms)
        list += svmssimplified
    return list
# get svmlist in repo
def getRepoSvms(clusters):
    list = []
    for c in clusters:
        for s in c["svms"]:
            list.append(
                {
                    "cluster":c["name"],
                    "name":s["name"]
                }
            )
    return list

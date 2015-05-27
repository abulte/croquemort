import argparse

from nameko.standalone.rpc import ClusterRpcProxy

from tools import generate_hash

config = {
    'AMQP_URI': 'amqp://guest:guest@localhost'
}

parser = argparse.ArgumentParser()
parser.add_argument('--csvfile', type=argparse.FileType('r'), required=True)
parser.add_argument('--group')
args = parser.parse_args()

with ClusterRpcProxy(config) as cluster_rpc:
    for line in args.csvfile:
        url = line.strip('\n')
        cluster_rpc.http_server.fetch.async(url, args.group or None)

if args.group:
    print('Group hash: {hash}'.format(hash=generate_hash(args.group)))
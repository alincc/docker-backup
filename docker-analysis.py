#! /usr/bin/python3

import argparse, subprocess, json
parser = argparse.ArgumentParser()
parser.add_argument("name", help="name of the container")
args = parser.parse_args()

for c in json.loads(subprocess.run(["docker", "inspect", args.name], stdout=subprocess.PIPE).stdout.decode('utf-8')):
    for i in json.loads(subprocess.run(["docker", "inspect", c['Image']], stdout=subprocess.PIPE).stdout.decode('utf-8')):
        h = c['HostConfig']
        r = h['RestartPolicy']
        o = c['Config']
        ic = i['Config']
        print('docker run -d {} --name {} --restart {} {} {} {} {} {} {} {} {}'
              .format('--priviledged' if h['Privileged'] else '',
                      c['Name'],
                      r['Name']+(':'+str(r['MaximumRetryCount']) if r['MaximumRetryCount'] else ''),
                      ' '.join(['-p '+(y['HostIp']+':' if y['HostIp'] else '')+y['HostPort']+':'+x for x in h['PortBindings'] for y in h['PortBindings'][x]]),
                      ' '.join(['--expose '+x for x in o['ExposedPorts'] if x not in set(ic['ExposedPorts'])]),
                      ' '.join(['-v '+x for x in h['Binds']]),
                      ' '.join(['--volumes-from '+x for x in h['VolumesFrom']]),
                      ' '.join(['--link '+x for x in h['Links']]),
                      ' '.join(["-e '"+x.replace("'", "\\'")+"'" for x in o['Env'] if x not in set(ic['Env'])]),
                      o['Image'],
                      ' '.join(o['Cmd']) if o['Cmd']!=ic['Cmd'] else ''))

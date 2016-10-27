#! /usr/bin/python3

import argparse, subprocess, json, re
parser = argparse.ArgumentParser()
parser.add_argument('container', nargs='*', help='name of the containers')
parser.add_argument('-r', '--recurse', action='store_true', help='recursively setup container')
args = parser.parse_args()

class c_list(list):
    def __iadd__(self, other):
        if other and other!='': self.append(other)
        return self

def has(dictionary, index):
    return index in dictionary and dictionary[index]
def hasnt(dictionary, index, value):
    return index not in dictionary or not dictionary[index] or value not in set(dictionary[index])
def match(dictionary, index, pattern):
    return index in dictionary and dictionary[index] and re.match(pattern, dictionary[index])
def isnt(dictionary, index, value, pre='', post=''):
    if index in dictionary and dictionary[index] and not dictionary[index] in value:
        if pre=='' and post=='':
            return True
        else:
            return pre+str(dictionary[index])+post
    return False if pre=='' and post=='' else ''
def text(dictionary, index, pre='', post=''):
    return pre+str(dictionary[index])+post if index in dictionary and dictionary[index] else ''

def compare(container1, container2):
    name1 = container1['Name'].strip('/')
    name2 = container2['Name'].strip('/')
    if (name1==name2): return 0
    h1 = container1['HostConfig']
    h2 = container2['HostConfig']
    if match(h1, 'VolumesFrom', '^'+name2+'$'): return -1
    if match(h1, 'Links', '^/?'+name2+':?.*$'): return -1
    if match(h2, 'VolumesFrom', '^'+name1+'$'): return 1
    if match(h2, 'Links', '^/?'+name1+':?.*$'): return 1
    return -1 if name1<name2 else 1

class Object(object):
    pass

class DockerObject:
    def __init__(self, name):
        assign(self, json.loads(subprocess.check_output(['docker', 'inspect', name]).decode('utf-8'))[0].items())
    def assign(o, arg):
        if isinstance(arg, dict):
            for k, v in arg.items():
                setattr(o, k, assign(Object(), v))
            return o
        else:
            return arg

class Container(DockerObject):
    def __init__(self, name):
        super().__init__(name)
    def command(self):
        s = self.State
        o = self.Config
        h = self.HostConfig
        r = h.RestartPolicy

class Image(DockerObject):
    def __init__(self, name):
        super().__init__(name)

def build(container):
    for c in json.loads(subprocess.check_output(['docker', 'inspect', container]).decode('utf-8')):
        s = c['State']
        o = c['Config']
        h = c['HostConfig']
        r = h['RestartPolicy']
        for i in json.loads(subprocess.check_output(['docker', 'inspect', c['Image']]).decode('utf-8')):
            ic = i['Config']
            params = c_list()
            if s['Status']=='running':
                if (o['AttachStdin'] and o['AttachStdout'] and
                    o['AttachStderr'] and o['Tty'] and
                    o['OpenStdin'] and o['StdinOnce']):
                    params+='run -it'
                else:
                    params+='run -d'
            else:
                params+='create'
            if isnt(r, 'Name', 'no'):  params+='--restart '+r['Name']+(isnt(r, 'MaximumRetryCount', 0, ':'))
            if has(h, 'Privileged'):   params+='--priviledged'
            if isnt(h, 'NetworkMode', ['default', 'bridge']): params+='--network '+h['NetworkMode']
            if has(c, 'Name'):         params+='--name '+c['Name']
            params+=' '.join(['-p '+text(y, 'HostIp', ':')+y['HostPort']+':'+x for x in h['PortBindings'] for y in h['PortBindings'][x]])
            if has(o, 'ExposedPorts'): params+=' '.join(['--expose '+x for x in o['ExposedPorts'] if hasnt(ic, 'ExposedPorts', x)])
            if has(h ,'Binds'):        params+=' '.join(['-v '+x for x in h['Binds']])
            if has(h, 'VolumesFrom'):  params+=' '.join(['--volumes-from '+x for x in h['VolumesFrom']])
            if has(h, 'Links'):        params+=' '.join(['--link '+x for x in h['Links']])
            if has(o, 'Env'):          params+=' '.join(["-e '"+x.replace("'", "'\"'\"'")+"'" for x in o['Env'] if 'Env' not in ic or not ic['Env'] or x not in set(ic['Env'])])
            params+=o['Image']
            if o['Cmd']!=ic['Cmd']:    params+=' '.join(o['Cmd'])
            print('docker '+' '.join(params));

containers = args.container or subprocess.check_output(['docker', 'ps', '-aq']).decode('utf-8').split('\n')
for container in containers:
    if (container): build(container)

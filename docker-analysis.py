#! /usr/bin/python3

import argparse, subprocess, json, re, itertools
parser = argparse.ArgumentParser()
parser.add_argument('container', nargs='*', help='name of the containers')
parser.add_argument('-d', '--dot', action='store_true', help='draw dot diagram instead of commandline')
parser.add_argument('-r', '--recurse', action='store_true', help='recursively setup container')
parser.add_argument('-c', '--command', help='docker command, e.g. -c "run -d"')
parser.add_argument('--restart', help='override the restart argument, e.g. --restart unless-stopped')
args = parser.parse_args()

class Object(object):
    pass

class Dict(dict):
    pass

class DockerObject(Dict):
    def __init__(self, name):
        DockerObject.assign(self, json.loads(subprocess.check_output(['docker', 'inspect', name]).decode('utf-8'))[0])
    @staticmethod
    def assign(o, arg):
        if isinstance(arg, dict):
            for k, v in arg.items():
                o[k] = v
                setattr(o, k, DockerObject.assign(Dict(), v))
            return o
        else:
            return arg
    class c_list(list):
        def __iadd__(self, other):
            if other and other!='': self.append(other)
            return self
    @staticmethod
    def has(dictionary, index):
        return index in dictionary and dictionary[index]
    @staticmethod
    def hasnt(dictionary, index, value):
        return index not in dictionary or not dictionary[index] or value not in set(dictionary[index])
    @staticmethod
    def match(dictionary, index, pattern):
        return index in dictionary and dictionary[index] and re.match(pattern, dictionary[index])
    @staticmethod
    def isnt(dictionary, index, value, pre='', post=''):
        if index in dictionary and dictionary[index] and not dictionary[index] in value:
            if pre=='' and post=='':
                return True
            else:
                return pre+str(dictionary[index])+post
        return False if pre=='' and post=='' else ''
    @staticmethod
    def text(dictionary, index, pre='', post=''):
        return pre+str(dictionary[index])+post if index in dictionary and dictionary[index] else ''

class Image(DockerObject):
    def __init__(self, name):
        super().__init__(name)

class Container(DockerObject):
    registry = dict()
    def __init__(self, name):
        super().__init__(name)
        self.name = self.Name.strip('/')
        Container.registry[self.name] = self
        self.image = Image(self.Image)
    def __del__(self):
        del Container.registry[self.name]
    @staticmethod
    def get(name):
        name = name.strip('/')
        if Container.has(Container.registry, name):
            return Container.registry[name]
        else:
            return Container(name)
    @staticmethod
    def create(names, recurse=False):
        for name in names:
            if name: c = Container.get(name)
            if recurse:
                Container.create(c.volumes() + c.links(), recurse)
        return Container.registry
    def __lt__(self, other):
        if self.name in other.volumes():
            return True
        if other.name in self.volumes():
            return False
        if self.name in other.links():
            return True
        if other.name in self.links():
            return False
        return self.name[::-1] < other.name[::-1]
    def volumes(self):
        res = []
        if not self.has(self.HostConfig, 'VolumesFrom'): return res
        res += self.HostConfig.VolumesFrom
        for v in itertools.islice(res, 0, len(res)): res += Container.get(re.sub(':.*$', '', v)).volumes()
        return res
    def links(self):
        res = []
        if not self.has(self.HostConfig, 'Links'): return res
        res += [ re.sub(':.*$', '', l).strip('/') for l in self.HostConfig.Links ]
        for l in itertools.islice(res, 0, len(res)): res += Container.get(l).links()
        return res
    def colour(self):
        if self.State.Running: return 'green'
        if self.State.Paused: return 'grey'
        if self.State.Restarting: return 'yellow2'
        return 'indianred1'
    def mounts(self):
        return [ m['Destination'] for m in self.Mounts ]
    def dot_(self):
        for v in self.volumes():
            print('  "'+self.name+'" -> "'+v+'" [label="'+'\\n'.join(self.get(v).mounts())+'"];')
        if self.has(self.HostConfig, 'Links'):
            for l in self.HostConfig.Links:
                print('  "'+self.name+'" -> "'+re.sub(':.*$', '', l).strip('/')+'" [label="'+re.sub('^.*:/'+self.name+'/', '', l)+'",style=dashed];')
    @staticmethod
    def dot():
        print('digraph G {')
        print('  rankdir=LR;')
        ips = dict()
        for c in Container.registry.values():
            for i, e in c.HostConfig.PortBindings.items():
                for b in e:
                    key = b['HostIp'] if b['HostIp'] else 'localhost'
                    if not key in ips:
                        ips[key] = []
                    ips[key].append(b['HostPort'])
        for ip, ports in ips.items():
            print('    subgraph cluster'+re.sub('\.', '_', ip)+' {')
            print('      label="'+ip+'";')
            for port in ports:
                print('      "'+ip+':'+port+'" [label="'+port+'"];')
            print('    }')
        for n, c in Container.registry.items():
            print('  "'+n+'" [label="'+n+'\\n'+c.Config.Image+'",fillcolor='+c.colour()+',style=filled];')
            for i, e in c.HostConfig.PortBindings.items():
                for b in e:
                    key = b['HostIp'] if b['HostIp'] else 'localhost'
                    print('  "'+key+':'+b['HostPort']+'" -> "'+n+'" [label="'+i+'",style=dashed];')
            if c.Mounts:
                for m in c.Mounts:
                    if not re.match('^/var/lib/docker/volumes/', m['Source']):
                        print('  "'+c.name+'" -> "'+m['Source']+'" [label="'+m['Destination']+'"];')
        for c in Container.registry.values():
            c.dot_()
        print("  {rank=same; ")
        for c in Container.registry.values():
            if c.Mounts:
                for m in c.Mounts:
                    if not re.match('^/var/lib/docker/volumes/', m['Source']):
                        print('    "'+m['Source']+'" [shape=rect];')
        print('  }')
        print("  {rank=same; ")
        for c in Container.registry.values():
            if c.HostConfig.VolumesFrom:
                for v in c.HostConfig.VolumesFrom:
                    print('    "'+v+'"')
        print('  }')
        print('}')
    def commandline(self, restart=False):
        s = self['State']
        o = self['Config']
        h = self['HostConfig']
        r = h['RestartPolicy']
        ic = self.image['Config']
        has = self.has
        hasnt = self.hasnt
        match = self.match
        isnt = self.isnt
        text = self.text
        if s['Running']:
            if (o['AttachStdin'] and o['AttachStdout'] and
                o['AttachStderr'] and o['Tty'] and
                o['OpenStdin'] and o['StdinOnce']):
                cmd='run -it'
            else:
                cmd='run -d'
        else:
            cmd='create'
        params = self.c_list()
        if restart: params+='--restart '+restart
        elif isnt(r, 'Name', 'no'): params+='--restart '+r['Name']+(isnt(r, 'MaximumRetryCount', 0, ':'))
        if has(h, 'Privileged'): params+='--priviledged'
        if isnt(h, 'NetworkMode', ['default', 'bridge']): params+='--net '+h['NetworkMode']
        params+='--name '+self.name
        params+=' '.join(['-p '+text(y, 'HostIp', ':')+y['HostPort']+':'+x for x in h['PortBindings'] for y in h['PortBindings'][x]])
        if has(o, 'ExposedPorts'): params+=' '.join(['--expose '+x for x in o['ExposedPorts'] if hasnt(ic, 'ExposedPorts', x)])
        if has(h ,'Binds'):        params+=' '.join(['-v '+x for x in h['Binds']])
        if has(h, 'VolumesFrom'):  params+=' '.join(['--volumes-from '+x for x in h['VolumesFrom']])
        if has(h, 'Links'):        params+=' '.join(['--link '+x.strip('/').replace(':/'+self.name+'/', ':') for x in h['Links']])
        if has(o, 'Env'):          params+=' '.join(["-e '"+x.replace("'", "'\"'\"'")+"'" for x in o['Env'] if 'Env' not in ic or not ic['Env'] or x not in set(ic['Env'])])
        params+=o['Image']
        if o['Cmd']!=ic['Cmd']:    params+=' '.join(o['Cmd'])
        return { 'cmd': cmd, 'params': params }

containers = args.container or subprocess.check_output(['docker', 'ps', '-aq']).decode('utf-8').split('\n')
if (args.dot):
    Container.create(containers, args.recurse)
    Container.dot()
else:
    for c in sorted(list(Container.create(containers, args.recurse).values())):
        b = c.commandline(args.restart)
        print('docker '+(args.command or b['cmd'])+' '+' '.join(b['params']))

#!/bin/bash -e

function get-volumes() {
    local vols=""
    for vol in ${*}; do
        local vf=$(docker inspect -f '{{.HostConfig.VolumesFrom}}' ${vol} | sed -n 's,^\[\(.*\)\]$,\1,p')
        if test -n "$vf"; then
            vols+=" "$(get-volumes $vf)
        fi
        vols+=" "$(docker inspect -f '{{.Config.Volumes}}' ${vol} | sed -n 's,^map\[\(.*\)\]$,\1,p' | sed 's,:[^ ]*,,g')
    done
    echo ${vols} | tr '[ ]' '[\n]' | sort | uniq | tr '[\n]' '[ ]'
}

backup=""
volumes=""
infile=""
tofile=""
toserver=""
tocontainer=""
while test $# -gt 0; do
    case "$1" in
        (-h|--help)
            cat <<EOF
$0 -b [OPTIONS]

OPTIONS:
  -b, --backup       <container> name of the docker container to backup
  -v, --volume       <volume>    add volume path to backup from container
  -a, --auto                     automatically detect volumes to backup from container
  -i, --in-file      <file>      take already existing backup file to import
  -s, --to-server    <server>    copy backup to docker instance on ssh server
  -c, --to-container <container> write backup into container on ssh server
  -o, --to-file      <file>      write backup to file

DESCRIPTION:

  Take docker backups and copy them to a file or restore them into a
  docker instance on an ssh target server.

  Note: Use ssh key exchange to prevent password query.
  Note: Only volume paths are backed-up correctly

EXAMPLE:

  $0 -b wordpress -a -o /tmp/wordpress.bak.tar.bz2
  $0 -i /tmp/wordpress.bak.tar.bz2 -c wordpress
  $0 -b backup-test -a -s server -c backup-test

EOF
            exit 0
            ;;
        (-b|--backup)
            shift
            backup="$1"
            ;;
        (-i|--in-file)
            shift
            infile="$1"
            ;;
        (-o|--to-file)
            shift
            tofile="$1"
            ;;
        (-s|--to-server)
            shift
            toserver="$1"
            ;;
        (-c|--to-container)
            shift
            tocontainer="$1"
            ;;
        (-a|--auto)
            if test -z "$backup"; then
                echo "**** Error: --auto first requires --backup, try $0 --help" 1>&2
                exit 1
            fi
            volumes+=" "$(get-volumes $backup)
            ;;            
        (-v|--volume)
            shift
            volumes+=("$1")
            ;;
        (*)
            echo "**** Error: unknown argument $1, try $0 --help" 1>&2
            exit 1
            ;;
    esac
    if test $# -eq 0; then
        echo "**** Error: missing argument, try $0 --help" 1>&2
        exit 1
    fi
    shift
done

if test -n "$backup"; then
    if test -z "${volumes}"; then
        echo "**** Error: no volumes to backup, try $0 --help" 1>&2
        exit 1
    fi
elif test -z "$infile"; then
    echo "**** Error: no input source specified, try $0 --help" 1>&2
    exit 1
fi
if test -n "$toserver"; then
    if test -z "$tocontainer"; then
        echo "**** Error: no target container specified, try $0 --help" 1>&2
        exit 1
    fi
elif test -z "$tofile" -a -z "$tocontainer";then
    echo "**** Error: no target specified, try $0 --help" 1>&2
    exit 1
fi

(
    if test -n "$backup"; then
        docker run --rm -i -w / --volumes-from $backup ubuntu tar cjP ${volumes}
    elif test -n "$infile"; then
        cat "$infile"
    fi
) | (
    if test -n "$toserver"; then
        ssh $toserver docker run --rm -i -w / --volumes-from $tocontainer ubuntu tar xjP
    elif test -n "$tocontainer"; then
        docker run --rm -i -w / --volumes-from $tocontainer ubuntu tar xjP
    elif test -n "$tofile";then
        cat > "$tofile"
    fi
)

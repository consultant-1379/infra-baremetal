# Looks for one set fio job logs and writes to output.txt
# All logs should use the same IO depth as that is not checked by this script.

import glob
import re

OUTPUT = 'output.txt'
LOG_RE = r'fio-(\d+)-.+\.log'
LOG_GLOB = r'fio-*.log'

IODEPTH_RE = r'iodepth=(\d+)'

IOPS_RE = r'(read|write): IOPS=(\d+)'
LAT_RE = r'(([sc]?lat) \(([un]sec)\):) .+ (avg=\s*([\d\.]+))'


def get_iodepth(fp):
    for line in fp:
        match = re.search(IODEPTH_RE, line)
        if match:
            return match.group(1)
    raise RuntimeError('IO depth not found')


def add_iops(fp, log_data):
    for line in fp:
        print(line)
        match = re.search(IOPS_RE, line)
        if match:
            print('MATCH')
            # full_line
            log_data['output'].append(match.group(0))
            # read or write, IOPS int
            log_data[f'{match.group(1)}_iops'] = int(match.group(2))
            return
    raise RuntimeError('IOPS not found')


def add_lat(fp, log_data):
    lines = []
    for line in fp:
        print('add_lat line: %s' % line)
        match = re.search(LAT_RE, line)
        if match:
            lines.append(f'{match.group(1)} {match.group(4)}')
            if match.group(2) == 'clat':
                sec = match.group(3)
                clat_avg = float(match.group(5))
                # Normalise to usec
                if sec == 'nsec':
                    clat_avg = clat_avg / 1000.0
        if len(lines) == 3:
            log_data['output'].extend(lines)
            log_data['clat_avg'] = clat_avg
            return
    raise RuntimeError('Latencies not found')


def process_logfile(logfile, data):
    match = re.search(LOG_RE, logfile)
    logid = int(match.group(1))

    if not data.get(logid):
        data[logid] = {}

    with open(logfile) as fp:
        # iodepth = get_iodepth(fp)

        log_read_data = {
            'output': [],
        }
        log_write_data = {
            'output': [],
        }

        log_read_data['output'].append(f'VM{logid}')
        log_write_data['output'].append(f'VM{logid}')

        print('Adding read IOPS')
        add_iops(fp, log_read_data)
        add_lat(fp, log_read_data)
        print('Adding write IOPS')
        add_iops(fp, log_write_data)
        add_lat(fp, log_write_data)


        # data[logid][iodepth] = {
        data[logid] = {
            'read': log_read_data,
            'write': log_write_data
        }


def write_data(output, data):
    read_iops = 0
    clat = []
    for item in sorted(data):
        clat.append(data[item]['read']['clat_avg'])
        read_iops += data[item]['read']['read_iops']
        for line in data[item]['read']['output']:
            output.write(line + '\n')

    output.write('\n\n')
    output.write(f'read avg clat: {sum(clat) / len(clat)}\n')
    output.write(f'read iops: {read_iops}\n')
    output.write('\n\n')

    write_iops = 0
    clat = []
    for item in sorted(data):
        clat.append(data[item]['write']['clat_avg'])
        write_iops += data[item]['write']['write_iops']
        for line in data[item]['write']['output']:
            output.write(line + '\n')

    output.write('\n\n')
    output.write(f'write avg clat: {sum(clat) / len(clat)}\n')
    output.write(f'write iops: {write_iops}\n')
    output.write('\n\n')

    output.write(f'total iops: {read_iops + write_iops}\n')


logfiles = glob.glob(LOG_GLOB)
if not logfiles:
    print('No log files found')
    exit()

with open(OUTPUT, 'w+') as output:
    data = {}
    for logfile in logfiles:
        print('Processing %s' % logfile)
        process_logfile(logfile, data)

    write_data(output, data)

from monitor.collector.cpu import CPUCollector
from monitor.collector.disk import DiskCollector
from monitor.collector.network import NetworkCollector

# 初始化收集器实例
cpu = CPUCollector()
disk = DiskCollector()
net = NetworkCollector()


def get_os_info():
    return {
        "cpu": cpu.collect(),
        "disk": disk.collect(),
        "network": net.collect(),
    }


if __name__ == "__main__":
    print(get_os_info())

    a = {'cpu': {'cpu_percent_overall': 23.1,
                 'cpu_percent_per_core': [0.0, 0.0, 48.6, 48.6, 0.0, 6.2, 0.0, 0.0, 0.0, 0.0, 50.0, 38.2, 48.5, 27.3,
                                          47.1, 40.0], 'cpu_count_logical': 16, 'cpu_count_physical': 8,
                 'memory_total': 29827330048, 'memory_available': 7939747840, 'memory_used': 21887582208,
                 'memory_percent': 73.4, 'swap_total': 12940189696, 'swap_used': 71876608, 'swap_percent': 0.6},
         'disk': {'C:\\': {'mountpoint': 'C:\\', 'fstype': 'NTFS', 'total': 289141682176, 'used': 187175342080,
                           'free': 101966340096, 'percent': 64.7},
                  'D:\\': {'mountpoint': 'D:\\', 'fstype': 'NTFS', 'total': 734003195904, 'used': 386326564864,
                           'free': 347676631040, 'percent': 52.6},
                  'io': {'read_count': 444750, 'write_count': 1033747, 'read_bytes': 26259840000,
                         'write_bytes': 21657992704}},
         'network': {'per_nic': {
            'vEthernet (WSL (Hyper-V firewall))': {'bytes_sent': 2981898, 'bytes_recv': 0, 'packets_sent': 9155,
                                                   'packets_recv': 0, 'errin': 0, 'errout': 0, 'dropin': 0,
                                                   'dropout': 0},
            '本地连接* 1': {'bytes_sent': 0, 'bytes_recv': 0, 'packets_sent': 0, 'packets_recv': 0, 'errin': 0,
                            'errout': 0, 'dropin': 0, 'dropout': 0},
            '本地连接* 2': {'bytes_sent': 0, 'bytes_recv': 0, 'packets_sent': 0, 'packets_recv': 0, 'errin': 0,
                            'errout': 0, 'dropin': 0, 'dropout': 0},
            'VMware Network Adapter VMnet1': {'bytes_sent': 3266, 'bytes_recv': 88, 'packets_sent': 3266,
                                              'packets_recv': 88, 'errin': 0, 'errout': 0, 'dropin': 0, 'dropout': 0},
            'VMware Network Adapter VMnet8': {'bytes_sent': 61144, 'bytes_recv': 227722, 'packets_sent': 61144,
                                              'packets_recv': 227722, 'errin': 0, 'errout': 0, 'dropin': 0,
                                              'dropout': 0},
            'WLAN': {'bytes_sent': 90100051, 'bytes_recv': 1280721193, 'packets_sent': 489612, 'packets_recv': 1081863,
                     'errin': 0, 'errout': 0, 'dropin': 0, 'dropout': 0},
            '以太网': {'bytes_sent': 0, 'bytes_recv': 0, 'packets_sent': 0, 'packets_recv': 0, 'errin': 0, 'errout': 0,
                       'dropin': 0, 'dropout': 0},
            'Loopback Pseudo-Interface 1': {'bytes_sent': 0, 'bytes_recv': 0, 'packets_sent': 0, 'packets_recv': 0,
                                            'errin': 0, 'errout': 0, 'dropin': 0, 'dropout': 0}},
                                                                   'total': {'bytes_sent': 93146433,
                                                                             'bytes_recv': 1280949003,
                                                                             'packets_sent': 563178,
                                                                             'packets_recv': 1309673}}}

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File Name   : make_chart.py
Author      : wzw
Date Created: 2025/7/30
Description : Add your script's purpose here.
"""
import matplotlib.pyplot as plt
import os


def bytes_to_mb(bytes_val):
    return bytes_val / 1024 / 1024


def generate_cpu_chart(cpu_data, output_path="cpu_chart.png"):
    """
    Generate a bar chart for CPU overall and per-core usage.
    :param cpu_data: dict with keys 'cpu_percent_overall' and 'cpu_percent_per_core'
    :param output_path: file path to save the chart image
    """
    labels = ["Overall"] + [f"Core {i + 1}" for i in range(len(cpu_data["cpu_percent_per_core"]))]
    values = [cpu_data["cpu_percent_overall"]] + cpu_data["cpu_percent_per_core"]

    plt.figure()
    plt.bar(labels, values)
    plt.xlabel("CPU")
    plt.ylabel("Usage (%)")
    plt.title("CPU Usage Overall and Per Core")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def generate_memory_chart(cpu_data, output_path="memory_chart.png"):
    """
    Generate a pie chart for memory and swap usage.
    :param cpu_data: dict with keys 'memory_used', 'memory_available', 'swap_used'
    :param output_path: file path to save the chart image
    """
    labels = ["Used Memory", "Available Memory", "Swap Used"]
    sizes = [
        bytes_to_mb(cpu_data["memory_used"]),
        bytes_to_mb(cpu_data["memory_available"]),
        bytes_to_mb(cpu_data["swap_used"]),
    ]

    plt.figure()
    plt.pie(sizes, labels=labels, autopct='%1.1f%%')
    plt.title("Memory and Swap Usage (MB)")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def generate_disk_chart(disk_data, output_path="disk_chart.png"):
    """
    Generate a bar chart for disk partition usage percentages.
    :param disk_data: dict mapping device names to dicts with 'percent'
                      and 'mountpoint', 'fstype', etc.
    :param output_path: file path to save the chart image
    """
    # Filter partitions with percent info
    devices = [dev for dev, info in disk_data.items() if isinstance(info, dict) and "percent" in info]
    percents = [disk_data[dev]["percent"] for dev in devices]

    plt.figure()
    plt.bar(devices, percents)
    plt.xlabel("Partition")
    plt.ylabel("Usage (%)")
    plt.title("Disk Partition Usage")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def generate_network_chart(network_data, output_path="network_chart.png"):
    """
    Generate a line chart for total network bytes sent and received (MB).
    :param network_data: dict with key 'total' containing 'bytes_sent' and 'bytes_recv'
                         (raw bytes)
    :param output_path: file path to save the chart image
    """
    sent_mb = bytes_to_mb(network_data["total"]["bytes_sent"])
    recv_mb = bytes_to_mb(network_data["total"]["bytes_recv"])
    labels = ["Sent", "Received"]
    values = [sent_mb, recv_mb]

    plt.figure()
    plt.bar(labels, values)
    plt.xlabel("Type")
    plt.ylabel("Data (MB)")
    plt.title("Network Throughput Total (MB)")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def generate_all_chart(data, output_path):
    os.makedirs(output_path, exist_ok=True)

    cpu_data = data["cpu"]
    memory_data = data["cpu"]  # memory 数据在 cpu 数据中
    disk_data = data["disk"]
    network_data = data["network"]

    cpu_path = os.path.join(output_path, "cpu_chart.png")
    memory_path = os.path.join(output_path, "memory_chart.png")
    disk_path = os.path.join(output_path, "disk_chart.png")
    network_path = os.path.join(output_path, "network_chart.png")

    generate_cpu_chart(cpu_data, cpu_path)
    generate_memory_chart(memory_data, memory_path)
    generate_disk_chart(disk_data, disk_path)
    generate_network_chart(network_data, network_path)

    print("Charts generated in the specified directory.")
    return {
        "cpu_chart": cpu_path,
        "memory_chart": memory_path,
        "disk_chart": disk_path,
        "network_chart": network_path
    }


# Example usage:
if __name__ == "__main__":
    # Mock data structure
    cpu_example = {
        "cpu_percent_overall": 75.3,
        "cpu_percent_per_core": [70.1, 80.2, 75.0, 76.5]
    }
    memory_example = {
        "memory_used": 4 * 1024 ** 3,
        "memory_available": 12 * 1024 ** 3,
        "swap_used": 1 * 1024 ** 3
    }
    disk_example = {
        "/": {"percent": 65.2},
        "/home": {"percent": 50.1},
        "io": {"read_count": 1000}  # ignored
    }
    network_example = {
        "total": {"bytes_sent": 500 * 1024 ** 2, "bytes_recv": 750 * 1024 ** 2}
    }

    # Ensure output directory exists
    os.makedirs("../templates/charts", exist_ok=True)
    generate_cpu_chart(cpu_example, "../templates/charts/cpu_chart.png")
    generate_memory_chart(memory_example, "../templates/charts/memory_chart.png")
    generate_disk_chart(disk_example, "../templates/charts/disk_chart.png")
    generate_network_chart(network_example, "../templates/charts/network_chart.png")

    print("Charts generated in ../templates/charts directory.")

"""Read OS memory for only the benchmark browser's CDP-reported process IDs."""

import json
import sys

import psutil

rows = []
for item in json.loads(sys.argv[1]):
    try:
        memory = psutil.Process(item["id"]).memory_info()
        rows.append({**item, "rssBytes": memory.rss, "vmsBytes": memory.vms})
    except (psutil.NoSuchProcess, psutil.AccessDenied) as error:
        rows.append({**item, "error": type(error).__name__})
print(json.dumps(rows))

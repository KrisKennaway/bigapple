# Constructs JSON representing boot1 levenshtein distance data from DB

import json
import sqlite3

DB_PATH = '/tank/apple2/data/apple2.db'

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    q = cursor.execute(
        """
        select boot1_sha1, boot1.name, count(*) as c from disks
          join 
        (select sha1, name from boot1) as boot1
          on disks.boot1_sha1 = boot1.sha1 group by 1;
        """
    )

    sha1_indexes = {}
    graph = {
        "nodes": [],
        "links": []
    }
    idx = 0
    for r in q:
        (sha1, name, count) = r
        if count < 10:
            continue
        sha1_indexes[sha1] = idx
        idx += 1
        graph["nodes"].append({"sha1": sha1, "name": name, "radius": count, "group": idx})

    q = cursor.execute(
        """
        select source, target, distance from boot1distances;
        """
    )

    for r in q:
        (source, target, distance) = r
        if source > target:
            try:
                graph["links"].append(
                    {"source": sha1_indexes[source], "target": sha1_indexes[target], "distance": distance})
            except KeyError:
                # Source or target is not common enough to include
                continue

    out = file("levenshtein.json", "w+")
    json.dump(graph, out, indent=4, separators=(',', ': '))

if __name__ == "__main__":
    main()

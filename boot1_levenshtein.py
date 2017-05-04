import bitstring
import heapq
import multiprocessing
import pylev
import sqlite3
import datetime
import vmprof

DB_PATH = '/tank/apple2/data/apple2.db'

WORKERS = 2

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    q = cursor.execute(
        """
        select boot1_sha1, boot1.data, count(*) as c from disks
          join 
        (select sha1, data from boot1) as boot1
          on disks.boot1_sha1 = boot1.sha1 group by 1;
        """
    )

    hashes = []
    sectors = {}
    for r in q:
        (hash, sector, count) = r
        sectors[hash] = bitstring.BitString(bytes=sector).bin
        hashes.append((count, intern(str(hash))))

    hashes.sort()

    num_items = len(hashes) * (len(hashes) + 1) / 2

    workitems = []
    for idx, data1 in enumerate(hashes):
        (cnt1, hash1) = data1
        for data2 in hashes[idx+1:]:
            (cnt2, hash2) = data2
            score = cnt1*cnt2
            heapq.heappush(workitems, (-score, hash1, hash2))

    num_workitems = len(workitems)

    queue = multiprocessing.JoinableQueue()
    results = multiprocessing.Queue()

    workers = []
    for _ in xrange(WORKERS):
        worker = multiprocessing.Process(target=levenshtein_worker, args=(queue, results))
        worker.start()
        workers.append(worker)

    print "Workers started"

    q = cursor.execute(
        """
        select source, target from boot1distances
        """
    )
    existing = set((intern(str(s)), intern(str(t))) for (s, t) in q)
    print "Found %d existing entries" % len(existing)

    items_put = 0
    while True:
        try:
            (score, hash1, hash2) = heapq.heappop(workitems)
        except IndexError:
            break
        if (hash1, hash2) in existing and (hash2, hash1) in existing:
            continue
        items_put += 1
        sector1 = sectors[hash1]
        sector2 = sectors[hash2]
        queue.put_nowait((hash1, hash2, sector1, sector2, score))

    del existing

    print "%d items put" % items_put
    queue.close()

    start_time = datetime.datetime.now()
    num_results = 0
    batch = []
    while True:
        result = results.get()
        num_results += 1
        (hash1, hash2, distance, score) = result

        batch.append(result)
        if num_results % 100 == 0 or num_results == items_put:
            # Insert results into DB

            cursor.executemany(
                """INSERT OR REPLACE INTO Boot1Distances (source, target, distance) VALUES (?, ?, ?)""",
                [(hash1, hash2, distance) for (hash1, hash2, distance, score) in batch]
            )

            # Inverse pairing
            cursor.executemany(
                """INSERT OR REPLACE INTO Boot1Distances (source, target, distance) VALUES (?, ?, ?)""",
                [(hash2, hash1, distance) for (hash1, hash2, distance, score) in batch]
            )

            conn.commit()

            if num_results == items_put:
                break

            now = datetime.datetime.now()
            eta = datetime.timedelta(
                seconds=(now - start_time).total_seconds() * items_put / num_results) + start_time
            print "%d/%d results = %f%% (Score: %d, ETA: %s)" % (
                num_results, items_put, float(100*num_results)/items_put, score, eta)
            batch = []

    print "Done"
    conn.close()


def levenshtein_worker(queue, results):
    while True:
        work = queue.get()
        (hash1, hash2, sector1, sector2, score) = work

        distance = pylev.levenshtein(sector1, sector2)
        results.put_nowait((hash1, hash2, distance, score))

        queue.task_done()


if __name__ == "__main__":
    main()

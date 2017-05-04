# Read all disk images under argv[1] path, and insert metadata into SQLite DB

import binascii
import hashlib
import os
import sqlite3
import sys

DB_PATH = '/tank/apple2/data/apple2.db'

def main():
    disks = []
    idx = 0
    for root, dirs, files in os.walk(sys.argv[1]):
        for f in files:
            if not f.lower().endswith('.dsk') and not f.lower().endswith('.do') and not f.lower().endswith('.po'):
                continue
            disk = os.path.join(root, f)
            try:
                # TODO: deal with filenames with 8-bit characters
                check_ascii = unicode(disk)
                disks.append(disk)
                idx += 1
            except UnicodeDecodeError:
                print "Skipping disk %s" % disk
                continue

    num_disks = len(disks)

    if num_disks == 0:
        return

    hashes = {}
    boot_sectors = {}
    # TODO: no need for this first pass if we're going to insert duplicate disks anyway
    for idx, f in enumerate(disks):

        print "(%d/%d:%d%%) %s" % (idx+1, num_disks, (idx+1)*100/num_disks, f)
        disk = bytearray(open(f, 'r').read())

        if len(disk) < 140*1024:
            print "Disk %s truncated (%d bytes)" % (len(disk))
        boot1 = disk[:256]

        sha1 = hashlib.sha1(disk).hexdigest()
        hashes.setdefault(sha1, []).append(f)

        boot_sectors[sha1] = boot1

    unique_disks = hashes.keys()
    print unique_disks
    num_unique_disks = len(unique_disks)
    print "%d/%d unique files" % (len(unique_disks), num_disks)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    boot1_hashes = set()
    idx = 0
    for disk_hash, boot1 in boot_sectors.iteritems():
        # Pick first duplicate disk name
        disk_name = hashes[disk_hash][0]

        print "(%d/%d %d%%): %s" % (idx+1, num_unique_disks, 100*(idx+1)/num_unique_disks, disk_name)
        boot1_hash = hashlib.sha1(boot1).hexdigest()

        if not boot1_hash in boot1_hashes:
            boot1_hashes.add(boot1_hash)

            # We insert first and then update, in case there is already a record.  We can't INSERT OR REPLACE because
            # that would clear the other fields, and sqlite has no UPSERT :(
            cursor.execute(
                "INSERT OR IGNORE INTO Boot1 (sha1) VALUES (?)",
                [boot1_hash]
            )
            cursor.execute(
                "UPDATE Boot1 SET data=? WHERE sha1=?",
                [buffer(boot1), boot1_hash]
            )
        idx += 1

        for disk in hashes[disk_hash]:
            cursor.execute(
                'INSERT OR IGNORE INTO Disks (path, sha1) VALUES (?, ?)', [disk, disk_hash]
            )
            cursor.execute(
                'UPDATE Disks set name=?, sha1=?, boot1_sha1=? WHERE path=?',
                [os.path.basename(disk), disk_hash, boot1_hash, disk]
            )

        conn.commit()

    conn.close()

if __name__ == "__main__":
    main()

"""Partial simulation of Apple II"""

import sqlite3

import memory
from py65.devices import mpu65c02

DB_PATH = '/tank/apple2/data/apple2.db'

MODE_READ = 0x1
MODE_WRITE = 0x2
MODE_RW = MODE_READ | MODE_WRITE

class Event(object):
    def __init__(self, event_type, details):
        self.event_type = event_type
        self.details = details

    def __str__(self):
        return "Event(%s): %s" % (self.event_type, self.details)


def _Event(region, message):
    def _Event(cpu):
        print "%s event: %s" % (region, message)

    return _Event
class TrapException(Exception):
    def __init__(self, address, msg):
        self.address = address
        self.msg = msg

    def __str__(self):
        return "$%04X: %s" % (self.address, self.msg)


class AppleII(object):
    def __init__(self):
        memory_map = [
            memory.MemoryRegion("Zero page", 0x0000, 0x00ff),
            memory.MemoryRegion("Stack", 0x0100, 0x01ff),
            memory.MemoryRegion(
                "Text page 1", 0x0400, 0x7ff,
                write_interceptor=self.TextPageWriteInterceptor),

            memory.MemoryRegion(
                "IO page", 0xc000, 0xc0ff, read_interceptor=self.IOInterceptor,
                write_interceptor=self.IOInterceptor),

            memory.MemoryRegion("Slot 1 ROM", 0xc100, 0xc1ff, writable=False),
            memory.MemoryRegion("Slot 2 ROM", 0xc200, 0xc2ff, writable=False),
            memory.MemoryRegion("Slot 3 ROM", 0xc300, 0xc3ff, writable=False),
            memory.MemoryRegion("Slot 4 ROM", 0xc400, 0xc4ff, writable=False),
            memory.MemoryRegion("Slot 5 ROM", 0xc500, 0xc5ff, writable=False),
            memory.MemoryRegion("Slot 6 ROM", 0xc600, 0xc6ff,
                entrypoints={
                    0xc65c: self._ReadDiskSector
                },
                writable=False
            ),
            memory.MemoryRegion("Slot 7 ROM", 0xc700, 0xc7ff, writable=False),

            memory.MemoryRegion(
                "ROM", 0xd000, 0xffff,
                entrypoints={
                    0xfca8: self._Wait,
                    0xfe89: _Event("ROM", "Select the keyboard (IN#0)")
                },
                writable=False
            )
        ]

        self.memory_manager = memory.MemoryManager(memory_map)
        self.memory = self.memory_manager.memory
        self.cpu = mpu65c02.MPU(memory=self.memory)

        # Set up interceptors for accessing various interesting parts of the memory map

        self.io_map = {
            0xc007: (MODE_WRITE, "Turn CXROM switch on"),
            0xc015: (MODE_READ, "Status of Peripheral/CXROM Access"),

            0xc051: (MODE_READ, "Display text"),
            0xc054: (MODE_READ, "Text page 1"),
            0xc056: (MODE_READ, "Enter lores mode"),
            # Slot 6 Disk II
            0xc0e0: (MODE_READ, "phase 0 off"),
            0xc0e1: (MODE_READ, "phase 0 on"),
            0xc0e2: (MODE_READ, "phase 1 off"),
            0xc0e3: (MODE_READ, "phase 1 on"),
            0xc0e4: (MODE_READ, "phase 2 off"),
            0xc0e5: (MODE_READ, "phase 2 on"),
            0xc0e6: (MODE_READ, "phase 3 off"),
            0xc0e7: (MODE_READ, "phase 3 on"),
            0xc0e8: (MODE_READ, "Drives off"),
            0xc0e9: (MODE_READ, "Selected drive on"),
            0xc0ea: (MODE_READ, "Select drive 1"),
            0xc0eb: (MODE_READ, "Select drive 2"),
            0xc0ec: (MODE_READ, "Shift while writing/read data"),
            0xc0ed: (MODE_READ, "Shift while writing/read data"),
            0xc0ee: (MODE_READ, "Enabling disk read mode."),
            0xc0ef: (MODE_READ, "Enabling disk write mode."),
        }
        # Need the ability to intercept execution, e.g. for the C65C sector read routine.

    def IOInterceptor(self, address, value=None):
        access_mode = MODE_READ if (value == None) else MODE_WRITE

        try:
            (mode, result) = self.io_map[address]

            if access_mode & mode:
                print "==== IO EVENT: %s" % result
            else:
                print "**** IO EVENT with unexpected mode: %s" % result
        except KeyError:
            if value:
                print TrapException(address, 'Wrote %02X ("%s")' % (value, chr(value)))
            else:
                print TrapException(address, 'Read')

    def _ReadDiskSector(self, cpu):
        print "Read disk sector from Track $%02X Sector $%02X" % (self.memory[0x41], self.memory[0x3d])
        cpu.pc = 0x801

    def _Wait(self, cpu):
        print "Waiting"

    # TODO: convert addresses to screen coordinates
    # See e.g. https://retrocomputing.stackexchange.com/questions/2534/what-are-the-screen-holes-in-apple-ii-graphics
    def TextPageWriteInterceptor(self, address, value):
        print 'Wrote "%s" to text page address $%04X' % (chr(value & 0x7f), address)

    def Run(self, pc, trace=False):
        self.cpu.pc = pc
        old_pc = self.cpu.pc
        while True:
            self.memory_manager.MaybeInterceptExecution(self.cpu, old_pc)
            old_pc = self.cpu.pc
            self.cpu.step(trace=trace)
            if self.cpu.pc == old_pc:
                break


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Load the most popular boot1
    # q = cursor.execute(
    #     """
    #     select boot1_sha1, boot1.data, count(*) from disks
    #       join
    #     (select sha1, data from boot1) as boot1
    #       on disks.boot1_sha1 = boot1.sha1 group by 1 order by 3 desc limit 1
    #     """
    # )

    # Dos 3.3
    q = cursor.execute(
        """
            select data from boot1 where sha1 = '7ab36247fdf62e87f98d2964dd74d6572d17fff0'
        """
    )
    for r in q:
        (boot1,) = r
    #
    # # boot1 image that prints stuff to the text page without using ROM entrypoints
    # q = cursor.execute(
    #     """
    #         select data from boot1 where sha1 = '62bda735bcb4a27ffbd833ebb4ff2503b983ea97'
    #     """
    # )
    for r in q:
        (boot1,) = r

    apple2 = AppleII()

    # Read in Apple IIE ROM image
    rom = bytearray(open("APPLE2E.ROM", "r").read())

    # XXX these should write-trap

    # Slot 6 ROM
    apple2.memory[0xc600:0xc6ff] = rom[0x0600:0x6ff]

    # Main ROM
    apple2.memory[0xd000:0xffff] = rom[0x5000:0x7fff]

    # TODO: why does this not use the 6502 reset vector?
    apple2.cpu.reset()

    apple2.memory[0x800:0x800 + len(boot1)] = bytearray(boot1)

    # Disk II firmware stores next page load address here
    apple2.memory[0x26] = 0x00
    apple2.memory[0x27] = 0x09

    # "3" is used for controller ID
    apple2.memory[0x3c] = 0x03

    # Sector to read
    apple2.memory[0x3d] = 0x00

    # Track to read
    apple2.memory[0x41] = 0x00

    # Booting from slot 6
    apple2.memory[0x2b] = 0x60

    #apple2.Run(0xfa62)  # Target of 6502 reset vector

    apple2.Run(0x801, trace=True)


if __name__ == '__main__':
    main()

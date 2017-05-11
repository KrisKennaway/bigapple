"""Partial simulation of Apple II"""

from py65.devices import mpu65c02
from py65 import memory

class AppleII(object):
    def __init__(self):
        # TODO: should trap by default
        self.memory = memory.ObservableMemory()
        self.cpu = mpu65c02.MPU(memory=self.memory)

        # Set up interceptors for accessing various interesting parts of the memory map

        # Text page 1
        self.memory.subscribe_to_write(xrange(0x400, 0x7ff), self.TextPageWriteInterceptor)

        self.memory.subscribe_to_write(xrange(0xc000, 0xffff), self.TraceWriteInterceptor)
        self.memory.subscribe_to_read(xrange(0xc000, 0xffff), self.TraceReadInterceptor)

    # TODO: convert addresses to screen coordinates
    def TextPageWriteInterceptor(self, address, value):
        print 'Wrote "%s" to text page address $%04X' % (chr(value & 0x7f), address)

    def TraceWriteInterceptor(self, address, value):
        print 'Wrote "%s" to address $%04X' % (chr(value), address)

    def TraceReadInterceptor(self, address):
        print 'Read from address $%04X' % address

    def Run(self, pc):
        self.cpu.pc = pc
        while True:
            self.cpu.step(trace=False)
            if self.cpu.pc == pc:
                break
            pc = self.cpu.pc


def main():

    boot1 = [
        0x01, 0x8d, 0xe8, 0xc0, 0x8d, 0x51, 0xc0, 0x8d, 0x54, 0xc0, 0xa0, 0x00, 0xa9, 0xa0, 0x99, 0x00,
        0x04, 0x99, 0x00, 0x05, 0x99, 0x00, 0x06, 0x99, 0x00, 0x07, 0xc8, 0xd0, 0xf1, 0xa9, 0x08, 0x85,
        0x01, 0xa9, 0x33, 0x85, 0x00, 0xb1, 0x00, 0xf0, 0x08, 0x09, 0x80, 0x99, 0xaf, 0x05, 0xc8, 0xd0,
        0xec, 0xf0, 0xfe, 0x54, 0x48, 0x49, 0x53, 0x20, 0x44, 0x49, 0x53, 0x4b, 0x20, 0x48, 0x41, 0x53,
        0x20, 0x4e, 0x4f, 0x20, 0x42, 0x4f, 0x4f, 0x54, 0x20, 0x43, 0x4f, 0x44, 0x45, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ]

    apple2 = AppleII()
    apple2.memory[0x800:0x800+len(boot1)] = boot1
    apple2.Run(0x801)

if __name__ == '__main__':
    main()
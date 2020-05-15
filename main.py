#!/usr/bin/env python3
 
from xo import XO, VM, User, SR
import asyncio

ADDRESS = "192.168.1.15"
USER = "admin"
PASSWORD = "hunter2"
TEMPLATE = "User VM"
DEFAULT_SR = "Local storage"

async def main():
    xo = XO(ADDRESS, USER, PASSWORD)
    await xo.open()

    crsid = "spqr2"

    user = await User.from_name(xo, crsid)
    if user is None:
        user = await User.new(xo, crsid)

    vm = await VM.new(xo, "%s-vm" % crsid, TEMPLATE)
    await vm.set_cores(2)
    await vm.set_memory("1GiB")
    await vm.set_description("A testing user VM")

    sr = (await SR.from_name(xo, DEFAULT_SR))[0]
    disk1 = await sr.new_disk("%s's disk" % crsid, "5GiB")
    await vm.add_disk(disk1)

    disk2 = await sr.new_disk("%s's second disk" % crsid, "256 MiB")
    await vm.add_disk(disk2)

    await user.set_acl(vm, "operator")

asyncio.get_event_loop().run_until_complete(main())
